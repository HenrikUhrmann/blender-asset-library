"""Rendert jede Gruppe mit bekannten Eingaben in Cycles und vergleicht Pixelwerte mit der erwarteten Mathematik.

Aufruf: blender -b --factory-startup --python tools/nodes/tests/verify.py
Schreibt nur in ein Temp-Verzeichnis.
"""
import math
import os
import sys
import tempfile

import bpy
from mathutils import Euler, Vector

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "groups"))
import anti_tile  # noqa: E402
import lib  # noqa: E402
import metal_preset  # noqa: E402
import polar_mapping  # noqa: E402
import sampler  # noqa: E402
import triplanar  # noqa: E402
import uv_pivot_transform  # noqa: E402
import world_coords  # noqa: E402

N = 8
TMP = tempfile.mkdtemp()
FAILS = []


def setup_scene(loc=(0, 0, 0), scale=(1, 1, 1), rot_z=0.0, euler=None):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = 1
    sc.cycles.use_denoising = False
    sc.cycles.filter_width = 0.01
    sc.render.resolution_x = sc.render.resolution_y = N
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = 'OPEN_EXR'
    sc.render.image_settings.color_depth = '32'
    sc.render.image_settings.color_mode = 'RGB'
    sc.view_settings.view_transform = 'Standard'
    sc.world = bpy.data.worlds.new("w")
    sc.world.use_nodes = True
    sc.world.node_tree.nodes["Background"].inputs[0].default_value = (0, 0, 0, 1)
    rotation = tuple(euler) if euler is not None else (0, 0, rot_z)
    bpy.ops.mesh.primitive_plane_add(size=2, location=loc, rotation=rotation)
    plane = bpy.context.active_object
    plane.scale = scale
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    cam.data.type = 'ORTHO'
    cam.data.ortho_scale = 2 * scale[0]
    cam.rotation_euler = rotation
    cam.location = Vector(loc) + Euler(rotation).to_matrix() @ Vector((0, 0, 5))
    sc.collection.objects.link(cam)
    sc.camera = cam
    return plane


def render_probe(plane, group, settings):
    """Material: UV -> Gruppe -> Emission. Gibt Liste der RGB-Pixel (Zeile für Zeile, unten beginnend)."""
    mat = bpy.data.materials.new("m")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    uv = nt.nodes.new("ShaderNodeTexCoord")
    g = nt.nodes.new("ShaderNodeGroup")
    g.node_tree = group
    for k, v in settings.get("inputs", {}).items():
        g.inputs[k].default_value = v
    if "Vector" in g.inputs and settings.get("uv", True):
        if settings.get("vector") == "position":
            geo = nt.nodes.new("ShaderNodeNewGeometry")
            nt.links.new(geo.outputs["Position"], g.inputs["Vector"])
        else:
            nt.links.new(uv.outputs["UV"], g.inputs["Vector"])
    em = nt.nodes.new("ShaderNodeEmission")
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(g.outputs[settings["output"]], em.inputs["Color"])
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    plane.data.materials.append(mat)
    path = os.path.join(TMP, "probe.exr")
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(path)
    px = list(img.pixels)
    bpy.data.images.remove(img)
    ch = len(px) // (N * N)
    return [tuple(px[(j * N + i) * ch:(j * N + i) * ch + 3]) for j in range(N) for i in range(N)]


def grid():
    for j in range(N):
        for i in range(N):
            yield (i + 0.5) / N, (j + 0.5) / N


def check(name, got, want, tol=1e-4):
    bad = [(k, g, w) for k, (g, w) in enumerate(zip(got, want)) if max(abs(a - b) for a, b in zip(g, w)) > tol]
    if bad:
        FAILS.append(name)
        k, g, w = bad[0]
        print(f"[FAIL] {name}: {len(bad)}/{len(want)} Pixel weichen ab, z. B. #{k}: erhalten {g}, erwartet {w}")
    else:
        print(f"[OK]   {name}")


def rot(v, a):
    c, s = math.cos(a), math.sin(a)
    return (c * v[0] - s * v[1], s * v[0] + c * v[1])


