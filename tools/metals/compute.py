"""Berechnet die Metall-Voreinstellungen aus den Rohdaten und schreibt metals.json.
Aufruf: python3 tools/metals/compute.py"""
import json
import os

import numpy as np

import optics as o

HERE = os.path.dirname(__file__)

# key, Anzeigename, Datenquelle-Schlüssel für Film (Oxid) oder None, Hinweis zum Film
METALS = [
    ("Al", "Aluminium", None, ""),
    ("Brass", "Brass (Cu70 Zn30)", None, ""),
    ("Cr", "Chromium", None, ""),
    ("Co", "Cobalt", None, ""),
    ("CommercialBronze", "Commercial Bronze (Cu90 Zn10)", None, ""),
    ("Cu", "Copper", None, ""),
    ("Au", "Gold", None, ""),
    ("Fe", "Iron (approx. carbon steel)", "Fe3O4", "Magnetit (Fe3O4)"),
    ("Mg", "Magnesium", None, ""),
    ("Ni", "Nickel", None, ""),
    ("Pd", "Palladium", None, ""),
    ("Pt", "Platinum", None, ""),
    ("RedBrass", "Red Brass (Cu85 Zn15)", None, ""),
    ("Ag", "Silver", None, ""),
    ("StainlessAustenitic", "Stainless Steel, austenitic (316-type)", "Fe3O4", "Eisenoxid (Magnetit) als Näherung für die Chrom-Eisen-Oxidschicht"),
    ("StainlessFerritic", "Stainless Steel, ferritic (430-type)", "Fe3O4", "Eisenoxid (Magnetit) als Näherung für die Chrom-Eisen-Oxidschicht"),
    ("Ti", "Titanium", "TiO2", "Titandioxid (TiO2), wie beim Anodisieren"),
    ("W", "Tungsten", None, ""),
    ("Zn", "Zinc", None, ""),
]
# Film-Ziel: Reflexionsminimum bei dieser Wellenlänge (nm) -> Farbeindruck
TINTS = [("straw", 450.0), ("purple", 550.0), ("blue", 650.0)]


def r4(a):
    return [round(float(x), 4) for x in a]


def main():
    out = {"treatments": [t for t, _ in TINTS], "metals": []}
    for key, label, film, film_note in METALS:
        n, k = o.interp_nk(key)
        f0, tint, n_rgb, k_rgb = o.metal_colors(n, k)
        entry = {
            "key": key, "label": label,
            "base_color": r4(f0), "edge_tint": r4(tint),
            "ior_rgb": r4(n_rgb), "extinction_rgb": r4(k_rgb),
            "ior_550": round(float(np.interp(550.0, o.WL, n)), 4),
            "reference": o.reference(key),
            "film": None,
        }
        if film:
            nf, kf = o.interp_nk(film)
            n_film = float(np.interp(550.0, o.WL, nf))
            thick = {}
            for name, target in TINTS:
                thick[name] = o.thickness_for_minimum(n, k, n_film, target)
            entry["film"] = {"material": film, "note": film_note, "ior": round(n_film, 3),
                             "thickness_nm": {k_: (round(v, 1) if v else None) for k_, v in thick.items()},
                             "reference": o.reference(film)}
        out["metals"].append(entry)
    with open(os.path.join(HERE, "metals.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print(f"{'Metall':40} {'Base Color':24} {'Edge Tint':24} {'n RGB':20} {'k RGB':20} film n / nm straw,purple,blue")
    for m in out["metals"]:
        fl = m["film"]
        ft = f"{fl['material']} n={fl['ior']} {list(fl['thickness_nm'].values())}" if fl else "-"
        print(f"{m['label']:40} {str(m['base_color']):24} {str(m['edge_tint']):24} {str(m['ior_rgb']):20} {str(m['extinction_rgb']):20} {ft}")


if __name__ == "__main__":
    main()
