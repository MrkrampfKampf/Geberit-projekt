# Stepper am Carrera-Schieberegler

## Hardware

Motor: 28BYJ-48 Stepper mit ULN2003-Treiberplatine.

Der Motor darf nicht direkt an den Pico. Die ULN2003-Platine kommt dazwischen.

```text
Pico GP10 -> ULN2003 IN1
Pico GP11 -> ULN2003 IN2
Pico GP12 -> ULN2003 IN3
Pico GP13 -> ULN2003 IN4

Pico GND  -> ULN2003 GND
5V        -> ULN2003 +5V
```

Wenn eine externe 5V-Versorgung genutzt wird:

```text
externe 5V + -> ULN2003 +5V
externe GND -> ULN2003 GND
Pico GND    -> ULN2003 GND
```

Nicht an `3V3` anschliessen. Der Stepper braucht 5V und deutlich mehr Strom als
ein Pico-GPIO liefern kann.

## Mechanik

Der 28BYJ-48 ist langsam, aber fuer einen ersten Prototyp brauchbar. Er muss den
roten Schieberegler mechanisch bewegen. Weil der Stepper kein Positionsfeedback
hat, muss die Software beim Start kalibriert werden:

1. Schieber mechanisch auf 0 setzen.
2. `zero` senden.
3. Kleine Schritte testen, z.B. `cw 32` oder `ccw 32`.
4. Richtung pruefen, ggf. `invert 1`.
5. Schrittbereich fuer 0 bis 100 Prozent setzen, z.B. `range 600`.

## Pico flashen

```powershell
.\install_stepper_slider_on_pico.ps1
```

## Kleiner Motortest

```powershell
.\test_stepper_slider.ps1
```

## Einzelbefehle

```powershell
.\.venv\Scripts\python.exe pc_send_stepper.py --port COM3 --cmd "cw 64"
.\.venv\Scripts\python.exe pc_send_stepper.py --port COM3 --cmd "ccw 64"
.\.venv\Scripts\python.exe pc_send_stepper.py --port COM3 --cmd "gas 25"
.\.venv\Scripts\python.exe pc_send_stepper.py --port COM3 --cmd "release"
```