def test_pivot():
    def run(name, inputs, fn):
        plane = setup_scene()
        grp = uv_pivot_transform.build()
        got = render_probe(plane, grp, {"inputs": inputs, "output": "Vector"})
        check(f"UV Pivot: {name}", got, [fn(u, v) for u, v in grid()])

    run("Identität", {}, lambda u, v: (u, v, 0))
    run("Scale 2", {"Scale": (2, 2, 1)}, lambda u, v: (0.5 + (u - .5) * 2, 0.5 + (v - .5) * 2, 0))
    run("Offset", {"Offset": (0.25, 0.1, 0)}, lambda u, v: (u - 0.25, v - 0.1, 0))
    run("Mirror X", {"Mirror X": True}, lambda u, v: (1 - u, v, 0))
    run("Mirror Y", {"Mirror Y": True}, lambda u, v: (u, 1 - v, 0))
    a = math.radians(30)
    # Textur um +30° gegen den Uhrzeigersinn drehen = Koordinaten um -30° drehen
    def rot_fn(u, v):
        x, y = rot((u - .5, v - .5), -a)
        return (x + .5, y + .5, 0)
    run("Rotation 30° (Textur gegen Uhrzeigersinn)", {"Rotation": a}, rot_fn)
    run("Pivot (0,0) + Scale 2", {"Pivot": (0, 0, 0), "Scale": (2, 2, 1)}, lambda u, v: (u * 2, v * 2, 0))


def test_polar():
    def run(name, inputs, fn, output="Vector"):
        plane = setup_scene()
        grp = polar_mapping.build()
        got = render_probe(plane, grp, {"inputs": inputs, "output": output})
        check(f"Polar: {name}", got, [fn(u, v) for u, v in grid()])

    def ang(u, v, off=0.0, mirror=False):
        a = ((math.atan2(v - .5, u - .5) + off) / (2 * math.pi)) % 1.0
        return abs(2 * a - 1) if mirror else a

    rad = lambda u, v: math.hypot(u - .5, v - .5)
    run("Standard", {}, lambda u, v: (ang(u, v), rad(u, v), 0))
    run("Repeat 3", {"Angular Repeat": 3}, lambda u, v: (ang(u, v) * 3, rad(u, v), 0))
    run("Angle Offset 90°", {"Angle Offset": math.pi / 2}, lambda u, v: (ang(u, v, math.pi / 2), rad(u, v), 0))
    run("Mirror", {"Mirror Angle": True}, lambda u, v: (ang(u, v, 0, True), rad(u, v), 0))
    run("Radial Scale 2", {"Radial Scale": 2.0}, lambda u, v: (ang(u, v), rad(u, v) * 2, 0))
    run("Ausgang Angle", {}, lambda u, v: (ang(u, v),) * 3, output="Angle")
    run("Ausgang Radius", {}, lambda u, v: (rad(u, v),) * 3, output="Radius")
    run("Center (0,0)", {"Center": (0, 0, 0)},
        lambda u, v: (ang(u + .5, v + .5), rad(u + .5, v + .5), 0))


def test_world():
    loc, scale, rz = (0.5, 0.25, 0.0), (1.5, 1.5, 1.0), math.radians(30)

    def run(name, inputs, fn, output="Vector"):
        plane = setup_scene(loc, scale, rz)
        grp = world_coords.build()
        got = render_probe(plane, grp, {"inputs": inputs, "output": output, "uv": False})
        want = []
        for u, v in grid():
            l = (2 * u - 1, 2 * v - 1)
            s = (scale[0] * l[0], scale[1] * l[1])
            r = rot(s, rz)
            want.append(fn(l, s, r))
        check(f"World Coords: {name}", got, want)

    world = lambda l, s, r: (loc[0] + r[0], loc[1] + r[1], 0)
    run("Mode 0 (World)", {"Mode": 0}, lambda l, s, r: world(l, s, r))
    run("Mode 1 (Object anchored)", {"Mode": 1}, lambda l, s, r: (r[0], r[1], 0))
    run("Mode 2 (Object scaled)", {"Mode": 2}, lambda l, s, r: (s[0], s[1], 0))
    run("Tile Size 2", {"Mode": 0, "Tile Size": 2.0},
        lambda l, s, r: tuple(c / 2 for c in world(l, s, r)))
    run("Offset", {"Mode": 1, "Offset": (0.1, 0.2, 0)}, lambda l, s, r: (r[0] + 0.1, r[1] + 0.2, 0))
    run("Planar XY", {"Mode": 1}, lambda l, s, r: (r[0], r[1], 0), output="XY")
    run("Planar XZ", {"Mode": 1}, lambda l, s, r: (r[0], 0, 0), output="XZ")
    run("Planar YZ", {"Mode": 1}, lambda l, s, r: (r[1], 0, 0), output="YZ")


def _plane_frame(euler):
    m = Euler(euler).to_matrix()
    return m, m @ Vector((0, 0, 1))


def _pos_normal_grid(euler):
    m, n = _plane_frame(euler)
    for u, v in grid():
        yield m @ Vector((2 * u - 1, 2 * v - 1, 0)), n


def _sgn(x):
    return -1.0 if x < 0 else 1.0


def _weights(n, blend):
    a = [abs(c) for c in n]
    mx = max(a)
    k = 1.0 / max(blend, 0.001)
    w = [(c / mx) ** k for c in a]
    t = sum(w)
    return [c / t for c in w]


