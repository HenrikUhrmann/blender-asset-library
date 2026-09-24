# Plan: Shader Utilities, Gruppe 1 "Mapping & Koordinaten"

Status: **Plan; Phase 0 ist gelaufen (Ergebnisse in Abschnitt 8), gebaut ist noch nichts.**

## 0. Ziel und Festlegungen

- 7 Node-Groups, als Assets veröffentlicht in `library/Node-Groups/Mapping Utils.blend`
  (eine Datei, gleichnamige Assets werden beim Neubau ersetzt).
- Katalog `Node-Groups/Mapping` (neue UUID in `library/blender_assets.cats.txt`).
- Namen mit Präfix `SU ` (Shader Utility), z. B. `SU Triplanar Image`. Tags: `mapping`, `utility`, plus Typ.
- Erzeugung **per Python-Skript** (reproduzierbar, versionierbar), nicht von Hand.
- Alle Gruppen selbstständig: keine externen Bilder, nichts verlinkt.
- Einheitliche Schnittstelle:
  - Eingang `Vector` (ausgeblendeter Wert), Ausgang `Vector` bzw. `Color`/`Alpha`.
  - Sockets in Panels gruppiert (`interface.new_panel`), jeder Socket mit Tooltip (`description`).
  - Winkel als Winkel-Sockets (`NodeSocketFloatAngle`), Maße in Metern, Faktoren mit min/max.
  - Deterministisch: gleicher `Seed` und gleiche Koordinaten ergeben gleiche Zufallswerte. So
    laufen mehrere Maps (Color, Roughness, Normal) im Anti-Tiling synchron.

### Wichtigstes Designproblem: Bilder in Gruppen
Triplanar, Anti-Tiling, Hex-Tiling und Parallax müssen selbst ein Bild abtasten (mehrere
Abtastungen an verschobenen Koordinaten). Optionen:
- **A)** Gruppe enthält einen Image-Texture-Node, das Bild wird pro Verwendung in der Gruppe gesetzt
  (Gruppe "Make Single User"). Funktioniert sicher, ist umständlich.
- **B)** Gruppe hat einen `Image`-Eingang (`NodeSocketImage`). Sauber, **falls Shader-Groups das in 5.2 unterstützen** (Phase 0).
- Fallback ohne Bildzugriff: Koordinaten-Gruppen (`UV Pivot`, `Polar`, `World Coords`) liefern nur Vektoren.

Entscheidung: B, wenn Phase 0 es bestätigt, sonst A mit klarer Beschreibung im Asset.

## 1. Phase 0: Verifikation (vor dem Bauen, ein Skript, ca. 30 Min)

`blender -b --factory-startup --python tools/nodes/spike.py` prüft und druckt:
1. Gibt es in Shader-Node-Trees `NodeSocketImage` im Interface, und lässt sich ein Image-Texture-Node damit versorgen?
2. Existiert `ShaderNodeVectorRotate` (mit `Center`), `ShaderNodeVectorMath` mit `WRAP`, `FLOOR`, `FRACTION`, `ShaderNodeTexWhiteNoise` mit 2D/3D?
3. Richtung von `Geometry > Incoming` (zur Kamera oder von ihr weg?) und Verhalten des `Tangent`-Nodes: `uv_map` als Node-Property, kann man sie nach außen geben? (Wenn nein: pro Gruppe in der Beschreibung dokumentieren.)
4. Bekommt ein per Skript erzeugtes Node-Group-Asset eine Vorschau (`preview_ensure`) und akzeptiert der Listing-Generator (`asset_listing generate`) Assets ohne Vorschau?
5. Werden Panels, Bool-Sockets und `default_value`-Grenzen (`min_value`/`max_value`) wie erwartet gespeichert?

Ergebnis fließt in die Schnittstellen unten ein. Ändert sich etwas, wird dieses Dokument angepasst.

## 2. Hilfsbibliothek `tools/nodes/lib.py`

