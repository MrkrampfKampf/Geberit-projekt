from __future__ import annotations

import argparse
import csv
import math
import time
from dataclasses import dataclass
from pathlib import Path

import cv2
import serial

from analyze_track_positions import SECTION_COLORS, section_for
from track_dual_cars_live import draw_car, find_car, track_mask


DEFAULT_PROFILE = {
    "start_finish": 26,
    "bottom_straight": 32,
    "top_straight": 28,
    "left_curve": 18,
    "right_curve": 18,
    "s_curve": 16,
    "transition": 18,
    "not_found": 0,
}


@dataclass
class ControlState:
    previous_detection: tuple[int, int] | None = None
    previous_center: tuple[int, int] | None = None
    previous_time: float | None = None
    current_gas: int = -1
    last_command_time: float = 0.0
    last_seen_time: float = 0.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Erster Kamera-Autopilot: Track-Abschnitt -> Stepper-Gaswert."
    )
    parser.add_argument("--camera", type=int, default=1)
    parser.add_argument("--port", default="COM3")
    parser.add_argument("--seconds", type=float, default=60.0)
    parser.add_argument("--car", choices=["orange", "cyan"], default="orange")
    parser.add_argument("--range-steps", type=int, default=290)
    parser.add_argument("--stepper-speed-us", type=int, default=1200)
    parser.add_argument("--max-gas", type=int, default=35)
    parser.add_argument("--min-command-interval", type=float, default=0.25)
    parser.add_argument("--lost-timeout", type=float, default=0.7)
    parser.add_argument("--output", default="autonomous_stepper_log.csv")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-gui", action="store_true")
    return parser.parse_args()


def clamp_gas(value: int, max_gas: int) -> int:
    return max(0, min(max_gas, int(value)))


def gas_for_section(section: str, max_gas: int) -> int:
    return clamp_gas(DEFAULT_PROFILE.get(section, DEFAULT_PROFILE["transition"]), max_gas)


def read_available(ser: serial.Serial, wait: float = 0.03) -> None:
    time.sleep(wait)
    while ser.in_waiting:
        print("pico:", ser.readline().decode("utf-8", errors="replace").strip())


def send_stepper(ser: serial.Serial | None, command: str, dry_run: bool) -> None:
    print(f"cmd: {command}")
    if dry_run:
        return
    assert ser is not None
    ser.write((command + "\n").encode("ascii"))
    ser.flush()
    read_available(ser)


def setup_stepper(args: argparse.Namespace) -> serial.Serial | None:
    if args.dry_run:
        print("Dry-run: Stepper wird nicht bewegt.")
        return None

    ser = serial.Serial(args.port, baudrate=115200, timeout=1)
    time.sleep(1.2)
    ser.reset_input_buffer()
    send_stepper(ser, f"speed {args.stepper_speed_us}", dry_run=False)
    send_stepper(ser, f"range {args.range_steps}", dry_run=False)
    send_stepper(ser, "zero", dry_run=False)
    send_stepper(ser, "gas 0", dry_run=False)
    return ser


def draw_status(frame, section: str, gas: int, speed_px_s: float, dry_run: bool) -> None:
    color = SECTION_COLORS.get(section, (255, 255, 255))
    suffix = " DRY" if dry_run else ""
    cv2.putText(
        frame,
        f"AI{suffix} section={section} gas={gas}% speed={speed_px_s:.0f}px/s",
        (20, 42),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        color,
        2,
    )


def main() -> None:
    args = parse_args()
    args.max_gas = clamp_gas(args.max_gas, 100)

    ser = setup_stepper(args)
    cap = cv2.VideoCapture(args.camera, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    if not cap.isOpened():
        if ser is not None:
            ser.close()
        raise SystemExit(f"Kamera {args.camera} konnte nicht geoeffnet werden.")

    state = ControlState()
    rows: list[dict[str, int | float | str]] = []
    started_at = time.monotonic()
    deadline = started_at + args.seconds

    print("Autopilot laeuft.")
    print("Profil:", DEFAULT_PROFILE)
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
                args.car,
                state.previous_detection,
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
                state.previous_detection = (cx, cy)
                state.last_seen_time = now
                section = section_for(cx, cy)

                if state.previous_center is not None and state.previous_time is not None:
                    dt = now - state.previous_time
                    if dt > 0:
                        speed_px_s = math.hypot(
                            cx - state.previous_center[0],
                            cy - state.previous_center[1],
                        ) / dt

                state.previous_center = (cx, cy)
                state.previous_time = now
            elif now - state.last_seen_time > args.lost_timeout:
                section = "not_found"

            target_gas = gas_for_section(section, args.max_gas)
            should_send = (
                target_gas != state.current_gas
                and now - state.last_command_time >= args.min_command_interval
            )
            if should_send:
                send_stepper(ser, f"gas {target_gas}", args.dry_run)
                state.current_gas = target_gas
                state.last_command_time = now

            rows.append(
                {
                    "time_s": round(elapsed, 3),
                    "car": args.car,
                    "section": section,
                    "gas": target_gas,
                    "speed_px_s": round(speed_px_s, 1),
                    "x": car["center"][0] if car else "",
                    "y": car["center"][1] if car else "",
                }
            )

            if not args.no_gui:
                draw_car(frame, args.car, car, candidates)
                draw_status(frame, section, target_gas, speed_px_s, args.dry_run)
                cv2.imshow("autonomous stepper driver", frame)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    break
    finally:
        send_stepper(ser, "gas 0", args.dry_run)
        send_stepper(ser, "release", args.dry_run)
        cap.release()
        if ser is not None:
            ser.close()
        if not args.no_gui:
            cv2.destroyAllWindows()

    out = Path(args.output)
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["time_s", "car", "section", "gas", "speed_px_s", "x", "y"],
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"Autopilot-Log gespeichert: {out.resolve()}")


if __name__ == "__main__":
    main()
