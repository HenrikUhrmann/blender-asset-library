# SU Metal Preset: Datenquellen und Methode

Node-Group `SU Metal Preset` (Datei `library/Node-Groups/Mapping Utils.blend`). Zwei Dropdowns: **Metal** und **Treatment**.
Ausgänge, passend zu Blenders **Metallic BSDF**: `Color` (Base Color), `Edge Color` (Edge Tint, F82-Modus),
`IOR` und `Extinction` (Physical-Conductor-Modus, je RGB), `Thin Film Thickness` (nm) und `Thin Film IOR`.

## Methode (reproduzierbar mit `tools/metals/`)
1. **Rohdaten:** gemessene n- und k-Spektren aus [refractiveindex.info](https://refractiveindex.info/) (Datenbank CC0,
   `tools/metals/fetch_data.py`, Kopien in `tools/metals/data/`).
2. **Base Color** = Fresnel-Reflexion bei senkrechtem Blick, je Wellenlänge (380 bis 780 nm) berechnet, über die
   CIE-1931-Farbanpassungsfunktionen (Näherung von Wyman et al. 2013) in lineares sRGB umgerechnet, weiß normiert.
3. **Edge Color** nach Blenders Definition (Cycles `bsdf_util.h`, F82-Tint): Verhältnis der echten Reflexion bei
   cos θ = 1/7 (etwa 82°) zum Schlick-Wert an derselben Stelle, je Kanal.
4. **IOR / Extinction:** je Kanal so gefittet, dass der Leiter-Fresnel genau Base Color und den 82°-Wert trifft.
   Dadurch sehen F82-Modus und Physical-Conductor-Modus gleich aus (Render-Vergleich: Differenz höchstens 0.001,
   Titan mit Dünnfilm 0.01). Bei Gold und Silber ist der Rotkanal ausgesättigt, dort sind sehr hohe k-Werte normal.
5. **Thin Film:** Schichtdicke in nm, bei der die Oxidschicht (Luft, Film, Metall, senkrechter Einfall) die Wellenlänge
   450 nm (Straw, gelb), 550 nm (Purple) bzw. 650 nm (Blue) durch Interferenz auslöscht (erstes Minimum).
   Das ist eine Berechnung aus den Messdaten, **keine** Tabellenwerte aus einer Datenbank. Film-IOR = n bei 550 nm
   des Oxids. Gilt nur, wo im Datensatz ein sichtbares Oxid vorhanden ist (unten).

