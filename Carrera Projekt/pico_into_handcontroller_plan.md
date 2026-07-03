# Pico W im Carrera-Handregler

Ziel:

```text
PC/KI -> Pico W -> echter Carrera-Handregler -> Wireless-Empfaenger -> Control Unit -> Auto
```

Der Handregler funkt weiter selbst. Der Pico ersetzt nur die elektrischen
Signale, die normalerweise vom Gashebel und optional von der Weichentaste kommen.

## Online-Fundlage

- Carrera Wireless 2.0 ist ein 2,4-GHz-System mit Frequenzhopping und nur fuer
  Carrera DIGITAL 124/132 gedacht. Der Handregler nutzt eine AAA-Zelle.
- Carrera Wireless+ Handregler/Empfaenger sind 2,4-GHz-Funktechnik und fuer bis
  zu 6 Fahrer ausgelegt.
- Ein Slotcar-Forum erwaehnt beim Carrera Wireless+ Handregler konkret ein
  ausgelötetes und durchgemessenes `Poti`. Das spricht dafuer, dass der Gashebel
  intern als Potentiometer/Analoggeber arbeitet.
- Ersatzteilshops listen fuer Wireless-Handregler einen
  `Geschwindigkeitshebel` und Reparaturen fuer den `Weichenschalter`. Das passt
  zum erwarteten Aufbau: Gashebel-Sensor plus separate Spurwechsel-Taste.
- Laser Drift zeigt, dass virtuelle Carrera-Controller prinzipiell moeglich
  sind, unterstuetzt aber nur alte IR-Controller und nicht 2,4-GHz Wireless+.

## Wahrscheinliche Anschlusspunkte im Handregler

Ohne Fotos/Messung kann man keine Pins sicher benennen. Die sinnvollen Stellen
sind aber:

### 1. Gashebel-Poti / Analoggeber

Gesuchte Anschluesse:

```text
Poti-Ende A  -> Versorgung oder GND
Poti-Ende B  -> GND oder Versorgung
Poti-Wischer -> Gas-Signal zum Mikrocontroller des Handreglers
```

Messung:

```text
Trigger losgelassen: Signalspannung messen
Trigger halb:        Signalspannung messen
Trigger voll:        Signalspannung messen
```

Wenn das Signal analog ist, gibt es zwei moegliche Pico-Ankopplungen:

- Digital-Potentiometer ersetzt das echte Poti.
- Pico-PWM plus Tiefpass erzeugt eine analoge Spannung.

Der sichere Start ist ein Digital-Poti oder ein hochohmiges Einspeisen ueber
Schutzwiderstand, nicht direkt ein Pico-GPIO an den Wischer.

### 2. Spurwechsel-Taste

Gesuchte Anschluesse:

```text
Taste Seite 1
Taste Seite 2
```

Messung:

```text
Taste offen:     Widerstand/Spannung messen
Taste gedrueckt: Widerstand/Spannung messen
```

Wenn die Taste nur zwei Kontakte kurzschliesst, kann der Pico spaeter mit einem
Optokoppler oder kleinem MOSFET parallel zur Taste schalten.

### 3. Masse / GND

GND findet man meistens am Minuspol der Batterie. Vor einer Verbindung mit dem
Pico muss gemessen werden:

```text
Handregler-Batterie-Minus -> GND
Pico-GND darf nur mit Controller-GND verbunden werden, wenn die Spannungen sicher sind.
```

### 4. Versorgung

Wireless 2.0 nutzt laut Anleitung eine AAA-Zelle. Wireless+ 10111 nutzt einen
LiPo-Akku. Den Pico sollten wir anfangs trotzdem nicht aus dem Handregler
versorgen.

Empfehlung:

```text
Pico bleibt per USB am PC.
Handregler bleibt mit eigener Batterie/Akku.
Nur GND/Signal verbinden, nachdem GND sicher gemessen wurde.
```

## No-Solder-Prototyp

Falls nicht geloetet werden darf:

- Mini-Grabber/Testclips an Poti-Beinchen oder Testpads
- Pogo-Pins auf Pads mit mechanischer Halterung
- Krokodilklemmen nur fuer grosse Kontakte wie Batterie-GND

