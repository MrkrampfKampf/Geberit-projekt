from __future__ import annotations

import argparse
import csv
import time
from pathlib import Path

import cv2

from track_dual_cars_live import draw_car, find_car, track_mask


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Nimmt Auto-Positionen ohne GUI-Fenster auf.")
    parser.add_argument("--camera", type=int, default=1)
    parser.add_argument("--seconds", type=float, default=30.0)
    parser.add_argument("--output", default="dual_car_positions.csv")
    parser.add_argument("--snapshot", default="dual_record_last_frame.jpg")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cap = cv2.VideoCapture(args.camera, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    if not cap.isOpened():
        raise SystemExit(f"Kamera {args.camera} konnte nicht geoeffnet werden.")

    previous: dict[str, tuple[int, int] | None] = {"orange": None, "cyan": None}
    rows: list[dict[str, int | float | str]] = []
    counts = {"orange": 0, "cyan": 0}
    started_at = time.monotonic()
    deadline = started_at + args.seconds
    last_frame = None

    print(f"Aufnahme startet fuer {args.seconds:.0f} Sekunden. Orange Auto jetzt fahren lassen.")

    try:
        while time.monotonic() < deadline:
            ok, frame = cap.read()
            if not ok:
                continue

            road = track_mask(frame)
            detections = {}
            candidates_by_color = {}
            for color_name in ("orange", "cyan"):
                car, _mask, candidates = find_car(
                    frame,
                    color_name,
                    previous[color_name],
                    road,
                    min_area=120,
                    max_area=3500,
                    min_center_y=100,
                    max_center_y=560,
                    min_track_ratio=0.35,
                )
                detections[color_name] = car
                candidates_by_color[color_name] = candidates
                if car is not None:
                    previous[color_name] = car["center"]
                    counts[color_name] += 1

            now = time.monotonic() - started_at
            for color_name, car in detections.items():
                if car is None:
                    continue
                cx, cy = car["center"]
                rows.append(
                    {
                        "time_s": round(now, 3),
                        "car": color_name,
                        "x": cx,
                        "y": cy,
                        "area": round(car["area"], 1),
                    }
                )

            for color_name in ("orange", "cyan"):
                draw_car(frame, color_name, detections[color_name], candidates_by_color[color_name])
            last_frame = frame
    finally:
        cap.release()

    out = Path(args.output)
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["time_s", "car", "x", "y", "area"])
        writer.writeheader()
        writer.writerows(rows)

    if last_frame is not None:
        cv2.imwrite(args.snapshot, last_frame)

    print("Aufnahme fertig.")
    print("Erkannte Positionen:", counts)
    print(f"CSV gespeichert: {out.resolve()}")
    print(f"Letztes Kontrollbild: {Path(args.snapshot).resolve()}")


if __name__ == "__main__":
    main()
