from __future__ import annotations

import argparse
import contextlib
import csv
import json
import math
import queue
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import cv2
from carreralib import ControlUnit
from carreralib.connection import TimeoutError as CarreraTimeout

from analyze_track_positions import SECTION_COLORS, section_for
from autonomous_stepper_driver import DEFAULT_PROFILE, clamp_gas, send_stepper, setup_stepper
from track_dual_cars_live import draw_car, find_car, track_mask


TUNE_ORDER = [
    "bottom_straight",
    "top_straight",
    "start_finish",
    "left_curve",
    "right_curve",
    "s_curve",
]


@dataclass
class LearningState:
    previous_detection: tuple[int, int] | None = None
    previous_center: tuple[int, int] | None = None
    previous_time: float | None = None
    previous_section: str = "not_found"
    current_gas: int = -1
    last_command_time: float = 0.0
    last_seen_time: float = 0.0
    lap_start_time: float | None = None
    lap_number: int = 0
    best_lap_s: float | None = None
    tune_index: int = 0
    pending_section: str | None = None
    pending_before: int | None = None
    appconnect_last_timestamp_ms: int | None = None
    appconnect_connected: bool = False
    appconnect_error: str = ""
    appconnect_last_sector: int | None = None
    appconnect_last_cu_timestamp_ms: int | None = None
    appconnect_last_lap_ms: int | None = None
    appconnect_start_light: int | None = None
    appconnect_mode: int | None = None
    appconnect_display: int | None = None
    appconnect_car_fuel: int | None = None


class AppConnectReader:
    def __init__(self, device: str, timeout: float) -> None:
        self.device = device
        self.timeout = timeout
        self.events: queue.Queue[dict[str, object]] = queue.Queue()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="appconnect-reader", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def close(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2.0)

    def _emit(self, kind: str, **values: object) -> None:
        values["kind"] = kind
        values["time_s"] = time.monotonic()
        self.events.put(values)

    def _run(self) -> None:
        try:
            with contextlib.closing(ControlUnit(self.device, timeout=self.timeout)) as cu:
                self._emit("connected", version=cu.version())
                while not self._stop.is_set():
                    try:
                        msg = cu.poll()
                    except CarreraTimeout:
                        continue
                    except Exception as exc:
                        # Report BLE/serial failures to the main loop instead of crashing the reader thread.
                        self._emit("error", error=str(exc))
                        break

                    if isinstance(msg, ControlUnit.Timer):
                        self._emit(
                            "timer",
                            address=msg.address,
                            timestamp_ms=msg.timestamp,
                            sector=msg.sector,
                        )
                    elif isinstance(msg, ControlUnit.Status):
                        self._emit(
                            "status",
                            fuel=list(msg.fuel),
                            start=msg.start,
                            mode=msg.mode,
                            pit=list(msg.pit),
                            display=msg.display,
                        )
        except Exception as exc:
            self._emit("error", error=str(exc))
        finally:
            self._emit("stopped")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Lern-Autopilot: Kamera erkennt Abschnitt, Stepper gibt Gas, Profil wird pro Runde angepasst."
    )
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--port", default="COM3")
    parser.add_argument("--car", choices=["orange", "cyan"], default="orange")
    parser.add_argument("--laps", type=int, default=10)
    parser.add_argument("--seconds", type=float, default=180.0)
    parser.add_argument("--range-steps", type=int, default=290)
    parser.add_argument("--stepper-speed-us", type=int, default=1200)
    parser.add_argument("--max-gas", type=int, default=38)
    parser.add_argument("--learn-step", type=int, default=1)
    parser.add_argument("--crash-drop", type=int, default=4)
    parser.add_argument("--min-lap-s", type=float, default=3.0)
    parser.add_argument("--lap-timeout-s", type=float, default=20.0)
    parser.add_argument("--lost-timeout", type=float, default=1.0)
    parser.add_argument("--min-command-interval", type=float, default=0.25)
    parser.add_argument(
        "--appconnect-device",
        default="",
        help="COM-Port oder AppConnect-Adresse, z.B. C5:7D:F4:7A:AC:42. Wenn gesetzt, liefern CU-Timer die Rundenzeiten.",
    )
    parser.add_argument(
        "--appconnect-car",
        type=int,
        default=6,
        help="Carrera-Adresse fuer Timer-Events. Autonomous/Ghost ist oft 6.",
    )
    parser.add_argument("--appconnect-sector", type=int, default=1)
    parser.add_argument("--appconnect-timeout", type=float, default=0.2)
    parser.add_argument("--output", default="learning_stepper_log.csv")
    parser.add_argument("--profile-output", default="learned_stepper_profile.json")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-gui", action="store_true")
    return parser.parse_args()


