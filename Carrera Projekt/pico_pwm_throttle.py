from machine import Pin, PWM
import sys
import time


# GP15 -> RC-Tiefpass -> Schutzwiderstand -> R1-Wischer/Controller-Gassignal
PWM_PIN = 15
PWM_FREQ = 20_000

pwm = PWM(Pin(PWM_PIN))
pwm.freq(PWM_FREQ)

limit_percent = 100
current_percent = 0


def set_pwm(percent):
    global current_percent
    percent = max(0, min(100, int(percent)))
    limited = round(percent * limit_percent / 100)
    duty = round(limited * 65535 / 100)
    pwm.duty_u16(duty)
    current_percent = percent
    print("ok gas", percent, "limited", limited, "duty", duty)


set_pwm(0)
print("PICO_PWM_THROTTLE_READY pin=GP15 freq=20000Hz")
print("commands: gas 0..100 | limit 0..100 | stop | status")

while True:
    line = sys.stdin.readline()
    if not line:
        time.sleep(0.01)
        continue

    line = line.strip().lower()
    if line in ("?", "help"):
        print("commands: gas 0..100 | limit 0..100 | stop | status")
        continue

    if line == "stop":
        set_pwm(0)
        continue

    if line == "status":
        print("status gas", current_percent, "limit", limit_percent, "pin", PWM_PIN)
        continue

    if line.startswith("limit "):
        try:
            limit_percent = max(0, min(100, int(line.split()[1])))
        except (IndexError, ValueError):
            print("error expected: limit 0..100")
            continue
        set_pwm(current_percent)
        continue

    if line.startswith("gas "):
        try:
            value = int(line.split()[1])
        except (IndexError, ValueError):
            print("error expected: gas 0..100")
            continue
        set_pwm(value)
        continue

    print("error unknown command")