def test_triplanar():
    orientations = {
        "Z oben": (0, 0, 0),
        "Z unten": (math.pi, 0, 0),
        "X positiv": (0, math.radians(90), 0),
        "Y negativ": (math.radians(90), 0, 0),
        "schräg": (math.radians(35), math.radians(20), math.radians(40)),
    }
    PROJ = {"X": (1, 2, 0), "Y": (2, 0, 1), "Z": (0, 1, 2)}

    def coords_run(label, euler, output, fn, inputs=None):
        plane = setup_scene(euler=euler)
        grp = triplanar.build_coords()
        got = render_probe(plane, grp, {"inputs": inputs or {}, "output": output, "vector": "position"})
        want = [fn(p, n) for p, n in _pos_normal_grid(euler)]
        check(f"Triplanar Coords {output} ({label})", got, want)

    for label, eul in orientations.items():
        for A in "XYZ":
            a, b, _ = PROJ[A]
            coords_run(label, eul, f"Vector {A}",
                       lambda p, n, a=a, b=b, A=A: (_sgn(n["XYZ".index(A)]) * p[a], p[b], 0))
        coords_run(label, eul, "Weights", lambda p, n: tuple(_weights(n, 0.2)))
    coords_run("Scale 2, Rotation 30°", (math.radians(35), math.radians(20), math.radians(40)), "Vector Z",
               lambda p, n: (lambda r: (r[0], r[1], 0))(
                   rot((_sgn(n[2]) * p[0] * 2, p[1] * 2), -math.radians(30))),
               inputs={"Scale": 2.0, "Rotation": math.radians(30)})
    coords_run("Blend 0.6", (math.radians(35), math.radians(20), math.radians(40)), "Weights",
               lambda p, n: tuple(_weights(n, 0.6)), inputs={"Blend": 0.6})
    coords_run("Object Space", (math.radians(35), math.radians(20), math.radians(40)), "Weights",
               lambda p, n: (0, 0, 1), inputs={"Object Space": True})

    # Blend-Gruppe
    plane = setup_scene()
    grp = triplanar.build_blend()
    got = render_probe(plane, grp, {"inputs": {"Color X": (1, 0, 0, 1), "Color Y": (0, 1, 0, 1),
                                                "Color Z": (0, 0, 1, 1), "Weights": (0.2, 0.3, 0.5)},
                                    "output": "Color"})
    check("Triplanar Blend", got, [(0.2, 0.3, 0.5)] * (N * N))

    # Normal-Blend: flache Map ergibt die Oberflächennormale
    for label, eul in orientations.items():
        plane = setup_scene(euler=eul)
        grp = triplanar.build_normal()
        got = render_probe(plane, grp, {"inputs": {"Weights": (0.5, 0.3, 0.2)}, "output": "Normal", "uv": False})
        check(f"Triplanar Normal: flache Map = Oberflächennormale ({label})", got,
              [tuple(n) for _, n in _pos_normal_grid(eul)])

    # Normal-Blend: geneigte Map, nur Z-Projektion, analytisch (Z oben und Z unten)
    tx, ty = 0.3, 0.2
    col = ((tx + 1) / 2, (ty + 1) / 2, (math.sqrt(1 - tx * tx - ty * ty) + 1) / 2, 1.0)
    tz = math.sqrt(1 - tx * tx - ty * ty)

    def expect(n, rz=0.0, flip=False, strength=1.0):
        x, y = tx * strength, (-ty if flip else ty) * strength
        x, y = rot((x, y), rz)
        s = _sgn(n[2])
        v = (s * x + n[0], y + n[1], abs(tz) * n[2])
        l = math.sqrt(sum(c * c for c in v))
        return tuple(c / l for c in v)

    for label in ("Z oben", "Z unten", "schräg"):
        eul = orientations[label]
        for name, inputs, kw in (("Basis", {}, {}),
                                 ("Rotation 30°", {"Rotation": math.radians(30)}, {"rz": math.radians(30)}),
                                 ("Flip Green", {"Flip Green": True}, {"flip": True}),
                                 ("Strength 0.5", {"Strength": 0.5}, {"strength": 0.5})):
            plane = setup_scene(euler=eul)
            grp = triplanar.build_normal()
            inputs = dict(inputs, **{"Normal Z": col, "Weights": (0.0, 0.0, 1.0)})
            got = render_probe(plane, grp, {"inputs": inputs, "output": "Normal", "uv": False})
            check(f"Triplanar Normal Z-Projektion {name} ({label})", got,
                  [expect(n, **kw) for _, n in _pos_normal_grid(eul)])


