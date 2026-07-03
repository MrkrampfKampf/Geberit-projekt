from __future__ import annotations

import argparse
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2

from track_dual_cars_live import draw_car, find_car, track_mask


class SharedFrame:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.frame: bytes | None = None
        self.status = "starting"
        self.running = True

    def set(self, frame: bytes, status: str) -> None:
        with self.lock:
            self.frame = frame
            self.status = status

    def get(self) -> tuple[bytes | None, str]:
        with self.lock:
            return self.frame, self.status


def camera_worker(shared: SharedFrame, camera: int) -> None:
    cap = cv2.VideoCapture(camera, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    previous: dict[str, tuple[int, int] | None] = {"orange": None, "cyan": None}

    if not cap.isOpened():
        shared.status = f"camera {camera} not open"
        return

    while shared.running:
        ok, frame = cap.read()
        if not ok:
            shared.status = "no camera frame"
            time.sleep(0.05)
            continue

        road = track_mask(frame)
        detections = {}
        candidate_map = {}
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
            candidate_map[color_name] = candidates
            if car is not None:
                previous[color_name] = car["center"]

        for color_name in ("orange", "cyan"):
            draw_car(frame, color_name, detections[color_name], candidate_map[color_name])

        status = "orange:{} cyan:{}".format(
            "ok" if detections["orange"] else "-",
            "ok" if detections["cyan"] else "-",
        )
        cv2.putText(
            frame,
            status,
            (20, 42),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 0),
            2,
        )

        encoded_ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
        if encoded_ok:
            shared.set(encoded.tobytes(), status)

    cap.release()


def make_handler(shared: SharedFrame):
    class TrackerHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args) -> None:
            return

        def do_GET(self) -> None:
            if self.path in ("/", "/index.html"):
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(
                    b"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Carrera Tracker</title>
  <style>
    body { margin: 0; background: #111; color: white; font-family: Arial, sans-serif; }
    header { padding: 10px 14px; background: #1b1b1b; font-size: 18px; }
    img { display: block; width: 100vw; height: calc(100vh - 44px); object-fit: contain; background: #000; }
  </style>
</head>
<body>
  <header>Carrera Tracker - orange und cyan</header>
  <img src="/stream.mjpg">
</body>
</html>"""
                )
                return

            if self.path == "/stream.mjpg":
                self.send_response(200)
                self.send_header("Age", "0")
                self.send_header("Cache-Control", "no-cache, private")
                self.send_header("Pragma", "no-cache")
                self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
                self.end_headers()

                while shared.running:
                    frame, _status = shared.get()
                    if frame is None:
                        time.sleep(0.05)
                        continue
                    try:
                        self.wfile.write(b"--frame\r\n")
                        self.wfile.write(b"Content-Type: image/jpeg\r\n")
                        self.wfile.write(f"Content-Length: {len(frame)}\r\n\r\n".encode("ascii"))
                        self.wfile.write(frame)
                        self.wfile.write(b"\r\n")
                    except (BrokenPipeError, ConnectionResetError):
                        break
                    time.sleep(0.03)
                return

            if self.path == "/status":
                _frame, status = shared.get()
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(status.encode("utf-8"))
                return

            self.send_error(404)

    return TrackerHandler


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Browser-basierter Carrera Kamera-Tracker.")
    parser.add_argument("--camera", type=int, default=1)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    shared = SharedFrame()
    worker = threading.Thread(target=camera_worker, args=(shared, args.camera), daemon=True)
    worker.start()

    server = ThreadingHTTPServer((args.host, args.port), make_handler(shared))
    print(f"Tracker im Browser: http://{args.host}:{args.port}/")
    print("Mit Ctrl+C beenden.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        shared.running = False
        server.server_close()


if __name__ == "__main__":
    main()
