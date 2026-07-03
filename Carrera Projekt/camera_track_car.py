from __future__ import annotations

import argparse
import csv
import time
from pathlib import Path

import cv2
import numpy as np


def nothing(_: int) -> None:
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Trackt ein farbig markiertes Carrera-Auto per PC-Kamera."
    )
    parser.add_argument("--camera", type=int, default=0, help="Kamera-Index, meistens 0.")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--output", default="camera_positions.csv")
    return parser.parse_args()


def create_controls() -> None:
    cv2.namedWindow("controls", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("controls", 420, 260)

    # Startwerte fuer rote/orange Markierungen. Bei andersfarbigem Klebeband anpassen.
    cv2.createTrackbar("h_min", "controls", 0, 179, nothing)
    cv2.createTrackbar("h_max", "controls", 20, 179, nothing)
    cv2.createTrackbar("s_min", "controls", 80, 255, nothing)
    cv2.createTrackbar("s_max", "controls", 255, 255, nothing)
    cv2.createTrackbar("v_min", "controls", 80, 255, nothing)
    cv2.createTrackbar("v_max", "controls", 255, 255, nothing)
    cv2.createTrackbar("min_area", "controls", 100, 5000, nothing)


def read_controls() -> tuple[np.ndarray, np.ndarray, int]:
    h_min = cv2.getTrackbarPos("h_min", "controls")
    h_max = cv2.getTrackbarPos("h_max", "controls")
    s_min = cv2.getTrackbarPos("s_min", "controls")
    s_max = cv2.getTrackbarPos("s_max", "controls")
    v_min = cv2.getTrackbarPos("v_min", "controls")
    v_max = cv2.getTrackbarPos("v_max", "controls")
    min_area = cv2.getTrackbarPos("min_area", "controls")
    lower = np.array([h_min, s_min, v_min], dtype=np.uint8)
    upper = np.array([h_max, s_max, v_max], dtype=np.uint8)
    return lower, upper, max(20, min_area)


def find_target(frame: np.ndarray, lower: np.ndarray, upper: np.ndarray, min_area: int):
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, lower, upper)
    mask = cv2.medianBlur(mask, 5)
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None, mask

    contour = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(contour)
    if area < min_area:
        return None, mask

    moments = cv2.moments(contour)
    if moments["m00"] == 0:
        return None, mask

    cx = int(moments["m10"] / moments["m00"])
    cy = int(moments["m01"] / moments["m00"])
    x, y, w, h = cv2.boundingRect(contour)
    return {"x": cx, "y": cy, "area": area, "rect": (x, y, w, h)}, mask


def main() -> None:
    args = parse_args()
    cap = cv2.VideoCapture(args.camera, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)

    if not cap.isOpened():
        raise SystemExit(f"Kamera {args.camera} konnte nicht geoeffnet werden.")

    create_controls()
    rows: list[dict[str, int | float]] = []
    started_at = time.monotonic()
    last_saved = 0.0

    print("Kamera laeuft.")
    print("q = beenden, s = Screenshot speichern")
    print("Tipp: Klebt einen roten/orangen Punkt auf das Auto und stellt die Regler ein.")

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("Kein Kamerabild empfangen.")
                break

            lower, upper, min_area = read_controls()
            target, mask = find_target(frame, lower, upper, min_area)

            now = time.monotonic() - started_at
            if target:
                x, y, w, h = target["rect"]
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                cv2.circle(frame, (target["x"], target["y"]), 8, (255, 0, 0), -1)
                cv2.putText(
                    frame,
                    f"x={target['x']} y={target['y']} area={int(target['area'])}",
                    (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 255, 0),
                    2,
                )

                if now - last_saved >= 0.1:
                    rows.append(
                        {
                            "time_s": round(now, 3),
                            "x": target["x"],
                            "y": target["y"],
                            "area": round(target["area"], 1),
                        }
                    )
                    last_saved = now
            else:
                cv2.putText(
                    frame,
                    "Kein Ziel erkannt",
                    (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 0, 255),
                    2,
                )

            cv2.imshow("camera", frame)
            cv2.imshow("mask", mask)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key == ord("s"):
                cv2.imwrite("camera_snapshot.jpg", frame)
                cv2.imwrite("camera_mask.jpg", mask)
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
