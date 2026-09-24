import json
import os
import re
import subprocess
import tempfile

import bpy
from bpy.props import BoolProperty, EnumProperty, StringProperty
from bpy.types import AddonPreferences, Operator

ADDON_DIR = os.path.dirname(__file__)
WARN_SIZE = 50 * 1024 * 1024
MAX_SIZE = 100 * 1024 * 1024

# ID-Typ -> Name der Collection in bpy.data
ID_COLLECTIONS = {
    'MATERIAL': 'materials',
    'OBJECT': 'objects',
    'COLLECTION': 'collections',
    'NODETREE': 'node_groups',
    'WORLD': 'worlds',
    'ACTION': 'actions',
    'BRUSH': 'brushes',
    'IMAGE': 'images',
    'MESH': 'meshes',
    'LIGHT': 'lights',
    'CAMERA': 'cameras',
}
COLLECTION_BY_NAME = {v: v for v in ID_COLLECTIONS.values()}


def _prefs(context):
    return context.preferences.addons[__package__].preferences


def _library_dir(context):
    repo = bpy.path.abspath(_prefs(context).repo_path)
    return os.path.join(repo, "library")


def _run(cmd, cwd=None):
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd[:3])} ... fehlgeschlagen:\n{proc.stderr or proc.stdout}")
    return proc.stdout


def _safe_name(name):
    return re.sub(r"[^\w\- ]", "_", name).strip() or "assets"


# ---------------------------------------------------------------- Kataloge

def _find_catalog_file(start_dir):
    d = start_dir
    while d:
        candidate = os.path.join(d, "blender_assets.cats.txt")
        if os.path.isfile(candidate):
            return candidate
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return None


def _parse_catalogs(path):
    cats = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("VERSION"):
                continue
            parts = line.split(":", 2)
            if len(parts) == 3:
                cats[parts[0]] = (parts[1], parts[2])
    return cats


def _merge_catalogs(assets, library_dir):
    """Übernimmt Katalog-Definitionen der Assets in die Library, damit die Sortierung erhalten bleibt."""
    if not bpy.data.filepath:
        return 0
    src = _find_catalog_file(os.path.dirname(bpy.data.filepath))
    if src is None:
        return 0
    source_cats = _parse_catalogs(src)
    dest = os.path.join(library_dir, "blender_assets.cats.txt")
    dest_cats = _parse_catalogs(dest) if os.path.isfile(dest) else {}
    added = []
    for a in assets:
        uid = str(a.asset_data.catalog_id)
        if uid in source_cats and uid not in dest_cats:
            dest_cats[uid] = source_cats[uid]
            added.append(uid)
    if not added:
        return 0
    with open(dest, "w", encoding="utf-8") as f:
        f.write("# This is an Asset Catalog Definition file for Blender.\n#\n"
                "# Empty lines and lines starting with `#` will be ignored.\n"
                "# The first non-ignored line should be the version indicator.\n"
                "# Other lines are of the format \"UUID:catalog/path/for/assets:simple catalog name\"\n\n"
                "VERSION 1\n\n")
        for uid, (path, simple) in sorted(dest_cats.items(), key=lambda kv: kv[1][0]):
            f.write(f"{uid}:{path}:{simple}\n")
    return len(added)


# ---------------------------------------------------------------- Enums

_cat_cache = []
_file_cache = []


def _category_items(self, context):
    global _cat_cache
    items = []
    lib = _library_dir(context)
    if os.path.isdir(lib):
        for name in sorted(os.listdir(lib)):
            if os.path.isdir(os.path.join(lib, name)) and not name.startswith(("_", ".")):
                items.append((name, name, ""))
    if not items:
        items = [("", "(keine Kategorie)", "")]
    _cat_cache = items
    return _cat_cache


def _file_items(self, context):
    global _file_cache
    items = []
    cat = self.new_category.strip() or self.category
    base = os.path.join(_library_dir(context), cat)
    if cat and os.path.isdir(base):
        for root, _dirs, files in os.walk(base):
            for fn in sorted(files):
                if fn.endswith(".blend"):
                    rel = os.path.relpath(os.path.join(root, fn), base)
                    items.append((rel, rel, ""))
    if not items:
        items = [("", "(keine Dateien)", "")]
    _file_cache = items
    return _file_cache


