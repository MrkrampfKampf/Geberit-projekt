# Carrera KI Projekt - Uebergabe fuer neuen PC / neuen Chat

Stand: 2026-07-02

Dieses Dokument enthaelt den kompletten Arbeitsstand. Der neue Chat soll nicht wieder bei der Hardware-Diskussion anfangen, sondern direkt mit der selbstlernenden KI weiterarbeiten.

## Ziel

Eine Carrera-Bahn soll mit Kamera, Python und Raspberry Pi Pico selbststaendig fahren lernen.

Aktueller Ansatz:

```text
Kamera erkennt Auto/Position -> Python entscheidet Gas -> Pico steuert Stepper -> Stepper bewegt echten Carrera-Schieberegler
```

Kein Digital-Poti ist aktuell verbaut. Die funktionierende Steuerung ist mechanisch ueber Stepper am Schieberegler.

## Hardware

Vorhanden/verwendet:

- Carrera-Bahn mit Control Unit, AppConnect, Wireless/Wireless 2.0 Komponenten
- Carrera Wireless 2.0 Handregler geoeffnet
- Raspberry Pi Pico W mit MicroPython
- 28BYJ-48 Stepper-Motor
- ULN2003/ALLNET Stepper-Treiberplatine mit Pins `INA INB INC IND GND +5V`
- Externe 5V-Versorgung/Elegoo-Batteriebox fuer Motorplatine
- Webcam/Kamera von oben fuer Bahnerkennung
- PC mit Python-Projekt

## Wichtige Erkenntnisse

- AppConnect/carreralib kann Setup/Fahrzeugparameter und Timer lesen, aber nicht direkt live Gas geben.
- Virtueller Wireless-Controller per Funk wurde nicht umgesetzt. Zu aufwendig/unsicher.
- Digital-Poti waere sauberer, aber aktuell nicht vorhanden. Empfehlung war `MCP4131-103E/P`, nicht `104`.
- Funktionierende Loesung ist jetzt: Stepper bewegt den echten physischen Schieberegler.

## Aktuelle Pico/Stepper-Verkabelung

Motorplatine:

```text
Pico GP18 -> INA / IN1
Pico GP19 -> INB / IN2
Pico GP20 -> INC / IN3
Pico GP21 -> IND / IN4

Pico GND  -> Motorplatine GND
5V Plus   -> Motorplatine +5V
5V Minus  -> Motorplatine GND
```

Wichtig:

- Pico und Motorversorgung muessen gemeinsamen GND haben.
- Motor nicht direkt an Pico anschliessen.
- Motor bleibt am weissen Stecker der Stepper-Platine.
- 5V kommen von externer Versorgung, nicht von `3V3`.

## Funktionierende mechanische Kalibrierung

Fakt nach Tests:

```text
Links  = Vollgas / 100%
Rechts = Nullgas / 0%
cw     = Richtung weniger Gas
ccw    = Richtung mehr Gas
```

Aktuelle Software-Logik in `pico_stepper_slider.py`:

```text
PIN_NUMBERS = (18, 19, 20, 21)
gas_direction = -1
```

Kalibrierung, die funktioniert:

```text
0% Gas  = physisch rechts / Nullgas
100% Gas theoretisch = ca. 400 Steps Richtung links / Vollgas
range_steps = 400
speed = 1200 us
gasdir = ccw
```

Getestet und funktionierend:

```text
gas 25 -> pos -100
gas 50 -> pos -200
gas 30 -> pos -120
gas 20 -> pos -80
gas 10 -> pos -40
gas 0  -> pos 0
```

Wichtig: `zero` nur senden, wenn der Schieberegler wirklich physisch bei 0% Gas steht.

## Pico-Kommandos

Pico-Firmware:

```text
pico_stepper_slider.py
```

Auf Pico installieren:

```powershell
.\install_stepper_slider_on_pico.ps1
```

Einzelbefehl senden:

```powershell
.\.venv\Scripts\python.exe pc_send_stepper.py --port COM3 --cmd "status"
```

Wichtige Befehle:

```text
speed 1200
range 400
zero
gas 0
gas 10
gas 20
gas 30
gas 50
release
status
```

Manueller Test:

