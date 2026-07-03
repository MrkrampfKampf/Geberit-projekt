from __future__ import annotations

import argparse
import time

import serial
from serial.tools import list_ports


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sendet Stepper-Befehle an den Pico.")
    parser.add_argument("--port", default="COM3")
    parser.add_argument("--cmd", default="status")
    parser.add_argument(
        "--sequence",
        default="",
        help="Mehrere Befehle in einer Verbindung, getrennt mit Semikolon.",
    )
    parser.add_argument("--wait", type=float, default=0.5)
    parser.add_argument("--list", action="store_true")
    return parser.parse_args()


def list_serial_ports() -> None:
    for port in list_ports.comports():
        print(f"{port.device}: {port.description}")


def read_available(ser: serial.Serial, wait: float = 0.25) -> None:
    time.sleep(wait)
    while ser.in_waiting:
        print(ser.readline().decode("utf-8", errors="replace").strip())


def main() -> None:
    args = parse_args()
    if args.list:
        list_serial_ports()
        return

    commands = [args.cmd]
    if args.sequence:
        commands = [item.strip() for item in args.sequence.split(";") if item.strip()]

    with serial.Serial(args.port, baudrate=115200, timeout=1) as ser:
        time.sleep(1.2)
        ser.reset_input_buffer()
        for command in commands:
            print(f"Sende: {command}")
            ser.write((command + "\n").encode("ascii"))
            ser.flush()
            read_available(ser, wait=args.wait)


if __name__ == "__main__":
    main()
