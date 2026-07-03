from __future__ import annotations

import argparse
import csv
import math
import time
from pathlib import Path

import cv2

from analyze_track_positions import SECTION_COLORS, section_for
from track_dual_cars_live import draw_car, find_car, track_mask


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Live-Monitor fuer orange Auto: Position, Abschnitt, Bildgeschwindigkeit."
    )
    parser.add_argument("--camera", type=int, default=1)
    parser.add_argument("--seconds", type=float, default=60.0)
    parser.add_argument("--output", default="orange_section_live.csv")
    parser.add_argument("--no-gui", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cap = cv2.VideoCapture(args.camera, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    if not cap.isOpened():
        raise SystemExit(f"Kamera {args.camera} konnte nicht geoeffnet werden.")

    rows: list[dict[str, int | float | str]] = []
    previous_center: tuple[int, int] | None = None
    previous_time: float | None = None
    previous_detection: tuple[int, int] | None = None
    started_at = time.monotonic()
    deadline = started_at + args.seconds
    last_printed_section = None
    last_print_time = 0.0

    print(f"Live-Monitor laeuft fuer {args.seconds:.0f} Sekunden.")
    print("q = beenden, wenn GUI sichtbar ist")

    try:
        while time.monotonic() < deadline:
            ok, frame = cap.read()
            if not ok:
                continue

            now = time.monotonic()
            elapsed = now - started_at
            road = track_mask(frame)
            car, _mask, candidates = find_car(
                frame,
                "orange",
                previous_detection,
                road,
                min_area=120,
                max_area=3500,
                min_center_y=100,
                max_center_y=560,
                min_track_ratio=0.35,
            )

            section = "not_found"
            speed_px_s = 0.0
            if car is not None:
                cx, cy = car["center"]
                previous_detection = (cx, cy)
                section = section_for(cx, cy)

                if previous_center is not None and previous_time is not None:
                    dt = now - previous_time
                    if dt > 0:
                        speed_px_s = math.hypot(cx - previous_center[0], cy - previous_center[1]) / dt

                previous_center = (cx, cy)
                previous_time = now
                rows.append(
                    {
                        "time_s": round(elapsed, 3),
                        "x": cx,
                        "y": cy,
                        "section": section,
                        "speed_px_s": round(speed_px_s, 1),
                    }
                )

            if section != last_printed_section or now - last_print_time > 2.0:
                print(f"{elapsed:6.2f}s  section={section:15s} speed={speed_px_s:7.1f}px/s")
                last_printed_section = section
                last_print_time = now

            if not args.no_gui:
                if car is not None:
                    draw_car(frame, "orange", car, candidates)
                    color = SECTION_COLORS.get(section, (255, 255, 255))
                    cv2.putText(
                        frame,
                        f"section={section} speed={speed_px_s:.0f}px/s",
                        (20, 42),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.8,
                        color,
                        2,
                    )
                else:
                    cv2.putText(
                        frame,
                        "orange not found",
                        (20, 42),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.8,
                        (0, 0, 255),
                        2,
                    )

                cv2.imshow("orange section monitor", frame)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    break
    finally:
        cap.release()
        if not args.no_gui:
            cv2.destroyAllWindows()

    out = Path(args.output)
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["time_s", "x", "y", "section", "speed_px_s"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Live-Daten gespeichert: {out.resolve()}")


if __name__ == "__main__":
    main()