- `new_group(name)` erstellt/ersetzt Gruppe; `iface(group, ...)` legt Sockets/Panels an.
- `add(tree, "ShaderNodeMath", op="MULTIPLY", inputs={...}, loc=...)` und `link(a_socket, b_socket)`.
- `math`/`vmath`-Kurzformen, automatisches Layout (Spalten nach Tiefe), Frames mit Labels.
- `mark_asset(group, catalog_id, tags, description, author, license="CC0")`.
- `save_into(blend_path)`: Datei öffnen (falls vorhanden), Gruppen ersetzen, speichern (wie das Add-on).
- Aufruf: `blender -b --factory-startup --python tools/nodes/build_all.py -- "library/Node-Groups/Mapping Utils.blend"`.

## 3. Die 7 Gruppen (Reihenfolge = Bauordnung)

### 3.1 `SU UV Pivot Transform`  (Aufwand: klein)
Skalieren, Drehen, Verschieben um einen frei wählbaren Pivot, plus Spiegeln.
- In: `Vector`, `Pivot` (Vektor, Standard 0.5/0.5/0), `Scale` (Vektor, 1), `Rotation` (Winkel), `Offset` (Vektor), `Mirror X` (Bool), `Mirror Y` (Bool)
- Out: `Vector`
- Aufbau: `Vector - Pivot` → Mirror per `Multiply` mit ±1 (aus Bool per `Math`) → `Multiply Scale` (Tiling-Semantik wie Mapping-Node: Scale 2 = doppelt so viele Kacheln) → `Vector Rotate` (Z, Winkel) → `+ Pivot` → `- Offset`.
- Reihenfolge fest dokumentieren: Spiegeln, Skalieren, Drehen, Verschieben.
- Test: UV-Grid-Bild, Rotation 90° um Mitte muss deckungsgleich zur Drehung sein.

### 3.2 `SU Polar Mapping`  (klein)
Kartesisch → Polar (für Kreis, Radial-Bürste, Zifferblatt, Strudel).
- In: `Vector`, `Center` (0.5/0.5/0), `Angle Offset` (Winkel), `Angular Repeat` (Ganzzahl ≥ 1, 1), `Radial Scale` (1), `Mirror Angle` (Bool)
- Out: `Vector` (U = Winkel-Fraktion × Repeat, V = Radius × Radial Scale), `Angle` (0..1), `Radius`
- Aufbau: `Vector - Center` → `Separate XYZ` → `Arctan2(y, x)` + Offset → `/ 2π`, `Wrap 0..1` → × Repeat; `Length` → × Radial Scale; bei Mirror `abs(angle-0.5)*2`.
- Bekannte Grenze: Naht bei 0/1 (Mip-Sprung in EEVEE), Abhilfe: ganzzahliger Repeat, in der Beschreibung erwähnen.

### 3.3 `SU World Coords`  (klein)
Textur-Koordinaten in Metern, unabhängig vom Objekt-UV.
- In: `Tile Size` (m pro Kachel, 1.0), `Mode` (Ganzzahl 0..2 mit Tooltip), `Offset` (Vektor)
- Modi: 0 = **World** (`Geometry > Position`), 1 = **Object anchored** (World − `Object Info > Location`, folgt Verschieben, ignoriert Skalierung), 2 = **Object scaled** (`Texture Coordinate > Object` × Objekt-Skalierung; `Object Info` hat in 5.2 keinen Scale-Ausgang, daher Länge der per `Vector Transform` in die Welt gebrachten Achsenvektoren, folgt Verschieben und Skalierung, Kacheln bleiben in Metern)
- Out: `Vector` (durch `Tile Size` geteilt, + Offset), `Vector X/Y/Z` planare Varianten (Y/Z, X/Z, X/Y) für Projektionen
- Modus-Wahl: Mix-Nodes mit Vergleichs-Math (`Compare`), Menu-Sockets nur, wenn Phase 0 sie für Shader bestätigt.

### 3.3b (intern) `SU _Triplanar Weights`  (klein, wird von 3.4 genutzt)
- In: `Normal` (Welt), `Blend` (0..1, 0.2), `Sharpness` optional
- Out: `Weights` (Vektor XYZ, Summe 1)
- Aufbau: `abs(Normal)` → `Power` mit `1/max(Blend, 0.001)` → durch Summe teilen.
- Gruppen mit `_` gelten als intern und bekommen kein Asset-Flag, werden aber in die Datei mitgeschrieben.

