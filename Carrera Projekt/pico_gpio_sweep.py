from machine import Pin
import sys
import time


GPIO_PINS = (
    0, 1, 2, 3, 4, 5, 6, 7, 8, 9,
    10, 11, 12, 13, 14, 15, 16, 17,
    18, 19, 20, 21, 22, 26, 27, 28,
)

pins = [Pin(pin, Pin.OUT) for pin in GPIO_PINS]


def all_off():
    for pin in pins:
        pin.value(0)


all_off()
print("PICO_GPIO_SWEEP_READY")
print("commands: sweep | hold GPIO | off")

while True:
    line = sys.stdin.readline()
    if not line:
        time.sleep(0.01)
        continue

    parts = line.strip().lower().split()
    if not parts:
        continue

    if parts[0] == "off":
        all_off()
        print("ok off")
    elif parts[0] == "hold":
        try:
            gpio = int(parts[1])
            all_off()
            Pin(gpio, Pin.OUT).value(1)
            print("ok hold gp", gpio)
        except (IndexError, ValueError):
            print("error expected: hold GPIO")
    elif parts[0] == "sweep":
        for gpio in GPIO_PINS:
            all_off()
            Pin(gpio, Pin.OUT).value(1)
            print("gp", gpio, "on")
            time.sleep(0.8)
        all_off()
        print("ok sweep")
    else:
        print("error unknown command")
