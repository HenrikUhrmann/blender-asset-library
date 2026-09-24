import lib

NAME = "SU UV Pivot Transform"


def build():
    ng = lib.new_group(NAME)
    lib.socket(ng, "Vector", 'VECTOR', out=True)
    lib.socket(ng, "Vector", 'VECTOR', hide_value=True, desc="Eingangskoordinaten (z. B. UV)")
    lib.socket(ng, "Pivot", 'VECTOR', default=(0.5, 0.5, 0.0), desc="Drehpunkt und Mitte für Skalieren und Spiegeln")
    lib.socket(ng, "Scale", 'VECTOR', default=(1.0, 1.0, 1.0), desc="Kachelung wie im Mapping-Node (2 = doppelt so viele Kacheln)")
    lib.socket(ng, "Rotation", 'ANGLE', default=0.0, desc="Dreht die Textur gegen den Uhrzeigersinn um den Pivot")
    lib.socket(ng, "Offset", 'VECTOR', default=(0.0, 0.0, 0.0), desc="Verschiebt die Textur in Richtung des Offsets")
    lib.socket(ng, "Mirror X", 'BOOL', default=False, desc="Spiegelt die Textur horizontal am Pivot")
    lib.socket(ng, "Mirror Y", 'BOOL', default=False, desc="Spiegelt die Textur vertikal am Pivot")
    gi, go = lib.group_io(ng)

    # Koordinaten-Reihenfolge (Textur-Reihenfolge ist umgekehrt: Spiegeln, Skalieren, Drehen, Verschieben)
    rel = lib.vmath(ng, 'SUBTRACT', gi.outputs["Vector"], gi.outputs["Pivot"])
    moved = lib.vmath(ng, 'SUBTRACT', rel.outputs[0], gi.outputs["Offset"])
    rot = lib.node(ng, "ShaderNodeVectorRotate", rotation_type='Z_AXIS', invert=True)
    lib.link(ng, moved.outputs[0], lib.sock(rot, "Vector"))
    lib.link(ng, gi.outputs["Rotation"], lib.sock(rot, "Angle"))
    scaled = lib.vmath(ng, 'MULTIPLY', rot.outputs["Vector"], gi.outputs["Scale"])
    sx = lib.math_node(ng, 'MULTIPLY_ADD', gi.outputs["Mirror X"], -2.0, 1.0)
    sy = lib.math_node(ng, 'MULTIPLY_ADD', gi.outputs["Mirror Y"], -2.0, 1.0)
    sign = lib.combine(ng, sx.outputs[0], sy.outputs[0], 1.0)
    mirrored = lib.vmath(ng, 'MULTIPLY', scaled.outputs[0], sign.outputs[0])
    back = lib.vmath(ng, 'ADD', mirrored.outputs[0], gi.outputs["Pivot"])
    lib.link(ng, back.outputs[0], go.inputs["Vector"])

    lib.autolayout(ng)
    lib.mark_asset(ng, "Skalieren, Drehen, Verschieben und Spiegeln von Koordinaten um einen frei wählbaren Pivot.",
                   ["mapping", "uv", "transform", "utility"])
    return ng