### 3.4 `SU Triplanar Image` und `SU Triplanar Normal`  (mittel)
Triplanar-Projektion mit sauberer Überblendung. Blenders eigenes Box-Mapping im Image-Node genügt für Farbe, ist aber für Normal Maps falsch und nicht mit Koordinaten aus 3.3 kombinierbar.
- **Image**: In: `Image`, `Vector` (Standard: World-Koordinaten aus 3.3), `Scale` (m), `Blend`, `Rotation` (Winkel), `Interpolation` (Linear/Closest über Node-Property, Standard Linear)
  Out: `Color`, `Alpha`
  - Aufbau: 3 planare Koordinatenpaare (YZ, XZ, XY), 3 × Image-Texture, gewichtet summiert (Weights aus 3.3b). Negative Seiten spiegeln nicht (Bild bleibt lesbar), ist per `Sign` abschaltbar.
- **Normal**: In: `Image` (Normal Map, Non-Color), `Vector`, `Scale`, `Blend`, `Strength`, `Flip Green` (Bool)
  Out: `Normal` (Weltraum-Vektor, direkt an Principled `Normal` anschließbar)
  - Aufbau: "Whiteout"-Überblendung (Golus): pro Achse Tangent-Normale auslesen (`*2-1`), mit Welt-Normale kombinieren, Achsen zurücksortieren, gewichtet mischen, normalisieren. Stärke per Lerp zur Welt-Normale.
- Test: Würfel und Kugel mit UV-Grid; Naht-Sichtbarkeit bei Blend 0/0.2/1; Normal-Map-Ergebnis mit eingebautem Box-Node vergleichen (Beleuchtungsrichtung prüfen).

### 3.5 `SU Anti-Tile Bombing`  (mittel bis groß)
Kachelmuster brechen: Zufalls-Offset, Rotation und Spiegelung pro Zelle, weich überblendet.
- In: `Image`, `Vector`, `Scale` (Kacheln pro Einheit), `Randomness` (0..1, 1), `Rotation Amount` (0..1 → bis 360°), `Mirror Chance` (0..1), `Blend Softness` (0..1, 0.25), `Contrast Preserve` (0..1, 0.5), `Mean Color` (Farbe, 0.5 grau; Mittelwert des Bildes), `Seed` (Ganzzahl)
- Out: `Color`, `Alpha`, `Cell ID` (Zufallswert pro Zelle, z. B. zum Färben)
- Verfahren (Iñigo-Quílez-Prinzip, 4 Nachbarzellen): `p = Vector × Scale`, `i = floor(p)`, `f = fract(p)`. Für jede der 4 Ecken: Zelle `i + c`, Hash über `White Noise` (2D, `Seed` als zusätzliche Komponente) liefert Offset, Winkel, Spiegel-Flag; Koordinate verschieben/drehen/spiegeln → Image abtasten. Gewicht = Produkt der geglätteten (smoothstep, Breite = `Blend Softness`) Achsenanteile.
- Kontrast: Mischen mittelt und macht flau; Korrektur `(Mix − Mean) / sqrt(Σw²) × k + Mean`, mit `k` über `Contrast Preserve`.
- Für Normal Maps: `Rotation Amount` 0 lassen oder Normal-XY mitdrehen (eigene Option `Normal Map Mode`, zweiter Ausgang `Normal Fixed`).
- Bekannte Grenzen: 4 Abtastungen pro Aufruf (Performance), Mip-Nähte in EEVEE an Zellgrenzen (Cycles filtert nicht, dort kein Problem). In der Beschreibung erwähnen.
- Test: Gras-/Stein-Textur in Groß, Wiederholungsmuster vorher/nachher; Color und Roughness mit gleichem `Seed` müssen deckungsgleich sein.

