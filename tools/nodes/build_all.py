"""Baut alle Mapping-Utility-Node-Groups in eine .blend-Datei.

Aufruf: blender -b --factory-startup --python tools/nodes/build_all.py -- <ziel.blend>
Gleichnamige Gruppen in der Zieldatei werden ersetzt, andere bleiben erhalten.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "groups"))

import anti_tile  # noqa: E402
import lib  # noqa: E402
import metal_preset  # noqa: E402
import polar_mapping  # noqa: E402
import sampler  # noqa: E402
import triplanar  # noqa: E402
import uv_pivot_transform  # noqa: E402
import world_coords  # noqa: E402

MODULES = [uv_pivot_transform, polar_mapping, world_coords, sampler, triplanar, anti_tile, metal_preset]


def main():
    target = sys.argv[sys.argv.index("--") + 1]
    lib.open_or_new(target)
    for m in MODULES:
        m.build()
        print("gebaut:", m.NAME)  # Triplanar baut drei Gruppen
    lib.save(target)
    print("gespeichert:", target)


if __name__ == "__main__":
    main()
