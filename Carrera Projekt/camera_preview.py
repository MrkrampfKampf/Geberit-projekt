from __future__ import annotations

import argparse

import cv2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Einfaches Kamera-Vorschaufenster.")
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--max-index", type=int, default=4)
    return parser.parse_args()


def open_camera(index: int) -> cv2.VideoCapture:
    cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    return cap


def main() -> None:
    args = parse_args()
    index = args.camera
    cap = open_camera(index)

    print("q = beenden, n = naechste Kamera, p = vorherige Kamera, s = Screenshot")

    while True:
        if not cap.isOpened():
            frame = None
            ok = False
        else:
            ok, frame = cap.read()

        if not ok or frame is None:
            frame = 255 * cv2.UMat(360, 640, cv2.CV_8UC3).get()
            cv2.putText(
                frame,
                f"Kamera {index}: kein Bild",
                (30, 180),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                (0, 0, 255),
                2,
            )
        else:
            cv2.putText(
                frame,
                f"Kamera {index}   q=quit n=next p=prev s=screenshot",
                (20, 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2,
            )

        cv2.imshow("Carrera Kamera Vorschau", frame)
        key = cv2.waitKey(20) & 0xFF

        if key == ord("q"):
            break
        if key in (ord("n"), ord("p")):
            cap.release()
            if key == ord("n"):
                index = (index + 1) % (args.max_index + 1)
            else:
                index = (index - 1) % (args.max_index + 1)
            cap = open_camera(index)
            print(f"Wechsle zu Kamera {index}")
        if key == ord("s") and ok and frame is not None:
            path = f"preview_camera_{index}.jpg"
            cv2.imwrite(path, frame)
            print(f"Screenshot gespeichert: {path}")

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