### 3.6 `SU Hex Tiling`  (groß)
Kachelfrei nach Mikkelsen, "Practical Real-Time Hex-Tiling" (JCGT 2022). Drei Abtastungen statt vier, ruhigeres Ergebnis als Bombing.
- In: `Image`, `Vector`, `Scale`, `Rotation` (Winkel-Streuung), `Contrast` (Exponent für die Gewichte, 0.5..8), `Seed`, `Mean Color`
- Out: `Color`, `Alpha`
- Verfahren: Koordinaten auf das Dreiecksgitter verzerren (Konstanten aus der Referenzimplementierung übernehmen, hier nicht aus dem Kopf festlegen), Zelle und Fraktion bestimmen, die 3 Ecken bestimmen (Dreieck oben/unten), pro Ecke Hash → Offset und Rotation, 3 × Image abtasten, Gewichte = Barycentric^Contrast, normalisieren, Varianz-Korrektur wie in 3.5.
- Die Histogramm-erhaltende Variante (Gauß-Transformation mit Lookup) ist optional und **nicht** Teil von V1.
- Intern eigene Gruppe `SU _Hex Grid` (liefert 3 Offsets, 3 Winkel, 3 Gewichte); der Sampler ist dünn.
- Test: gleiche Testtextur wie 3.5, Vergleich beider Methoden, Gewichtssumme muss überall 1 sein (Debug-Ausgang `Weights`).

### 3.7 `SU Parallax Occlusion`  (groß, zuletzt)
Scheinbare Tiefe ohne Displacement (vor allem für EEVEE).
- In: `Height` (Bild, Non-Color), `Vector` (UV), `Depth` (m oder relativ, 0.05), `Center` (0..1, Bezugshöhe, 0.5), `Invert Height` (Bool), `UV Map` (Text, falls Phase 0 nur per Node-Property; sonst Beschreibung)
- Out: `Vector` (verschobene UV für alle weiteren Maps), `Depth Sampled` (Höhe am Treffer)
- Verfahren: Tangenten-Basis aus `Tangent` und `Normal` (Bitangente = Kreuzprodukt), Blickvektor im Tangentenraum, Schrittweite = `xy / z × Depth`. **Fest ausgerollte Schleife** (Shader-Nodes haben keine Repeat-Zone): N Höhen-Abtastungen, ab dem ersten Schritt, an dem die Schicht unter der Höhe liegt, wird gestoppt (`Compare`/`Mix` mit Merker), Endposition per linearer Interpolation der beiden letzten Schritte.
- Varianten per Skript-Parameter erzeugt: `SU Parallax Occlusion 8` / `16` (Standard) / `32` (sehr viele Nodes, nur bei Bedarf).
- Grenzen: Silhouetten ändern sich nicht, an steilen Winkeln entstehen Artefakte; in Cycles ist echtes Displacement besser. Vorzeichen des Blickvektors und Bitangenten-Flip in Phase 0 klären.
- Test: Ziegel-Height auf Plane, Kamera flach und steil, mit Referenz-Displacement vergleichen.

## 4. Testumgebung `tools/nodes/tests/test_scene.py`
- Erzeugt Ebene, Würfel und Kugel, `UV_GRID`-Testbild (`bpy.ops.image.new(generated_type='UV_GRID')`) und eine Kachel-Testtextur (Prozedural in ein Bild gebacken), setzt pro Gruppe ein Material mit Beispielverwendung.
- Rendert kleine Bilder (Cycles, 64 Samples, 256²) nach `tools/nodes/tests/out/`, damit wir vorher/nachher sehen. Ausgabe wird **nicht** ins Repo gepusht (`.gitignore`).
- Automatische Sanity-Checks im Skript: Gruppe lädt ohne Fehler, keine ungültigen Links, Gewichtssummen ≈ 1.

## 5. Veröffentlichung
1. `build_all.py` baut die Gruppen und schreibt `library/Node-Groups/Mapping Utils.blend` (gleichnamige Gruppen werden ersetzt).
2. Katalog-UUID in `blender_assets.cats.txt` ergänzen.
3. `blender -b --factory-startup -c asset_listing generate library`, dann committen und pushen (oder über das Add-on).
4. Pro Gruppe eine Doku-Seite in `docs/shader-utils/` (Zweck, Eingänge, Beispiel-Verkabelung als Bild, Grenzen).

## 6. Reihenfolge und Aufwand
1. Phase 0 (Spike-Skript) und `lib.py`
2. `UV Pivot Transform`, `Polar Mapping`, `World Coords`
3. `Triplanar` (Weights, Image, Normal)
4. `Anti-Tile Bombing`
5. `Hex Tiling`
6. `Parallax Occlusion`

