# Raspberry Pi Pico W als Gasfinger

Der Pico W ersetzt keinen PC und keine Kamera. Er ist der kleine Servo-Controller,
der spaeter den Carrera-Gashebel drueckt.

## Verdrahtung fuer einen SG90 Servo

- Servo Signal, orange/gelb: Pico W `GP15`
- Servo Plus, rot: externe `5V` Versorgung
- Servo Minus, braun/schwarz: GND
- Pico W `GND` mit Servo-GND verbinden

Wichtig: Den Servo nicht aus dem 3.3V-Pin des Pico versorgen.

## Pico flashen

1. Thonny installieren oder oeffnen.
2. Pico W per USB anschliessen.
3. MicroPython fuer Raspberry Pi Pico W installieren, falls noch nicht drauf.
4. Datei `pico_servo_controller.py` in Thonny oeffnen.
5. Auf dem Pico als `main.py` speichern.
6. Pico kurz abziehen und wieder einstecken.

Danach sollte der Pico als COM-Port erscheinen. Auf diesem PC wurde er als
`COM3 USB Serial Device` erkannt.

## COM-Port am PC finden

```powershell
.\.venv\Scripts\python.exe pc_send_gas.py
```

## Servo testen

Beispiel mit `COM3`:

```powershell
.\.venv\Scripts\python.exe pc_send_gas.py --port COM3 --gas 30 --seconds 2
```

Der Servo geht auf 30 Prozent und danach wieder auf 0.

Kurzer Test mit vorbereitetem Skript:

```powershell
.\pico_test_gas.ps1
```

Erst ohne Carrera-Controller testen. Danach Servo mechanisch so befestigen,
dass `gas 0` den Trigger nicht drueckt und kleine Werte den Trigger vorsichtig
bewegen.