```powershell
.\.venv\Scripts\python.exe pc_send_stepper.py --port COM3 --cmd "speed 1200"
.\.venv\Scripts\python.exe pc_send_stepper.py --port COM3 --cmd "range 400"
.\.venv\Scripts\python.exe pc_send_stepper.py --port COM3 --cmd "gas 30"
.\.venv\Scripts\python.exe pc_send_stepper.py --port COM3 --cmd "gas 0"
.\.venv\Scripts\python.exe pc_send_stepper.py --port COM3 --cmd "release"
```

## Kamera/Tracker Stand

Es gibt zwei Tracker-Arten:

1. Python/OpenCV Tracker
2. Browser-Kamera-Tracker mit Kameraauswahl

Python/OpenCV sah zuletzt nur Kamera `0`. Kamera 1 war nicht offen:

```text
camera 0: opened=True frame=True
camera 1: opened=False
```

Windows zeigte aber mehrere Kameras, u.a.:

- Integrated Webcam
- Integrated IR Webcam
- HD Pro Webcam C920
- Yealink Room Camera

Wenn die falsche Kamera im Python-Tracker sichtbar ist, Browser-Tracker verwenden:

```powershell
.\start_browser_camera_tracker.ps1
```

Browser-URL:

```text
http://127.0.0.1:8766/browser_camera_tracker.html
```

Dort Kamera und Aufloesung auswaehlen, z.B. `1920x1080`, und Start druecken.

Hinweis: Der Browser-Tracker ist vor allem zum Anschauen/Ausrichten gebaut. Der Python-Autopilot nutzt aktuell OpenCV/Kameraindex.

## Streckenanalyse / Abschnitte

Es wurden bereits Kamerapositionen und Streckenabschnitte erstellt.

Wichtige Dateien:

```text
dual_car_positions.csv
track_position_analysis.csv
track_section_stats.csv
track_summary.md
track_map_overlay.jpg
track_speed_heatmap.jpg
```

Aktuelle Abschnittslogik ist in:

```text
analyze_track_positions.py -> section_for(x, y)
```

Abschnitte:

```text
bottom_straight
start_finish
left_curve
s_curve
top_straight
right_curve
transition
not_found
```

Letzte bekannte Abschnittswerte aus `track_section_stats.csv`:

```text
bottom_straight avg 834.3 px/s
left_curve     avg 680.1 px/s
right_curve    avg 663.3 px/s
s_curve        avg 609.0 px/s
start_finish   avg 922.3 px/s
top_straight   avg 679.9 px/s
```

## Autopilot und Lern-KI

Normaler Autopilot:

```text
autonomous_stepper_driver.py
run_autonomous_stepper.ps1
run_autonomous_stepper_dry.ps1
```

Lern-Autopilot:

```text
learning_stepper_driver.py
run_learning_stepper.ps1
run_learning_stepper_dry.ps1
```

Aktueller Startbefehl fuer Lernfahrt:

```powershell
.\run_learning_stepper.ps1
```

Der Startbefehl nutzt:

```text
camera 0
port COM3
car orange
laps 10
seconds 180
range-steps 290
stepper-speed-us 1200
max-gas 38
```

Lernprinzip:

- Kamera erkennt Auto.
- Abschnitt wird per `section_for(x, y)` bestimmt.
- Profil gibt pro Abschnitt Gaswert vor.
- Nach Start/Ziel-Uebergang wird Rundenzeit erkannt.
- Pro Runde wird ein Abschnitt leicht schneller gemacht.
- Wenn Rundenzeit besser wird, bleibt Aenderung.
- Wenn schlechter oder Auto verloren, wird Aenderung zurueckgenommen bzw. Gas reduziert.
- Wenn Auto verloren: `gas 0`.

Startprofil aus `autonomous_stepper_driver.py`:

```text
start_finish:    26
bottom_straight: 32
top_straight:    28
left_curve:      18
right_curve:     18
s_curve:         16
transition:      18
not_found:        0
```

Lernreihenfolge in `learning_stepper_driver.py`:

```text
bottom_straight
top_straight
start_finish
left_curve
right_curve
s_curve
```

Outputs der Lern-KI:

```text
learning_stepper_log.csv
learned_stepper_profile.json
```

