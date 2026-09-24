"""Hilfsfunktionen zum Bauen von Shader-Node-Groups (Blender 5.2, im Hintergrund lauffähig)."""
import math
import os

import bpy

AUTHOR = "Henrik Uhrmann"
CATALOG_MAPPING = "3f6b1c2a-5d7e-4a90-8b14-6c2d9e0f7a11"  # Node-Groups/Mapping
CATALOG_METALS = "8d1e4f70-2b93-4c6a-a5d8-1e7f3c9b2a44"  # Node-Groups/Metals
TWO_PI = 2 * math.pi

_KINDS = {
    'FLOAT': ('NodeSocketFloat', None),
    'ANGLE': ('NodeSocketFloat', 'ANGLE'),
    'INT': ('NodeSocketInt', None),
    'BOOL': ('NodeSocketBool', None),
    'VECTOR': ('NodeSocketVector', None),
    'COLOR': ('NodeSocketColor', None),
    'CLOSURE': ('NodeSocketClosure', None),
    'MENU': ('NodeSocketMenu', None),
}


def new_group(name):
    """Legt eine leere Shader-Node-Group an; eine gleichnamige alte wird ersetzt."""
    old = bpy.data.node_groups.get(name)
    if old is not None:
        bpy.data.node_groups.remove(old)
    ng = bpy.data.node_groups.new(name, "ShaderNodeTree")
    ng.use_fake_user = True
    return ng


def clear_su_groups(prefix="SU "):
    """Entfernt alle Gruppen mit diesem Präfix (vor einem Neubau, damit keine alten Versionen übrig bleiben)."""
    for g in list(bpy.data.node_groups):
        if g.name.startswith(prefix):
            bpy.data.node_groups.remove(g)


def get_or_build(name, builder):
    """Interne Hilfsgruppe nur einmal pro Build erzeugen (mehrfaches Neuanlegen würde Verweise brechen)."""
    g = bpy.data.node_groups.get(name)
    return g if g is not None else builder()


def group_node(ng, tree):
    n = node(ng, "ShaderNodeGroup")
    n.node_tree = tree
    return n


def evaluate(ng, closure, coord):
    """Wertet einen Sampler-Closure (Coord -> Color) an einer Koordinate aus und gibt den Color-Socket zurück."""
    e = node(ng, "NodeEvaluateClosure")
    e.input_items.new('VECTOR', 'Coord')
    e.output_items.new('RGBA', 'Result')
    link(ng, closure, e.inputs["Closure"])
    link(ng, coord, e.inputs["Coord"])
    return e.outputs["Result"]


def add_panel(ng, name):
    return ng.interface.new_panel(name, default_closed=False)


def socket(ng, name, kind, *, out=False, default=None, min=None, max=None,
           desc="", hide_value=False, panel=None):
    idname, subtype = _KINDS[kind]
    kw = {"parent": panel} if panel is not None else {}
    s = ng.interface.new_socket(name, description=desc, in_out='OUTPUT' if out else 'INPUT',
                                socket_type=idname, **kw)
    if subtype:
        s.subtype = subtype
    if default is not None:
        s.default_value = default
    if min is not None:
        s.min_value = min
    if max is not None:
        s.max_value = max
    if hide_value:
        s.hide_value = True
    return s


def node(ng, idname, label=None, **props):
    n = ng.nodes.new(idname)
    if label:
        n.label = label
    for k, v in props.items():
        setattr(n, k, v)
    return n


def sock(n, name, *, out=False, index=0):
    """Aktivierten Socket nach Name holen (index bei mehrfachen gleichen Namen, z. B. 'Vector')."""
    pool = n.outputs if out else n.inputs
    hits = [s for s in pool if s.name == name and s.enabled]
    if not hits:
        raise KeyError(f"{n.bl_idname} hat keinen aktiven Socket '{name}'")
    return hits[index]


def link(ng, src, dst):
    ng.links.new(src, dst)


def const(n, socket_obj, value):
    socket_obj.default_value = value


def math_node(ng, op, a=None, b=None, c=None, clamp=False):
    n = node(ng, "ShaderNodeMath", operation=op, use_clamp=clamp)
    for i, v in enumerate((a, b, c)):
        if v is None:
            continue
        if isinstance(v, bpy.types.NodeSocket):
            link(ng, v, n.inputs[i])
        else:
            n.inputs[i].default_value = v
    return n


