"""Triplanar. Öffentlich (Assets), mit Sampler-Closure als Eingang (Coord -> Color, siehe sampler.py):

  SU Triplanar         -> Color
  SU Triplanar Normal  -> Normal (Weltraum, Whiteout-Überblendung), Sampler liefert eine Normal-Map-Farbe

Intern (kein Asset, nur Bausteine):
  SU _Triplanar Coords        -> Vector X/Y/Z (Koordinaten je Projektionsachse) + Weights
  SU _Triplanar Blend         -> mischt 3 Farben mit den Weights
  SU _Triplanar Normal Blend  -> mischt 3 Normal-Map-Farben zu einem Weltraum-Normalvektor

Rechtshändiges Koordinatensystem. Projektion entlang Achse A nutzt Ebenenachsen (a, b) so, dass a x b = +A:
X: (y, z), Y: (z, x), Z: (x, y). Auf Rückseiten (Normale < 0) wird u gespiegelt, damit nichts spiegelverkehrt ist.
"""
import lib

NAME_COORDS = "SU _Triplanar Coords"
NAME_BLEND = "SU _Triplanar Blend"
NAME_NORMAL = "SU _Triplanar Normal Blend"
NAME_PUBLIC = "SU Triplanar"
NAME_PUBLIC_NORMAL = "SU Triplanar Normal"
NAME = NAME_PUBLIC  # für build_all-Ausgabe

# Projektionsachse A -> (a, b) als Indizes 0=x, 1=y, 2=z
PROJ = {"X": (1, 2, 0), "Y": (2, 0, 1), "Z": (0, 1, 2)}  # (a, b, A)


def _sign_of(ng, comp):
    """+1 für >= 0, -1 für < 0."""
    neg = lib.math_node(ng, 'LESS_THAN', comp, 0.0)
    return lib.math_node(ng, 'MULTIPLY_ADD', neg.outputs[0], -2.0, 1.0).outputs[0]


def _surface_normal(ng, object_space_socket):
    geo = lib.node(ng, "ShaderNodeNewGeometry")
    to_obj = lib.node(ng, "ShaderNodeVectorTransform", vector_type='NORMAL',
                      convert_from='WORLD', convert_to='OBJECT')
    lib.link(ng, geo.outputs["Normal"], to_obj.inputs[0])
    _, n = lib.mix(ng, 'VECTOR', object_space_socket, geo.outputs["Normal"], to_obj.outputs[0])
    return n