## Metalle
| Metall | Base Color (linear) | Vergleich physicallybased.info | Quelle der Messdaten |
|---|---|---|---|
| Aluminium | (0.91, 0.92, 0.92) | (0.92, 0.92, 0.92) | A. D. Rakić. Algorithm for the determination of intrinsic optical constants of metal films: application to aluminum. App |
| Brass (Cu70 Zn30) | (0.90, 0.78, 0.41) | (0.91, 0.78, 0.42) | M. R. Querry. Optical constants, Contractor Report CRDC-CR-85034 (1985) |
| Chromium | (0.55, 0.56, 0.55) | (0.65, 0.69, 0.70) | P. B. Johnson and R. W. Christy. Optical constants of transition metals: Ti, V, Cr, Mn, Fe, Co, Ni, and Pd. Phys. Rev. B |
| Cobalt | (0.68, 0.66, 0.61) | (0.70, 0.70, 0.67) | P. B. Johnson and R. W. Christy. Optical constants of transition metals: Ti, V, Cr, Mn, Fe, Co, Ni, and Pd. Phys. Rev. B |
| Commercial Bronze (Cu90 Zn10) | (0.94, 0.72, 0.46) | - | M. R. Querry. Optical constants, Contractor Report CRDC-CR-85034 (1985) |
| Copper | (0.91, 0.62, 0.52) | (0.93, 0.62, 0.52) | P. B. Johnson and R. W. Christy. Optical constants of the noble metals. Phys. Rev. B 6, 4370-4379 (1972) |
| Gold | (1.00, 0.73, 0.36) | (1.06, 0.77, 0.31) | P. B. Johnson and R. W. Christy. Optical constants of the noble metals. Phys. Rev. B 6, 4370-4379 (1972) |
| Iron (approx. carbon steel) | (0.53, 0.51, 0.49) | (0.53, 0.51, 0.49) | P. B. Johnson and R. W. Christy. Optical constants of transition metals: Ti, V, Cr, Mn, Fe, Co, Ni, and Pd. Phys. Rev. B |
| Magnesium | (0.96, 0.95, 0.95) | (0.96, 0.95, 0.95) | 1) H.-J. Hagemann, W. Gudat, and C. Kunz. Optical constants from the far infrared to the x-ray region: Mg, Al, Cu, Ag, A |
| Nickel | (0.69, 0.64, 0.56) | (0.70, 0.64, 0.56) | P. B. Johnson and R. W. Christy. Optical constants of transition metals: Ti, V, Cr, Mn, Fe, Co, Ni, and Pd. Phys. Rev. B |
| Palladium | (0.73, 0.70, 0.65) | (0.73, 0.70, 0.66) | P. B. Johnson and R. W. Christy. Optical constants of transition metals: Ti, V, Cr, Mn, Fe, Co, Ni, and Pd. Phys. Rev. B |
| Platinum | (0.67, 0.64, 0.58) | (0.77, 0.73, 0.68) | A. D. Rakić, A. B. Djurišic, J. M. Elazar, M. L. Majewski. Optical properties of metallic films for vertical-cavity opto |
| Red Brass (Cu85 Zn15) | (0.89, 0.72, 0.41) | - | M. R. Querry. Optical constants, Contractor Report CRDC-CR-85034 (1985) |
| Silver | (0.99, 0.98, 0.98) | (0.99, 0.98, 0.97) | P. B. Johnson and R. W. Christy. Optical constants of the noble metals. Phys. Rev. B 6, 4370-4379 (1972) |
| Stainless Steel, austenitic (316-type) | (0.67, 0.64, 0.60) | (0.67, 0.64, 0.60) | Björn Karlsson, Carl G. Ribbing. Optical constants and spectral selectivity of stainless steel and its oxides. J. Appl. |
| Stainless Steel, ferritic (430-type) | (0.60, 0.59, 0.57) | - | Björn Karlsson, Carl G. Ribbing. Optical constants and spectral selectivity of stainless steel and its oxides. J. Appl. |
| Titanium | (0.62, 0.58, 0.54) | (0.44, 0.40, 0.36) | P. B. Johnson and R. W. Christy. Optical constants of transition metals: Ti, V, Cr, Mn, Fe, Co, Ni, and Pd. Phys. Rev. B |
| Tungsten | (0.52, 0.49, 0.47) | (0.54, 0.54, 0.52) | A. D. Rakić, A. B. Djurišic, J. M. Elazar, M. L. Majewski. Optical properties of metallic films for vertical-cavity opto |
| Zinc | (0.87, 0.87, 0.85) | (0.81, 0.84, 0.86) | W. S. M. Werner, K. Glantschnig, C. Ambrosch-Draxl. Optical constants and inelastic electron-scattering data for 17 elem |

Ein Abgleich mit [physicallybased.info](https://physicallybased.info/) (dort ebenfalls aus refractiveindex.info-Daten): Base Color stimmt
bei Aluminium, Messing, Kupfer, Eisen, Magnesium, Nickel, Palladium, Silber und austenitischem Edelstahl auf etwa 0.01 überein.
Bei Chrom, Platin, Titan, Wolfram, Zink und Gold weichen sie ab, weil andere Messreihen verwendet werden.
Nicht enthalten: **Zinnbronze** (Cu-Sn) und Kohlenstoffstahl. Es gibt keine sichtbaren Messdaten dafür in der Datenbank.
„Commercial Bronze“ ist Cu90 Zn10 (eine Messing-Legierung), „Iron“ dient als Näherung für Kohlenstoffstahl.

## Treatment (Dünnfilm)
Optionen: `Bare (polished)` (0 nm), `Oxide Tint: Straw`, `Oxide Tint: Purple`, `Oxide Tint: Blue`.
Anlassfarben bei Stahl und Edelstahl (Eisenoxid) bzw. Anodisieren bei Titan (TiO2). Dicken in nm:

| Metall | Oxid | Straw | Purple | Blue |
|---|---|---|---|---|
| Iron (approx. carbon steel) | Fe3O4 (n = 2.343) | 33.2 | 42.6 | 50.4 |
| Stainless Steel, austenitic (316-type) | Fe3O4 (n = 2.343) | 30.9 | 40.8 | 51.1 |
| Stainless Steel, ferritic (430-type) | Fe3O4 (n = 2.343) | 29.0 | 38.8 | 48.2 |
| Titanium | TiO2 (n = 2.436) | 30.7 | 39.6 | 48.5 |

Für alle anderen Metalle ist die Dicke 0 (für Kupfer und Messing liefert die Datenbank kein Cu2O im sichtbaren Bereich,
für Edelmetalle bildet sich keine Schicht). Für Edelstahl ist Magnetit (Fe3O4) eine Näherung der Chrom-Eisen-Oxidschicht.
Die Oxidabsorption wird nicht berücksichtigt (nur n, nicht k des Films).

## Grenzen
- Das Dropdown ist getestet, indem die Menüs im Test fest gesetzt wurden. Die Auswahl in der Blender-Oberfläche bitte selbst prüfen.
- Gealterte Oberflächen (Patina, Rost) sind mit diesem Modell nicht abgedeckt.
