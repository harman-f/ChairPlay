# ChairPlay UI v4 — Live Display Panels POC

## Basis / Fehlerursache des vorigen Builds
- **Basierend auf PR #166** (`work/chairplay-skoda790-fastbuild-v2-20261104`) und nicht auf PR #162 / einer älteren Stock-UI.
- **Korrigierter Pfad-Befund:** Das Buildskript `gradle/upstream.gradle.kts` patcht beim `:upstreamCore`-Schritt `AirPlayInfoPlist.build()` und ruft dort ausdrücklich `ClusterProfile.advertise(info)` auf. Der ursprüngliche POC-Hook aus PR #167 war auf diesem Weg tatsächlich erreichbar. Ein zwischenzeitlicher zusätzlicher DiPlay-`/info`-Hook war redundant und wurde zurückgenommen, weil er mit den bestehenden Gradle-Guards kollidierte. Nicht validiert waren die iOS-Akzeptanz des neuen `displayPanels`-Formats und die Live-Wirkung auf Zoom/mm.
- Der alte Full-Windows-Build ist damit **keine** gültige Bestätigung oder Widerlegung einer Live-Skalierung.

## Was die Oberfläche zeigen soll
Unter **AltScreen → Vehicle Profile → Scaling** bleiben dieselben Zoom-Regler und deren bestehende Werte erhalten. Nur ein kurzer experimenteller Block wird direkt davor eingefügt:

1. **Apply changes live (experimental)** AUS / EIN. Er ist bei jedem App-Neustart wieder AUS, und das Ankreuzen unterbricht keine bestehende Sitzung.
2. Bei EIN: **Step 1: connect → Reconnect once**. Dadurch wird für die nächste /info-Antwort ein zusätzliches `displayPanels`-Array angeboten. Der bestehende `displays`-Descriptor bleibt unangetastet. Neben dem Button steht, ob ein Panel-Descriptor angeboten wurde.
3. **Step 2: baseline → Send unchanged panel**. Erst wenn der Type-111-Stream aktiv ist, darf der unveränderte Befehl auf dem AirPlay-Event-Kanal gesendet werden.
4. Bei positivem lokalem Sendeergebnis: **Step 3: scaling**. Danach die **bestehenden** Segmented-Regler `Zoom factor` und `Physical zoom` benutzen. Beim Speichern des aktiven Profils sendet ChairPlay automatisch eine vollständige `updateDisplayPanels`-Payload mit der aktuellen Kombination aus Zoomfaktor, effektiver physischer Größe, unveränderter Pixel-Geometrie, Panel-UID und Videostream-UUID. Auflösung, Safe Areas und View/Stream-Zuordnung werden nicht live verändert.
5. **Evidence** zeigt explizit lokalen Transportstatus, `iOS ACK: NOT_OBSERVED`, `visual effect: UNKNOWN`; das sind keine Erfolgsbestätigungen.

## Akzeptanztest mit echtem iPhone
- Vor dem Test iOS-Version, den aktiven MU1440-Cluster-View, Zoom/physische Größe und einen Screenshot protokollieren.
- Zunächst den **normalen Reconnect-Weg** für die beiden Scaling-Regler als Positivkontrolle prüfen.
- Einmal live **Baseline senden**. CarPlay-Hauptschirm und VC-Stream dürfen nicht verschwinden; sonst das Experiment deaktivieren und neu verbinden.
- Einmal **nur Zoom factor** (z. B. 85 → 125) testen, danach bei Bedarf **nur Physical zoom**. Jeweils neue Screenshots/Videoaufnahme machen, Session-Kontinuität feststellen und Logs aus `Settings → Experiments → Logs` sichern.
- Wird `LOCAL_SENT` angezeigt, hat ChairPlay den Befehl geschrieben. Der iOS-26.1-Handler für `updateDisplayPanels` verarbeitet jedoch nach dem vorliegenden Decompile nur Panel-Identität und Videostreams; **eine Live-Anwendung von mm/zoom ist nicht belegt**. Ein unverändertes Bild nach lokalem Versand ist ein aussagekräftiges negatives Ergebnis für diesen Weg, kein UI-Fehler.
- Unter iOS 27 `zoomFactorByDisplayIndex` / `DisplayConfigurationChanged` separat prüfen; es handelt sich nach bisheriger Evidenz um iPhone-interne Konfiguration, nicht um einen bestätigten Zubehör-Befehl. Ein direkter Zusammenhang mit CarPlay Ultra ist offen.

## Build / Integration
- Aktiver Entwicklungsstand: PR #166 und aufgesetzter Draft-PR #168.
- Nur CI-Artifact `chairplay-skoda790-build44-manual-patch` mit `app/chairplay.jar`, **keine Neuinstallation**, keine Änderung an lokalen MFi-Schlüsseln und Pairings.
- Bestehende ChairPlay-Installation schließen, `app/chairplay.jar` sichern, den Pfad aus dem ZIP in die Installation kopieren, danach starten. Die ZIP allein ist keine Standalone-Anwendung.
- CI prüft die Marker `UI v4` und `Apply changes live (experimental)`, Kotlin-/Web-Tests sowie generierte JAR. Eine gebaute JAR ist **noch kein iPhone-Nachweis**.