def render_composite(plane, make):
    """make(nt) -> Ausgangs-Socket; wird an eine Emission gehängt."""
    mat = bpy.data.materials.new("mc")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out_sock = make(nt)
    em = nt.nodes.new("ShaderNodeEmission")
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(out_sock, em.inputs["Color"])
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    plane.data.materials.append(mat)
    path = os.path.join(TMP, "probe.exr")
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(path)
    px = list(img.pixels)
    bpy.data.images.remove(img)
    ch = len(px) // (N * N)
    return [tuple(px[(j * N + i) * ch:(j * N + i) * ch + 3]) for j in range(N) for i in range(N)]


def test_anti_tile():
    SC = 3.0
    corners = anti_tile.CORNERS

    def coords(inputs, output):
        plane = setup_scene()
        grp = anti_tile.build_coords()
        base = {"Scale": SC}
        base.update(inputs)
        return render_probe(plane, grp, {"inputs": base, "output": output})

    def pts():
        return [(SC * u, SC * v) for u, v in grid()]

    def smooth(x, soft):
        s = max(soft, 0.001)
        t = min(max((x - (0.5 - s / 2)) / s, 0.0), 1.0)
        return t * t * (3 - 2 * t)

    # 1. Identität ohne Zufall
    for k in range(1, 5):
        got = coords({"Randomness": 0.0}, f"Vector {k}")
        check(f"Anti-Tile: Vector {k} ohne Zufall = p", got, [(px, py, 0) for px, py in pts()])

    # 2. Gewichte
    for soft in (1.0, 0.4, 0.0):
        for k, (cx, cy) in enumerate(corners, start=1):
            def w(px, py, cx=cx, cy=cy):
                tx, ty = smooth(px - math.floor(px), soft), smooth(py - math.floor(py), soft)
                return (tx if cx else 1 - tx) * (ty if cy else 1 - ty)
            got = coords({"Blend Softness": soft}, f"Weight {k}")
            check(f"Anti-Tile: Weight {k}, Softness {soft}", got, [(w(px, py),) * 3 for px, py in pts()])

    # 3. Hash je Zelle konsistent, Offsets in [0,1], variieren, hängen vom Seed ab
    def offsets(seed):
        table, bad, allv = {}, 0, []
        for k, (cx, cy) in enumerate(corners, start=1):
            got = coords({"Seed": seed}, f"Vector {k}")
            for (px, py), g in zip(pts(), got):
                cell = (math.floor(px) + cx, math.floor(py) + cy)
                off = (g[0] - px, g[1] - py)
                allv.append(off)
                if cell in table and max(abs(a - b) for a, b in zip(table[cell], off)) > 1e-4:
                    bad += 1
                table.setdefault(cell, off)
        return table, bad, allv

    t0, bad0, allv = offsets(0)
    t5, _, _ = offsets(5)
    in_range = all(-1e-5 <= c <= 1 + 1e-5 for o in allv for c in o)
    varied = len({(round(o[0], 3), round(o[1], 3)) for o in t0.values()}) > len(t0) // 2
    seed_dep = any(max(abs(a - b) for a, b in zip(t0[c], t5[c])) > 1e-3 for c in t0)
    for label, ok in (("gleiche Zelle = gleicher Offset (Nachbarn stimmig)", bad0 == 0),
                      ("Offsets liegen in [0,1]", in_range), ("Offsets variieren zwischen Zellen", varied),
                      ("Seed ändert die Verteilung", seed_dep)):
        if ok:
            print(f"[OK]   Anti-Tile: {label}")
        else:
            FAILS.append(label)
            print(f"[FAIL] Anti-Tile: {label}")

    # 4. Rotation erhält Abstand zur Zellmitte, Spiegelung flippt x
    for k, (cx, cy) in enumerate(corners, start=1):
        rot_run = coords({"Rotation Amount": 1.0}, f"Vector {k}")
        mir_run = coords({"Mirror Chance": 1.0}, f"Vector {k}")
        bad_r = bad_m = 0
        for (px, py), gr, gm in zip(pts(), rot_run, mir_run):
            cell = (math.floor(px) + cx, math.floor(py) + cy)
            off = t0[cell]
            ctr = (cell[0] + 0.5, cell[1] + 0.5)
            d_want = math.hypot(px - ctr[0], py - ctr[1])
            d_got = math.hypot(gr[0] - off[0] - ctr[0], gr[1] - off[1] - ctr[1])
            if abs(d_want - d_got) > 1e-4:
                bad_r += 1
            want_m = (2 * ctr[0] - px + off[0], py + off[1])
            if abs(gm[0] - want_m[0]) > 1e-4 or abs(gm[1] - want_m[1]) > 1e-4:
                bad_m += 1
        for label, bad in ((f"Rotation erhält Abstand (Ecke {k})", bad_r), (f"Spiegelung flippt x (Ecke {k})", bad_m)):
            if bad == 0:
                print(f"[OK]   Anti-Tile: {label}")
            else:
                FAILS.append(label)
                print(f"[FAIL] Anti-Tile: {label}: {bad} Pixel")

    # 5. Cell ID im Bereich und konstant je nächster Zelle
    got = coords({}, "Cell ID")
    per_cell, ok = {}, True
    for (px, py), g in zip(pts(), got):
        cell = (math.floor(px + 0.5), math.floor(py + 0.5))
        if cell in per_cell and abs(per_cell[cell] - g[0]) > 1e-5:
            ok = False
        per_cell.setdefault(cell, g[0])
        ok = ok and 0.0 <= g[0] <= 1.0
    if ok and len(set(round(v, 3) for v in per_cell.values())) > 1:
        print("[OK]   Anti-Tile: Cell ID konstant je Zelle, 0..1, variiert")
    else:
        FAILS.append("Cell ID")
        print("[FAIL] Anti-Tile: Cell ID")

    # 6. Blend: konstante Farbe bleibt (Summe der Gewichte = 1), Kontrasterhalt-Formel
    def blend_run(cp, colors, mean, soft=1.0):
        plane = setup_scene()

        def make(nt):
            uv = nt.nodes.new("ShaderNodeTexCoord")
            c = nt.nodes.new("ShaderNodeGroup")
            c.node_tree = anti_tile.build_coords()
            c.inputs["Scale"].default_value = SC
            c.inputs["Blend Softness"].default_value = soft
            nt.links.new(uv.outputs["UV"], c.inputs["Vector"])
            b = nt.nodes.new("ShaderNodeGroup")
            b.node_tree = anti_tile.build_blend()
            for i in range(1, 5):
                b.inputs[f"Color {i}"].default_value = colors[i - 1]
                nt.links.new(c.outputs[f"Weight {i}"], b.inputs[f"Weight {i}"])
            b.inputs["Contrast Preserve"].default_value = cp
            b.inputs["Mean Color"].default_value = mean
            return b.outputs["Color"]
        return render_composite(plane, make)

    const = (0.3, 0.6, 0.9, 1.0)
    # Konstante Farbe bleibt erhalten, wenn Kontrast aus ist oder Mean Color = Farbe
    # (bei cp=1 und Mean != Farbe wird sie prinzipbedingt vom Mittelwert weggezogen)
    for cp, mean_c in ((0.0, (0.5, 0.5, 0.5, 1.0)), (1.0, const)):
        got = blend_run(cp, [const] * 4, mean_c)
        check(f"Anti-Tile Blend: konstante Farbe bleibt (Contrast Preserve {cp})", got, [const[:3]] * (N * N))

    cols = [(1, 0, 0, 1), (0, 1, 0, 1), (0, 0, 1, 1), (0.5, 0.5, 0.5, 1)]
    mean = (0.4, 0.4, 0.4, 1.0)
    for cp in (0.0, 0.5, 1.0):
        got = blend_run(cp, cols, mean)
        want = []
        for px, py in pts():
            tx, ty = smooth(px - math.floor(px), 1.0), smooth(py - math.floor(py), 1.0)
            ws = [(1 - tx) * (1 - ty), tx * (1 - ty), (1 - tx) * ty, tx * ty]
            mixed = [sum(w * c[ch] for w, c in zip(ws, cols)) for ch in range(3)]
            k = 1 / math.sqrt(max(sum(w * w for w in ws), 1e-6))
            gain = 1 + (k - 1) * cp
            want.append(tuple(mean[ch] + (mixed[ch] - mean[ch]) * gain for ch in range(3)))
        check(f"Anti-Tile Blend: Kontrast-Formel (Contrast Preserve {cp})", got, want)


