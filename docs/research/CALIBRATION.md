# SafeArea / freier Kartenbereich — Analyse 03.11.2026

## Begriffsklärung
- **Frame:** 1010×376 px, Type-111-Stream. Alle 7 im aktuellen Profil deklarierten `viewAreas` haben denselben Frame; nur die eingebetteten SafeRect-/URL-Kontexte unterscheiden sich.
- **SafeArea:** vom iPhone zu berücksichtigendes rechteckiges Innenfenster für UI/Labels; sie ist **kein Clip-Path** und schneidet den H.264-Videostream nicht physisch auf dieses Rechteck zu.
- **OEM-Maske:** mit NanoVG gerenderte Instrumente, Panels, Fußleisten; die CarPlay-Karte existiert darunter weiterhin.
- **Navi-Overlay:** zusätzliche `zone/lanes/turn/eta`-Shapes im Quellprofil; derzeit immer pro View gezeichnet, nicht separat schaltbar. Der echte VC-Navi-Hinweis ist in den Fotos teils transparent. Ziel ist die tatsächliche Überdeckung, nicht eine rein dekorative Nachbildung.

## Fotoabgleich (visuell, nicht subpixelgenau)
**Bild 1: Wide.** Der Verlauf der unteren seitlichen Abschrägungen passt zum polygonalen Footermask des Branches; freie Rasterfläche bis zur Statusleiste. Breite SafeArea x=40..970 ist oberhalb des Footers grundsätzlich plausibel. Ihr rechnerischer Schnitt mit dem Footer von y=274..288 ist falsch. Kalibrierung auf y=58..274.

**Bild 2: Panels.** Die geneigten Innenkanten links/rechts stimmen in der entzerrten Foto-Gegenüberstellung näherungsweise mit `x=160→244` links und `x=856→775` rechts überein. Das SafeRect x=290..720 ist ein konservatives **Innenrechteck**, nicht die gesamte sichtbare trapezförmige Fläche. Die vordere Fußleiste beginnt y=306, weshalb SafeRect y=61..315 9 px ins Verdeckte reicht. Korrektur y=61..306.

**Bild 3: Rundinstrumente.** Außenkreis-Mitten `(189,187)`, `(821,187)`, Radius 182 treffen die äußeren Dial-Grenzen schon ungefähr. Bei y=187 ist die dazwischen liegende freie Spalte ca. 268 px breit (`x=371..639`). Das vorhandene SafeRect x=364..644 ist 12 px zu breit. Korrektur auf x=372..638, Endhöhe y=307 wegen darunterliegendem ETA-Demoblock. Die vorhandene oberste Navi-Demo-Schicht entspricht nicht dem Bild mit *Zielführung nicht aktiv*.

## Referenzbild-Reihenfolge
Die Screenshots in der Chatübergabe: #1 breite Karte; #2 Seitenpaneele; #3 Rundinstrumente. Reihenfolge im ChairPlay-Profil ist **0 Dials, 1 Wide, 2 Panels**. Die verbleibenden Views 3/4 sind reine Cover-Ansichten ohne neue Karte; nicht löschen.

## Offene Präzisionsfragen
- Perspektive: Die Originalfotos sind aus leicht unterschiedlicher Kameraposition aufgenommen; die Entzerrung in der Chat-Analyse ist eine geometrische Näherung.
- Sichtbarkeit von CarPlay-Labels: Ein `safeArea`-Rect darf die transparente Demo-Nav-Zone überlagern. Will man sichtbare Inhalte tatsächlich freihalten, braucht man ggf. *andere* SafeArea-Presets mit/ohne Navi-Overlay, was einen neuen `requestViewArea`-Ablauf und iOS-Test erfordert.
- Der Original-Free790-Contract enthält ein einzelnes 606×344-SafeRect bei (202,16), während der Kolleg:innen-Branch 7 deklarierte Bereiche nutzt. Die Originalwerte sind **Protokollbeleg**, aber kein Beweis, dass alle 7 experimental SafeAreas den OEM-Layouts entsprechen.
- Foto zeigt ein Demo-Raster mit Markierungen; es ist kein Beleg, dass die angezeigten Rasterzahlen im iOS-Frame identisch zu tatsächlich gerenderten Fensterpixeln sind.

## Auswirkung auf künftige Coding-Änderung
Zuerst **nur** die zwei JSON-Dateien unter Windows testen. Danach optional `ShapePainter` in Gruppen `oem`, `nav-top`, `nav-lanes`, `nav-turn`, `nav-eta`, `debug` aufteilen. State von `CarViews` halten und über vorhandene Control/API nachrüsten. Keine sechs künstlichen Car-Views, die die eigentliche iOS-ViewArea-Zuordnung verfälschen. Keine Änderung des Fahrzeug-`core.so` aus diesem ChairPlay-Projekt ableiten.

### Akzeptanztests
1. /info: 1010×376 px, **202×75 mm**, fps 40, Type 111, ViewArea-Indices 4/5/6.
2. Polygon-/Kreis-Grundmasken bleiben unverändert; zugeschnittene Rechtecke überschneiden diese Vektormasken nicht.
3. Jede der drei Kartenansichten im Windows-Screenshot mit entsprechendem Original vergleichen; visuelle Abweichung als Pixelabstand dokumentieren statt nur »sieht ähnlich aus«.
4. Mit/ohne Navi-Demo im Windows-Host sehen, ob der tatsächliche frei sichtbare Bildbereich für Navigation sinkt; CarPlay reagiert möglicherweise unterschiedlich auf App/URL/Area.
5. Kein geheimes MFi-Material, Wifi-Passwort, Pairing oder Releasebinary in Git.