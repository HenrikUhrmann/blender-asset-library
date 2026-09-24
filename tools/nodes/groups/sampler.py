"""SU Image Sampler: Closure (Coord -> Color) mit einem Image-Texture-Node, als Eingang für
SU Triplanar, SU Triplanar Normal und SU Anti-Tile. Bild im Node "Image" innerhalb der Gruppe setzen (Tab)."""
import lib

NAME = "SU Image Sampler"


def build():
    ng = lib.new_group(NAME)
    lib.socket(ng, "Sampler", 'CLOSURE', out=True, desc="Sampler-Closure: nimmt eine Koordinate, liefert die Bildfarbe")
    gi, go = lib.group_io(ng)
    cin = lib.node(ng, "NodeClosureInput")
    cout = lib.node(ng, "NodeClosureOutput")
    cin.pair_with_output(cout)
    cout.input_items.new('VECTOR', 'Coord')
    cout.output_items.new('RGBA', 'Result')
    tex = lib.node(ng, "ShaderNodeTexImage", label="Image", extension='REPEAT', interpolation='Linear')
    tex.name = "Image"
    lib.link(ng, cin.outputs["Coord"], tex.inputs["Vector"])
    lib.link(ng, tex.outputs["Color"], cout.inputs["Result"])
    lib.link(ng, cout.outputs["Closure"], go.inputs["Sampler"])
    lib.autolayout(ng)
    lib.mark_asset(ng, "Sampler-Closure mit Image-Texture: Bild im Node 'Image' setzen (Tab). Pro Bild eine Einzelkopie "
                       "der Gruppe. Eingang für SU Triplanar, SU Triplanar Normal und SU Anti-Tile.",
                   ["mapping", "sampler", "closure", "utility"])
    return ng