def mat_sampler(nt, kind, const=(0.5, 0.5, 1.0, 1.0)):
    """Sampler-Closure im Material: 'coord' -> Farbe = (x, y, 0), 'const' -> feste Farbe."""
    cin = nt.nodes.new("NodeClosureInput")
    cout = nt.nodes.new("NodeClosureOutput")
    cin.pair_with_output(cout)
    cout.input_items.new('VECTOR', 'Coord')
    cout.output_items.new('RGBA', 'Result')
    if kind == 'coord':
        sep = nt.nodes.new("ShaderNodeSeparateXYZ")
        comb = nt.nodes.new("ShaderNodeCombineXYZ")
        nt.links.new(cin.outputs["Coord"], sep.inputs[0])
        nt.links.new(sep.outputs["X"], comb.inputs["X"])
        nt.links.new(sep.outputs["Y"], comb.inputs["Y"])
        nt.links.new(comb.outputs[0], cout.inputs["Result"])
    else:
        rgb = nt.nodes.new("ShaderNodeRGB")
        rgb.outputs[0].default_value = const
        nt.links.new(rgb.outputs[0], cout.inputs["Result"])
    return cout.outputs["Closure"]


def wrapper_run(plane, builder, sampler_kind, inputs, output, vector="uv", const=(0.5, 0.5, 1.0, 1.0)):
    def make(nt):
        smp = mat_sampler(nt, sampler_kind, const)
        g = nt.nodes.new("ShaderNodeGroup")
        g.node_tree = builder()
        nt.links.new(smp, g.inputs["Sampler"])
        for k, v in inputs.items():
            g.inputs[k].default_value = v
        if vector == "position":
            geo = nt.nodes.new("ShaderNodeNewGeometry")
            nt.links.new(geo.outputs["Position"], g.inputs["Vector"])
        elif vector == "uv":
            uv = nt.nodes.new("ShaderNodeTexCoord")
            nt.links.new(uv.outputs["UV"], g.inputs["Vector"])
        return g.outputs[output]
    return render_composite(plane, make)