def build_coords():
    ng = lib.new_group(NAME_COORDS)
    lib.socket(ng, "Vector X", 'VECTOR', out=True, desc="Koordinaten für die Projektion entlang X (Ebene YZ)")
    lib.socket(ng, "Vector Y", 'VECTOR', out=True, desc="Koordinaten für die Projektion entlang Y (Ebene ZX)")
    lib.socket(ng, "Vector Z", 'VECTOR', out=True, desc="Koordinaten für die Projektion entlang Z (Ebene XY)")
    lib.socket(ng, "Weights", 'VECTOR', out=True, desc="Gewichte der drei Projektionen (X, Y, Z), Summe 1")
    lib.socket(ng, "Vector", 'VECTOR', hide_value=True,
               desc="3D-Koordinaten, z. B. aus SU World Coords (Mode 0/1 = Weltachsen, Mode 2 = Objektachsen)")
    lib.socket(ng, "Scale", 'FLOAT', default=1.0, desc="Kachelung (2 = doppelt so viele Kacheln)")
    lib.socket(ng, "Rotation", 'ANGLE', default=0.0, desc="Dreht die Textur in jeder Projektion gegen den Uhrzeigersinn")
    lib.socket(ng, "Blend", 'FLOAT', default=0.2, min=0.0, max=1.0,
               desc="Breite der Überblendung: 0 = harte Kanten, 1 = sehr weich")
    lib.socket(ng, "Object Space", 'BOOL', default=False,
               desc="Achsen und Normale im Objektraum statt im Weltraum (zu SU World Coords Mode 2 passend)")
    gi, go = lib.group_io(ng)

    n = _surface_normal(ng, gi.outputs["Object Space"])
    ns = lib.separate(ng, n)
    signs = {"X": _sign_of(ng, ns.outputs["X"]), "Y": _sign_of(ng, ns.outputs["Y"]), "Z": _sign_of(ng, ns.outputs["Z"])}

    v = lib.vmath(ng, 'SCALE', gi.outputs["Vector"], scale=gi.outputs["Scale"])
    vs = lib.separate(ng, v.outputs[0])
    comp = [vs.outputs["X"], vs.outputs["Y"], vs.outputs["Z"]]

    for A in ("X", "Y", "Z"):
        a, b, _ = PROJ[A]
        u = lib.math_node(ng, 'MULTIPLY', comp[a], signs[A])
        planar = lib.combine(ng, u.outputs[0], comp[b], 0.0)
        rot = lib.node(ng, "ShaderNodeVectorRotate", rotation_type='Z_AXIS', invert=True)
        lib.link(ng, planar.outputs[0], lib.sock(rot, "Vector"))
        lib.link(ng, gi.outputs["Rotation"], lib.sock(rot, "Angle"))
        lib.link(ng, rot.outputs["Vector"], go.inputs[f"Vector {A}"])

    # Gewichte: (|n| / max|n|) ^ (1 / max(Blend, 0.001)), dann auf Summe 1 normieren
    absn = lib.vmath(ng, 'ABSOLUTE', n)
    abs_s = lib.separate(ng, absn.outputs[0])
    m = lib.math_node(ng, 'MAXIMUM', lib.math_node(ng, 'MAXIMUM', abs_s.outputs["X"], abs_s.outputs["Y"]).outputs[0],
                      abs_s.outputs["Z"])
    inv_m = lib.math_node(ng, 'DIVIDE', 1.0, lib.math_node(ng, 'MAXIMUM', m.outputs[0], 1e-6).outputs[0])
    ratio = lib.vmath(ng, 'SCALE', absn.outputs[0], scale=inv_m.outputs[0])
    k = lib.math_node(ng, 'DIVIDE', 1.0, lib.math_node(ng, 'MAXIMUM', gi.outputs["Blend"], 0.001).outputs[0])
    kvec = lib.combine(ng, k.outputs[0], k.outputs[0], k.outputs[0])
    powed = lib.vmath(ng, 'POWER', ratio.outputs[0], kvec.outputs[0])
    ps = lib.separate(ng, powed.outputs[0])
    total = lib.math_node(ng, 'ADD', lib.math_node(ng, 'ADD', ps.outputs["X"], ps.outputs["Y"]).outputs[0],
                          ps.outputs["Z"])
    inv_total = lib.math_node(ng, 'DIVIDE', 1.0, total.outputs[0])
    weights = lib.vmath(ng, 'SCALE', powed.outputs[0], scale=inv_total.outputs[0])
    lib.link(ng, weights.outputs[0], go.inputs["Weights"])

    lib.autolayout(ng)
    return ng


def build_blend():
    ng = lib.new_group(NAME_BLEND)
    lib.socket(ng, "Color", 'COLOR', out=True)
    lib.socket(ng, "Color X", 'COLOR', default=(0.8, 0.8, 0.8, 1.0), desc="Bild, abgetastet mit Vector X")
    lib.socket(ng, "Color Y", 'COLOR', default=(0.8, 0.8, 0.8, 1.0), desc="Bild, abgetastet mit Vector Y")
    lib.socket(ng, "Color Z", 'COLOR', default=(0.8, 0.8, 0.8, 1.0), desc="Bild, abgetastet mit Vector Z")
    lib.socket(ng, "Weights", 'VECTOR', default=(0.0, 0.0, 1.0), hide_value=True, desc="Aus SU Triplanar Coords")
    gi, go = lib.group_io(ng)
    ws = lib.separate(ng, gi.outputs["Weights"])
    parts = [lib.vmath(ng, 'SCALE', gi.outputs[f"Color {A}"], scale=ws.outputs[A]).outputs[0] for A in "XYZ"]
    s1 = lib.vmath(ng, 'ADD', parts[0], parts[1])
    s2 = lib.vmath(ng, 'ADD', s1.outputs[0], parts[2])
    lib.link(ng, s2.outputs[0], go.inputs["Color"])
    lib.autolayout(ng)
    return ng


