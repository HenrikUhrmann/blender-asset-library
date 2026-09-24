# Blender Online Asset Library

Persönliche Remote Asset Library für Blender 5.2+, gehostet über GitHub Pages.

## In Blender einbinden
`Edit > Preferences > File Paths > Asset Libraries > +  > Remote Library`
und diese URL eintragen:

    https://HenrikUhrmann.github.io/blender-asset-library/

(Falls Blender nach der Datei fragt: `_asset-library-meta.json` liegt im Root dieser URL.)

## Assets hinzufügen
1. Asset in Blender markieren (Rechtsklick > Mark as Asset), Katalog zuweisen.
2. Die .blend muss **selbstständig** sein: keine Links auf andere Dateien, Texturen packen
   (`File > External Data > Pack Resources`), Datei ohne Fake-Referenzen speichern.
3. Datei nach `library/<Kategorie>/` legen (z. B. `library/Materials/`).
4. Veröffentlichen:

       BLENDER=/pfad/zu/blender ./publish.sh "Added <Asset>"

   (`BLENDER` weglassen, wenn `blender` im PATH liegt.) Das Skript erzeugt Index,
   Vorschaubilder und Hashes (`blender -c asset_listing generate library`), committet und pusht.
   GitHub Pages veröffentlicht nach ca. 1 Minute.

Neue Kataloge in `library/blender_assets.cats.txt` eintragen (`UUID:Pfad:Name`).

## Limits (GitHub Free)
- Veröffentlichte Seite: max. 1 GB, einzelne Datei max. 100 MB (Warnung ab 50 MB)
- Bandbreite: ca. 100 GB/Monat (Soft-Limit)
- **Kein Git LFS** verwenden, Pages liefert LFS-Dateien nicht aus.
- Repo und Pages sind **öffentlich**: Blender unterstützt (noch) keine Authentifizierung.
  Keine privaten oder Firmen-Assets hier ablegen.
