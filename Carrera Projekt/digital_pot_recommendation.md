# Digital-Poti Empfehlung fuer Carrera Handregler

## Empfehlung

Nehmt als erstes:

```text
MCP4131-103E/P
```

Warum:

- 10 kOhm linear, passend als Ersatz fuer einen typischen Carrera-Gas-Poti.
- SPI, also direkt vom Raspberry Pi Pico steuerbar.
- DIP-8 Gehaeuse, dadurch viel leichter zu loeten als SMD.
- Laeuft laut Datenblatt ab 1.8 V bis 5.5 V.
- 129 Schritte reichen fuer Gaswerte.

Quelle: Microchip MCP4131 Produktseite und Datenblatt.

Alternative, wenn sicher mindestens ca. 2.7 V am Controller/Logikteil anliegen:

```text
MCP41010-I/P
```

Der hat 10 kOhm und 256 Schritte, braucht aber typischerweise mindestens 2.7 V.

Nicht als erste Wahl:

```text
X9C103 / X9C103S Modul
```

Der ist zwar 10 kOhm, aber eher fuer 5 V gedacht und hat nur eine Up/Down-Steuerung.
Fuer Pico + Carrera ist der MCP4131 sauberer.

## Anschlussidee

Der Digital-Poti ersetzt den echten Schieberegler R1 elektrisch:

```text
R1 oberes Ende  -> P0A
R1 Wischer      -> P0W
R1 unteres Ende -> P0B

Pico GND        -> Controller GND / Batterie-Minus
Pico SPI SCK    -> SCK
Pico SPI MOSI   -> SDI/SDO
Pico GPIO CS    -> CS
```

Wichtig: Der echte R1 sollte nicht parallel weiter aktiv sein, sonst verfaelscht er
die Werte. Am saubersten ist: R1-Wischer trennen/anheben und die Controller-Seite
des Wischers an P0W anschliessen.

## Warum besser als Pico-PWM direkt?

Digital-Poti ist fuer den Controller mehr wie ein echter Regler:

- kein PWM-Flackern
- kein RC-Filter noetig
- weniger Risiko, dass der echte Poti das Signal auf 0 zieht
- Gaswert bleibt stabil, bis der Pico ihn aendert
- KI kann exakt z.B. 0 bis 128 Stufen setzen

Pico-PWM direkt ist billiger und geht schneller zum Testen, aber es ist elektrisch
mehr ein Trick als ein echter Poti-Ersatz.

## Quellen

- MCP4131: https://www.microchip.com/en-us/product/mcp4131
- MCP413X/415X Datenblatt: https://ww1.microchip.com/downloads/en/devicedoc/22060b.pdf
- MCP41XXX/42XXX Datenblatt: https://ww1.microchip.com/downloads/en/devicedoc/11195c.pdf
- Carrera Wireless 2.0 Controller Info: https://www.amazon.com/Carrera-Wireless-Controller-Digital-Tracks/dp/B0D7W9NW4W
- Hinweis zu Carrera Digital 10k-Poti aus Slotcar-Forum: https://www.hrwforum.com/forum/hrw-all-scales/club-home-connection/carrera-digital-north-america/7362-digital-vs-analog-controller