def test_wrappers():
    orient = {"Z oben": (0, 0, 0), "Z unten": (math.pi, 0, 0),
              "schräg": (math.radians(35), math.radians(20), math.radians(40))}
    PROJ = {"X": (1, 2, 0), "Y": (2, 0, 1), "Z": (0, 1, 2)}

    # SU Triplanar mit Koordinaten-Sampler: Farbe = Summe w_A * (uv_A.x, uv_A.y, 0)
    for label, eul in orient.items():
        for scale, rz in ((1.0, 0.0), (2.0, math.radians(30))):
            plane = setup_scene(euler=eul)
            got = wrapper_run(plane, lambda: (triplanar.build() and bpy.data.node_groups["SU Triplanar"]), 'coord',
                              {"Scale": scale, "Rotation": rz}, "Color", vector="position")
            want = []
            for p, n in _pos_normal_grid(eul):
                w = _weights(n, 0.2)
                acc = [0.0, 0.0]
                for k, A in enumerate("XYZ"):
                    a, b, _ = PROJ[A]
                    r = rot((_sgn(n["XYZ".index(A)]) * p[a] * scale, p[b] * scale), -rz)
                    acc[0] += w[k] * r[0]
                    acc[1] += w[k] * r[1]
                want.append((acc[0], acc[1], 0.0))
            check(f"SU Triplanar (Sampler): {label}, Scale {scale}, Rotation {round(math.degrees(rz))}°", got, want)

    # SU Triplanar Normal: flache Map = Oberflächennormale; geneigte Map analytisch (Z-Projektion)
    tx, ty = 0.3, 0.2
    tz = math.sqrt(1 - tx * tx - ty * ty)
    col = ((tx + 1) / 2, (ty + 1) / 2, (tz + 1) / 2, 1.0)
    for label, eul in orient.items():
        plane = setup_scene(euler=eul)
        got = wrapper_run(plane, lambda: (triplanar.build() and bpy.data.node_groups["SU Triplanar Normal"]),
                          'const', {}, "Normal", vector="position", const=(0.5, 0.5, 1.0, 1.0))
        check(f"SU Triplanar Normal (Sampler): flache Map ({label})", got,
              [tuple(n) for _, n in _pos_normal_grid(eul)])
    for label in ("Z oben", "Z unten"):
        eul = orient[label]
        plane = setup_scene(euler=eul)
        got = wrapper_run(plane, lambda: (triplanar.build() and bpy.data.node_groups["SU Triplanar Normal"]),
                          'const', {"Strength": 0.5, "Flip Green": True}, "Normal", vector="position", const=col)
        want = []
        for _, n in _pos_normal_grid(eul):
            x, y = tx * 0.5, -ty * 0.5
            s = _sgn(n[2])
            v = (s * x + n[0], y + n[1], abs(tz) * n[2])
            l = math.sqrt(sum(c * c for c in v))
            want.append(tuple(c / l for c in v))
        check(f"SU Triplanar Normal (Sampler): geneigte Map, Strength 0.5, Flip Green ({label})", got, want)

    # SU Anti-Tile: ohne Zufall = p; mit Zufall identisch zur manuellen Verdrahtung der internen Gruppen
    SC = 3.0
    plane = setup_scene()
    got = wrapper_run(plane, lambda: (anti_tile.build() and bpy.data.node_groups["SU Anti-Tile"]), 'coord',
                      {"Scale": SC, "Randomness": 0.0}, "Color")
    check("SU Anti-Tile (Sampler): ohne Zufall = p", got, [(SC * u, SC * v, 0) for u, v in grid()])

    inputs = {"Scale": SC, "Randomness": 1.0, "Rotation Amount": 1.0, "Mirror Chance": 0.5, "Seed": 7,
              "Contrast Preserve": 0.3, "Mean Color": (0.4, 0.4, 0.4, 1.0)}
    plane = setup_scene()
    got = wrapper_run(plane, lambda: (anti_tile.build() and bpy.data.node_groups["SU Anti-Tile"]), 'coord',
                      inputs, "Color")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    plane = setup_scene()

    def manual(nt):
        smp = mat_sampler(nt, 'coord')
        c = nt.nodes.new("ShaderNodeGroup")
        c.node_tree = anti_tile.build_coords()
        b = nt.nodes.new("ShaderNodeGroup")
        b.node_tree = anti_tile.build_blend()
        uv = nt.nodes.new("ShaderNodeTexCoord")
        nt.links.new(uv.outputs["UV"], c.inputs["Vector"])
        for k in ("Scale", "Randomness", "Rotation Amount", "Mirror Chance", "Seed"):
            c.inputs[k].default_value = inputs[k]
        b.inputs["Contrast Preserve"].default_value = inputs["Contrast Preserve"]
        b.inputs["Mean Color"].default_value = inputs["Mean Color"]
        for i in range(1, 5):
            e = nt.nodes.new("NodeEvaluateClosure")
            e.input_items.new('VECTOR', 'Coord')
            e.output_items.new('RGBA', 'Result')
            nt.links.new(smp, e.inputs["Closure"])
            nt.links.new(c.outputs[f"Vector {i}"], e.inputs["Coord"])
            nt.links.new(e.outputs["Result"], b.inputs[f"Color {i}"])
            nt.links.new(c.outputs[f"Weight {i}"], b.inputs[f"Weight {i}"])
        return b.outputs["Color"]
    want = render_composite(plane, manual)
    check("SU Anti-Tile (Sampler): entspricht manueller Verdrahtung (Seed 7, Rotation, Mirror)", got, want)

    # SU Image Sampler: liefert die Bildfarbe an den Koordinaten
    bpy.ops.wm.read_factory_settings(use_empty=True)
    plane = setup_scene()
    img = bpy.data.images.new("t", 2, 2)
    img.pixels = [1, 0, 0, 1, 0, 1, 0, 1, 0, 0, 1, 1, 1, 1, 1, 1]
    img.pack()
    grp = sampler.build()
    grp.nodes["Image"].image = img
    grp.nodes["Image"].interpolation = 'Closest'

    def smp_make(nt):
        g = nt.nodes.new("ShaderNodeGroup")
        g.node_tree = grp
        e = nt.nodes.new("NodeEvaluateClosure")
        e.input_items.new('VECTOR', 'Coord')
        e.output_items.new('RGBA', 'Result')
        nt.links.new(g.outputs["Sampler"], e.inputs["Closure"])
        uv = nt.nodes.new("ShaderNodeTexCoord")
        nt.links.new(uv.outputs["UV"], e.inputs["Coord"])
        return e.outputs["Result"]
    got = render_composite(plane, smp_make)
    cols = {(0, 0): (1, 0, 0), (1, 0): (0, 1, 0), (0, 1): (0, 0, 1), (1, 1): (1, 1, 1)}
    want = [cols[(int(u * 2), int(v * 2))] for u, v in grid()]
    check("SU Image Sampler: liefert Bildfarben (Closest)", got, want)