def initial_profile(max_gas: int) -> dict[str, int]:
    return {
        section: clamp_gas(value, max_gas)
        for section, value in DEFAULT_PROFILE.items()
        if section != "not_found"
    } | {"not_found": 0}


def gas_for_section(profile: dict[str, int], section: str, max_gas: int) -> int:
    return clamp_gas(profile.get(section, profile.get("transition", 0)), max_gas)


def apply_next_trial(profile: dict[str, int], state: LearningState, args: argparse.Namespace) -> None:
    section = TUNE_ORDER[state.tune_index % len(TUNE_ORDER)]
    state.tune_index += 1
    state.pending_section = section
    state.pending_before = profile[section]
    profile[section] = clamp_gas(profile[section] + args.learn_step, args.max_gas)
    print(f"Trial: {section} {state.pending_before}% -> {profile[section]}%")


def finish_lap(profile: dict[str, int], state: LearningState, lap_time_s: float, args: argparse.Namespace) -> None:
    improved = state.best_lap_s is None or lap_time_s <= state.best_lap_s

    if state.pending_section is not None and state.pending_before is not None:
        if improved:
            print(f"Keep: {state.pending_section} bei {profile[state.pending_section]}%")
        else:
            print(
                f"Revert: {state.pending_section} {profile[state.pending_section]}% -> {state.pending_before}%"
            )
            profile[state.pending_section] = state.pending_before

    if improved:
        state.best_lap_s = lap_time_s

    state.pending_section = None
    state.pending_before = None
    apply_next_trial(profile, state, args)


def append_event(current: str, event: str) -> str:
    if not current:
        return event
    return f"{current};{event}"


def handle_lap(
    profile: dict[str, int],
    state: LearningState,
    lap_time_s: float,
    args: argparse.Namespace,
    source: str,
    now: float,
) -> None:
    state.lap_start_time = now
    state.lap_number += 1
    print(f"Runde {state.lap_number} ({source}): {lap_time_s:.2f}s")
    finish_lap(profile, state, lap_time_s, args)


def process_appconnect_events(
    reader: AppConnectReader | None,
    profile: dict[str, int],
    state: LearningState,
    args: argparse.Namespace,
    now: float,
) -> str:
    if reader is None:
        return ""

    event = ""
    while True:
        try:
            message = reader.events.get_nowait()
        except queue.Empty:
            break

        kind = message["kind"]
        if kind == "connected":
            state.appconnect_connected = True
            print(f"AppConnect verbunden. CU-Version: {message.get('version')}")
            event = append_event(event, "appconnect_connected")
        elif kind == "error":
            state.appconnect_error = str(message.get("error", ""))
            print(f"AppConnect Fehler: {state.appconnect_error}")
            event = append_event(event, "appconnect_error")
        elif kind == "stopped":
            state.appconnect_connected = False
        elif kind == "status":
            fuel = message.get("fuel")
            state.appconnect_start_light = int(message["start"])
            state.appconnect_mode = int(message["mode"])
            state.appconnect_display = int(message["display"])
            if isinstance(fuel, list) and 0 <= args.appconnect_car < len(fuel):
                state.appconnect_car_fuel = int(fuel[args.appconnect_car])
        elif kind == "timer":
            address = int(message["address"])
            sector = int(message["sector"])
            timestamp_ms = int(message["timestamp_ms"])
            state.appconnect_last_sector = sector
            state.appconnect_last_cu_timestamp_ms = timestamp_ms

            if address != args.appconnect_car or sector != args.appconnect_sector:
                continue

            if state.appconnect_last_timestamp_ms is None:
                state.appconnect_last_timestamp_ms = timestamp_ms
                state.lap_start_time = now
                print(f"AppConnect Start/Ziel Referenz erkannt: {timestamp_ms} ms")
                event = append_event(event, "appconnect_first_start_finish")
                continue

            lap_ms = timestamp_ms - state.appconnect_last_timestamp_ms
            if lap_ms < int(args.min_lap_s * 1000):
                continue

            state.appconnect_last_timestamp_ms = timestamp_ms
            state.appconnect_last_lap_ms = lap_ms
            handle_lap(profile, state, lap_ms / 1000.0, args, "appconnect", now)
            event = append_event(event, "appconnect_lap")

    return event


