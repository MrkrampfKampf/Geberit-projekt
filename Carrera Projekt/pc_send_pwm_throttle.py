from __future__ import annotations

import argparse
import time

import serial
from serial.tools import list_ports


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sendet PWM-Gaswerte an den Pico.")
    parser.add_argument("--port", default="COM3")
    parser.add_argument("--gas", type=int, default=0)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--seconds", type=float, default=1.0)
    parser.add_argument("--list", action="store_true")
    return parser.parse_args()


def list_serial_ports() -> None:
    for port in list_ports.comports():
        print(f"{port.device}: {port.description}")


def read_available(ser: serial.Serial) -> None:
    time.sleep(0.15)
    while ser.in_waiting:
        print(ser.readline().decode("utf-8", errors="replace").strip())


def main() -> None:
    args = parse_args()
    if args.list:
        list_serial_ports()
        return

    gas = max(0, min(100, args.gas))
    with serial.Serial(args.port, baudrate=115200, timeout=1) as ser:
        time.sleep(1.2)
        ser.reset_input_buffer()

        if args.limit is not None:
            limit = max(0, min(100, args.limit))
            print(f"Sende: limit {limit}")
            ser.write(f"limit {limit}\n".encode("ascii"))
            ser.flush()
            read_available(ser)

        print(f"Sende: gas {gas}")
        ser.write(f"gas {gas}\n".encode("ascii"))
        ser.flush()
        read_available(ser)

        time.sleep(args.seconds)

        print("Sende: stop")
        ser.write(b"stop\n")
        ser.flush()
        read_available(ser)


if __name__ == "__main__":
    main()