Nach jedem Schritt: Test-Render ansehen, du gibst frei, dann publish. Bei Schritt 4 bis 6 sollten wir
uns Zeit für Rückmeldungen nehmen, weil Look und Performance subjektiv sind.

## 7. Entscheidungen (vom Nutzer bestätigt)
- **Cycles hat Priorität**, EEVEE muss ebenfalls funktionieren. Folgen: Cycles filtert Texturen ohne Mipmaps,
  die Mip-Nähte bei Bombing/Polar sind dort kein Thema. Bei Konflikten zählt das Cycles-Ergebnis.
  Parallax Occlusion ist damit nachrangig (Cycles hat echtes Displacement) und wird als letztes gebaut.
- **Eine gemeinsame Datei** `Mapping Utils.blend` für alle Gruppen.
- **Bild-Eingang:** Variante B, wenn Phase 0 sie bestätigt. Sonst Variante A (Bild in der Gruppe setzen,
  Gruppe zur Einzelkopie machen); dann melde ich mich, bevor ich baue.

## 8. Phase 0: Ergebnisse (Blender 5.2.0 LTS, `tools/nodes/spike.py`)

| Frage | Ergebnis | Folge für den Plan |
|---|---|---|
| Bild-Socket (`NodeSocketImage`) in Shader-Groups | **Nein.** Erlaubt: Float, Int, Bool, Vector, Color, Menu, Shader, Bundle, Closure | **Closure als Ersatz** (siehe Abschnitt 10): Sampler-Closure statt Bild-Eingang |
| Winkel-Socket | Ja, als `NodeSocketFloat` mit `subtype='ANGLE'` | wie geplant |
| String-Socket | Nein | `UV Map` im Parallax nicht als Eingang; Tangent-Node hat `uv_map` nur als Node-Property (Standard leer, Typen `RADIAL`/`UV_MAP`), also pro Gruppe dokumentieren |
| Menu-Socket / Menu-Switch-Node | Socket ja, **Node `ShaderNodeMenuSwitch` nein** | `Mode` in World Coords als Int (0..2) mit Vergleichs-Math |
| Panels, Bool, min/max/default/description, hide_value | funktionieren | wie geplant |
| Nodes: Vector Rotate, Vector Math, Math, White Noise (1D bis 4D), Tangent, Geometry, Object Info, Texture Coordinate, Separate/Combine XYZ, Mix, Map Range, Normal Map, Bump, Image Texture | alle vorhanden | wie geplant |
| Vector-Math-Operationen `WRAP`, `FLOOR`, `FRACTION`, `NORMALIZE`, `CROSS_PRODUCT`, `DOT_PRODUCT`, `LENGTH`, `SCALE`, `REFLECT` | vorhanden | wie geplant |
| Math-Operationen `ARCTAN2`, `COMPARE`, `WRAP`, `FRACT`, `POWER`, `PINGPONG`, `SIGN` | vorhanden; **`SMOOTHSTEP` fehlt** | Smoothstep über `Map Range` (Typ `SMOOTHSTEP`/`SMOOTHERSTEP`) |
| Geometry-Ausgänge | Position, Normal, Tangent, True Normal, Incoming, Parametric, Backfacing, Pointiness, Random Per Island | `Tangent` und `Incoming` direkt nutzbar |
| Bild-Interpolation | Linear, Closest, Cubic, Smart | `Interpolation` als Node-Property, nicht als Socket |
| Asset ohne Vorschau ins Listing | **Ja**, der Generator läuft durch; der Eintrag hat dann kein `thumbnail` | Vorschauen optional, später eigene Icons erzeugen |
| `asset_generate_preview()` im Hintergrund | läuft ohne Fehler, Vorschaugröße danach unbekannt | nicht darauf verlassen |

Noch offen (erst beim Bauen prüfbar, weil es Rendern braucht): Richtung von `Geometry > Incoming` und
Vorzeichen der Bitangente (nur für Parallax relevant, kommt zuletzt).

## 9. Baufortschritt
- [x] `lib.py`, `build_all.py`, `tests/verify.py` (rendert in Cycles bekannte Eingaben und vergleicht Pixelwerte mit der Mathematik)
- [x] `SU UV Pivot Transform` (7 Prüfungen ok), `SU Polar Mapping` (8 ok), `SU World Coords` (8 ok)
- [x] Triplanar, Anti-Tile Bombing (Closure-Umbau, siehe unten)
- [ ] Hex Tiling, Parallax
- Gebaut nach `library/Node-Groups/Mapping Utils.blend`, **noch nicht committet/gepusht**.