def vmath(ng, op, a=None, b=None, scale=None):
    n = node(ng, "ShaderNodeVectorMath", operation=op)
    for i, v in ((0, a), (1, b)):
        if v is None:
            continue
        if isinstance(v, bpy.types.NodeSocket):
            link(ng, v, n.inputs[i])
        else:
            n.inputs[i].default_value = v
    if scale is not None:
        if isinstance(scale, bpy.types.NodeSocket):
            link(ng, scale, n.inputs[3])
        else:
            n.inputs[3].default_value = scale
    return n


def combine(ng, x=None, y=None, z=None):
    n = node(ng, "ShaderNodeCombineXYZ")
    for i, v in enumerate((x, y, z)):
        if v is None:
            continue
        if isinstance(v, bpy.types.NodeSocket):
            link(ng, v, n.inputs[i])
        else:
            n.inputs[i].default_value = v
    return n


def separate(ng, vec):
    n = node(ng, "ShaderNodeSeparateXYZ")
    link(ng, vec, n.inputs[0])
    return n


def mix(ng, data_type, fac, a, b):
    """Mix-Node: data_type 'FLOAT' oder 'VECTOR'; fac, a, b sind Sockets oder Konstanten."""
    n = node(ng, "ShaderNodeMix", data_type=data_type)
    for name, v in (("Factor", fac), ("A", a), ("B", b)):
        s = sock(n, name)
        if isinstance(v, bpy.types.NodeSocket):
            link(ng, v, s)
        else:
            s.default_value = v
    return n, sock(n, "Result", out=True)


def group_io(ng):
    gi = node(ng, "NodeGroupInput")
    go = node(ng, "NodeGroupOutput")
    return gi, go


def autolayout(ng):
    """Spaltenweises Layout nach Tiefe im Graph (Eingang links, Ausgang rechts)."""
    nodes = list(ng.nodes)
    depth = {n: 0 for n in nodes}
    for _ in range(len(nodes)):
        changed = False
        for l in ng.links:
            d = depth[l.from_node] + 1
            if d > depth[l.to_node]:
                depth[l.to_node] = d
                changed = True
        if not changed:
            break
    outs = [n for n in nodes if n.bl_idname == "NodeGroupOutput"]
    top = max(depth.values())
    for n in outs:
        depth[n] = top
    cols = {}
    for n in nodes:
        cols.setdefault(depth[n], []).append(n)
    for d, col in cols.items():
        y = 0
        for n in col:
            n.location = (d * 240, -y)
            y += (n.height if n.height > 0 else 140) + 40


def mark_asset(ng, description, tags, catalog_id=CATALOG_MAPPING):
    ng.asset_mark()
    ad = ng.asset_data
    ad.description = description
    ad.author = AUTHOR
    for t in tags:
        ad.tags.new(t, skip_if_exists=True)
    ad.catalog_id = catalog_id
    ng.use_fake_user = True


def open_or_new(path):
    if os.path.exists(path):
        bpy.ops.wm.open_mainfile(filepath=path)
    else:
        bpy.ops.wm.read_factory_settings(use_empty=True)
    clear_su_groups()


def save(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=path, compress=True)


def menu_switch(ng, data_type, menu_socket, items, default=None, fixed_menu=None):
    """Menu-Switch-Node (auch im Shader-Editor nutzbar). items: {Name: Wert}. Gibt den Output-Socket zurück.
    Ein Menü-Socket darf nur an EINEN Menu-Switch angeschlossen werden.
    menu_socket: Socket, der das Menü liefert; fixed_menu: stattdessen feste Auswahl (nur für Tests)."""
    ms = ng.nodes.new("GeometryNodeMenuSwitch")
    ms.data_type = data_type
    for nm in [i.name for i in ms.enum_items]:
        ms.enum_items.remove(ms.enum_items[nm])
    for name in items:
        ms.enum_items.new(name)
    if fixed_menu is not None:
        ms.inputs["Menu"].default_value = fixed_menu
    else:
        ng.links.new(menu_socket, ms.inputs["Menu"])
    for name, value in items.items():
        ms.inputs[name].default_value = value
    return ms.outputs["Output"]
