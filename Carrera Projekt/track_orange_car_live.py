from __future__ import annotations

import argparse
import csv
import time
from pathlib import Path

import cv2
import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Trackt das orange Auto auf der Bahn.")
    parser.add_argument("--camera", type=int, default=1)
    parser.add_argument("--output", default="orange_car_positions.csv")
    parser.add_argument("--min-area", type=float, default=250)
    parser.add_argument("--max-area", type=float, default=3500)
    parser.add_argument("--min-center-y", type=int, default=130)
    parser.add_argument("--max-center-y", type=int, default=540)
    parser.add_argument("--min-track-ratio", type=float, default=0.5)
    return parser.parse_args()


def orange_mask(frame: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    ranges = [
        (np.array([0, 70, 50]), np.array([28, 255, 255])),
        (np.array([165, 70, 50]), np.array([179, 255, 255])),
    ]
    mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
    for lower, upper in ranges:
        mask |= cv2.inRange(hsv, lower, upper)
    mask = cv2.medianBlur(mask, 5)
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    return cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)


def track_mask(frame: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    dark = cv2.inRange(gray, 0, 95)
    kernel = np.ones((13, 13), np.uint8)
    return cv2.dilate(dark, kernel, iterations=2)


def dark_ratio(mask: np.ndarray, x: int, y: int, w: int, h: int) -> float:
    height, width = mask.shape[:2]
    pad = 14
    x0 = max(0, x - pad)
    y0 = max(0, y - pad)
    x1 = min(width, x + w + pad)
    y1 = min(height, y + h + pad)
    region = mask[y0:y1, x0:x1]
    if region.size == 0:
        return 0.0
    return float(cv2.countNonZero(region)) / float(region.size)


def find_car(
    frame: np.ndarray,
    previous: tuple[int, int] | None,
    min_area: float,
    max_area: float,
    min_center_y: int,
    max_center_y: int,
    min_track_ratio: float,
):
    color = orange_mask(frame)
    track = track_mask(frame)
    contours, _ = cv2.findContours(color, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    candidates = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < min_area or area > max_area:
            continue

        x, y, w, h = cv2.boundingRect(contour)
        if w < 12 or h < 8 or w > 120 or h > 120:
            continue

        ratio = dark_ratio(track, x, y, w, h)
        if ratio < min_track_ratio:
            continue

        moments = cv2.moments(contour)
        if moments["m00"] == 0:
            continue
        cx = int(moments["m10"] / moments["m00"])
        cy = int(moments["m01"] / moments["m00"])
        if cy < min_center_y or cy > max_center_y:
            continue

        distance_penalty = 0.0
        if previous is not None:
            px, py = previous
            distance_penalty = ((cx - px) ** 2 + (cy - py) ** 2) ** 0.5

        score = area * (1.0 + ratio) - distance_penalty * 3.0
        candidates.append(
            {
                "center": (cx, cy),
                "rect": (x, y, w, h),
                "area": area,
                "ratio": ratio,
                "score": score,
            }
        )

    if not candidates:
        return None, color, track, []

    return max(candidates, key=lambda item: item["score"]), color, track, candidates


def main() -> None:
    args = parse_args()
    cap = cv2.VideoCapture(args.camera, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    if not cap.isOpened():
        raise SystemExit(f"Kamera {args.camera} konnte nicht geoeffnet werden.")

    rows: list[dict[str, int | float]] = []
    previous: tuple[int, int] | None = None
    started_at = time.monotonic()
    last_saved = 0.0

    print("Orange-Car-Tracker laeuft.")
    print("q = beenden, s = Screenshot speichern")

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("Kein Kamerabild.")
                break

            car, color, track, candidates = find_car(
                frame,
                previous,
                min_area=args.min_area,
                max_area=args.max_area,
                min_center_y=args.min_center_y,
                max_center_y=args.max_center_y,
                min_track_ratio=args.min_track_ratio,
            )

            for candidate in candidates:
                x, y, w, h = candidate["rect"]
                cv2.rectangle(frame, (x, y), (x + w, y + h), (80, 80, 80), 1)

            now = time.monotonic() - started_at
            if car is not None:
                x, y, w, h = car["rect"]
                cx, cy = car["center"]
                previous = (cx, cy)
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 3)
                cv2.circle(frame, (cx, cy), 8, (255, 0, 0), -1)
                cv2.putText(
                    frame,
                    f"orange car x={cx} y={cy} area={int(car['area'])}",
                    (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 255, 0),
                    2,
                )
                if now - last_saved >= 0.05:
                    rows.append(
                        {
                            "time_s": round(now, 3),
                            "x": cx,
                            "y": cy,
                            "area": round(car["area"], 1),
                        }
                    )
                    last_saved = now
            else:
                cv2.putText(
                    frame,
                    "orange car nicht gefunden",
                    (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 0, 255),
                    2,
                )

            cv2.imshow("orange car tracker", frame)
            cv2.imshow("orange mask", color)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key == ord("s"):
                cv2.imwrite("orange_tracker_snapshot.jpg", frame)
                cv2.imwrite("orange_tracker_mask.jpg", color)
                cv2.imwrite("track_mask.jpg", track)
                print("Screenshots gespeichert.")
    finally:
        cap.release()
        cv2.destroyAllWindows()

    out = Path(args.output)
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["time_s", "x", "y", "area"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Positionen gespeichert: {out.resolve()}")


if __name__ == "__main__":
    main()
