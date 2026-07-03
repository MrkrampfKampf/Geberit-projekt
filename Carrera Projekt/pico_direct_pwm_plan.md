# Pico direkt als Gas-Signal

Ziel:

```text
PC/KI -> Pico GP15 PWM -> geglaettete Analogspannung -> R1-Gas-Signal im Handregler
```

Das ist die Variante ohne Digital-Poti und ohne Servo.

## Wichtig

Der echte Schieberegler `R1` kann den Pico-Ausgang elektrisch festhalten, wenn
er mechanisch auf 0 steht. Deshalb gibt es zwei Stufen:

### Test, nicht final

```text
Pico GP15 -> 10k Schutzwiderstand -> R1-Wischer
Pico GND  -> Batterie-Minus/GND vom Handregler
R1 bleibt mechanisch auf 0
```

Das kann funktionieren, wenn der Controller-Eingang hochohmig genug ist. Wenn
R1 den Wischer stark nach GND zieht, sieht der Controller aber weiter 0 Gas.

### Besser

```text
R1-Wischer-Leitung trennen oder mittleren R1-Pin anheben
Pico GP15 -> RC-Filter -> 10k Schutzwiderstand -> Controller-Seite vom Wischer
Pico GND  -> Controller-GND
```

Dann kaempft der Pico nicht gegen den echten Regler.

## RC-Filter

Minimal:

```text
Pico GP15 -> 10k -> Analogknoten
Analogknoten -> 100nF bis 1uF -> GND
Analogknoten -> 10k Schutzwiderstand -> R1-Wischer/Controller-Gassignal
```

Ohne Kondensator ist es nur PWM, keine saubere Analogspannung. Es kann trotzdem
zufaellig gehen, ist aber unruhiger.

## Pico flashen

```powershell
.\install_pwm_throttle_on_pico.ps1
```

## Vorsichtiger Test

```powershell
.\test_pwm_throttle.ps1
```

Das setzt ein Ausgangslimit von 30 Prozent und sendet kurz `gas 10`.

## Warum erst messen?

Wir muessen wissen, welche Spannung der Handregler am R1-Wischer erwartet. Wenn
die interne Referenz z.B. nur 1.8 V ist, waere Pico-3.3-V-Vollgas zu hoch.
Darum hat die Pico-Software den Befehl:

```text
limit 0..100
```

Damit kann man die maximale Ausgabe begrenzen.
