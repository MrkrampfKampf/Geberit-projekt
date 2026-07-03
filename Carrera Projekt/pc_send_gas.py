from __future__ import annotations

import argparse
import time

import serial
from serial.tools import list_ports


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sendet Gaswerte an den Raspberry Pi Pico W Servo-Controller."
    )
    parser.add_argument("--port", help="COM-Port, z.B. COM5. Ohne Wert werden Ports gelistet.")
    parser.add_argument("--gas", type=int, default=0, help="Gaswert 0..100.")
    parser.add_argument("--seconds", type=float, default=2.0)
    return parser.parse_args()


def list_serial_ports() -> None:
    ports = list(list_ports.comports())
    if not ports:
        print("Keine seriellen Ports gefunden.")
        return

    for port in ports:
        print(f"{port.device}: {port.description}")


def send(port: str, gas: int, seconds: float) -> None:
    gas = max(0, min(100, gas))
    with serial.Serial(port, baudrate=115200, timeout=1) as ser:
        time.sleep(1.5)
        ser.reset_input_buffer()
        command = f"gas {gas}\n".encode("ascii")
        print(f"Sende an {port}: gas {gas}")
        ser.write(command)
        ser.flush()
        print(ser.readline().decode("utf-8", errors="replace").strip())
        time.sleep(seconds)
        ser.write(b"stop\n")
        ser.flush()
        print(ser.readline().decode("utf-8", errors="replace").strip())


def main() -> None:
    args = parse_args()
    if not args.port:
        list_serial_ports()
        return
    send(args.port, args.gas, args.seconds)


if __name__ == "__main__":
    main()
