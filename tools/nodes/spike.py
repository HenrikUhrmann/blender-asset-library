"""Phase 0: prüft, was Blender 5.2 für Shader-Node-Groups unterstützt. Schreibt nichts in die Library.
Aufruf: blender -b --factory-startup --python tools/nodes/spike.py
"""
import os
import tempfile

import bpy

def check(label, fn):
    try:
        print(f"[OK]   {label}: {fn()}")
    except Exception as e:
        print(f"[FAIL] {label}: {type(e).__name__}: {e}")

print("Blender", bpy.app.version_string)
ng = bpy.data.node_groups.new("spike", "ShaderNodeTree")
ifc = ng.interface

# 1. Interface-Sockets
for st in ("NodeSocketImage", "NodeSocketMenu", "NodeSocketBool", "NodeSocketInt",
           "NodeSocketFloatAngle", "NodeSocketVector", "NodeSocketColor", "NodeSocketString"):
    check(f"socket {st} im Shader-Group-Interface",
          lambda st=st: ifc.new_socket(st, in_out='INPUT', socket_type=st).socket_type)
check("Panel", lambda: ifc.new_panel("P").name)

img_in = next((i for i in ifc.items_tree if getattr(i, "socket_type", "") == "NodeSocketImage"), None)
if img_in:
    gi = ng.nodes.new("NodeGroupInput")
    tex = ng.nodes.new("ShaderNodeTexImage")
    print("Image-Texture-Node Eingänge:", [s.identifier for s in tex.inputs])
    img_sock = next((s for s in tex.inputs if s.type == 'CUSTOM' or "Image" in s.name), None)
    print("Image-Eingang am Texture-Node:", img_sock.identifier if img_sock else None)
    if img_sock:
        check("Group-Image-Socket -> Image-Texture-Node verlinken",
              lambda: ng.links.new(gi.outputs[img_in.name], img_sock) and "ok")

# 2. Nodes vorhanden?
for idn in ("ShaderNodeVectorRotate", "ShaderNodeVectorMath", "ShaderNodeMath", "ShaderNodeTexWhiteNoise",
            "ShaderNodeTangent", "ShaderNodeNewGeometry", "ShaderNodeObjectInfo", "ShaderNodeTexCoord",
            "ShaderNodeSeparateXYZ", "ShaderNodeCombineXYZ", "ShaderNodeMix", "ShaderNodeMapRange",
            "ShaderNodeNormalMap", "ShaderNodeBump", "ShaderNodeTexImage", "ShaderNodeMenuSwitch"):
    check(f"Node {idn}", lambda idn=idn: ng.nodes.new(idn).bl_label)

vm = ng.nodes.new("ShaderNodeVectorMath")
check("VectorMath-Operationen", lambda: [o for o in ("WRAP", "FLOOR", "FRACTION", "SINE", "NORMALIZE",
        "CROSS_PRODUCT", "DOT_PRODUCT", "LENGTH", "SCALE", "REFLECT")
        if o in vm.bl_rna.properties["operation"].enum_items.keys()])
m = ng.nodes.new("ShaderNodeMath")
check("Math-Operationen", lambda: [o for o in ("ARCTAN2", "COMPARE", "SMOOTH_MIN", "WRAP", "FRACT", "POWER",
        "PINGPONG", "SMOOTHSTEP", "SIGN") if o in m.bl_rna.properties["operation"].enum_items.keys()])
wn = ng.nodes.new("ShaderNodeTexWhiteNoise")
check("WhiteNoise Dimensionen", lambda: list(wn.bl_rna.properties["noise_dimensions"].enum_items.keys()))
tan = ng.nodes.new("ShaderNodeTangent")
check("Tangent: direction_type / uv_map",
      lambda: (tan.direction_type, tan.uv_map, list(tan.bl_rna.properties["direction_type"].enum_items.keys())))
tx = ng.nodes.new("ShaderNodeTexImage")
check("TexImage interpolation / projection",
      lambda: (list(tx.bl_rna.properties["interpolation"].enum_items.keys()),
               list(tx.bl_rna.properties["projection"].enum_items.keys())))
check("Geometry-Outputs", lambda: [s.name for s in ng.nodes.new("ShaderNodeNewGeometry").outputs])

# 3. Interface-Grenzen und Beschreibung
def bounds():
    s = ifc.new_socket("f", in_out='INPUT', socket_type="NodeSocketFloat")
    s.min_value, s.max_value, s.default_value, s.description = 0.0, 1.0, 0.5, "tip"
    return (s.min_value, s.max_value, s.default_value, s.description)
check("min/max/default/description", bounds)
check("hide_value", lambda: setattr(ifc.items_tree[0], "hide_value", True) or "ok")

# 4. Asset markieren, Vorschau, Speichern
def asset():
    ng.asset_mark()
    ng.asset_data.description = "d"
    ng.asset_data.tags.new("t")
    return (ng.asset_data.catalog_id, [t.name for t in ng.asset_data.tags])
check("asset_mark", asset)
check("preview_ensure", lambda: ng.preview_ensure() is not None)
check("Vorschau-Größe vor Rendern", lambda: tuple(ng.preview.image_size))
check("asset_generate_preview", lambda: ng.asset_generate_preview() or "ok")

tmp = os.path.join(tempfile.mkdtemp(), "lib", "spike.blend")
os.makedirs(os.path.dirname(tmp))
bpy.ops.wm.save_as_mainfile(filepath=tmp)
print("SPIKE_FILE:", tmp)
