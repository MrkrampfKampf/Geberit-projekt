from machine import Pin, PWM
import sys
import time


SERVO_PIN = 15
MIN_US = 1000
MAX_US = 2000
FREQ = 50


pwm = PWM(Pin(SERVO_PIN))
pwm.freq(FREQ)


def set_servo_percent(percent):
    percent = max(0, min(100, int(percent)))
    pulse_us = MIN_US + (MAX_US - MIN_US) * percent / 100
    duty = int(pulse_us * 65535 / 20000)
    pwm.duty_u16(duty)
    return percent, int(pulse_us)


set_servo_percent(0)
print("PICO_SERVO_READY pin=15 range=0..100")

while True:
    line = sys.stdin.readline()
    if not line:
        time.sleep(0.01)
        continue

    line = line.strip().lower()
    if line in ("?", "help"):
        print("commands: gas 0..100 | center | stop")
        continue

    if line == "stop":
        percent, pulse_us = set_servo_percent(0)
        print("ok gas", percent, "pulse_us", pulse_us)
        continue

    if line == "center":
        percent, pulse_us = set_servo_percent(50)
        print("ok gas", percent, "pulse_us", pulse_us)
        continue

    if line.startswith("gas "):
        try:
            value = int(line.split()[1])
        except (IndexError, ValueError):
            print("error expected: gas 0..100")
            continue
        percent, pulse_us = set_servo_percent(value)
        print("ok gas", percent, "pulse_us", pulse_us)
        continue

    print("error unknown command")
