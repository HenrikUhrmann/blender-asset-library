"""Vergleich F82-Tint vs Physical Conductor und Dünnfilm mit SU Metal Preset (feste Auswahl).
Aufruf: blender -b --factory-startup --python tools/nodes/tests/visual_metal.py -- <ausgabeordner>"""
import os
import sys

import bpy
import numpy as np

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "groups"))
import metal_preset  # noqa: E402

out_dir = sys.argv[sys.argv.index("--") + 1]
os.makedirs(out_dir, exist_ok=True)
CASES = [("Copper", "Bare (polished)"), ("Gold", "Bare (polished)"), ("Iron (approx. carbon steel)", "Bare (polished)"),
         ("Iron (approx. carbon steel)", "Oxide Tint: Straw"), ("Iron (approx. carbon steel)", "Oxide Tint: Purple"),
         ("Iron (approx. carbon steel)", "Oxide Tint: Blue"), ("Titanium", "Oxide Tint: Blue"),
         ("Brass (Cu70 Zn30)", "Bare (polished)")]


def render(name, mode, metal, treat):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'; sc.cycles.samples = 64; sc.cycles.use_denoising = False
    sc.render.resolution_x = sc.render.resolution_y = 256
    sc.view_settings.view_transform = 'Standard'
    sc.render.image_settings.file_format = 'OPEN_EXR'; sc.render.image_settings.color_mode = 'RGB'
    w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
    # Studio-ähnliche Umgebung: Verlauf hell/dunkel, damit Fresnel-Verläufe sichtbar sind
    nt = w.node_tree; nt.nodes.clear()
    tc = nt.nodes.new("ShaderNodeTexCoord"); sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    ramp = nt.nodes.new("ShaderNodeValToRGB"); bg = nt.nodes.new("ShaderNodeBackground"); o = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(tc.outputs["Generated"], sep.inputs[0]); nt.links.new(sep.outputs["Z"], ramp.inputs["Fac"])
    ramp.color_ramp.elements[0].color = (0.05, 0.05, 0.05, 1); ramp.color_ramp.elements[1].color = (2.0, 2.0, 2.0, 1)
    nt.links.new(ramp.outputs["Color"], bg.inputs["Color"]); nt.links.new(bg.outputs[0], o.inputs[0])
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1, segments=64, ring_count=32); obj = bpy.context.active_object
    bpy.ops.object.shade_smooth()
    cam = bpy.data.objects.new("c", bpy.data.cameras.new("c")); cam.location = (0, -4, 0); cam.rotation_euler = (1.5708, 0, 0)
    cam.data.lens = 80; sc.collection.objects.link(cam); sc.camera = cam
    mat = bpy.data.materials.new("m"); mat.use_nodes = True
    n = mat.node_tree; n.nodes.clear()
    g = n.nodes.new("ShaderNodeGroup"); g.node_tree = metal_preset.build(fixed=(metal, treat))
    b = n.nodes.new("ShaderNodeBsdfMetallic"); out = n.nodes.new("ShaderNodeOutputMaterial")
    b.inputs["Roughness"].default_value = 0.15
    if mode == "f82":
        b.fresnel_type = 'F82'
        n.links.new(g.outputs["Color"], b.inputs["Base Color"]); n.links.new(g.outputs["Edge Color"], b.inputs["Edge Tint"])
    else:
        b.fresnel_type = 'PHYSICAL_CONDUCTOR'
        n.links.new(g.outputs["IOR"], b.inputs["IOR"]); n.links.new(g.outputs["Extinction"], b.inputs["Extinction"])
    n.links.new(g.outputs["Thin Film Thickness"], b.inputs["Thin Film Thickness"])
    n.links.new(g.outputs["Thin Film IOR"], b.inputs["Thin Film IOR"])
    n.links.new(b.outputs[0], out.inputs["Surface"])
    obj.data.materials.append(mat)
    p = os.path.join(out_dir, name + ".exr"); sc.render.filepath = p
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(p); px = np.array(img.pixels[:]).reshape(256, 256, -1)[:, :, :3]
    # Bildmitte (Kugel), 40x40 Pixel
    return px[108:148, 108:148].reshape(-1, 3).mean(axis=0)


for metal, treat in CASES:
    a = render("a", "f82", metal, treat); b = render("b", "cond", metal, treat)
    print(f"RESULT {metal[:22]:22} {treat:20} F82 {np.round(a,3)}  Conductor {np.round(b,3)}  max.Diff {np.abs(a-b).max():.3f}")