### Schritt 3 (Triplanar), erste Fassung, ERSETZT durch den Closure-Umbau unten
Mit Variante A bräuchte eine fertige Triplanar-Gruppe drei Image-Nodes (je Achse), und das Bild müsste dreimal
gesetzt werden. Deshalb drei kleine Gruppen; dazwischen setzt der Nutzer drei Image-Nodes (einer, dann Shift+D):
- `SU Triplanar Coords`: `Vector X/Y/Z` (Ebenenkoordinaten je Achse, Rückseiten korrekt entspiegelt) und `Weights`;
  Eingänge `Vector`, `Scale`, `Rotation`, `Blend`, `Object Space`
- `SU Triplanar Blend`: `Color X/Y/Z` + `Weights` → `Color`
- `SU Triplanar Normal Blend`: `Normal X/Y/Z` (Farben der Normal-Map-Abtastungen) + `Weights`, `Strength`, `Rotation`,
  `Flip Green`, `Object Space` → `Normal` (Weltraum, direkt an Principled `Normal`)
- Konvention (rechtshändig): Projektion entlang A nutzt (a, b) mit a×b = +A: X: (y, z), Y: (z, x), Z: (x, y);
  u wird gespiegelt, wenn die Normale entlang A negativ ist. Whiteout im Ebenenrahmen (T' = s·e_a, B = e_b, N' = s·e_A).
- Für reine Farbe reicht oft auch der Image-Node mit Projektion `Box` (ein Node), die Gruppen lohnen sich für Normal Maps,
  Weltkoordinaten und mehrere Maps mit identischen Koordinaten.
- Prüfung: 41 Renders in `verify.py` (Koordinaten und Gewichte in 5 Orientierungen, Blend, flache Normal-Map ergibt die
  Oberflächennormale, geneigte Map mit Rotation/Flip/Strength analytisch). Die analytische Erwartung leite ich aus derselben
  Herleitung ab; ein Sichttest mit echtem Normal-Map-Bild steht noch aus.

### Schritt 4 (Anti-Tile Bombing), erste Fassung, ERSETZT durch den Closure-Umbau unten
- `SU Anti-Tile Coords`: `Vector 1..4` (je Nachbarzelle), `Weight 1..4`, `Cell ID`.
  Eingänge: `Vector`, `Scale`, `Randomness`, `Rotation Amount`, `Mirror Chance`, `Blend Softness`, `Seed`.
  Vier Image-Nodes dahinter (einen anlegen, dreimal Shift+D), jeder mit demselben Bild.
- `SU Anti-Tile Blend`: `Color 1..4`, `Weight 1..4`, `Contrast Preserve` (Standard 0), `Mean Color` → `Color`.
- Hash je Zelle: White Noise 4D (Zelle, Seed) liefert Offset, Winkel und Spiegel-Flag; gleicher `Seed` gibt bei allen Maps die
  gleiche Verteilung. Jede Zelle bekommt bei allen vier Nachbarn denselben Wert (geprüft).
- **Normal Maps:** `Rotation Amount` und `Mirror Chance` auf 0 lassen (nur Offset). Drehung mit Normalen-Korrektur ist nicht gebaut.
- **Kontrasterhalt** (Varianzkorrektur) ist bei fleckigen Texturen schädlich (dunkle Gitterlinien, im Sichttest bestätigt),
  deshalb Standard 0. Bei konstanter Farbe verschiebt sie diese prinzipbedingt weg von `Mean Color`.
- Prüfung: 34 Renders (Identität, Gewichte je Softness, Hash-Konsistenz je Zelle, Seed-Abhängigkeit, Rotation erhält Abstand,
  Spiegelung, Cell ID, Blend-Formel). Sichttest: `tools/nodes/tests/visual_antitile.py`.
- Bekannte Grenze: An den Überblendzonen entstehen bei sparsamen Mustern (Punkte) Doppelbilder; bei Stein, Gras, Sand,
  Beton kaum sichtbar. Vier Abtastungen pro Map.

