# Virtueller Carrera-Handregler

Ziel:

```text
PC/KI -> virtueller Handregler -> Carrera Wireless+ Empfaenger -> Control Unit -> Auto
```

## Ergebnis der Recherche

### 1. AppConnect kann keinen Live-Handregler emulieren

Unsere installierte `carreralib` kann Speed-/Brake-/Fuel-Grundeinstellungen,
Start/Reset/CODE und Timer-Events. Es gibt aber keinen Live-Befehl wie
`gas 60%` oder `lanechange`.

AppConnect bleibt also gut fuer:

- Rundenzeiten
- Start/Reset
- Fahrzeug-Grundeinstellungen
- Datenlogging

Aber nicht fuer:

- echten Gasfinger in Echtzeit

### 2. Laser Drift existiert, aber nur fuer alte IR-Wireless-Controller

Projekt:

https://github.com/buntine/laser-drift

Das Projekt kann Carrera Digital 132/124 per Software steuern und nimmt
TCP-Befehle wie `p0s8` fuer Speed oder `p0l1` fuer Lane Change.

Wichtig: Laut README wird nur der aeltere Infrarot-Wireless-Tower emuliert.
Modernes 2.4-GHz Wireless+ wird dort ausdruecklich nicht unterstuetzt.

Fazit: Sehr interessant als Vorlage, aber nicht direkt mit unseren
Wireless+/Wireless-2.0-Empfaengern nutzbar.

### 3. Wireless+ wurde offenbar schon reverse-engineered, aber nicht offen genug

In Slotcar-Foren gibt es Hinweise, dass Bastler Carrera Wireless+ mit
Arduino/nRF24L01+ erfolgreich emuliert haben. Ein Beitrag nennt explizit,
dass ein Arduino-basierter Transceiver direkt mit dem Carrera Wireless+
Empfaenger gesprochen hat.

Ein anderer Beitrag fragt nach `nRF24L01+`-Details wie Channel und Address.
Das deutet stark darauf hin, dass Wireless+ technisch in diese Richtung geht.

Aber: Ich habe keinen kompletten, direkt nutzbaren Open-Source-Code mit
Channel/Adresse/Payload/CRC/Handshake fuer Carrera Wireless+ gefunden.

### 4. Wireless+ und Wireless 2.0 sind nicht kompatibel

Carrera beschreibt, dass Wireless 2.0 Controller nur mit Wireless 2.0
Receiver funktionieren und alte Wireless+ Controller nur mit Wireless+
Receiver. Parallelbetrieb ist moeglich, aber die Fahrzeugadressen duerfen
nicht doppelt vergeben werden.

Das bedeutet: Wir muessen genau wissen, welchen Empfaenger wir emulieren
wollen: Wireless+ oder Wireless 2.0.

## Was wir fuer echte Wireless-Emulation brauchen

Der Pico W alleine reicht sehr wahrscheinlich nicht, weil sein Funkteil nur
Wi-Fi/Bluetooth kann und nicht beliebige Carrera-2.4-GHz-Pakete senden kann.

Realistische Hardware:

- Pico W oder Arduino als Steuer-MCU
- externes `nRF24L01+` Funkmodul
- Logic Analyzer oder SDR/Sniffer zum Reverse Engineering
- RF24-Bibliothek oder eigener nRF24-Treiber

Minimaler Forschungsweg:

1. Herausfinden, welcher Empfaenger aktiv ist: Wireless+ oder Wireless 2.0.
2. Falls Wireless+: nRF24L01+ Modul besorgen.
3. Versuchen, Wireless+-Pakete zu sniffen:
   - Channel/Frequenz
   - Adresse/Pipe
   - Payload-Laenge
   - Speed-Wert
   - Lane-Change-Bit
   - Pairing/Channel-ID
4. Danach Pico/Arduino als Sender programmieren.
5. Erst mit niedriger Sendeleistung und nur an unserer eigenen Bahn testen.

## Praktische Bewertung

Schnell nutzbar:

- AppConnect + Kamera + Ghost-Car
- Pico als Servo/Controller-Innensteuerung

Moeglich, aber Forschungsprojekt:

- Wireless+ Empfaenger direkt per nRF24L01+ emulieren

Nicht direkt moeglich:

- Pico W alleine als Wireless+ Controller
- AppConnect als Live-Gascontroller

## Empfehlung

Wenn wir unbedingt ohne Oeffnen des Handreglers und ohne Servo arbeiten wollen,
ist die naechste sinnvolle Hardware:

```text
2x nRF24L01+ Modul
1x Logic Analyzer oder SDR/Sniffer
Jumper-Kabel
Breadboard
```

Dann starten wir ein eigenes Reverse-Engineering-Projekt fuer Wireless+.
Das kann funktionieren, ist aber deutlich mehr Aufwand als die bisherige
Kamera/Pico-Software.

Wenn wir den echten Handregler doch nutzen duerfen, ist der praktischere Plan in
`pico_into_handcontroller_plan.md` beschrieben.
