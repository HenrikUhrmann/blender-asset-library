"""Sichtbeispiel: Triplanar allein vs. Triplanar mit Anti-Tile-Sampler auf einer Kugel.
Aufruf: blender -b --factory-startup --python tools/nodes/tests/visual_triplanar.py -- <ausgabeordner>"""
import os
import sys

import bpy
import numpy as np

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "groups"))
import anti_tile  # noqa: E402
import sampler  # noqa: E402
import triplanar  # noqa: E402

out_dir = sys.argv[sys.argv.index("--") + 1]
os.makedirs(out_dir, exist_ok=True)
R = 256
rng = np.random.default_rng(3)
yy, xx = np.mgrid[0:R, 0:R] / R
img = np.zeros((R, R, 3)); img[:] = (0.35, 0.3, 0.25)
for _ in range(40):
    cx, cy, r = rng.random(), rng.random(), 0.02 + 0.05 * rng.random()
    col = rng.random(3) * 0.6 + 0.2
    for ox in (-1, 0, 1):
        for oy in (-1, 0, 1):
            img[(xx - cx - ox) ** 2 + (yy - cy - oy) ** 2 < r * r] = col
img[(xx - 0.3) ** 2 + (yy - 0.7) ** 2 < 0.06 ** 2] = (0.9, 0.05, 0.05)
rgba = np.dstack([img, np.ones((R, R))]).astype(np.float32)


def render(name, with_anti):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'; sc.cycles.samples = 4; sc.cycles.use_denoising = False
    sc.render.resolution_x = sc.render.resolution_y = 512
    sc.view_settings.view_transform = 'Standard'
    sc.world = bpy.data.worlds.new("w")
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1, segments=64, ring_count=32)
    obj = bpy.context.active_object
    bpy.ops.object.shade_smooth()
    cam = bpy.data.objects.new("c", bpy.data.cameras.new("c"))
    cam.location = (0, -4, 0.6); cam.rotation_euler = (1.42, 0, 0)
    cam.data.lens = 60
    sc.collection.objects.link(cam); sc.camera = cam
    t = bpy.data.images.new("tex", R, R); t.pixels.foreach_set(rgba.ravel()); t.pack()

    mat = bpy.data.materials.new("m"); mat.use_nodes = True
    nt = mat.node_tree; nt.nodes.clear()
    smp = nt.nodes.new("ShaderNodeGroup"); sg = sampler.build(); sg.nodes["Image"].image = t; smp.node_tree = sg
    src = smp.outputs["Sampler"]
    if with_anti:
        a = nt.nodes.new("ShaderNodeGroup"); a.node_tree = anti_tile.build_anti_tile_sampler()
        a.inputs["Scale"].default_value = 1.0
        a.inputs["Rotation Amount"].default_value = 1.0
        a.inputs["Mirror Chance"].default_value = 0.5
        nt.links.new(src, a.inputs["Sampler"]); src = a.outputs["Sampler"]
    tri = nt.nodes.new("ShaderNodeGroup"); triplanar.build(); tri.node_tree = bpy.data.node_groups["SU Triplanar"]
    tri.inputs["Scale"].default_value = 1.5
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    nt.links.new(geo.outputs["Position"], tri.inputs["Vector"])
    nt.links.new(src, tri.inputs["Sampler"])
    em = nt.nodes.new("ShaderNodeEmission"); o = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(tri.outputs["Color"], em.inputs["Color"]); nt.links.new(em.outputs[0], o.inputs["Surface"])
    obj.data.materials.append(mat)
    sc.render.image_settings.file_format = 'PNG'
    sc.render.filepath = os.path.join(out_dir, name)
    bpy.ops.render.render(write_still=True)


render("triplanar.png", False)
render("triplanar_antitile.png", True)
