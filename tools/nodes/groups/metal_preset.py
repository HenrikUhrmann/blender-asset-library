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
# Skalierung, damit alle Werte in Color-Ramp-Farben (0..1) passen; nach dem Lesen wieder zurückgerechnet
SCALE_N, SCALE_K, SCALE_T, SCALE_FILM = 8.0, 32.0, 64.0, 4.0


def load():
    with open(DATA, encoding="utf-8") as f:
        return json.load(f)


def _ramp(ng, values, index_fac):
    """Color Ramp (Constant) als Nachschlagetabelle: Eintrag i gilt für Index i. values: Liste von RGBA-Tupeln."""
    n = len(values)
    r = ng.nodes.new("ShaderNodeValToRGB")
    ramp = r.color_ramp
    ramp.interpolation = 'CONSTANT'
    while len(ramp.elements) < n:
        ramp.elements.new(1.0)
    while len(ramp.elements) > n:
        ramp.elements.remove(ramp.elements[len(ramp.elements) - 1])
    for i, v in enumerate(values):
        ramp.elements[i].position = i / n
        ramp.elements[i].color = v
    lib.link(ng, index_fac, r.inputs["Fac"])
    return r


def build(fixed=None):
    """fixed = (Metallname, Behandlungsname) fixiert die Menüs (nur für Tests).

    Aufbau: je Dropdown genau ein Menu-Switch (Ausgabe = Index), weil ein Menü-Socket nur an EINEN Switch
    angeschlossen werden darf. Die Werte kommen aus Color-Ramp-Tabellen (Constant), die der Index anspricht."""
    data = load()
    metals = sorted(data["metals"], key=lambda m: m["label"])
    n_metals = len(metals)

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

    # Genau ein Menu-Switch je Dropdown, Ausgabe = Index
    metal_idx = lib.menu_switch(ng, 'INT', gi.outputs["Metal"], {m["label"]: i for i, m in enumerate(metals)},
                                fixed_menu=fixed[0] if fixed else None)
    treat_idx = lib.menu_switch(ng, 'INT', gi.outputs["Treatment"], {t: i for i, t in enumerate(TREATMENTS)},
                                fixed_menu=fixed[1] if fixed else None)

    # Index -> Fac in der Mitte des jeweiligen Ramp-Eintrags
    plus = lib.math_node(ng, 'ADD', metal_idx, 0.5)
    fac = lib.math_node(ng, 'DIVIDE', plus.outputs[0], float(n_metals)).outputs[0]

    def rgba(v, a=1.0):
        return (v[0], v[1], v[2], a)

    ramp_base = _ramp(ng, [rgba(m["base_color"], (m["film"]["ior"] if m["film"] else DEFAULT_FILM_IOR) / SCALE_FILM)
                           for m in metals], fac)
    ramp_edge = _ramp(ng, [rgba(m["edge_tint"]) for m in metals], fac)
    ramp_n = _ramp(ng, [rgba([x / SCALE_N for x in m["ior_rgb"]]) for m in metals], fac)
    ramp_k = _ramp(ng, [rgba([x / SCALE_K for x in m["extinction_rgb"]]) for m in metals], fac)

    def thick(m):
        t = m["film"]["thickness_nm"] if m["film"] else {}
        return [(t.get(k) or 0.0) / SCALE_T for k in ("straw", "purple", "blue")]
    ramp_t = _ramp(ng, [rgba(thick(m)) for m in metals], fac)

    lib.link(ng, ramp_base.outputs["Color"], go.inputs["Color"])
    lib.link(ng, ramp_edge.outputs["Color"], go.inputs["Edge Color"])
    lib.link(ng, lib.vmath(ng, 'SCALE', ramp_n.outputs["Color"], scale=SCALE_N).outputs[0], go.inputs["IOR"])
    lib.link(ng, lib.vmath(ng, 'SCALE', ramp_k.outputs["Color"], scale=SCALE_K).outputs[0], go.inputs["Extinction"])
    lib.link(ng, lib.math_node(ng, 'MULTIPLY', ramp_base.outputs["Alpha"], SCALE_FILM).outputs[0],
             go.inputs["Thin Film IOR"])

    # Dicke: Behandlung 0 = keine Schicht, 1/2/3 = Straw/Purple/Blue aus den drei Kanälen von ramp_t
    ts = lib.separate(ng, ramp_t.outputs["Color"])
    total = None
    for t_index, channel in ((1, "X"), (2, "Y"), (3, "Z")):
        sel = lib.math_node(ng, 'COMPARE', treat_idx, float(t_index), 0.5)
        part = lib.math_node(ng, 'MULTIPLY', sel.outputs[0], ts.outputs[channel])
        total = part if total is None else lib.math_node(ng, 'ADD', total.outputs[0], part.outputs[0])
    lib.link(ng, lib.math_node(ng, 'MULTIPLY', total.outputs[0], SCALE_T).outputs[0], go.inputs["Thin Film Thickness"])

    lib.autolayout(ng)
    lib.mark_asset(ng, "Metall-Voreinstellung für Blenders Metallic BSDF: Dropdown für Metall (u. a. Stahl, Edelstahl, "
                       "Messing, Kupfer, Nickel, Gold) und Oxid-Behandlung. Ausgänge Color, Edge Color, IOR, Extinction, "
                       "Thin Film Thickness/IOR. Messwerte aus refractiveindex.info.",
                   ["metal", "material", "preset", "thin film", "utility"], catalog_id=lib.CATALOG_METALS)
    return ng
