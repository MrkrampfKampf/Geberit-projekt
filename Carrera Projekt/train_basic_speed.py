from __future__ import annotations

import argparse
import contextlib
import csv
import statistics
import time
from dataclasses import dataclass
from pathlib import Path

try:
    from carreralib import ControlUnit
    from carreralib.connection import TimeoutError as CarreraTimeout
except ModuleNotFoundError as exc:
    raise SystemExit(
        "carreralib fehlt. Installiere zuerst die Abhaengigkeiten mit:\n"
        "  python -m pip install -r requirements.txt"
    ) from exc


@dataclass
class SpeedResult:
    speed: int
    status: str
    laps_ms: list[int]
    score_ms: int | None = None


def validate_speed_range(min_speed: int, max_speed: int) -> None:
    if min_speed < 0 or max_speed > 15:
        raise SystemExit("Speed-Werte muessen zwischen 0 und 15 liegen.")
    if min_speed > max_speed:
        raise SystemExit("--min-speed darf nicht groesser als --max-speed sein.")


def collect_laps(
    cu: ControlUnit,
    car_addr: int,
    laps: int,
    timeout_s: float,
    min_lap_ms: int,
) -> list[int] | None:
    """Collect lap times from start/finish timer events for one car."""
    timestamps: list[int] = []
    last_key: tuple[int, int, int] | None = None
    deadline = time.monotonic() + timeout_s

    while len(timestamps) < laps + 1:
        if time.monotonic() > deadline:
            return None

        try:
            msg = cu.poll()
        except CarreraTimeout:
            continue

        if not isinstance(msg, ControlUnit.Timer):
            continue
        if msg.address != car_addr or msg.sector != 1:
            continue

        key = (msg.address, msg.timestamp, msg.sector)
        if key == last_key:
            continue

        if timestamps and msg.timestamp - timestamps[-1] < min_lap_ms:
            continue

        last_key = key
        timestamps.append(msg.timestamp)
        print(f"  Durchfahrt {len(timestamps)}: {msg.timestamp} ms")
        deadline = time.monotonic() + timeout_s

    return [timestamps[i] - timestamps[i - 1] for i in range(1, len(timestamps))]


def score_laps(lap_times: list[int]) -> int:
    scoring_laps = lap_times[1:] if len(lap_times) > 1 else lap_times
    return round(statistics.median(scoring_laps))


def write_results(path: Path, rows: list[SpeedResult]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["speed", "status", "laps_ms", "score_ms"],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "speed": row.speed,
                    "status": row.status,
                    "laps_ms": ";".join(str(value) for value in row.laps_ms),
                    "score_ms": "" if row.score_ms is None else row.score_ms,
                }
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Testet Carrera-Speed-Stufen und findet die schnellste stabile "
            "Stufe anhand der Rundenzeiten."
        )
    )
    parser.add_argument(
        "device",
        help="COM-Port oder AppConnect-Adresse, z.B. COM3 oder C6:34:FA:1D:1D:5D",
    )
    parser.add_argument(
        "--car",
        type=int,
        default=0,
        help="carreralib-Adresse: Controller 1 = 0, Controller 2 = 1",
    )
    parser.add_argument("--min-speed", type=int, default=3)
    parser.add_argument("--max-speed", type=int, default=10)
    parser.add_argument("--laps", type=int, default=4, help="Runden pro Speed-Test")
    parser.add_argument(
        "--timeout",
        type=float,
        default=12.0,
        help="Sekunden ohne neue Runde = Crash/Timeout",
    )
    parser.add_argument(
        "--min-lap-ms",
        type=int,
        default=800,
        help="Ignoriert unrealistisch kurze doppelte Timer-Events.",
    )
    parser.add_argument(
        "--start",
        action="store_true",
        help="Startet vor jedem Test die CU-Startsequenz per Software.",
    )
    parser.add_argument(
        "--output",
        default="carrera_speed_results.csv",
        help="CSV-Datei fuer die Ergebnisse.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    validate_speed_range(args.min_speed, args.max_speed)

    rows: list[SpeedResult] = []

    with contextlib.closing(ControlUnit(args.device, timeout=0.3)) as cu:
        print("Verbunden. CU-Version:", cu.version())
        print()
        print("Vorbereitung:")
        print("- Nur ein Testauto auf der Bahn.")
        print("- Auto auf Controller 1 codieren, wenn --car 0 verwendet wird.")
        print("- Fuel an der Control Unit fuer den ersten Test auf OFF stellen.")
        print("- Auto vor Start/Ziel stellen und den Controller auf Vollgas halten.")

        for speed in range(args.min_speed, args.max_speed + 1):
            input(
                f"\nSpeed-Stufe {speed}: Auto vor Start/Ziel stellen, "
                "dann Enter druecken..."
            )

            print(f"Setze Speed-Stufe {speed} ...")
            cu.setspeed(args.car, speed)
            time.sleep(0.4)

            cu.reset()
            time.sleep(0.2)
            if args.start:
                cu.start()
                time.sleep(0.2)

            print("Jetzt fahren lassen. Warte auf Runden...")
            lap_times = collect_laps(
                cu=cu,
                car_addr=args.car,
                laps=args.laps,
                timeout_s=args.timeout,
                min_lap_ms=args.min_lap_ms,
            )

            if lap_times is None:
                print(f"  Ergebnis Speed {speed}: Crash/Timeout")
                rows.append(SpeedResult(speed=speed, status="crash_or_timeout", laps_ms=[]))
            else:
                score = score_laps(lap_times)
                print(f"  Rundenzeiten: {lap_times}")
                print(f"  Score, Median ohne erste Runde: {score} ms")
                rows.append(
                    SpeedResult(
                        speed=speed,
                        status="ok",
                        laps_ms=lap_times,
                        score_ms=score,
                    )
                )

            input("Auto stoppen/zuruecksetzen, dann Enter fuer die naechste Stufe...")

    out = Path(args.output)
    write_results(out, rows)

    ok_results = [row for row in rows if row.status == "ok" and row.score_ms is not None]
    print("\n--- Ergebnis ---")
    if ok_results:
        best = min(ok_results, key=lambda row: row.score_ms or 999999999)
        print(
            f"Beste stabile Speed-Stufe: {best.speed} "
            f"mit ca. {best.score_ms} ms Median"
        )
    else:
        print("Keine stabile Stufe gefunden. Versucht z.B. --min-speed 1 --max-speed 6.")

    print(f"CSV gespeichert: {out.resolve()}")


if __name__ == "__main__":
    main()