def test_composition():
    """Anti-Tile Sampler als Modifikator: in SU Triplanar und gegen SU Anti-Tile (Color)."""
    SC = 3.0
    PROJ = {"X": (1, 2, 0), "Y": (2, 0, 1), "Z": (0, 1, 2)}

    def grp_at_sampler():
        anti_tile.build()
        return bpy.data.node_groups["SU Anti-Tile Sampler"]

    def grp_tri():
        triplanar.build()
        return bpy.data.node_groups["SU Triplanar"]

    # 1. Anti-Tile Sampler (Zufall an) == SU Anti-Tile (Color) bei gleichen Einstellungen
    inputs = {"Scale": SC, "Randomness": 1.0, "Rotation Amount": 1.0, "Mirror Chance": 0.5, "Seed": 3,
              "Contrast Preserve": 0.2, "Mean Color": (0.4, 0.4, 0.4, 1.0)}
    plane = setup_scene()
    want = wrapper_run(plane, lambda: (anti_tile.build() and bpy.data.node_groups["SU Anti-Tile"]), 'coord',
                       inputs, "Color")

    bpy.ops.wm.read_factory_settings(use_empty=True)
    plane = setup_scene()

    def via_modifier(nt):
        smp = mat_sampler(nt, 'coord')
        m = nt.nodes.new("ShaderNodeGroup")
        m.node_tree = grp_at_sampler()
        nt.links.new(smp, m.inputs["Sampler"])
        for k, v in inputs.items():
            m.inputs[k].default_value = v
        e = nt.nodes.new("NodeEvaluateClosure")
        e.input_items.new('VECTOR', 'Coord')
        e.output_items.new('RGBA', 'Result')
        nt.links.new(m.outputs["Sampler"], e.inputs["Closure"])
        uv = nt.nodes.new("ShaderNodeTexCoord")
        nt.links.new(uv.outputs["UV"], e.inputs["Coord"])
        return e.outputs["Result"]
    got = render_composite(plane, via_modifier)
    check("SU Anti-Tile Sampler (Modifikator) == SU Anti-Tile (Color)", got, want)

    # 2. Triplanar(Anti-Tile Sampler(Koordinaten-Sampler)) mit Randomness 0 == Triplanar(Koordinaten-Sampler)
    for label, eul in (("Z unten", (math.pi, 0, 0)),
                       ("schräg", (math.radians(35), math.radians(20), math.radians(40)))):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        plane = setup_scene(euler=eul)

        def combo(nt):
            smp = mat_sampler(nt, 'coord')
            m = nt.nodes.new("ShaderNodeGroup")
            m.node_tree = grp_at_sampler()
            nt.links.new(smp, m.inputs["Sampler"])
            m.inputs["Randomness"].default_value = 0.0
            t = nt.nodes.new("ShaderNodeGroup")
            t.node_tree = grp_tri()
            nt.links.new(m.outputs["Sampler"], t.inputs["Sampler"])
            geo = nt.nodes.new("ShaderNodeNewGeometry")
            nt.links.new(geo.outputs["Position"], t.inputs["Vector"])
            return t.outputs["Color"]
        got = render_composite(plane, combo)
        want = []
        for p, n in _pos_normal_grid(eul):
            w = _weights(n, 0.2)
            acc = [0.0, 0.0]
            for k, A in enumerate("XYZ"):
                a, b, _ = PROJ[A]
                acc[0] += w[k] * _sgn(n["XYZ".index(A)]) * p[a]
                acc[1] += w[k] * p[b]
            want.append((acc[0], acc[1], 0.0))
        check(f"Triplanar(Anti-Tile Sampler(..)) Randomness 0 == Triplanar ({label})", got, want)


