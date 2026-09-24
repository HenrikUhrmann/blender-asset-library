"""SU Metal Preset: Dropdown für Metall und Oberflächenbehandlung, liefert Werte für Blenders Metallic BSDF.

Datenquelle: tools/metals/metals.json (erzeugt von tools/metals/compute.py aus refractiveindex.info, CC0).
Ausgänge passend zum Metallic BSDF: Color = Base Color (F0), Edge Color = Edge Tint (F82-Tint), IOR und
Extinction (Physical Conductor, je RGB), Thin Film Thickness (nm) und Thin Film IOR.
"""
import json
import os

import lib

NAME = "SU Metal Preset"
DATA = os.path.join(os.path.dirname(__file__), "..", "..", "metals", "metals.json")

TREATMENTS = {  # Menüname -> Schlüssel in metals.json (None = ohne Film)
    "Bare (polished)": None,
    "Oxide Tint: Straw": "straw",
    "Oxide Tint: Purple": "purple",
    "Oxide Tint: Blue": "blue",
}
DEFAULT_FILM_IOR = 1.33  # Blender-Standard, wird nur wirksam, wenn Dicke > 0


def load():
    with open(DATA, encoding="utf-8") as f:
        return json.load(f)


def build(fixed=None):
    """fixed = (Metallname, Behandlungsname) fixiert die Menüs (nur für Tests)."""
    data = load()
    metals = sorted(data["metals"], key=lambda m: m["label"])

    ng = lib.new_group(NAME)
    lib.socket(ng, "Color", 'COLOR', out=True, desc="Base Color (Reflexion bei senkrechtem Blick, F0), linear")
    lib.socket(ng, "Edge Color", 'COLOR', out=True,
               desc="Edge Tint für Metallic BSDF im Modus F82 Tint (Verhältnis zu Schlick bei ca. 82°)")
    lib.socket(ng, "IOR", 'VECTOR', out=True, desc="Brechungsindex n je RGB, für Metallic BSDF im Modus Physical Conductor")
    lib.socket(ng, "Extinction", 'VECTOR', out=True, desc="Extinktionskoeffizient k je RGB, für Physical Conductor")
    lib.socket(ng, "Thin Film Thickness", 'FLOAT', out=True,
               desc="Schichtdicke in nm für die gewählte Behandlung (0 = keine Schicht)")
    lib.socket(ng, "Thin Film IOR", 'FLOAT', out=True, desc="Brechungsindex der Oxidschicht (bei 550 nm)")
    lib.socket(ng, "Metal", 'MENU', desc="Metall bzw. Legierung. Werte aus refractiveindex.info (Messdaten)")
    lib.socket(ng, "Treatment", 'MENU',
               desc="Oxidschicht: Anlassfarben (Stahl, Edelstahl) bzw. Anodisieren (Titan). Farbton = Wellenlänge, die die "
                    "Schicht auslöscht (Straw 450 nm, Purple 550 nm, Blue 650 nm). Nur bei Eisen, Edelstahl und Titan; "
                    "sonst 0 nm")
    gi, go = lib.group_io(ng)
    metal_menu, treat_menu = gi.outputs["Metal"], gi.outputs["Treatment"]
    fm = fixed[0] if fixed else None
    ft = fixed[1] if fixed else None

    def per_metal(dtype, fn):
        return lib.menu_switch(ng, dtype, metal_menu, {m["label"]: fn(m) for m in metals}, fixed_menu=fm)

    def rgba(v):
        return (v[0], v[1], v[2], 1.0)

    lib.link(ng, per_metal('RGBA', lambda m: rgba(m["base_color"])), go.inputs["Color"])
    lib.link(ng, per_metal('RGBA', lambda m: rgba(m["edge_tint"])), go.inputs["Edge Color"])
    lib.link(ng, per_metal('VECTOR', lambda m: tuple(m["ior_rgb"])), go.inputs["IOR"])
    lib.link(ng, per_metal('VECTOR', lambda m: tuple(m["extinction_rgb"])), go.inputs["Extinction"])
    lib.link(ng, per_metal('FLOAT', lambda m: m["film"]["ior"] if m["film"] else DEFAULT_FILM_IOR),
             go.inputs["Thin Film IOR"])

    thickness_items = {}
    for tname, tkey in TREATMENTS.items():
        if tkey is None:
            thickness_items[tname] = 0.0
        else:
            thickness_items[tname] = per_metal(
                'FLOAT', lambda m, tkey=tkey: (m["film"]["thickness_nm"][tkey] or 0.0) if m["film"] else 0.0)
    ms = ng.nodes.new("GeometryNodeMenuSwitch")
    ms.data_type = 'FLOAT'
    for nm in [i.name for i in ms.enum_items]:
        ms.enum_items.remove(ms.enum_items[nm])
    for tname in TREATMENTS:
        ms.enum_items.new(tname)
    if ft is not None:
        ms.inputs["Menu"].default_value = ft
    else:
        ng.links.new(treat_menu, ms.inputs["Menu"])
    for tname, val in thickness_items.items():
        if isinstance(val, float):
            ms.inputs[tname].default_value = val
        else:
            ng.links.new(val, ms.inputs[tname])
    lib.link(ng, ms.outputs["Output"], go.inputs["Thin Film Thickness"])

    lib.autolayout(ng)
    lib.mark_asset(ng, "Metall-Voreinstellung für Blenders Metallic BSDF: Dropdown für Metall (u. a. Stahl, Edelstahl, "
                       "Messing, Kupfer, Nickel, Gold) und Oxid-Behandlung. Ausgänge Color, Edge Color, IOR, Extinction, "
                       "Thin Film Thickness/IOR. Messwerte aus refractiveindex.info.",
                   ["metal", "material", "preset", "thin film", "utility"], catalog_id=lib.CATALOG_METALS)
    return ng
