from machine import Pin
import sys
import time


# 28BYJ-48 stepper via ULN2003 board.
# Wiring:
#   Pico GP18 -> INA/IN1
#   Pico GP19 -> INB/IN2
#   Pico GP20 -> INC/IN3
#   Pico GP21 -> IND/IN4
#   Pico GND  -> ULN2003 GND
#   5V supply -> ULN2003 +5V
PIN_NUMBERS = (18, 19, 20, 21)

HALF_STEP_SEQUENCE = (
    (1, 0, 0, 0),
    (1, 1, 0, 0),
    (0, 1, 0, 0),
    (0, 1, 1, 0),
    (0, 0, 1, 0),
    (0, 0, 1, 1),
    (0, 0, 0, 1),
    (1, 0, 0, 1),
)

pins = [Pin(pin, Pin.OUT) for pin in PIN_NUMBERS]
step_index = 0
position_steps = 0
range_steps = 290
delay_us = 1500
inverted = False
gas_direction = -1  # +1 = cw increases gas, -1 = ccw increases gas


def write_phase(phase):
    for pin, value in zip(pins, phase):
        pin.value(value)


def release():
    write_phase((0, 0, 0, 0))


def one_step(direction):
    global step_index, position_steps
    if inverted:
        direction = -direction
    step_index = (step_index + direction) % len(HALF_STEP_SEQUENCE)
    write_phase(HALF_STEP_SEQUENCE[step_index])
    position_steps += direction
    time.sleep_us(delay_us)


def hold_position():
    write_phase(HALF_STEP_SEQUENCE[step_index])


def move_steps(steps, hold=False):
    direction = 1 if steps >= 0 else -1
    for _ in range(abs(int(steps))):
        one_step(direction)
    if hold:
        hold_position()
    else:
        release()
    print("ok pos", position_steps)


def set_gas(percent):
    global position_steps
    percent = max(0, min(100, int(percent)))
    target = round(gas_direction * range_steps * percent / 100)
    move_steps(target - position_steps, hold=True)
    print("ok gas", percent, "target", target, "pos", position_steps)


def print_help():
    print("commands:")
    print("  cw STEPS        move clockwise")
    print("  ccw STEPS       move counter-clockwise")
    print("  move STEPS      relative move, negative allowed")
    print("  gas 0..100      move to percent of calibrated range")
    print("                 gas commands keep motor holding position")
    print("  gasdir cw|ccw   set direction that increases gas")
    print("  range STEPS     set 100 percent range")
    print("  zero            set current position as 0")
    print("  speed US        set delay per half-step, e.g. 1500")
    print("  spin SECONDS    spin clockwise for a duration")
    print("  spinccw SECONDS spin counter-clockwise for a duration")
    print("  wiggle SECONDS STEPS  repeat right/left movements")
    print("  invert 0|1      reverse direction")
    print("  release         coils off")
    print("  testpins        light IN1..IN4 one after another")
    print("  hold            turn all outputs on for 3 seconds")
    print("  status          print state")


release()
print("PICO_STEPPER_SLIDER_READY pins=GP18,GP19,GP20,GP21")
print_help()

while True:
    line = sys.stdin.readline()
    if not line:
        time.sleep(0.01)
        continue

    parts = line.strip().lower().split()
    if not parts:
        continue

    command = parts[0]

    try:
        if command in ("?", "help"):
            print_help()
        elif command == "cw":
            move_steps(int(parts[1]))
        elif command == "ccw":
            move_steps(-int(parts[1]))
        elif command == "move":
            move_steps(int(parts[1]))
        elif command == "gas":
            set_gas(int(parts[1]))
        elif command == "gasdir":
            value = parts[1]
            if value == "cw":
                gas_direction = 1
            elif value == "ccw":
                gas_direction = -1
            else:
                print("error expected: gasdir cw|ccw")
                continue
            print("ok gasdir", value)
        elif command == "range":
            range_steps = max(1, int(parts[1]))
            print("ok range", range_steps)
        elif command == "zero":
            position_steps = 0
            print("ok zero")
        elif command == "speed":
            delay_us = max(100, int(parts[1]))
            print("ok speed", delay_us)
        elif command == "spin":
            seconds = max(0, float(parts[1]))
            end_time = time.ticks_add(time.ticks_ms(), int(seconds * 1000))
            while time.ticks_diff(end_time, time.ticks_ms()) > 0:
                one_step(1)
            release()
            print("ok spin", seconds, "pos", position_steps)
        elif command == "spinccw":
            seconds = max(0, float(parts[1]))
            end_time = time.ticks_add(time.ticks_ms(), int(seconds * 1000))
            while time.ticks_diff(end_time, time.ticks_ms()) > 0:
                one_step(-1)
            release()
            print("ok spinccw", seconds, "pos", position_steps)
        elif command == "wiggle":
            seconds = max(0, float(parts[1]))
            steps = max(1, int(parts[2])) if len(parts) > 2 else 512
            end_time = time.ticks_add(time.ticks_ms(), int(seconds * 1000))
            cycles = 0
            while time.ticks_diff(end_time, time.ticks_ms()) > 0:
                for _ in range(steps):
                    if time.ticks_diff(end_time, time.ticks_ms()) <= 0:
                        break
                    one_step(1)
                for _ in range(steps):
                    if time.ticks_diff(end_time, time.ticks_ms()) <= 0:
                        break
                    one_step(-1)
                cycles += 1
            release()
            print("ok wiggle", seconds, "steps", steps, "cycles", cycles, "pos", position_steps)
        elif command == "invert":
            inverted = bool(int(parts[1]))
            print("ok invert", int(inverted))
        elif command == "release":
            release()
            print("ok release")
        elif command == "testpins":
            for index, pin in enumerate(pins, start=1):
                release()
                pin.value(1)
                print("pin", index, "on")
                time.sleep(1)
            release()
            print("ok testpins")
        elif command == "hold":
            write_phase((1, 1, 1, 1))
            print("ok hold on")
            time.sleep(3)
            release()
            print("ok hold off")
        elif command == "status":
            print(
                "status pos",
                position_steps,
                "range",
                range_steps,
                "speed",
                delay_us,
                "invert",
                int(inverted),
                "gasdir",
                "cw" if gas_direction > 0 else "ccw",
            )
        else:
            print("error unknown command")
    except (IndexError, ValueError):
        print("error bad command")