def build_normal():
    ng = lib.new_group(NAME_NORMAL)
    lib.socket(ng, "Normal", 'VECTOR', out=True, desc="Normale im Weltraum, direkt an Principled BSDF > Normal")
    for A in "XYZ":
        lib.socket(ng, f"Normal {A}", 'COLOR', default=(0.5, 0.5, 1.0, 1.0),
                   desc=f"Normal-Map-Bild (Non-Color), abgetastet mit Vector {A}")
    lib.socket(ng, "Weights", 'VECTOR', default=(0.0, 0.0, 1.0), hide_value=True, desc="Aus SU Triplanar Coords")
    lib.socket(ng, "Strength", 'FLOAT', default=1.0, min=0.0, desc="Stärke des Reliefs")
    lib.socket(ng, "Rotation", 'ANGLE', default=0.0, desc="Gleicher Wert wie Rotation in SU Triplanar Coords")
    lib.socket(ng, "Flip Green", 'BOOL', default=False, desc="Für DirectX-Normal-Maps (Grünkanal invertieren)")
    lib.socket(ng, "Object Space", 'BOOL', default=False, desc="Gleicher Wert wie Object Space in SU Triplanar Coords")
    gi, go = lib.group_io(ng)

    n = _surface_normal(ng, gi.outputs["Object Space"])
    ns = lib.separate(ng, n)
    n_comp = [ns.outputs["X"], ns.outputs["Y"], ns.outputs["Z"]]
    ws = lib.separate(ng, gi.outputs["Weights"])
    flip = lib.math_node(ng, 'MULTIPLY_ADD', gi.outputs["Flip Green"], -2.0, 1.0)

    total = None
    for A in "XYZ":
        a, b, idx_A = PROJ[A]
        decoded = lib.node(ng, "ShaderNodeVectorMath", operation='MULTIPLY_ADD')
        lib.link(ng, gi.outputs[f"Normal {A}"], decoded.inputs[0])
        decoded.inputs[1].default_value = (2.0, 2.0, 2.0)
        decoded.inputs[2].default_value = (-1.0, -1.0, -1.0)
        t = lib.separate(ng, decoded.outputs[0])
        ty = lib.math_node(ng, 'MULTIPLY', t.outputs["Y"], flip.outputs[0])
        tx_s = lib.math_node(ng, 'MULTIPLY', t.outputs["X"], gi.outputs["Strength"])
        ty_s = lib.math_node(ng, 'MULTIPLY', ty.outputs[0], gi.outputs["Strength"])
        planar = lib.combine(ng, tx_s.outputs[0], ty_s.outputs[0], 0.0)
        rot = lib.node(ng, "ShaderNodeVectorRotate", rotation_type='Z_AXIS', invert=False)
        lib.link(ng, planar.outputs[0], lib.sock(rot, "Vector"))
        lib.link(ng, gi.outputs["Rotation"], lib.sock(rot, "Angle"))
        r = lib.separate(ng, rot.outputs["Vector"])

        s = _sign_of(ng, n_comp[idx_A])
        va = lib.math_node(ng, 'MULTIPLY_ADD', s, r.outputs["X"], n_comp[a])       # s*tx + n_a
        vb = lib.math_node(ng, 'ADD', r.outputs["Y"], n_comp[b])                    # ty + n_b
        tz_abs = lib.math_node(ng, 'ABSOLUTE', t.outputs["Z"])
        vA = lib.math_node(ng, 'MULTIPLY', tz_abs.outputs[0], n_comp[idx_A])        # |tz| * n_A
        slots = [None, None, None]
        slots[a], slots[b], slots[idx_A] = va.outputs[0], vb.outputs[0], vA.outputs[0]
        world_vec = lib.combine(ng, *slots)
        weighted = lib.vmath(ng, 'SCALE', world_vec.outputs[0], scale=ws.outputs[A])
        total = weighted if total is None else lib.vmath(ng, 'ADD', total.outputs[0], weighted.outputs[0])

    norm = lib.vmath(ng, 'NORMALIZE', total.outputs[0])
    to_world = lib.node(ng, "ShaderNodeVectorTransform", vector_type='NORMAL',
                        convert_from='OBJECT', convert_to='WORLD')
    lib.link(ng, norm.outputs[0], to_world.inputs[0])
    _, result = lib.mix(ng, 'VECTOR', gi.outputs["Object Space"], norm.outputs[0], to_world.outputs[0])
    lib.link(ng, result, go.inputs["Normal"])

    lib.autolayout(ng)
    return ng


def _wire(ng, gi, node_, names):
    for n in names:
        lib.link(ng, gi.outputs[n], node_.inputs[n])


