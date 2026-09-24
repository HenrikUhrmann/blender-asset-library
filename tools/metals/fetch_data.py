"""Lädt die benötigten optischen Konstanten aus refractiveindex.info (CC0) nach tools/metals/data/.
Quelle: https://github.com/polyanskiy/refractiveindex.info-database (Lizenz CC0-1.0)."""
import os
import urllib.parse
import urllib.request

BASE = "https://raw.githubusercontent.com/polyanskiy/refractiveindex.info-database/main/database/data/"
HERE = os.path.dirname(__file__)

# key -> Pfad relativ zu database/data/
FILES = {
    # Metalle
    "Al": "main/Al/nk/Rakic.yml",
    "Cu": "main/Cu/nk/Johnson.yml",
    "Au": "main/Au/nk/Johnson.yml",
    "Ag": "main/Ag/nk/Johnson.yml",
    "Fe": "main/Fe/nk/Johnson.yml",
    "Ni": "main/Ni/nk/Johnson.yml",
    "Cr": "main/Cr/nk/Johnson.yml",
    "Ti": "main/Ti/nk/Johnson.yml",
    "Co": "main/Co/nk/Johnson.yml",
    "Zn": "main/Zn/nk/Werner.yml",
    "Pt": "main/Pt/nk/Rakic-LD.yml",
    "Pd": "main/Pd/nk/Johnson.yml",
    "W": "main/W/nk/Rakic-LD.yml",
    "Mg": "main/Mg/nk/Hagemann.yml",
    "Brass": "other/alloys/Cu-Zn/nk/Querry-Cu70Zn30.yml",
    "RedBrass": "other/alloys/Cu-Zn/nk/Querry-Cu85Zn15.yml",
    "CommercialBronze": "other/alloys/Cu-Zn/nk/Querry-Cu90Zn10.yml",
    "StainlessAustenitic": "other/alloys/stainless steel/nk/Karlsson-austenitic.yml",
    "StainlessFerritic": "other/alloys/stainless steel/nk/Karlsson-ferritic.yml",
    # Oxide für Dünnfilm-IOR
    "Fe3O4": "main/Fe3O4/nk/Querry.yml",
    "TiO2": "main/TiO2/nk/Siefke.yml",
}

os.makedirs(os.path.join(HERE, "data"), exist_ok=True)
for key, path in FILES.items():
    url = BASE + urllib.parse.quote(path)
    dest = os.path.join(HERE, "data", key + ".yml")
    with urllib.request.urlopen(url, timeout=60) as r, open(dest, "wb") as f:
        f.write(r.read())
    print("ok", key, path)
