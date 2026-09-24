"""Anti-Tiling per Zell-Bombing (4 Nachbarzellen). Öffentlich (Asset), mit Sampler-Closure als Eingang:

  SU Anti-Tile          -> Color, Cell ID
  SU Anti-Tile Sampler  -> Sampler (Closure). Modifikator: nimmt einen Sampler, gibt einen kachelfreien Sampler
                           zurück, z. B. SU Image Sampler -> SU Anti-Tile Sampler -> SU Triplanar

Intern (kein Asset, nur Bausteine):
  SU _Anti-Tile Coords -> Vector 1..4 (Koordinaten je Nachbarzelle), Weight 1..4, Cell ID
  SU _Anti-Tile Blend  -> mischt 4 Farben mit den Gewichten, mit Kontrasterhalt

Zellen: p = Vector * Scale, i = floor(p), Ecken c in {(0,0), (1,0), (0,1), (1,1)}, Zelle = i + c.
Pro Zelle liefert ein White-Noise-Hash (Zelle, Seed) Offset, Winkel und Spiegel-Flag:
  uv_c = R(Winkel) * (Spiegel * (p - Mitte)) + Mitte + Offset,  Mitte = Zelle + 0.5
"""
import lib

NAME_COORDS = "SU _Anti-Tile Coords"
NAME_BLEND = "SU _Anti-Tile Blend"
NAME_PUBLIC = "SU Anti-Tile"
NAME_SAMPLER = "SU Anti-Tile Sampler"
NAME = NAME_PUBLIC

CORNERS = ((0, 0), (1, 0), (0, 1), (1, 1))


