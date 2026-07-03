from machine import Pin
import sys
import time


def make_onboard_led():
    try:
        return Pin("LED", Pin.OUT)
    except TypeError:
        return Pin(25, Pin.OUT)


onboard = make_onboard_led()
external = Pin(14, Pin.OUT)


def set_leds(value):
    onboard.value(value)
    external.value(value)


set_leds(0)
print("PICO_LED_TEST_READY")
print("internal LED and GP14 are controlled together")
print("commands: on | off | blink | fast | status")

while True:
    line = sys.stdin.readline()
    if not line:
        time.sleep(0.01)
        continue

    cmd = line.strip().lower()

    if cmd == "on":
        set_leds(1)
        print("ok on")
    elif cmd == "off":
        set_leds(0)
        print("ok off")
    elif cmd == "blink":
        for _ in range(10):
            set_leds(1)
            time.sleep(0.3)
            set_leds(0)
            time.sleep(0.3)
        print("ok blink")
    elif cmd == "fast":
        for _ in range(30):
            set_leds(1)
            time.sleep(0.05)
            set_leds(0)
            time.sleep(0.05)
        print("ok fast")
    elif cmd == "status":
        print("status onboard_and_gp14", external.value())
    else:
        print("error unknown command")
