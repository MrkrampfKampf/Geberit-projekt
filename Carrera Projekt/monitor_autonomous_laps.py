from __future__ import annotations

import argparse
import contextlib
import csv
import time
from pathlib import Path

from carreralib import ControlUnit
from carreralib.connection import TimeoutError as CarreraTimeout


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Schreibt Rundenzeiten eines Ghost/Autonomous Cars in eine CSV."
    )
    parser.add_argument(
        "device",
        help="COM-Port oder AppConnect-Adresse, z.B. COM3 oder C5:7D:F4:7A:AC:42",
    )
    parser.add_argument(
        "--car",
        type=int,
        default=6,
        help="Autonomous/Ghost Car ist bei carreralib normalerweise Adresse 6.",
    )
    parser.add_argument("--seconds", type=int, default=120)
    parser.add_argument("--min-lap-ms", type=int, default=800)
    parser.add_argument("--output", default="autonomous_laps.csv")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows: list[dict[str, int | str]] = []
    last_timestamp: int | None = None
    lap_number = 0
    started_at = time.monotonic()
    deadline = started_at + args.seconds

    with contextlib.closing(ControlUnit(args.device, timeout=0.5)) as cu:
        print("Verbunden. CU-Version:", cu.version())
        print(f"Hoere {args.seconds} Sekunden auf Timer-Events von Adresse {args.car} ...")

        while time.monotonic() < deadline:
            try:
                msg = cu.poll()
            except CarreraTimeout:
                continue

            if not isinstance(msg, ControlUnit.Timer):
                continue
            if msg.address != args.car or msg.sector != 1:
                continue

            if last_timestamp is None:
                last_timestamp = msg.timestamp
                print(f"Start/Ziel erkannt: {msg.timestamp} ms")
                continue

            lap_ms = msg.timestamp - last_timestamp
            if lap_ms < args.min_lap_ms:
                continue

            last_timestamp = msg.timestamp
            lap_number += 1
            elapsed_s = round(time.monotonic() - started_at, 3)
            rows.append(
                {
                    "lap": lap_number,
                    "lap_ms": lap_ms,
                    "cu_timestamp_ms": msg.timestamp,
                    "elapsed_s": elapsed_s,
                }
            )
            print(f"Runde {lap_number}: {lap_ms} ms")

    out = Path(args.output)
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["lap", "lap_ms", "cu_timestamp_ms", "elapsed_s"],
        )
        writer.writeheader()
        writer.writerows(rows)

    if rows:
        lap_times = [int(row["lap_ms"]) for row in rows]
        best = min(lap_times)
        avg = round(sum(lap_times) / len(lap_times))
        print(f"Beste Runde: {best} ms")
        print(f"Durchschnitt: {avg} ms")
    else:
        print("Keine vollstaendige Runde erkannt.")

    print(f"CSV gespeichert: {out.resolve()}")


if __name__ == "__main__":
    main()
