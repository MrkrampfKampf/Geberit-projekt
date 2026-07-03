from __future__ import annotations

import argparse
import csv
import time
from pathlib import Path

import cv2
import numpy as np


COLOR_RANGES = {
    "orange": [
        (np.array([0, 70, 50]), np.array([28, 255, 255])),
        (np.array([165, 70, 50]), np.array([179, 255, 255])),
    ],
    "cyan": [
        (np.array([78, 55, 45]), np.array([112, 255, 255])),
    ],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Trackt orange und tuerkis/blau markierte Autos.")
    parser.add_argument("--camera", type=int, default=1)
    parser.add_argument("--colors", default="orange,cyan", help="Kommagetrennt: orange,cyan")
    parser.add_argument("--output", default="dual_car_positions.csv")
    parser.add_argument("--min-area", type=float, default=120)
    parser.add_argument("--max-area", type=float, default=3500)
    parser.add_argument("--min-center-y", type=int, default=100)
    parser.add_argument("--max-center-y", type=int, default=560)
    parser.add_argument("--min-track-ratio", type=float, default=0.35)
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--hide-masks", action="store_true")
    return parser.parse_args()


def color_mask(frame: np.ndarray, color_name: str) -> np.ndarray:
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
    for lower, upper in COLOR_RANGES[color_name]:
        mask |= cv2.inRange(hsv, lower, upper)
    mask = cv2.medianBlur(mask, 5)
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    return cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)


def track_mask(frame: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    dark = cv2.inRange(gray, 0, 105)
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
    color_name: str,
    previous: tuple[int, int] | None,
    road: np.ndarray,
    min_area: float,
    max_area: float,
    min_center_y: int,
    max_center_y: int,
    min_track_ratio: float,
):
    mask = color_mask(frame, color_name)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    candidates = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < min_area or area > max_area:
            continue

        x, y, w, h = cv2.boundingRect(contour)
        if w < 8 or h < 6 or w > 130 or h > 130:
            continue

        moments = cv2.moments(contour)
        if moments["m00"] == 0:
            continue
        cx = int(moments["m10"] / moments["m00"])
        cy = int(moments["m01"] / moments["m00"])
        if cy < min_center_y or cy > max_center_y:
            continue

        ratio = dark_ratio(road, x, y, w, h)
        if ratio < min_track_ratio:
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
        return None, mask, []
    return max(candidates, key=lambda item: item["score"]), mask, candidates


def draw_car(frame: np.ndarray, color_name: str, car, candidates) -> None:
    color = (0, 165, 255) if color_name == "orange" else (255, 255, 0)
    for candidate in candidates:
        x, y, w, h = candidate["rect"]
        cv2.rectangle(frame, (x, y), (x + w, y + h), (70, 70, 70), 1)

    if car is None:
        return

    x, y, w, h = car["rect"]
    cx, cy = car["center"]
    cv2.rectangle(frame, (x, y), (x + w, y + h), color, 3)
    cv2.circle(frame, (cx, cy), 7, color, -1)
    cv2.putText(
        frame,
        f"{color_name} x={cx} y={cy}",
        (x, max(22, y - 8)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        color,
        2,
    )


def main() -> None:
    args = parse_args()
    colors = [item.strip() for item in args.colors.split(",") if item.strip()]
    for color_name in colors:
        if color_name not in COLOR_RANGES:
            raise SystemExit(f"Unbekannte Farbe: {color_name}")

    cap = cv2.VideoCapture(args.camera, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    if not cap.isOpened():
        raise SystemExit(f"Kamera {args.camera} konnte nicht geoeffnet werden.")

    cv2.namedWindow("dual car tracker", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("dual car tracker", 1280, 720)
    if not args.hide_masks:
        cv2.namedWindow("orange mask", cv2.WINDOW_NORMAL)
        cv2.namedWindow("cyan mask", cv2.WINDOW_NORMAL)

    previous: dict[str, tuple[int, int] | None] = {color_name: None for color_name in colors}
    rows: list[dict[str, int | float | str]] = []
    started_at = time.monotonic()
    last_saved = 0.0

    print("Dual-Car-Tracker laeuft.")
    print("q = beenden, s = Screenshot speichern")

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("Kein Kamerabild.")
                break

            road = track_mask(frame)
            detections = {}
            masks = {}
            all_candidates = {}

            for color_name in colors:
                car, mask, candidates = find_car(
                    frame,
                    color_name,
                    previous[color_name],
                    road,
                    min_area=args.min_area,
                    max_area=args.max_area,
                    min_center_y=args.min_center_y,
                    max_center_y=args.max_center_y,
                    min_track_ratio=args.min_track_ratio,
                )
                detections[color_name] = car
                masks[color_name] = mask
                all_candidates[color_name] = candidates
                if car is not None:
                    previous[color_name] = car["center"]

            for color_name in colors:
                draw_car(frame, color_name, detections[color_name], all_candidates[color_name])

            now = time.monotonic() - started_at
            if now - last_saved >= 0.05:
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
                last_saved = now

            status = " ".join(f"{color_name}:{'ok' if detections[color_name] else '-'}" for color_name in colors)
            cv2.putText(frame, status, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            cv2.imshow("dual car tracker", frame)
            if not args.hide_masks:
                for color_name in colors:
                    cv2.imshow(f"{color_name} mask", masks[color_name])

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key == ord("s"):
                cv2.imwrite("dual_tracker_snapshot.jpg", frame)
                for color_name in colors:
                    cv2.imwrite(f"dual_{color_name}_mask.jpg", masks[color_name])
                print("Screenshots gespeichert.")
    finally:
        cap.release()
        cv2.destroyAllWindows()

    out = Path(args.output)
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["time_s", "car", "x", "y", "area"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Positionen gespeichert: {out.resolve()}")


if __name__ == "__main__":
    main()
