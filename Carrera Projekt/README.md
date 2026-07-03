# Carrera Speed Trainer

Ja, das Setup auf den Fotos koennen wir so fuer den ersten Schritt nutzen:
AppConnect verbindet den PC mit der Control Unit, und Python misst Rundenzeiten
und testet automatisch verschiedene Carrera-Speed-Stufen.

Wichtig: Das ist noch keine echte Kurven-KI mit Gas/Bremse pro Streckenabschnitt.
Mit AppConnect setzen wir die maximale Speed-Stufe des Autos und messen, welche
Stufe schnell und stabil bleibt. Fuer echtes Live-Gasgeben muesste spaeter ein
Controller elektronisch emuliert oder umgebaut werden.

## 1. Status auf diesem PC

Erledigt:

- Python 3.12.10 wurde benutzerweit installiert.
- Die virtuelle Umgebung `.venv` wurde erstellt.
- `carreralib==1.0.3` wurde installiert.
- AppConnect wurde gefunden: `C5:7D:F4:7A:AC:42`.
- Die Control Unit antwortet mit Firmware `5339`.

## 2. Verbindung testen

Im Projektordner:

```powershell
.\test_connection.ps1
```

## Lokale Rundenzeit-UI

AppConnect einstecken, Bahn einschalten und dann:

```powershell
.\start_lap_ui.ps1
```

Die Weboberflaeche laeuft lokal unter:

```text
http://127.0.0.1:8780/
```

Der Reset-Button leert die Anzeige und setzt den CU-Timer zurueck. Jede
vollstaendige Runde wird in der Tabelle erfasst und kann als CSV exportiert
werden.

10-Runden-Duell mit demselben Auto:

1. `Duell neu` druecken.
2. Fahrer 1 faehrt 10 vollstaendige Runden.
3. Wenn Fahrer 1 fertig ist, Auto zurueckstellen und `Fahrer 2 starten`
   druecken.
4. Fahrer 2 faehrt 10 vollstaendige Runden.
5. Die UI zeigt Gewinner nach Gesamtzeit und Durchschnitt an.

## 3. Projekt neu vorbereiten

Nur falls die virtuelle Umgebung geloescht wurde:

```powershell
$env:LOCALAPPDATA\Programs\Python\Python312\python.exe -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Falls PowerShell die Aktivierung blockiert:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
.\.venv\Scripts\Activate.ps1
```

## 4. AppConnect finden

AppConnect in die Control Unit stecken, Bahn einschalten, Handy-Apps schliessen
und Bluetooth am PC aktivieren.

```powershell
.\.venv\Scripts\python.exe -m carreralib
```

Merke dir entweder den COM-Port, z.B. `COM3`, oder die Bluetooth-Adresse, z.B.
`C6:34:FA:1D:1D:5D`. Bei unserem Test wurde `C5:7D:F4:7A:AC:42` gefunden.

## 5. Auto vorbereiten

- Nur ein Auto auf die Bahn stellen.
- Auto auf Controller 1 codieren.
- Fuel an der Control Unit fuer den ersten Test auf OFF stellen.
- Leitplanken an kritische Kurven setzen.
- Controller beim Test auf Vollgas halten.
- Auto nicht auf Augenhoehe fahren lassen.

Bei `carreralib` ist Controller 1 die Adresse `0`, Controller 2 ist `1`.

## 6. Trainer starten

Einfach:

```powershell
.\run_trainer.ps1
```

Oder manuell:

Mit Bluetooth-Adresse:

```powershell
.\.venv\Scripts\python.exe train_basic_speed.py C5:7D:F4:7A:AC:42 --car 0 --min-speed 3 --max-speed 10 --laps 4
```

Oder mit COM-Port:

```powershell
.\.venv\Scripts\python.exe train_basic_speed.py COM3 --car 0 --min-speed 3 --max-speed 10 --laps 4
```

Wenn die Control Unit nicht von selbst zaehlt, nutze zusaetzlich `--start`:

```powershell
.\.venv\Scripts\python.exe train_basic_speed.py COM3 --car 0 --min-speed 3 --max-speed 10 --laps 4 --start
```

Am Ende entsteht `carrera_speed_results.csv` mit allen getesteten Stufen.

## Naechster Ausbau

Wenn das stabil funktioniert, koennen wir als naechstes Brake-Stufen testen,
mehrere Autos getrennt auswerten oder eine zweite Version bauen, die eine
modifizierte Controller-Elektronik ansteuert und dann wirklich pro Kurve Gas
und Bremse regelt.

## Kamera und Pico W

Fuer echte KI-Fahrt brauchen wir zwei Dinge:

- Webcam von oben als Augen.
- Raspberry Pi Pico W plus Servo als Gasfinger am Carrera-Controller.

Die Pico-W-Anleitung steht in `pico_setup.md`.

Status:

- MicroPython wurde auf den Pico W geflasht.
- `pico_servo_controller.py` wurde als `main.py` auf den Pico kopiert.
- Der Pico ist als `COM3` erreichbar.
- `gas 0` wurde erfolgreich getestet.

## Streckenkarte aus Kameradaten

Nach einer 30-Sekunden-Aufnahme:

```powershell
.\analyze_track.ps1
```

Erzeugt:

- `track_map_overlay.jpg`
- `track_speed_heatmap.jpg`
- `track_position_analysis.csv`
- `track_section_stats.csv`

Live-Monitor fuer das orange Auto:

```powershell
.\monitor_orange_sections.ps1
```

## Virtueller Wireless-Handregler

Recherche und naechste Schritte stehen in `virtual_controller_research.md`.