def build_triplanar():
    ng = lib.new_group(NAME_PUBLIC)
    lib.socket(ng, "Color", 'COLOR', out=True)
    lib.socket(ng, "Sampler", 'CLOSURE', desc="Sampler-Closure (Coord -> Color), z. B. aus SU Image Sampler")
    lib.socket(ng, "Vector", 'VECTOR', hide_value=True,
               desc="3D-Koordinaten, z. B. aus SU World Coords (Mode 0/1 = Weltachsen, Mode 2 = Objektachsen)")
    lib.socket(ng, "Scale", 'FLOAT', default=1.0, desc="Kachelung (2 = doppelt so viele Kacheln)")
    lib.socket(ng, "Rotation", 'ANGLE', default=0.0, desc="Dreht die Textur in jeder Projektion gegen den Uhrzeigersinn")
    lib.socket(ng, "Blend", 'FLOAT', default=0.2, min=0.0, max=1.0,
               desc="Breite der Überblendung: 0 = harte Kanten, 1 = sehr weich")
    lib.socket(ng, "Object Space", 'BOOL', default=False,
               desc="Achsen und Normale im Objektraum statt im Weltraum (zu SU World Coords Mode 2 passend)")
    gi, go = lib.group_io(ng)

    coords = lib.group_node(ng, lib.get_or_build(NAME_COORDS, build_coords))
    blend = lib.group_node(ng, lib.get_or_build(NAME_BLEND, build_blend))
    _wire(ng, gi, coords, ["Vector", "Scale", "Rotation", "Blend", "Object Space"])
    for A in "XYZ":
        color = lib.evaluate(ng, gi.outputs["Sampler"], coords.outputs[f"Vector {A}"])
        lib.link(ng, color, blend.inputs[f"Color {A}"])
    lib.link(ng, coords.outputs["Weights"], blend.inputs["Weights"])
    lib.link(ng, blend.outputs["Color"], go.inputs["Color"])

    lib.autolayout(ng)
    lib.mark_asset(ng, "Triplanar-Projektion ohne UVs mit Sampler-Closure (z. B. SU Image Sampler). Für Farbe, "
                       "Roughness und andere Maps; Normal Maps mit SU Triplanar Normal.",
                   ["mapping", "triplanar", "utility"])
    return ng


def build_triplanar_normal():
    ng = lib.new_group(NAME_PUBLIC_NORMAL)
    lib.socket(ng, "Normal", 'VECTOR', out=True, desc="Normale im Weltraum, direkt an Principled BSDF > Normal")
    lib.socket(ng, "Sampler", 'CLOSURE', desc="Sampler-Closure, der eine Normal-Map-Farbe liefert (Bild als Non-Color)")
    lib.socket(ng, "Vector", 'VECTOR', hide_value=True, desc="3D-Koordinaten, z. B. aus SU World Coords")
    lib.socket(ng, "Scale", 'FLOAT', default=1.0, desc="Kachelung (2 = doppelt so viele Kacheln)")
    lib.socket(ng, "Rotation", 'ANGLE', default=0.0, desc="Dreht die Textur in jeder Projektion gegen den Uhrzeigersinn")
    lib.socket(ng, "Blend", 'FLOAT', default=0.2, min=0.0, max=1.0, desc="Breite der Überblendung")
    lib.socket(ng, "Strength", 'FLOAT', default=1.0, min=0.0, desc="Stärke des Reliefs")
    lib.socket(ng, "Flip Green", 'BOOL', default=False, desc="Für DirectX-Normal-Maps (Grünkanal invertieren)")
    lib.socket(ng, "Object Space", 'BOOL', default=False,
               desc="Achsen und Normale im Objektraum statt im Weltraum (zu SU World Coords Mode 2 passend)")
    gi, go = lib.group_io(ng)

    coords = lib.group_node(ng, lib.get_or_build(NAME_COORDS, build_coords))
    nblend = lib.group_node(ng, lib.get_or_build(NAME_NORMAL, build_normal))
    _wire(ng, gi, coords, ["Vector", "Scale", "Rotation", "Blend", "Object Space"])
    _wire(ng, gi, nblend, ["Rotation", "Strength", "Flip Green", "Object Space"])
    for A in "XYZ":
        color = lib.evaluate(ng, gi.outputs["Sampler"], coords.outputs[f"Vector {A}"])
        lib.link(ng, color, nblend.inputs[f"Normal {A}"])
    lib.link(ng, coords.outputs["Weights"], nblend.inputs["Weights"])
    lib.link(ng, nblend.outputs["Normal"], go.inputs["Normal"])

    lib.autolayout(ng)
    lib.mark_asset(ng, "Triplanar für Normal Maps: mischt die drei Projektionen mit Whiteout-Überblendung zu einem "
                       "Weltraum-Normalvektor. Sampler liefert die Normal-Map-Farbe.",
                   ["mapping", "triplanar", "normal", "utility"])
    return ng


def build():
    lib.get_or_build(NAME_COORDS, build_coords)
    lib.get_or_build(NAME_BLEND, build_blend)
    lib.get_or_build(NAME_NORMAL, build_normal)
    build_triplanar_normal()
    return build_triplanar()