def handle_crash(profile: dict[str, int], state: LearningState, args: argparse.Namespace) -> None:
    if state.pending_section is not None and state.pending_before is not None:
        section = state.pending_section
        profile[section] = max(0, state.pending_before - args.crash_drop)
        print(f"Crash/Lost: {section} auf {profile[section]}% reduziert")
    state.pending_section = None
    state.pending_before = None


def write_profile(path: Path, profile: dict[str, int], state: LearningState) -> None:
    payload = {
        "profile": profile,
        "best_lap_s": state.best_lap_s,
        "tune_order": TUNE_ORDER,
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def draw_status(
    frame,
    section: str,
    gas: int,
    state: LearningState,
    profile: dict[str, int],
    dry_run: bool,
    appconnect_enabled: bool,
) -> None:
    color = SECTION_COLORS.get(section, (255, 255, 255))
    suffix = " DRY" if dry_run else ""
    data = " APP" if appconnect_enabled and state.appconnect_connected else ""
    best = "-" if state.best_lap_s is None else f"{state.best_lap_s:.2f}s"
    pending = state.pending_section or "-"
    cv2.putText(
        frame,
        f"LEARN{suffix}{data} lap={state.lap_number} best={best} section={section} gas={gas}% trial={pending}",
        (20, 42),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.72,
        color,
        2,
    )
    y = 72
    for item in TUNE_ORDER:
        cv2.putText(
            frame,
            f"{item}:{profile[item]}",
            (20, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.48,
            (230, 230, 230),
            1,
        )
        y += 22


def main() -> None:
    args = parse_args()
    args.max_gas = clamp_gas(args.max_gas, 100)
    profile = initial_profile(args.max_gas)
    state = LearningState()
    rows: list[dict[str, int | float | str]] = []
    appconnect = None
    if args.appconnect_device:
        appconnect = AppConnectReader(args.appconnect_device, args.appconnect_timeout)
        appconnect.start()
        print(
            f"AppConnect-Daten aktiv: device={args.appconnect_device} "
            f"car={args.appconnect_car} sector={args.appconnect_sector}"
        )

    try:
        ser = setup_stepper(args)
    except Exception:
        if appconnect is not None:
            appconnect.close()
        raise

    cap = cv2.VideoCapture(args.camera, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    if not cap.isOpened():
        if ser is not None:
            ser.close()
        if appconnect is not None:
            appconnect.close()
        raise SystemExit(f"Kamera {args.camera} konnte nicht geoeffnet werden.")

    started_at = time.monotonic()
    deadline = started_at + args.seconds
    print("Lern-Autopilot laeuft.")
    print("Startprofil:", profile)
    print("q = beenden, wenn GUI sichtbar ist")

    try:
        while time.monotonic() < deadline and state.lap_number < args.laps:
            ok, frame = cap.read()
            if not ok:
                continue

            now = time.monotonic()
            elapsed = now - started_at
            event = process_appconnect_events(appconnect, profile, state, args, now)
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

                crossed_start = section == "start_finish" and state.previous_section != "start_finish"
                if crossed_start and appconnect is None:
                    if state.lap_start_time is None:
                        state.lap_start_time = now
                        event = append_event(event, "first_start_finish")
                        print("Start/Ziel Referenz erkannt.")
                    else:
                        lap_time_s = now - state.lap_start_time
                        if lap_time_s >= args.min_lap_s:
                            handle_lap(profile, state, lap_time_s, args, "camera", now)
                            event = append_event(event, "lap")

                state.previous_section = section
            elif now - state.last_seen_time > args.lost_timeout:
                event = append_event(event, "lost")
                handle_crash(profile, state, args)
                send_stepper(ser, "gas 0", args.dry_run)
                print("Auto nicht erkannt. Stoppe zur Sicherheit.")
                break

            if (
                state.lap_start_time is not None
                and now - state.lap_start_time > args.lap_timeout_s
                and state.previous_section != "start_finish"
            ):
                event = append_event(event, "lap_timeout")
                handle_crash(profile, state, args)
                send_stepper(ser, "gas 0", args.dry_run)
                print("Runden-Timeout. Stoppe zur Sicherheit.")
                break

            target_gas = gas_for_section(profile, section, args.max_gas)
            if (
                target_gas != state.current_gas
                and now - state.last_command_time >= args.min_command_interval
            ):
                send_stepper(ser, f"gas {target_gas}", args.dry_run)
                state.current_gas = target_gas
                state.last_command_time = now

            rows.append(
                {
                    "time_s": round(elapsed, 3),
                    "lap": state.lap_number,
                    "car": args.car,
                    "section": section,
                    "gas": target_gas,
                    "speed_px_s": round(speed_px_s, 1),
                    "x": car["center"][0] if car else "",
                    "y": car["center"][1] if car else "",
                    "event": event,
                    "pending_section": state.pending_section or "",
                    "best_lap_s": "" if state.best_lap_s is None else round(state.best_lap_s, 3),
                    "appconnect_connected": int(state.appconnect_connected),
                    "appconnect_sector": "" if state.appconnect_last_sector is None else state.appconnect_last_sector,
                    "appconnect_cu_timestamp_ms": ""
                    if state.appconnect_last_cu_timestamp_ms is None
                    else state.appconnect_last_cu_timestamp_ms,
                    "appconnect_lap_ms": ""
                    if state.appconnect_last_lap_ms is None
                    else state.appconnect_last_lap_ms,
                    "appconnect_start_light": ""
                    if state.appconnect_start_light is None
                    else state.appconnect_start_light,
                    "appconnect_mode": "" if state.appconnect_mode is None else state.appconnect_mode,
                    "appconnect_display": ""
                    if state.appconnect_display is None
                    else state.appconnect_display,
                    "appconnect_car_fuel": ""
                    if state.appconnect_car_fuel is None
                    else state.appconnect_car_fuel,
                    "appconnect_error": state.appconnect_error,
                }
            )

            if not args.no_gui:
                draw_car(frame, args.car, car, candidates)
                draw_status(
                    frame,
                    section,
                    target_gas,
                    state,
                    profile,
                    args.dry_run,
                    appconnect is not None,
                )
                cv2.imshow("learning stepper driver", frame)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    break
    finally:
        send_stepper(ser, "gas 0", args.dry_run)
        send_stepper(ser, "release", args.dry_run)
        cap.release()
        if appconnect is not None:
            appconnect.close()
        if ser is not None:
            ser.close()
        if not args.no_gui:
            cv2.destroyAllWindows()

    out = Path(args.output)
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "time_s",
                "lap",
                "car",
                "section",
                "gas",
                "speed_px_s",
                "x",
                "y",
                "event",
                "pending_section",
                "best_lap_s",
                "appconnect_connected",
                "appconnect_sector",
                "appconnect_cu_timestamp_ms",
                "appconnect_lap_ms",
                "appconnect_start_light",
                "appconnect_mode",
                "appconnect_display",
                "appconnect_car_fuel",
                "appconnect_error",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    profile_out = Path(args.profile_output)
    write_profile(profile_out, profile, state)
    print(f"Lern-Log gespeichert: {out.resolve()}")
    print(f"Profil gespeichert: {profile_out.resolve()}")


if __name__ == "__main__":
    main()