# ---------------------------------------------------------------- Assets sammeln

def _collect_assets(context, scope):
    found = []
    if scope == 'SELECTED':
        for a in getattr(context, "selected_assets", None) or []:
            idb = getattr(a, "local_id", None)
            if idb is not None:
                found.append(idb)
    else:
        for coll in ID_COLLECTIONS.values():
            for idb in getattr(bpy.data, coll):
                if idb.asset_data is not None:
                    found.append(idb)
    return found


# ---------------------------------------------------------------- Operator

class ASSETPUB_OT_publish(Operator):
    bl_idname = "asset_publisher.publish"
    bl_label = "Publish to Online Library"
    bl_description = "Assets in die lokale Library schreiben, Listing erzeugen und nach Git pushen"

    scope: EnumProperty(
        name="Assets",
        items=[('SELECTED', "Ausgewählte (Asset Browser)", ""),
               ('ALL', "Alle markierten Assets dieser Datei", "")],
        default='SELECTED')
    category: EnumProperty(name="Kategorie", items=_category_items)
    new_category: StringProperty(name="Neue Kategorie", description="Leer lassen, um die Auswahl oben zu nutzen")
    target_mode: EnumProperty(
        name="Zieldatei",
        items=[('NEW', "Neue Datei", ""), ('EXISTING', "In bestehende Datei", "")],
        default='NEW')
    new_filename: StringProperty(name="Dateiname", default="assets")
    existing_file: EnumProperty(name="Datei", items=_file_items)
    overwrite: BoolProperty(name="Gleichnamige Assets ersetzen", default=True)
    push: BoolProperty(name="Nach Git pushen", default=True)

    def invoke(self, context, event):
        if not _prefs(context).repo_path:
            self.report({'ERROR'}, "Repo-Pfad in den Add-on-Einstellungen setzen")
            return {'CANCELLED'}
        if not os.path.isdir(_library_dir(context)):
            self.report({'ERROR'}, f"Ordner nicht gefunden: {_library_dir(context)}")
            return {'CANCELLED'}
        if not _collect_assets(context, self.scope):
            self.scope = 'ALL'
        if _file_items(self, context)[0][0] == "":
            self.target_mode = 'NEW'
        return context.window_manager.invoke_props_dialog(self, width=440)

    def draw(self, context):
        col = self.layout.column()
        col.prop(self, "scope")
        col.separator()
        col.prop(self, "category")
        col.prop(self, "new_category")
        col.prop(self, "target_mode", expand=True)
        if self.target_mode == 'EXISTING':
            col.prop(self, "existing_file")
        else:
            col.prop(self, "new_filename")
        col.prop(self, "overwrite")
        col.prop(self, "push")

    def execute(self, context):
        prefs = _prefs(context)
        repo = bpy.path.abspath(prefs.repo_path)
        lib = _library_dir(context)
        git = prefs.git_exe or "git"

        assets = _collect_assets(context, self.scope)
        if not assets:
            self.report({'ERROR'}, "Keine Assets gefunden (im Asset Browser auswählen oder Assets markieren)")
            return {'CANCELLED'}

        cat = _safe_name(self.new_category) if self.new_category.strip() else self.category
        if not cat:
            self.report({'ERROR'}, "Keine Kategorie gewählt")
            return {'CANCELLED'}
        if self.target_mode == 'EXISTING' and self.existing_file:
            target = os.path.join(lib, cat, self.existing_file)
        else:
            target = os.path.join(lib, cat, _safe_name(self.new_filename) + ".blend")

        items = []
        for a in assets:
            coll = ID_COLLECTIONS.get(a.id_type)
            if coll is None:
                self.report({'WARNING'}, f"Typ {a.id_type} ({a.name}) wird nicht unterstützt")
                continue
            items.append({"coll": coll, "name": a.name})
        ids = {a for a in assets if a.id_type in ID_COLLECTIONS}
        if not ids:
            return {'CANCELLED'}

        context.window.cursor_set('WAIT')
        try:
            if self.push:
                try:
                    _run([git, "pull", "--rebase", "--autostash"], cwd=repo)
                except RuntimeError as e:
                    self.report({'WARNING'}, f"git pull fehlgeschlagen, mache trotzdem weiter: {e}")

            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_blend = os.path.join(tmpdir, "assets.blend")
                bpy.data.libraries.write(tmp_blend, ids, path_remap='ABSOLUTE', compress=True)
                spec_path = os.path.join(tmpdir, "spec.json")
                with open(spec_path, "w", encoding="utf-8") as f:
                    json.dump({"tmp": tmp_blend, "target": target, "items": items,
                               "overwrite": self.overwrite}, f)
                cmd = [prefs.blender_exe or bpy.app.binary_path, "-b", "--factory-startup"]
                if os.path.exists(target):
                    cmd.append(target)
                cmd += ["--python-exit-code", "1", "--python", os.path.join(ADDON_DIR, "worker.py"),
                        "--", spec_path]
                out = _run(cmd)

            size = os.path.getsize(target)
            if size > MAX_SIZE:
                self.report({'ERROR'}, f"{os.path.basename(target)} ist {size // 2**20} MB, GitHub erlaubt max. 100 MB. Nicht gepusht.")
                return {'CANCELLED'}
            if size > WARN_SIZE:
                self.report({'WARNING'}, f"{os.path.basename(target)} ist {size // 2**20} MB (GitHub warnt ab 50 MB)")

            new_cats = _merge_catalogs([a for a in assets if a.id_type in ID_COLLECTIONS], lib)

            _run([prefs.blender_exe or bpy.app.binary_path, "-b", "--factory-startup",
                  "-c", "asset_listing", "generate", lib])

            skipped = re.search(r"ASSETPUB_SKIPPED:(\[.*\])", out)
            skipped = json.loads(skipped.group(1)) if skipped else []

            if self.push:
                _run([git, "add", "-A"], cwd=repo)
                names = ", ".join(i["name"] for i in items[:3]) + ("..." if len(items) > 3 else "")
                proc = subprocess.run([git, "commit", "-m", f"Publish {names}"], cwd=repo,
                                      capture_output=True, text=True)
                if proc.returncode not in (0, 1):
                    raise RuntimeError(proc.stderr or proc.stdout)
                _run([git, "push"], cwd=repo)
        except Exception as e:
            self.report({'ERROR'}, str(e)[:800])
            return {'CANCELLED'}
        finally:
            context.window.cursor_set('DEFAULT')

        msg = f"{len(items) - len(skipped)} Asset(s) nach {cat}/{os.path.basename(target)} geschrieben"
        if new_cats:
            msg += f", {new_cats} Katalog(e) übernommen"
        if skipped:
            msg += f", übersprungen (existieren schon): {', '.join(skipped)}"
        msg += ", gepusht" if self.push else ", nicht gepusht"
        self.report({'INFO'}, msg)
        return {'FINISHED'}