def build_coords():
    ng = lib.new_group(NAME_COORDS)
    for i in range(1, 5):
        lib.socket(ng, f"Vector {i}", 'VECTOR', out=True, desc=f"Koordinaten für Image-Node {i}")
    for i in range(1, 5):
        lib.socket(ng, f"Weight {i}", 'FLOAT', out=True, desc=f"Gewicht von Image-Node {i}, Summe aller vier = 1")
    lib.socket(ng, "Cell ID", 'FLOAT', out=True, desc="Zufallswert 0..1 pro Zelle (z. B. für Farbvariation)")
    lib.socket(ng, "Vector", 'VECTOR', hide_value=True, desc="Eingangskoordinaten (z. B. UV oder SU World Coords)")
    lib.socket(ng, "Scale", 'FLOAT', default=1.0, desc="Zellen pro Einheit (1 = eine Zelle je Bildwiederholung)")
    lib.socket(ng, "Randomness", 'FLOAT', default=1.0, min=0.0, max=1.0, desc="Stärke der zufälligen Verschiebung je Zelle")
    lib.socket(ng, "Rotation Amount", 'FLOAT', default=0.0, min=0.0, max=1.0,
               desc="Zufällige Drehung je Zelle (1 = bis 360°). Für Normal Maps auf 0 lassen")
    lib.socket(ng, "Mirror Chance", 'FLOAT', default=0.0, min=0.0, max=1.0,
               desc="Wahrscheinlichkeit, eine Zelle horizontal zu spiegeln. Für Normal Maps auf 0 lassen")
    lib.socket(ng, "Blend Softness", 'FLOAT', default=0.5, min=0.0, max=1.0,
               desc="Breite der Überblendung zwischen Zellen (1 = ganze Zelle, 0 = harte Kanten)")
    lib.socket(ng, "Seed", 'INT', default=0, desc="Zufallsstart. Gleicher Seed = gleiche Verteilung bei allen Maps")
    gi, go = lib.group_io(ng)

    v = lib.separate(ng, lib.vmath(ng, 'SCALE', gi.outputs["Vector"], scale=gi.outputs["Scale"]).outputs[0])
    p = lib.combine(ng, v.outputs["X"], v.outputs["Y"], 0.0)
    base = lib.vmath(ng, 'FLOOR', p.outputs[0])
    frac = lib.separate(ng, lib.vmath(ng, 'FRACTION', p.outputs[0]).outputs[0])

    # Überblendung je Achse: smoothstep über [0.5 - s/2, 0.5 + s/2]
    s = lib.math_node(ng, 'MAXIMUM', gi.outputs["Blend Softness"], 0.001)
    half = lib.math_node(ng, 'MULTIPLY', s.outputs[0], 0.5)
    lo = lib.math_node(ng, 'SUBTRACT', 0.5, half.outputs[0])
    hi = lib.math_node(ng, 'ADD', 0.5, half.outputs[0])
    t = {}
    for ax in ("X", "Y"):
        mr = lib.node(ng, "ShaderNodeMapRange", data_type='FLOAT', interpolation_type='SMOOTHSTEP', clamp=True)
        lib.link(ng, frac.outputs[ax], lib.sock(mr, "Value"))
        lib.link(ng, lo.outputs[0], lib.sock(mr, "From Min"))
        lib.link(ng, hi.outputs[0], lib.sock(mr, "From Max"))
        t[ax] = (lib.math_node(ng, 'SUBTRACT', 1.0, mr.outputs[0]).outputs[0], mr.outputs[0])  # (1 - t, t)

    chance_thr = lib.math_node(ng, 'SUBTRACT', 1.0, gi.outputs["Mirror Chance"])
    for idx, (cx, cy) in enumerate(CORNERS, start=1):
        cell = lib.vmath(ng, 'ADD', base.outputs[0], (float(cx), float(cy), 0.0))
        noise = lib.node(ng, "ShaderNodeTexWhiteNoise", noise_dimensions='4D')
        lib.link(ng, cell.outputs[0], lib.sock(noise, "Vector"))
        lib.link(ng, gi.outputs["Seed"], lib.sock(noise, "W"))
        rnd = lib.separate(ng, noise.outputs["Color"])
        off = lib.combine(ng,
                          lib.math_node(ng, 'MULTIPLY', rnd.outputs["X"], gi.outputs["Randomness"]).outputs[0],
                          lib.math_node(ng, 'MULTIPLY', rnd.outputs["Y"], gi.outputs["Randomness"]).outputs[0], 0.0)
        angle = lib.math_node(ng, 'MULTIPLY',
                              lib.math_node(ng, 'MULTIPLY', rnd.outputs["Z"], gi.outputs["Rotation Amount"]).outputs[0],
                              lib.TWO_PI)
        flip = lib.math_node(ng, 'GREATER_THAN', noise.outputs["Value"], chance_thr.outputs[0])
        sign = lib.math_node(ng, 'MULTIPLY_ADD', flip.outputs[0], -2.0, 1.0)
        center = lib.vmath(ng, 'ADD', cell.outputs[0], (0.5, 0.5, 0.0))
        d = lib.vmath(ng, 'SUBTRACT', p.outputs[0], center.outputs[0])
        dm = lib.vmath(ng, 'MULTIPLY', d.outputs[0], lib.combine(ng, sign.outputs[0], 1.0, 1.0).outputs[0])
        rot = lib.node(ng, "ShaderNodeVectorRotate", rotation_type='Z_AXIS', invert=False)
        lib.link(ng, dm.outputs[0], lib.sock(rot, "Vector"))
        lib.link(ng, angle.outputs[0], lib.sock(rot, "Angle"))
        back = lib.vmath(ng, 'ADD', rot.outputs["Vector"], center.outputs[0])
        uv = lib.vmath(ng, 'ADD', back.outputs[0], off.outputs[0])
        lib.link(ng, uv.outputs[0], go.inputs[f"Vector {idx}"])

        wx = t["X"][1] if cx else t["X"][0]
        wy = t["Y"][1] if cy else t["Y"][0]
        w = lib.math_node(ng, 'MULTIPLY', wx, wy)
        lib.link(ng, w.outputs[0], go.inputs[f"Weight {idx}"])

    nearest = lib.vmath(ng, 'FLOOR', lib.vmath(ng, 'ADD', p.outputs[0], (0.5, 0.5, 0.0)).outputs[0])
    nid = lib.node(ng, "ShaderNodeTexWhiteNoise", noise_dimensions='4D')
    lib.link(ng, nearest.outputs[0], lib.sock(nid, "Vector"))
    lib.link(ng, gi.outputs["Seed"], lib.sock(nid, "W"))
    lib.link(ng, nid.outputs["Value"], go.inputs["Cell ID"])

    lib.autolayout(ng)
    return ng