Fuer dauerhaftes Fahren ist Loeten deutlich zuverlaessiger.

## Was wir als naechstes brauchen

1. Handregler-Modell klaeren: Wireless+ 10111 oder Wireless 2.0 10121.
2. Fotos vom geoeffneten Handregler:
   - ganze Platine
   - Gashebel-Bereich
   - Weichentaste
   - Akku/Batterieanschluss
3. Multimeter-Messwerte:
   - Batteriespannung
   - GND
   - Gas-Signal bei los/halb/voll
   - Tasten-Kontakte offen/gedrueckt

Erst danach koennen wir sicher sagen, ob der Pico per Digital-Poti, PWM-Analog
oder Schalttransistor angeschlossen wird.

## Kein Multimeter vorhanden: Pico als Voltmeter

Wenn kein Multimeter da ist, kann der Pico selbst als einfaches DC-Voltmeter
genutzt werden. Dafuer darf ein unbekannter Controller-Pin aber nicht direkt an
den Pico-ADC. Es braucht einen Schutz-Spannungsteiler:

```text
Messpunkt am Handregler -> 220k -> Pico GP26/ADC0 -> 100k -> Pico GND
Pico GND -> Batterie-Minus des Handreglers
```

Dann starten:

```powershell
.\start_pico_voltmeter.ps1
```

Das Skript `pico_voltmeter.py` rechnet den Spannungsteiler ein und zeigt
`input_v` als geschaetzte Spannung am Messpunkt.

Falls keine 220k/100k vorhanden sind, gehen als Notloesung auch 100k/100k oder
10k/4.7k. Hohe Werte sind besser, weil sie den Handregler weniger beeinflussen.

## Befund am geoeffneten Wireless-2.0-Handregler

Auf den Fotos vom 2026-07-01 ist Folgendes erkennbar:

- `R1` ist der lange Schieberegler am Gashebel. Das ist sehr wahrscheinlich
  das Gas-Potentiometer bzw. der analoge Gasgeber.
- `S2` sitzt oben beim kleinen Taster. Das ist sehr wahrscheinlich die
  Spurwechsel-/Set-/Funktionstaste.
- `B+` ist auf der Platine direkt am roten Batteriekabel markiert.
- Batterie-Minus liegt am Federkontakt des AAA-Batteriefachs und ist der
  wahrscheinlichste GND-Bezugspunkt.
- Auf der Rueckseite ist eine kleine Elektronik mit Spule `L4` und IC sichtbar.
  Das spricht dafuer, dass aus der AAA-Zelle intern eine hoehere stabile
  Versorgung erzeugt wird. Deshalb duerfen Pico-GPIOs nicht blind an R1/S2.

### Naechster Messplan fuer R1

Mit Batterie herausgenommen, Multimeter auf Ohm:

1. Widerstand zwischen den beiden aeusseren elektrischen Anschluessen von `R1`
   messen.
2. Widerstand zwischen mittlerem Anschluss/Wischer und Anschluss A messen:
   - Gas losgelassen
   - Gas halb gedrueckt
   - Gas voll gedrueckt
3. Widerstand zwischen Wischer und Anschluss B genauso messen.

Mit Batterie eingesetzt, Multimeter auf DC-Volt:

1. Schwarze Messspitze an Batterie-Minus/GND.
2. Spannung an den drei `R1`-Anschluessen messen:
   - Gas losgelassen
   - Gas halb gedrueckt
   - Gas voll gedrueckt

Erwartung:

```text
Ein R1-Anschluss bleibt nahe GND.
Ein R1-Anschluss bleibt auf einer festen Referenzspannung.
Der Wischer veraendert sich mit dem Gashebel.
```

Nur dieser Wischer ist spaeter das relevante Gas-Signal.

### Wahrscheinlich beste Ankopplung

Wenn `R1` ein normales Potentiometer ist, ist die sauberste Pico-Loesung:

```text
Pico -> SPI/I2C Digital-Potentiometer -> ersetzt/parallelisiert R1-Signal
```

Ein direkter Pico-PWM-Ausgang an den Wischer ist erst nach Spannungsmessung
vertretbar und braucht mindestens Schutzwiderstand und Tiefpass.
