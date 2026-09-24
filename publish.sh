#!/bin/bash
# Erzeugt die Remote-Asset-Listing-Dateien und pusht nach GitHub.
# Aufruf: ./publish.sh "Nachricht"
# Blender-Pfad: Umgebungsvariable BLENDER setzen, sonst wird `blender` im PATH genutzt.
set -e
cd "$(dirname "$0")"
BLENDER="${BLENDER:-blender}"
"$BLENDER" -b --factory-startup -c asset_listing generate library
git add -A
git commit -m "${1:-Update asset library}" || echo "Nichts zu committen"
git push
du -sh library