def build_blend():
    ng = lib.new_group(NAME_BLEND)
    lib.socket(ng, "Color", 'COLOR', out=True)
    for i in range(1, 5):
        lib.socket(ng, f"Color {i}", 'COLOR', default=(0.8, 0.8, 0.8, 1.0), desc=f"Ausgang des Image-Nodes {i}")
    for i in range(1, 5):
        lib.socket(ng, f"Weight {i}", 'FLOAT', default=0.25, desc=f"Weight {i} aus SU Anti-Tile Coords")
    lib.socket(ng, "Contrast Preserve", 'FLOAT', default=0.0, min=0.0, max=1.0,
               desc="Gleicht den Kontrastverlust durch das Überblenden aus (0 = aus). Hilft bei gleichmäßigen, "
                    "rauschartigen Texturen (Gras, Sand); bei fleckigen oder kontrastreichen Texturen entstehen "
                    "dunkle Ränder an den Zellgrenzen, dann klein halten")
    lib.socket(ng, "Mean Color", 'COLOR', default=(0.5, 0.5, 0.5, 1.0),
               desc="Durchschnittsfarbe der Textur, um die der Kontrast korrigiert wird")
    gi, go = lib.group_io(ng)

    total = None
    squares = None
    for i in range(1, 5):
        part = lib.vmath(ng, 'SCALE', gi.outputs[f"Color {i}"], scale=gi.outputs[f"Weight {i}"])
        total = part if total is None else lib.vmath(ng, 'ADD', total.outputs[0], part.outputs[0])
        sq = lib.math_node(ng, 'MULTIPLY', gi.outputs[f"Weight {i}"], gi.outputs[f"Weight {i}"])
        squares = sq if squares is None else lib.math_node(ng, 'ADD', squares.outputs[0], sq.outputs[0])
    k = lib.math_node(ng, 'DIVIDE', 1.0, lib.math_node(ng, 'SQRT',
                      lib.math_node(ng, 'MAXIMUM', squares.outputs[0], 1e-6).outputs[0]).outputs[0])
    k_minus_1 = lib.math_node(ng, 'SUBTRACT', k.outputs[0], 1.0)
    gain = lib.math_node(ng, 'MULTIPLY_ADD', k_minus_1.outputs[0], gi.outputs["Contrast Preserve"], 1.0)
    dev = lib.vmath(ng, 'SUBTRACT', total.outputs[0], gi.outputs["Mean Color"])
    scaled = lib.vmath(ng, 'SCALE', dev.outputs[0], scale=gain.outputs[0])
    out = lib.vmath(ng, 'ADD', scaled.outputs[0], gi.outputs["Mean Color"])
    lib.link(ng, out.outputs[0], go.inputs["Color"])

    lib.autolayout(ng)
    return ng


def build_anti_tile():
    ng = lib.new_group(NAME_PUBLIC)
    lib.socket(ng, "Color", 'COLOR', out=True)
    lib.socket(ng, "Cell ID", 'FLOAT', out=True, desc="Zufallswert 0..1 pro Zelle (z. B. für Farbvariation)")
    lib.socket(ng, "Sampler", 'CLOSURE', desc="Sampler-Closure (Coord -> Color), z. B. aus SU Image Sampler")
    lib.socket(ng, "Vector", 'VECTOR', hide_value=True, desc="Eingangskoordinaten (z. B. UV oder SU World Coords)")
    lib.socket(ng, "Scale", 'FLOAT', default=1.0, desc="Zellen pro Einheit (1 = eine Zelle je Bildwiederholung)")
    lib.socket(ng, "Randomness", 'FLOAT', default=1.0, min=0.0, max=1.0, desc="Stärke der zufälligen Verschiebung je Zelle")
    lib.socket(ng, "Rotation Amount", 'FLOAT', default=0.0, min=0.0, max=1.0,
               desc="Zufällige Drehung je Zelle (1 = bis 360°). Für Normal Maps auf 0 lassen")
    lib.socket(ng, "Mirror Chance", 'FLOAT', default=0.0, min=0.0, max=1.0,
               desc="Wahrscheinlichkeit, eine Zelle horizontal zu spiegeln. Für Normal Maps auf 0 lassen")
    lib.socket(ng, "Blend Softness", 'FLOAT', default=0.5, min=0.0, max=1.0,
               desc="Breite der Überblendung zwischen Zellen (1 = ganze Zelle, 0 = harte Kanten)")
    lib.socket(ng, "Seed", 'INT', default=0, desc="Zufallsstart. Gleicher Seed = gleiche Verteilung bei allen Maps")
    lib.socket(ng, "Contrast Preserve", 'FLOAT', default=0.0, min=0.0, max=1.0,
               desc="Gleicht den Kontrastverlust durch das Überblenden aus (0 = aus). Hilft bei gleichmäßigen, "
                    "rauschartigen Texturen (Gras, Sand); bei fleckigen oder kontrastreichen Texturen entstehen "
                    "dunkle Ränder an den Zellgrenzen, dann klein halten")
    lib.socket(ng, "Mean Color", 'COLOR', default=(0.5, 0.5, 0.5, 1.0),
               desc="Durchschnittsfarbe der Textur, um die der Kontrast korrigiert wird")
    gi, go = lib.group_io(ng)

    coords = lib.group_node(ng, lib.get_or_build(NAME_COORDS, build_coords))
    blend = lib.group_node(ng, lib.get_or_build(NAME_BLEND, build_blend))
    for n in ("Vector", "Scale", "Randomness", "Rotation Amount", "Mirror Chance", "Blend Softness", "Seed"):
        lib.link(ng, gi.outputs[n], coords.inputs[n])
    for n in ("Contrast Preserve", "Mean Color"):
        lib.link(ng, gi.outputs[n], blend.inputs[n])
    for i in range(1, 5):
        color = lib.evaluate(ng, gi.outputs["Sampler"], coords.outputs[f"Vector {i}"])
        lib.link(ng, color, blend.inputs[f"Color {i}"])
        lib.link(ng, coords.outputs[f"Weight {i}"], blend.inputs[f"Weight {i}"])
    lib.link(ng, blend.outputs["Color"], go.inputs["Color"])
    lib.link(ng, coords.outputs["Cell ID"], go.inputs["Cell ID"])

    lib.autolayout(ng)
    lib.mark_asset(ng, "Bricht sichtbare Kachelwiederholung auf: Zell-Bombing mit Zufalls-Offset, Drehung und "
                       "Spiegelung. Sampler-Closure (z. B. SU Image Sampler) als Eingang.",
                   ["mapping", "anti-tiling", "random", "utility"])
    return ng


