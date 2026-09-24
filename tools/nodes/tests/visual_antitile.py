"""Sichtbeispiel: gleiche Textur normal gekachelt vs. Anti-Tile. Aufruf:
blender -b --factory-startup --python tools/nodes/tests/visual_antitile.py -- <ausgabeordner>"""
import math
import os
import sys

import bpy
import numpy as np

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "groups"))
import anti_tile  # noqa: E402
import sampler  # noqa: E402

out_dir = sys.argv[sys.argv.index("--") + 1]
os.makedirs(out_dir, exist_ok=True)
R = 256

# Kachelbare Testtextur: Fleckenmuster mit einem auffälligen roten Punkt (macht Wiederholungen sichtbar)
rng = np.random.default_rng(3)
yy, xx = np.mgrid[0:R, 0:R] / R
img = np.zeros((R, R, 3))
img[:] = (0.35, 0.3, 0.25)
for _ in range(40):
    cx, cy, r = rng.random(), rng.random(), 0.02 + 0.05 * rng.random()
    col = rng.random(3) * 0.6 + 0.2
    for ox in (-1, 0, 1):
        for oy in (-1, 0, 1):
            m = (xx - cx - ox) ** 2 + (yy - cy - oy) ** 2 < r * r
            img[m] = col
m = (xx - 0.3) ** 2 + (yy - 0.7) ** 2 < 0.06 ** 2
img[m] = (0.9, 0.05, 0.05)
rgba = np.dstack([img, np.ones((R, R))]).astype(np.float32)
W = 512


def render(name, anti, cp=0.5, soft=0.5):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.samples = 4
    sc.cycles.use_denoising = False
    sc.render.resolution_x = sc.render.resolution_y = W
    sc.view_settings.view_transform = 'Standard'
    sc.world = bpy.data.worlds.new("w")
    bpy.ops.mesh.primitive_plane_add(size=2)
    plane = bpy.context.active_object
    cam = bpy.data.objects.new("c", bpy.data.cameras.new("c"))
    cam.data.type = 'ORTHO'
    cam.data.ortho_scale = 2
    cam.location = (0, 0, 5)
    sc.collection.objects.link(cam)
    sc.camera = cam
    mat = bpy.data.materials.new("m")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    uv = nt.nodes.new("ShaderNodeTexCoord")
    t = bpy.data.images.new("tex", R, R)
    t.pixels.foreach_set(rgba.ravel())
    t.pack()
    if anti:
        smp = nt.nodes.new("ShaderNodeGroup")
        sg = sampler.build()
        sg.nodes["Image"].image = t
        smp.node_tree = sg
        a = nt.nodes.new("ShaderNodeGroup")
        a.node_tree = anti_tile.build()
        a.inputs["Scale"].default_value = 5
        a.inputs["Rotation Amount"].default_value = 1.0
        a.inputs["Mirror Chance"].default_value = 0.5
        a.inputs["Blend Softness"].default_value = soft
        a.inputs["Contrast Preserve"].default_value = cp
        a.inputs["Mean Color"].default_value = (0.4, 0.35, 0.3, 1)
        nt.links.new(uv.outputs["UV"], a.inputs["Vector"])
        nt.links.new(smp.outputs["Sampler"], a.inputs["Sampler"])
        color = a.outputs["Color"]
    else:
        mp = nt.nodes.new("ShaderNodeMapping")
        mp.inputs["Scale"].default_value = (5, 5, 5)
        nt.links.new(uv.outputs["UV"], mp.inputs["Vector"])
        im = nt.nodes.new("ShaderNodeTexImage")
        im.image = t
        nt.links.new(mp.outputs[0], im.inputs["Vector"])
        color = im.outputs["Color"]
    em = nt.nodes.new("ShaderNodeEmission")
    o = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(color, em.inputs["Color"])
    nt.links.new(em.outputs[0], o.inputs["Surface"])
    plane.data.materials.append(mat)
    sc.render.image_settings.file_format = 'PNG'
    sc.render.filepath = os.path.join(out_dir, name)
    bpy.ops.render.render(write_still=True)


render("tiled.png", False)
render("antitile_closure.png", True, cp=0.0)