class ASSETPUB_Preferences(AddonPreferences):
    bl_idname = __package__

    repo_path: StringProperty(
        name="Library-Repo", subtype='DIR_PATH',
        description="Lokaler Klon des Git-Repos (enthält den Ordner 'library')")
    git_exe: StringProperty(name="Git", default="git")
    blender_exe: StringProperty(
        name="Blender (Listing)", subtype='FILE_PATH',
        description="Leer = aktuell laufendes Blender (muss 5.2+ sein)")

    def draw(self, context):
        col = self.layout.column()
        col.prop(self, "repo_path")
        col.prop(self, "git_exe")
        col.prop(self, "blender_exe")


def _menu_func(self, context):
    self.layout.operator(ASSETPUB_OT_publish.bl_idname, icon='EXPORT')


_classes = (ASSETPUB_OT_publish, ASSETPUB_Preferences)
_menus = ("TOPBAR_MT_file", "ASSETBROWSER_MT_context_menu")


def register():
    for c in _classes:
        bpy.utils.register_class(c)
    for m in _menus:
        t = getattr(bpy.types, m, None)
        if t is not None:
            t.append(_menu_func)


def unregister():
    for m in _menus:
        t = getattr(bpy.types, m, None)
        if t is not None:
            t.remove(_menu_func)
    for c in reversed(_classes):
        bpy.utils.unregister_class(c)