def build_anti_tile_sampler():
    ng = lib.new_group(NAME_SAMPLER)
    lib.socket(ng, "Sampler", 'CLOSURE', out=True, desc="Kachelfreier Sampler (Coord -> Color)")
    lib.socket(ng, "Sampler", 'CLOSURE', desc="Sampler-Closure (Coord -> Color), z. B. aus SU Image Sampler")
    lib.socket(ng, "Scale", 'FLOAT', default=1.0, desc="Zellen pro Einheit (1 = eine Zelle je Bildwiederholung)")
    lib.socket(ng, "Randomness", 'FLOAT', default=1.0, min=0.0, max=1.0, desc="Stärke der zufälligen Verschiebung je Zelle")
    lib.socket(ng, "Rotation Amount", 'FLOAT', default=0.0, min=0.0, max=1.0,
               desc="Zufällige Drehung je Zelle (1 = bis 360°). Für Normal Maps auf 0 lassen")
    lib.socket(ng, "Mirror Chance", 'FLOAT', default=0.0, min=0.0, max=1.0,
               desc="Wahrscheinlichkeit, eine Zelle horizontal zu spiegeln. Für Normal Maps auf 0 lassen")
    lib.socket(ng, "Blend Softness", 'FLOAT', default=0.5, min=0.0, max=1.0,
               desc="Breite der Überblendung zwischen Zellen (1 = ganze Zelle, 0 = harte Kanten)")
    lib.socket(ng, "Seed", 'INT', default=0, desc="Zufallsstart. Gleicher Seed = gleiche Verteilung bei allen Maps")
    lib.socket(ng, "Contrast Preserve", 'FLOAT', default=0.0, min=0.0, max=1.0,
               desc="Gleicht den Kontrastverlust durch das Überblenden aus (0 = aus). Bei fleckigen Texturen klein halten")
    lib.socket(ng, "Mean Color", 'COLOR', default=(0.5, 0.5, 0.5, 1.0),
               desc="Durchschnittsfarbe der Textur, um die der Kontrast korrigiert wird")
    gi, go = lib.group_io(ng)

    cin = lib.node(ng, "NodeClosureInput")
    cout = lib.node(ng, "NodeClosureOutput")
    cin.pair_with_output(cout)
    cout.input_items.new('VECTOR', 'Coord')
    cout.output_items.new('RGBA', 'Result')

    coords = lib.group_node(ng, lib.get_or_build(NAME_COORDS, build_coords))
    blend = lib.group_node(ng, lib.get_or_build(NAME_BLEND, build_blend))
    lib.link(ng, cin.outputs["Coord"], coords.inputs["Vector"])
    for n in ("Scale", "Randomness", "Rotation Amount", "Mirror Chance", "Blend Softness", "Seed"):
        lib.link(ng, gi.outputs[n], coords.inputs[n])
    for n in ("Contrast Preserve", "Mean Color"):
        lib.link(ng, gi.outputs[n], blend.inputs[n])
    for i in range(1, 5):
        color = lib.evaluate(ng, gi.outputs["Sampler"], coords.outputs[f"Vector {i}"])
        lib.link(ng, color, blend.inputs[f"Color {i}"])
        lib.link(ng, coords.outputs[f"Weight {i}"], blend.inputs[f"Weight {i}"])
    lib.link(ng, blend.outputs["Color"], cout.inputs["Result"])
    lib.link(ng, cout.outputs["Closure"], go.inputs["Sampler"])

    lib.autolayout(ng)
    lib.mark_asset(ng, "Sampler-Modifikator gegen sichtbare Kachelwiederholung: nimmt einen Sampler und gibt einen "
                       "kachelfreien Sampler zurück. Z. B. SU Image Sampler -> SU Anti-Tile Sampler -> SU Triplanar.",
                   ["mapping", "anti-tiling", "sampler", "closure", "utility"])
    return ng


def build():
    lib.get_or_build(NAME_COORDS, build_coords)
    lib.get_or_build(NAME_BLEND, build_blend)
    build_anti_tile_sampler()
    return build_anti_tile()
