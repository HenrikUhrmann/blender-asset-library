import lib

NAME = "SU World Coords"


def build():
    ng = lib.new_group(NAME)
    lib.socket(ng, "Vector", 'VECTOR', out=True, desc="3D-Koordinaten in Kacheln")
    lib.socket(ng, "YZ", 'VECTOR', out=True, desc="Planar: Y als U, Z als V (Projektion entlang X)")
    lib.socket(ng, "XZ", 'VECTOR', out=True, desc="Planar: X als U, Z als V (Projektion entlang Y)")
    lib.socket(ng, "XY", 'VECTOR', out=True, desc="Planar: X als U, Y als V (Projektion entlang Z)")
    lib.socket(ng, "Tile Size", 'FLOAT', default=1.0, min=0.0001, desc="Kantenlänge einer Kachel in Metern")
    lib.socket(ng, "Mode", 'INT', default=0, min=0, max=2,
               desc="0 = World (fest im Raum), 1 = Object anchored (folgt Position, ignoriert Skalierung), "
                    "2 = Object scaled (folgt Position, Rotation und Skalierung, Kacheln bleiben in Metern)")
    lib.socket(ng, "Offset", 'VECTOR', default=(0.0, 0.0, 0.0), desc="Verschiebung in Kacheln")
    gi, go = lib.group_io(ng)

    geo = lib.node(ng, "ShaderNodeNewGeometry")
    info = lib.node(ng, "ShaderNodeObjectInfo")
    texco = lib.node(ng, "ShaderNodeTexCoord")
    world = geo.outputs["Position"]
    anchored = lib.vmath(ng, 'SUBTRACT', world, info.outputs["Location"])
    # Object Info hat in 5.2 keinen Scale-Ausgang: Skalierung = Länge der in die Welt transformierten Achsenvektoren
    axis_len = []
    for axis in ((1, 0, 0), (0, 1, 0), (0, 0, 1)):
        vt = lib.node(ng, "ShaderNodeVectorTransform", vector_type='VECTOR',
                      convert_from='OBJECT', convert_to='WORLD')
        vt.inputs[0].default_value = axis
        ln = lib.vmath(ng, 'LENGTH', vt.outputs[0])
        axis_len.append(ln.outputs["Value"])
    obj_scale = lib.combine(ng, *axis_len)
    scaled = lib.vmath(ng, 'MULTIPLY', texco.outputs["Object"], obj_scale.outputs[0])

    is1 = lib.math_node(ng, 'COMPARE', gi.outputs["Mode"], 1.0, 0.5)
    is2 = lib.math_node(ng, 'COMPARE', gi.outputs["Mode"], 2.0, 0.5)
    _, m1 = lib.mix(ng, 'VECTOR', is1.outputs[0], world, anchored.outputs[0])
    _, m2 = lib.mix(ng, 'VECTOR', is2.outputs[0], m1, scaled.outputs[0])

    inv = lib.math_node(ng, 'DIVIDE', 1.0, gi.outputs["Tile Size"])
    tiled = lib.vmath(ng, 'SCALE', m2, scale=inv.outputs[0])
    final = lib.vmath(ng, 'ADD', tiled.outputs[0], gi.outputs["Offset"])
    lib.link(ng, final.outputs[0], go.inputs["Vector"])

    xyz = lib.separate(ng, final.outputs[0])
    for out_name, (a, b) in {"YZ": ("Y", "Z"), "XZ": ("X", "Z"), "XY": ("X", "Y")}.items():
        c = lib.combine(ng, xyz.outputs[a], xyz.outputs[b], 0.0)
        lib.link(ng, c.outputs[0], go.inputs[out_name])

    lib.autolayout(ng)
    lib.mark_asset(ng, "Weltkoordinaten in Metern für Texturen unabhängig von UVs, mit drei Modi und planaren Ausgängen.",
                   ["mapping", "world", "coordinates", "utility"])
    return ng
