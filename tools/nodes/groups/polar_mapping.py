import lib

NAME = "SU Polar Mapping"


def build():
    ng = lib.new_group(NAME)
    lib.socket(ng, "Vector", 'VECTOR', out=True, desc="U = Winkel × Repeat, V = Radius × Radial Scale")
    lib.socket(ng, "Angle", 'FLOAT', out=True, desc="Winkel 0..1 (nach Offset und Spiegelung, vor Repeat)")
    lib.socket(ng, "Radius", 'FLOAT', out=True, desc="Abstand zum Zentrum × Radial Scale")
    lib.socket(ng, "Vector", 'VECTOR', hide_value=True, desc="Eingangskoordinaten (z. B. UV)")
    lib.socket(ng, "Center", 'VECTOR', default=(0.5, 0.5, 0.0), desc="Mittelpunkt der Polarkoordinaten")
    lib.socket(ng, "Angle Offset", 'ANGLE', default=0.0, desc="Dreht die Startrichtung des Winkels")
    lib.socket(ng, "Angular Repeat", 'INT', default=1, min=1, max=1000,
               desc="Wie oft die Textur um das Zentrum wiederholt wird (ganzzahlig, damit die Naht passt)")
    lib.socket(ng, "Radial Scale", 'FLOAT', default=1.0, desc="Streckt den Radius")
    lib.socket(ng, "Mirror Angle", 'BOOL', default=False, desc="Spiegelt den Winkel, damit die Naht bei 0/1 wegfällt")
    gi, go = lib.group_io(ng)

    d = lib.vmath(ng, 'SUBTRACT', gi.outputs["Vector"], gi.outputs["Center"])
    xyz = lib.separate(ng, d.outputs[0])
    atan = lib.math_node(ng, 'ARCTAN2', xyz.outputs["Y"], xyz.outputs["X"])
    plus = lib.math_node(ng, 'ADD', atan.outputs[0], gi.outputs["Angle Offset"])
    frac = lib.math_node(ng, 'DIVIDE', plus.outputs[0], lib.TWO_PI)
    wrap = lib.math_node(ng, 'WRAP', frac.outputs[0], 1.0, 0.0)  # Value, Max, Min

    two_a = lib.math_node(ng, 'MULTIPLY_ADD', wrap.outputs[0], 2.0, -1.0)
    mirrored = lib.math_node(ng, 'ABSOLUTE', two_a.outputs[0])
    _, angle = lib.mix(ng, 'FLOAT', gi.outputs["Mirror Angle"], wrap.outputs[0], mirrored.outputs[0])

    u = lib.math_node(ng, 'MULTIPLY', angle, gi.outputs["Angular Repeat"])
    length = lib.vmath(ng, 'LENGTH', d.outputs[0])
    radius = lib.math_node(ng, 'MULTIPLY', length.outputs["Value"], gi.outputs["Radial Scale"])
    vec = lib.combine(ng, u.outputs[0], radius.outputs[0], 0.0)

    lib.link(ng, vec.outputs[0], go.inputs["Vector"])
    lib.link(ng, angle, go.inputs["Angle"])
    lib.link(ng, radius.outputs[0], go.inputs["Radius"])

    lib.autolayout(ng)
    lib.mark_asset(ng, "Kartesisch zu polar: Winkel und Radius um ein Zentrum, mit Wiederholung, Offset und Spiegelung.",
                   ["mapping", "polar", "radial", "utility"])
    return ng