def test_metal():
    """SU Metal Preset: feste Menüauswahl (im Hintergrund lässt sich das Dropdown nicht setzen), Werte gegen metals.json."""
    data = metal_preset.load()
    by_label = {m["label"]: m for m in data["metals"]}
    cases = [("Copper", "Bare (polished)"), ("Iron (approx. carbon steel)", "Oxide Tint: Straw"),
             ("Titanium", "Oxide Tint: Blue"), ("Stainless Steel, austenitic (316-type)", "Oxide Tint: Purple"),
             ("Gold", "Oxide Tint: Blue"), ("Brass (Cu70 Zn30)", "Bare (polished)"),
             ("Silver", "Bare (polished)"), ("Tungsten", "Oxide Tint: Straw")]
    for metal, treat in cases:
        m = by_label[metal]
        tkey = metal_preset.TREATMENTS[treat]
        thick = (m["film"]["thickness_nm"][tkey] or 0.0) if (m["film"] and tkey) else 0.0
        film_ior = m["film"]["ior"] if m["film"] else metal_preset.DEFAULT_FILM_IOR
        want = {"Color": tuple(m["base_color"]), "Edge Color": tuple(m["edge_tint"]),
                "IOR": tuple(m["ior_rgb"]), "Extinction": tuple(m["extinction_rgb"]),
                "Thin Film Thickness": (thick,) * 3, "Thin Film IOR": (film_ior,) * 3}
        for out, w in want.items():
            plane = setup_scene()
            grp = metal_preset.build(fixed=(metal, treat))
            got = render_probe(plane, grp, {"inputs": {}, "output": out, "uv": False})
            check(f"Metal Preset [{metal} / {treat}] {out}", got, [w] * (N * N), tol=2e-4)


_only = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
for t in (test_pivot, test_polar, test_world, test_triplanar, test_anti_tile, test_wrappers, test_composition, test_metal):
    if _only and not any(o_ in t.__name__ for o_ in _only):
        continue
    try:
        t()
    except Exception as e:
        FAILS.append(t.__name__)
        import traceback
        traceback.print_exc()
        print(f"[FAIL] {t.__name__}: {type(e).__name__}: {e}")

print("ERGEBNIS:", "ALLE OK" if not FAILS else f"FEHLER in {len(FAILS)}: {FAILS}")