## 10. Umbau auf Sampler-Closures (Ersatz für die Coords/Blend-Aufteilung)
Blender 5.2 hat im Shader-Editor Closure Zone (`NodeClosureInput`/`NodeClosureOutput`) und `NodeEvaluateClosure`,
in Shader-Groups gibt es Closure-Sockets. Getestet: Closure mit Image-Texture wird an eine Gruppe übergeben und dort an
mehreren Koordinaten ausgewertet, in **Cycles und EEVEE** mit richtigem Ergebnis. Damit fällt die Aufteilung weg.

**Sampler-Signatur (fest):** Eingang `Coord` (Vector), Ausgang `Result` (RGBA).

Öffentliche Assets:
- `SU Image Sampler`: Ausgang `Sampler` (Closure). Enthält Zone mit Image-Texture-Node `Image`
  (Bild dort setzen, pro Bild eine Einzelkopie; Interpolation/Extension ebenfalls dort). Eigene Sampler
  (prozedural, mehrere Nodes) funktionieren genauso.
- `SU Triplanar`: `Sampler`, `Vector`, `Scale`, `Rotation`, `Blend`, `Object Space` → `Color`
- `SU Triplanar Normal`: dazu `Strength`, `Flip Green` → `Normal` (Weltraum). Der Sampler liefert die Normal-Map-Farbe
  (Bild als Non-Color).
- `SU Anti-Tile`: `Sampler`, `Vector`, `Scale`, `Randomness`, `Rotation Amount`, `Mirror Chance`, `Blend Softness`, `Seed`,
  `Contrast Preserve`, `Mean Color` → `Color`, `Cell ID`. Für Normal Maps `Rotation Amount`/`Mirror Chance` auf 0.

Interne Bausteine (kein Asset, werden beim Anhängen als Abhängigkeit mitgeführt):
`SU _Triplanar Coords`, `SU _Triplanar Blend`, `SU _Triplanar Normal Blend`, `SU _Anti-Tile Coords`, `SU _Anti-Tile Blend`.

Nutzung: `SU Image Sampler` (Bild setzen) → `Sampler` von `SU Triplanar` bzw. `SU Anti-Tile`. Mehrere Maps mit identischer
Verteilung: je Map ein Sampler und eine Gruppe mit gleichem `Seed` und gleichen Einstellungen.
Hex Tiling und Parallax bauen ebenfalls auf diesem Sampler auf (Parallax: Sampler liefert die Höhe im Rotkanal).

Prüfung: 112 Renders in `verify.py`, darunter die Wrapper mit Koordinaten-Sampler (analytisch), mit konstantem
Normal-Map-Sampler und gegen manuelle Verdrahtung der internen Gruppen, sowie `SU Image Sampler` mit echtem Bild.
Sichttest (`visual_antitile.py`) mit dem Bild-Sampler entspricht dem Ergebnis der ersten Fassung.

### Anti-Tile als Sampler-Modifikator (Kombination mit Triplanar)
- `SU Anti-Tile Sampler`: `Sampler` (Closure) rein, `Sampler` (Closure) raus; gleiche Parameter wie `SU Anti-Tile`
  (ohne `Vector`, `Cell ID`). Innen eine Closure-Zone, die den eingehenden Sampler viermal mit Zellkoordinaten aufruft.
- Kette: `SU Image Sampler` -> `SU Anti-Tile Sampler` -> `SU Triplanar` (oder `SU Triplanar Normal` mit
  `Rotation Amount`/`Mirror Chance` = 0). Anti-Tile wirkt dann in jeder der drei Projektionsebenen (12 Abtastungen je Map).
- Allgemein: jede Gruppe mit Signatur Sampler -> Sampler ist ein Modifikator und lässt sich verketten
  (Kandidaten später: UV Pivot Transform, Polar Mapping als Sampler-Modifikator).
- Prüfung: Closure in Closure mit erfassten Werten funktioniert (Modifikator == `SU Anti-Tile`, Triplanar(Anti-Tile Sampler)
  bei Randomness 0 == Triplanar). Sichttest auf Kugel: `tools/nodes/tests/visual_triplanar.py`.
- Bekannte Grenze: Closures sind neu; nur die hier getesteten Verschachtelungen sind geprüft.