## Ablauf fuer neuen PC / neuen Chat

1. Projektordner kopieren.
2. Python installieren.
3. Virtuelle Umgebung und Requirements installieren.
4. Pico anschliessen und COM-Port pruefen.
5. Pico-Firmware flashen.
6. Stepper-Verkabelung pruefen.
7. Schieberegler physisch auf Nullgas rechts stellen.
8. `zero`, `range 400`, `speed 1200`, `gas 30`, `gas 0` testen.
9. Kamera ausrichten, Tracker pruefen.
10. Lernfahrt starten.

Setup-Kommandos:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\install_stepper_slider_on_pico.ps1
```

Pico-Test:

```powershell
.\.venv\Scripts\python.exe pc_send_stepper.py --port COM3 --cmd "speed 1200"
.\.venv\Scripts\python.exe pc_send_stepper.py --port COM3 --cmd "range 400"
.\.venv\Scripts\python.exe pc_send_stepper.py --port COM3 --cmd "zero"
.\.venv\Scripts\python.exe pc_send_stepper.py --port COM3 --cmd "gas 30"
.\.venv\Scripts\python.exe pc_send_stepper.py --port COM3 --cmd "gas 0"
```

Tracker pruefen:

```powershell
.\start_browser_camera_tracker.ps1
```

Lern-KI starten:

```powershell
.\run_learning_stepper.ps1
```

## Sicherheitsverhalten

Die KI soll immer `gas 0` setzen wenn:

- Auto nicht erkannt wird
- Kamera ausfaellt
- Runden-Timeout passiert
- User stoppt

Das ist in `learning_stepper_driver.py` bereits vorgesehen.

## Bekannte Probleme / naechste Aufgaben

1. Python/OpenCV Kameraindex muss auf neuem PC neu ermittelt werden.
2. Browser-Tracker kann richtige Kamera anzeigen, aber Autopilot nutzt derzeit OpenCV.
3. Wenn die richtige Kamera in OpenCV nicht Kamera 0 ist, Startskripte anpassen.
4. Selbstlernende KI ist vorbereitet, aber noch nicht final auf echter Fahrt getestet.
5. Runden-Erkennung ueber Kamera-Abschnitt `start_finish` ist implementiert, muss real validiert werden.
6. Max-Gas ist absichtlich konservativ auf 38 begrenzt.
7. Wenn Auto rausfliegt, `max-gas` oder Kurvenwerte senken.

## Wichtig fuer den naechsten Chat

Bitte im neuen Chat diese Datei zuerst lesen und NICHT wieder bei Hardware-Auswahl anfangen.

Der naechste konkrete Arbeitsauftrag:

```text
Wir haben Carrera-Bahn, Kamera, Python, Pico W, Stepper am echten Handregler.
Die Stepper-Steuerung funktioniert.
0% Gas ist rechts, 100% Gas ist links.
Pico Pins: GP18..GP21 an INA..IND.
range 400, speed 1200, gasdir ccw.
Bitte starte ab hier mit der selbstlernenden KI:
1. Kamera/Tracker auf neuem PC validieren.
2. Lern-Autopilot mit run_learning_stepper.ps1 starten.
3. Falls Kameraindex falsch ist, korrigieren.
4. Rundenzeiten und learned_stepper_profile.json auswerten.
5. Profil iterativ verbessern.
```

## Zentrale Dateien zum Mitnehmen

Unbedingt kopieren:

```text
pico_stepper_slider.py
pc_send_stepper.py
install_stepper_slider_on_pico.ps1
autonomous_stepper_driver.py
learning_stepper_driver.py
run_learning_stepper.ps1
run_learning_stepper_dry.ps1
track_dual_cars_live.py
track_orange_car_live.py
analyze_track_positions.py
browser_camera_tracker.html
start_browser_camera_tracker.ps1
requirements.txt
RPI_PICO_W-v1.28.0.uf2
track_section_stats.csv
track_summary.md
```

Optional, aber hilfreich:

```text
dual_car_positions.csv
track_map_overlay.jpg
track_speed_heatmap.jpg
virtual_controller_research.md
digital_pot_recommendation.md
stepper_slider_plan.md
pico_setup.md
```
