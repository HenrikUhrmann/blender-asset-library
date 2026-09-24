"""Läuft in einer Hintergrund-Blender-Instanz.

Hängt die Assets aus der temporären Datei an die Zieldatei an (oder legt sie neu an),
packt Bilder und speichert. Aufruf: blender -b [ziel.blend] --python worker.py -- spec.json
"""
import json
import os
import sys

import bpy

spec_path = sys.argv[sys.argv.index("--") + 1]
with open(spec_path, encoding="utf-8") as f:
    spec = json.load(f)

target = spec["target"]
if not os.path.exists(target):
    bpy.ops.wm.read_factory_settings(use_empty=True)

wanted = {}
skipped = []
for item in spec["items"]:
    coll = getattr(bpy.data, item["coll"])
    existing = coll.get(item["name"])
    if existing is not None:
        if not spec["overwrite"]:
            skipped.append(item["name"])
            continue
        coll.remove(existing, do_unlink=True)
    wanted.setdefault(item["coll"], []).append(item["name"])

loaded = []
with bpy.data.libraries.load(spec["tmp"], link=False) as (src, dst):
    for coll, names in wanted.items():
        available = set(getattr(src, coll))
        setattr(dst, coll, [n for n in names if n in available])
for coll in wanted:
    loaded.extend(i for i in getattr(dst, coll) if i is not None)

for idb in loaded:
    idb.use_fake_user = True
    if idb.asset_data is None:
        idb.asset_mark()

for img in bpy.data.images:
    if img.source == 'FILE' and img.filepath and img.packed_file is None:
        try:
            img.pack()
        except RuntimeError as e:
            print(f"WARNUNG: Bild {img.name} konnte nicht gepackt werden: {e}")

if bpy.data.libraries:
    print("WARNUNG: Datei enthält verlinkte Libraries, Assets sind nicht selbstständig.")

bpy.data.orphans_purge(do_recursive=True)
os.makedirs(os.path.dirname(target), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=target, compress=True)

print("ASSETPUB_ADDED:" + json.dumps([i.name for i in loaded]))
print("ASSETPUB_SKIPPED:" + json.dumps(skipped))
