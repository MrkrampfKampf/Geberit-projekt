from __future__ import annotations

import argparse
import time

import serial
from serial.tools import list_ports


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sendet LED-Testbefehle an den Pico.")
    parser.add_argument("--port", default="COM3")
    parser.add_argument("--cmd", default="blink")
    parser.add_argument("--wait", type=float, default=7.0)
    parser.add_argument("--list", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.list:
        for port in list_ports.comports():
            print(f"{port.device}: {port.description}")
        return

    with serial.Serial(args.port, baudrate=115200, timeout=1) as ser:
        time.sleep(1.2)
        ser.reset_input_buffer()
        print(f"Sende: {args.cmd}")
        ser.write((args.cmd.strip() + "\n").encode("ascii"))
        ser.flush()
        time.sleep(args.wait)
        while ser.in_waiting:
            print(ser.readline().decode("utf-8", errors="replace").strip())


if __name__ == "__main__":
    main()
