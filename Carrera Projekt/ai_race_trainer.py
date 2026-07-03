from __future__ import annotations

import argparse
import csv
import json
import math
import random
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import serial

try:
    import winsound
except ImportError:
    winsound = None

from analyze_track_positions import SECTION_COLORS, section_for
from track_dual_cars_live import draw_car, find_car, track_mask


CURVE_SECTIONS = {"left_curve", "right_curve", "s_curve"}
STRAIGHT_SECTIONS = {"bottom_straight", "top_straight"}


@dataclass
class PathSample:
    timestamp: float
    cell_key: str
    section: str
    x: int
    y: int
    speed_px_s: float
    gas: int


@dataclass
class TrainerState:
    mode: str = "WAIT_START"
    base_gas: int = 10
    run_number: int = 0
    completed_laps: int = 0
    loss_count: int = 0
    losses_since_lap: int = 0
    current_gas: int = -1
    last_command_time: float = 0.0
    previous_detection: tuple[int, int] | None = None
    previous_center: tuple[int, int] | None = None
    launch_start_center: tuple[int, int] | None = None
    previous_time: float | None = None
    previous_section: str = ""
    last_seen_time: float = 0.0
    last_moving_time: float = 0.0
    run_started_at: float = 0.0
    has_moved_this_run: bool = False
    last_launch_boost_time: float = 0.0
    last_stall_boost_time: float = 0.0
    temporary_gas: int = 0
    lap_reference_seen: bool = False
    last_start_cross_time: float = 0.0
    next_time_boost: float = 0.0
    last_event: str = "Regler auf 0, Auto auf Bahn, dann S druecken"
    motion_window: deque[tuple[float, int, int]] = field(default_factory=deque)
    recent_path: deque[PathSample] = field(default_factory=deque)
    lap_cells: set[str] = field(default_factory=set)
    known_cells: set[str] = field(default_factory=set)
    cell_failures: dict[str, int] = field(default_factory=dict)
    cell_limits: dict[str, int] = field(default_factory=dict)
    clean_laps_since_boost: int = 0
    clean_boost_series: int = 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Selbstlernender Carrera-Trainer: Kamera erkennt Auto, Pico bewegt Gasregler."
    )
    parser.add_argument("--camera", type=int, default=1)
    parser.add_argument("--port", default="COM3")
    parser.add_argument("--car", choices=["orange", "cyan"], default="cyan")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--range-steps", type=int, default=435)
    parser.add_argument("--stepper-speed-us", type=int, default=1200)
    parser.add_argument("--start-gas", type=int, default=20)
    parser.add_argument("--gas-step", type=int, default=2)
    parser.add_argument("--laps-per-boost", type=int, default=2)
    parser.add_argument("--max-gas", type=int, default=60)
    parser.add_argument("--launch-max-gas", type=int, default=35)
    parser.add_argument("--launch-step", type=int, default=5)
    parser.add_argument("--cell-size", type=int, default=80)
    parser.add_argument("--cell-radius", type=int, default=1)
    parser.add_argument("--crash-radius", type=int, default=1)
    parser.add_argument("--crash-memory-s", type=float, default=2.2)
    parser.add_argument("--crash-drop", type=int, default=5)
    parser.add_argument("--curve-crash-extra-drop", type=int, default=0)
    parser.add_argument("--pre-curve-drop", type=int, default=5)
    parser.add_argument("--root-cause-loss-threshold", type=int, default=2)
    parser.add_argument("--root-cause-memory-s", type=float, default=6.0)
    parser.add_argument("--upstream-fast-drop", type=int, default=5)
    parser.add_argument("--upstream-max-cells", type=int, default=9)
    parser.add_argument("--explore-random-cells", type=int, default=3)
    parser.add_argument("--explore-random-drop", type=int, default=5)
    parser.add_argument("--failure-limit-threshold", type=int, default=20)
    parser.add_argument("--failure-limit-margin", type=int, default=5)
    parser.add_argument("--failure-limit-step", type=int, default=3)
    parser.add_argument("--loss-tail-cells", type=int, default=24)
    parser.add_argument("--loss-tail-drop", type=int, default=5)
    parser.add_argument("--clean-straight-random-cells", type=int, default=4)
    parser.add_argument("--clean-straight-recover", type=int, default=2)
    parser.add_argument("--curve-explore-every-clean-series", type=int, default=3)
    parser.add_argument("--curve-explore-random-cells", type=int, default=2)
    parser.add_argument("--curve-explore-recover", type=int, default=1)
    parser.add_argument("--recover-step", type=int, default=2)
    parser.add_argument("--min-drive-gas", type=int, default=20)
    parser.add_argument("--stall-boost-limit", type=int, default=35)
    parser.add_argument("--stall-boost-step", type=int, default=5)
    parser.add_argument("--min-lap-s", type=float, default=4.0)
    parser.add_argument(
        "--level-survival-s",
        type=float,
        default=0.0,
        help="Optionaler Zeit-Boost ohne Start/Ziel-Erkennung. 0 = aus.",
    )
    parser.add_argument("--min-command-interval", type=float, default=0.20)
    parser.add_argument("--lost-timeout", type=float, default=1.0)
    parser.add_argument("--start-grace", type=float, default=2.0)
    parser.add_argument("--launch-timeout", type=float, default=1.4)
    parser.add_argument("--stopped-timeout", type=float, default=1.0)
    parser.add_argument("--stopped-distance-px", type=float, default=22.0)
    parser.add_argument("--moving-speed-px-s", type=float, default=35.0)
    parser.add_argument("--launch-moved-distance-px", type=float, default=35.0)
    parser.add_argument("--countdown", type=int, default=3)
    parser.add_argument("--min-area", type=float, default=120)
    parser.add_argument("--max-area", type=float, default=3500)
    parser.add_argument("--min-center-y", type=int, default=100)
    parser.add_argument("--max-center-y", type=int, default=560)
    parser.add_argument("--min-track-ratio", type=float, default=0.35)
    parser.add_argument("--min-cell-track-ratio", type=float, default=0.08)
    parser.add_argument("--profile-input", default="")
    parser.add_argument("--profile-output", default="ai_race_profile.json")
    parser.add_argument("--output", default="ai_race_trainer_log.csv")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-gui", action="store_true")
    parser.add_argument("--auto-start", action="store_true")
    parser.add_argument("--zero-on-start", action=argparse.BooleanOptionalAction, default=True)
    return parser.parse_args()


def clamp_gas(value: int, max_gas: int) -> int:
    return max(0, min(max_gas, int(value)))


def cell_for(x: int, y: int, cell_size: int) -> str:
    return f"{x // cell_size},{y // cell_size}"


def parse_cell(key: str) -> tuple[int, int]:
    left, right = key.split(",", 1)
    return int(left), int(right)


def nearby_cells(key: str, radius: int) -> list[str]:
    cx, cy = parse_cell(key)
    result = []
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            result.append(f"{cx + dx},{cy + dy}")
    return result


def cell_track_ratio(road, key: str, cell_size: int) -> float:
    if road is None or not key:
        return 1.0
    try:
        cx, cy = parse_cell(key)
    except ValueError:
        return 0.0

    height, width = road.shape[:2]
    x0 = max(0, cx * cell_size)
    y0 = max(0, cy * cell_size)
    x1 = min(width, x0 + cell_size)
    y1 = min(height, y0 + cell_size)
    if x0 >= x1 or y0 >= y1:
        return 0.0
    roi = road[y0:y1, x0:x1]
    if roi.size == 0:
        return 0.0
    return float(cv2.countNonZero(roi)) / float(roi.size)


def is_track_cell(road, key: str, args: argparse.Namespace) -> bool:
    return cell_track_ratio(road, key, args.cell_size) >= args.min_cell_track_ratio


def filter_learning_to_track(
    state: TrainerState,
    local_drops: dict[str, int],
    road,
    args: argparse.Namespace,
) -> int:
    if road is None:
        return 0
    before = len(state.known_cells) + len(local_drops)
    state.known_cells = {key for key in state.known_cells if is_track_cell(road, key, args)}
    for key in list(local_drops):
        if not is_track_cell(road, key, args):
            del local_drops[key]
    for key in list(state.cell_failures):
        if not is_track_cell(road, key, args):
            del state.cell_failures[key]
    for key in list(state.cell_limits):
        if not is_track_cell(road, key, args):
            del state.cell_limits[key]
    return before - (len(state.known_cells) + len(local_drops))


def load_learning_map(
    args: argparse.Namespace,
) -> tuple[int, dict[str, int], set[str], dict[str, int], dict[str, int]]:
    base_gas = clamp_gas(args.start_gas, args.max_gas)
    local_drops: dict[str, int] = {}
    known_cells: set[str] = set()
    cell_failures: dict[str, int] = {}
    cell_limits: dict[str, int] = {}

    path = Path(args.profile_input) if args.profile_input else Path(args.profile_output)
    if not path.exists():
        return base_gas, local_drops, known_cells, cell_failures, cell_limits

    try:
        with path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Lernprofil kann nicht geladen werden, starte neu: {exc}")
        return base_gas, local_drops, known_cells, cell_failures, cell_limits

    base_gas = clamp_gas(int(payload.get("base_gas", base_gas)), args.max_gas)
    completed_laps = int(payload.get("completed_laps", 0) or 0)
    if completed_laps == 0 and base_gas > args.start_gas:
        print(
            f"Profil hatte {base_gas}% ohne echte Runde. "
            f"Setze Basisgas zurueck auf {args.start_gas}%."
        )
        base_gas = args.start_gas
    loaded_drops = payload.get("local_drops", {})
    if isinstance(loaded_drops, dict):
        for key, value in loaded_drops.items():
            try:
                parse_cell(key)
                local_drops[key] = max(0, int(value))
            except (ValueError, TypeError):
                continue
    loaded_known = payload.get("known_cells", [])
    if isinstance(loaded_known, list):
        for key in loaded_known:
            if not isinstance(key, str):
                continue
            try:
                parse_cell(key)
                known_cells.add(key)
            except ValueError:
                continue
    loaded_failures = payload.get("cell_failures", {})
    if isinstance(loaded_failures, dict):
        for key, value in loaded_failures.items():
            try:
                parse_cell(key)
                cell_failures[key] = max(0, int(value))
            except (ValueError, TypeError):
                continue
    loaded_limits = payload.get("cell_limits", {})
    if isinstance(loaded_limits, dict):
        for key, value in loaded_limits.items():
            try:
                parse_cell(key)
                cell_limits[key] = clamp_gas(int(value), args.max_gas)
            except (ValueError, TypeError):
                continue
    known_cells.update(local_drops)
    known_cells.update(cell_limits)

    print(
        f"Lernprofil geladen: base_gas={base_gas}, "
        f"bekannte Zellen={len(known_cells)}, lokale Bremsstellen={len(local_drops)}, "
        f"harte Limits={len(cell_limits)}"
    )
    return base_gas, local_drops, known_cells, cell_failures, cell_limits


def save_learning_map(
    path: Path,
    state: TrainerState,
    local_drops: dict[str, int],
    args: argparse.Namespace,
) -> None:
    payload = {
        "base_gas": state.base_gas,
        "local_drops": dict(sorted(local_drops.items())),
        "cell_failures": dict(sorted(state.cell_failures.items())),
        "cell_limits": dict(sorted(state.cell_limits.items())),
        "known_cells": sorted(state.known_cells),
        "cell_size": args.cell_size,
        "cell_radius": args.cell_radius,
        "gas_step": args.gas_step,
        "max_gas": args.max_gas,
        "start_gas": args.start_gas,
        "min_drive_gas": args.min_drive_gas,
        "range_steps": args.range_steps,
        "crash_memory_s": args.crash_memory_s,
        "crash_drop": args.crash_drop,
        "curve_crash_extra_drop": args.curve_crash_extra_drop,
        "pre_curve_drop": args.pre_curve_drop,
        "root_cause_loss_threshold": args.root_cause_loss_threshold,
        "root_cause_memory_s": args.root_cause_memory_s,
        "upstream_fast_drop": args.upstream_fast_drop,
        "upstream_max_cells": args.upstream_max_cells,
        "explore_random_cells": args.explore_random_cells,
        "explore_random_drop": args.explore_random_drop,
        "failure_limit_threshold": args.failure_limit_threshold,
        "failure_limit_margin": args.failure_limit_margin,
        "failure_limit_step": args.failure_limit_step,
        "loss_tail_cells": args.loss_tail_cells,
        "loss_tail_drop": args.loss_tail_drop,
        "clean_straight_random_cells": args.clean_straight_random_cells,
        "clean_straight_recover": args.clean_straight_recover,
        "curve_explore_every_clean_series": args.curve_explore_every_clean_series,
        "curve_explore_random_cells": args.curve_explore_random_cells,
        "curve_explore_recover": args.curve_explore_recover,
        "launch_max_gas": args.launch_max_gas,
        "launch_step": args.launch_step,
        "completed_laps": state.completed_laps,
        "loss_count": state.loss_count,
        "losses_since_lap": state.losses_since_lap,
        "clean_boost_series": state.clean_boost_series,
        "clean_laps_since_boost": state.clean_laps_since_boost,
        "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


class Stepper:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.ser: serial.Serial | None = None

    def open(self) -> None:
        if self.args.dry_run:
            print("Dry-run: Pico wird nicht bewegt.")
            return

        self.ser = serial.Serial(self.args.port, baudrate=115200, timeout=1)
        time.sleep(1.2)
        self.ser.reset_input_buffer()
        self.send(f"speed {self.args.stepper_speed_us}", force=True)
        self.send(f"range {self.args.range_steps}", force=True)
        self.send("gasdir ccw", force=True)
        self.send("release", force=True)

    def close(self) -> None:
        if self.ser is not None:
            self.ser.close()

    def send(self, command: str, force: bool = False) -> None:
        print(f"cmd: {command}")
        if self.args.dry_run:
            return
        if self.ser is None:
            raise RuntimeError("Stepper-Serial ist nicht offen.")
        self.ser.write((command + "\n").encode("ascii"))
        self.ser.flush()
        time.sleep(0.08 if force else 0.03)
        while self.ser.in_waiting:
            print("pico:", self.ser.readline().decode("utf-8", errors="replace").strip())

    def gas(self, percent: int, state: TrainerState, now: float, force: bool = False) -> None:
        percent = clamp_gas(percent, self.args.max_gas)
        if not force:
            if percent == state.current_gas:
                return
            if now - state.last_command_time < self.args.min_command_interval:
                return
        self.send(f"gas {percent}", force=force)
        state.current_gas = percent
        state.last_command_time = now

    def prepare_start(self, state: TrainerState, now: float) -> None:
        self.send(f"speed {self.args.stepper_speed_us}", force=True)
        self.send(f"range {self.args.range_steps}", force=True)
        self.send("gasdir ccw", force=True)
        self.gas(0, state, now, force=True)
        if self.args.zero_on_start:
            self.send("zero", force=True)
        self.gas(0, state, now, force=True)


def local_drop_for_cell(local_drops: dict[str, int], key: str, radius: int) -> int:
    if not key:
        return 0
    return max((local_drops.get(item, 0) for item in nearby_cells(key, radius)), default=0)


def local_limit_for_cell(cell_limits: dict[str, int], key: str, radius: int, max_gas: int) -> int:
    if not key:
        return max_gas
    return min((cell_limits.get(item, max_gas) for item in nearby_cells(key, radius)), default=max_gas)


def gas_for_position(
    state: TrainerState,
    local_drops: dict[str, int],
    cell_key: str,
    args: argparse.Namespace,
) -> int:
    drop = local_drop_for_cell(local_drops, cell_key, args.cell_radius)
    target = clamp_gas(state.base_gas - drop, args.max_gas)
    target = min(target, local_limit_for_cell(state.cell_limits, cell_key, args.cell_radius, args.max_gas))
    if state.base_gas <= 0:
        return 0
    return max(0, min(args.max_gas, max(args.min_drive_gas, target)))


def minimum_running_gas(state: TrainerState, args: argparse.Namespace) -> int:
    if state.base_gas <= 0:
        return args.min_drive_gas
    return clamp_gas(max(args.min_drive_gas, state.base_gas), args.max_gas)


def hold_or_minimum_gas(state: TrainerState, args: argparse.Namespace) -> int:
    if state.current_gas > 0:
        return clamp_gas(state.current_gas, args.max_gas)
    return minimum_running_gas(state, args)


def reset_run_tracking(state: TrainerState, now: float, args: argparse.Namespace) -> None:
    state.run_started_at = now
    state.last_seen_time = now
    state.last_moving_time = now
    state.has_moved_this_run = False
    state.last_launch_boost_time = now
    state.last_stall_boost_time = now
    state.temporary_gas = state.base_gas
    state.previous_detection = None
    state.previous_center = None
    state.launch_start_center = None
    state.previous_time = None
    state.previous_section = ""
    state.lap_reference_seen = False
    state.last_start_cross_time = 0.0
    state.motion_window.clear()
    state.recent_path.clear()
    state.lap_cells.clear()
    if args.level_survival_s > 0:
        state.next_time_boost = now + args.level_survival_s
    else:
        state.next_time_boost = 0.0


def play_tone(frequency: int, duration_ms: int) -> None:
    if winsound is not None:
        try:
            winsound.Beep(frequency, duration_ms)
        except RuntimeError:
            winsound.MessageBeep()
            time.sleep(duration_ms / 1000)
        return
    print("\a", end="", flush=True)
    time.sleep(duration_ms / 1000)


def draw_countdown_frame(frame, text: str) -> None:
    height, width = frame.shape[:2]
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (width, height), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.45, frame, 0.55, 0, frame)

    scale = 5.0 if len(text) <= 2 else 3.2
    thickness = 8
    (text_width, text_height), _baseline = cv2.getTextSize(
        text,
        cv2.FONT_HERSHEY_SIMPLEX,
        scale,
        thickness,
    )
    x = max(20, (width - text_width) // 2)
    y = max(text_height + 20, (height + text_height) // 2)
    cv2.putText(
        frame,
        text,
        (x, y),
        cv2.FONT_HERSHEY_SIMPLEX,
        scale,
        (0, 255, 255),
        thickness,
    )


def run_countdown(cap, args: argparse.Namespace, last_frame) -> None:
    if args.countdown <= 0:
        play_tone(1320, 300)
        return

    frame = last_frame.copy()
    for number in range(args.countdown, 0, -1):
        ok, fresh = cap.read()
        if ok:
            frame = fresh
        display = frame.copy()
        draw_countdown_frame(display, str(number))
        if not args.no_gui:
            cv2.imshow("AI Race Trainer", display)
            cv2.waitKey(1)
        play_tone(880, 170)
        time.sleep(0.80)

    ok, fresh = cap.read()
    if ok:
        frame = fresh
    display = frame.copy()
    draw_countdown_frame(display, "LOS")
    if not args.no_gui:
        cv2.imshow("AI Race Trainer", display)
        cv2.waitKey(1)
    play_tone(1320, 380)
    time.sleep(0.20)


def start_run(
    stepper: Stepper,
    state: TrainerState,
    args: argparse.Namespace,
    now: float,
    cap=None,
    last_frame=None,
) -> None:
    stepper.prepare_start(state, now)
    state.mode = "COUNTDOWN"
    state.last_event = "Motor auf 0, Countdown laeuft"
    if cap is not None and last_frame is not None:
        run_countdown(cap, args, last_frame)
    state.mode = "RUNNING"
    state.run_number += 1
    reset_run_tracking(state, time.monotonic(), args)
    state.last_event = f"Run {state.run_number} gestartet mit Basisgas {state.base_gas}%"
    print(state.last_event)


def increase_base_gas(state: TrainerState, args: argparse.Namespace, reason: str) -> str:
    before = state.base_gas
    state.base_gas = clamp_gas(before + args.gas_step, args.max_gas)
    if state.base_gas == before:
        return f"{reason}: Basisgas bleibt bei {before}%"
    return f"{reason}: Basisgas {before}% -> {state.base_gas}%"


def reward_successful_lap(
    state: TrainerState,
    local_drops: dict[str, int],
    args: argparse.Namespace,
    reason: str,
) -> str:
    base_event = increase_base_gas(state, args, reason)
    recovered = 0
    for cell_key in list(state.lap_cells):
        before = local_drops.get(cell_key, 0)
        if before <= 0:
            continue
        after = max(0, before - args.recover_step)
        if after == 0:
            del local_drops[cell_key]
        else:
            local_drops[cell_key] = after
        recovered += 1
    state.lap_cells.clear()
    state.temporary_gas = state.base_gas
    if recovered:
        return f"{base_event}; {recovered} Zellen +{args.recover_step}% freigegeben"
    return base_event


def apply_loss_to_recent_cells(
    state: TrainerState,
    local_drops: dict[str, int],
    args: argparse.Namespace,
    now: float,
    fallback_cell: str,
    road,
) -> str:
    samples = [sample for sample in state.recent_path if now - sample.timestamp <= args.crash_memory_s and sample.cell_key]
    root_samples = [
        sample
        for sample in state.recent_path
        if now - sample.timestamp <= args.root_cause_memory_s and sample.cell_key
    ]

    curve_indices = [index for index, item in enumerate(samples) if item.section in CURVE_SECTIONS]
    curve_related = bool(curve_indices)
    first_curve_index = curve_indices[0] if curve_indices else -1
    last_curve_index = curve_indices[-1] if curve_indices else -1
    selected = samples
    if curve_related:
        selected = samples[: last_curve_index + 1]

    weighted_cells: dict[str, int] = {}
    cause_cells: dict[str, str] = {}

    tail_count = 0
    seen_tail: set[str] = set()
    skipped_latest_cell = False
    for sample in reversed(root_samples):
        if not sample.cell_key or sample.cell_key in seen_tail:
            continue
        if fallback_cell and sample.cell_key == fallback_cell and not skipped_latest_cell:
            seen_tail.add(sample.cell_key)
            skipped_latest_cell = True
            continue
        seen_tail.add(sample.cell_key)
        previous_drop = weighted_cells.get(sample.cell_key, 0)
        weighted_cells[sample.cell_key] = max(previous_drop, args.loss_tail_drop)
        if args.loss_tail_drop >= previous_drop:
            cause_cells[sample.cell_key] = "tail"
        tail_count += 1
        if tail_count >= args.loss_tail_cells:
            break

    selected_for_crash = list(selected)
    if fallback_cell and len(selected_for_crash) > 1 and selected_for_crash[-1].cell_key == fallback_cell:
        selected_for_crash = selected_for_crash[:-1]

    for index, sample in enumerate(selected_for_crash):
        if curve_related:
            if sample.section in CURVE_SECTIONS:
                drop = args.crash_drop + args.curve_crash_extra_drop
            elif index < first_curve_index:
                drop = args.pre_curve_drop
            else:
                drop = max(1, args.crash_drop // 2)
        else:
            drop = args.crash_drop
        previous_drop = weighted_cells.get(sample.cell_key, 0)
        weighted_cells[sample.cell_key] = max(previous_drop, drop)
        if drop >= previous_drop:
            cause_cells[sample.cell_key] = "crash"

    if not weighted_cells and fallback_cell:
        weighted_cells[fallback_cell] = args.crash_drop
        cause_cells[fallback_cell] = "fallback"

    observed_gas_by_cell: dict[str, int] = {}
    for sample in root_samples:
        if sample.cell_key and sample.gas > 0:
            observed_gas_by_cell[sample.cell_key] = max(
                observed_gas_by_cell.get(sample.cell_key, 0),
                sample.gas,
            )

    root_cause_active = state.losses_since_lap >= args.root_cause_loss_threshold
    upstream_count = 0
    if root_cause_active and root_samples:
        speed_values = sorted(sample.speed_px_s for sample in root_samples if sample.speed_px_s > 0)
        if speed_values:
            threshold_index = min(len(speed_values) - 1, max(0, int(len(speed_values) * 0.65)))
            speed_threshold = max(args.moving_speed_px_s * 1.5, speed_values[threshold_index])
        else:
            speed_threshold = args.moving_speed_px_s * 1.5

        candidate_scores: dict[str, tuple[float, PathSample]] = {}
        for index, sample in enumerate(root_samples):
            score = 0.0
            if sample.speed_px_s >= speed_threshold:
                score += sample.speed_px_s
            if sample.section in STRAIGHT_SECTIONS and sample.gas >= max(args.min_drive_gas, state.base_gas):
                score += 160.0
            if sample.section in CURVE_SECTIONS:
                score += 110.0

            next_items = root_samples[index + 1 : min(len(root_samples), index + 6)]
            if sample.section in STRAIGHT_SECTIONS and any(item.section in CURVE_SECTIONS for item in next_items):
                score += 260.0

            if score <= 0:
                continue
            previous = candidate_scores.get(sample.cell_key)
            if previous is None or score > previous[0]:
                candidate_scores[sample.cell_key] = (score, sample)

        ranked = sorted(candidate_scores.values(), key=lambda item: item[0], reverse=True)
        for _score, sample in ranked[: args.upstream_max_cells]:
            drop = args.upstream_fast_drop
            if sample.section in CURVE_SECTIONS:
                drop += args.curve_crash_extra_drop
            elif sample.section in STRAIGHT_SECTIONS:
                drop += max(1, args.pre_curve_drop // 2)
            previous_drop = weighted_cells.get(sample.cell_key, 0)
            weighted_cells[sample.cell_key] = max(previous_drop, drop)
            if drop >= previous_drop:
                cause_cells[sample.cell_key] = "upstream"
            upstream_count += 1

        random_pool = ranked[args.upstream_max_cells : args.upstream_max_cells + 12]
        if random_pool and args.explore_random_cells > 0:
            sample_count = min(args.explore_random_cells, len(random_pool))
            for _score, sample in random.sample(random_pool, sample_count):
                drop = args.explore_random_drop
                if sample.section in STRAIGHT_SECTIONS:
                    drop += max(1, args.pre_curve_drop // 3)
                previous_drop = weighted_cells.get(sample.cell_key, 0)
                weighted_cells[sample.cell_key] = max(previous_drop, drop)
                if drop >= previous_drop:
                    cause_cells[sample.cell_key] = "explore"
                upstream_count += 1

    updates: dict[str, int] = {}
    for cell_key, drop in weighted_cells.items():
        if not is_track_cell(road, cell_key, args):
            continue
        updates[cell_key] = max(updates.get(cell_key, 0), drop)
        if cause_cells.get(cell_key) == "tail":
            continue
        for neighbor in nearby_cells(cell_key, args.crash_radius):
            if neighbor == cell_key:
                continue
            if not is_track_cell(road, neighbor, args):
                continue
            updates[neighbor] = max(updates.get(neighbor, 0), max(1, drop // 2))

    if not weighted_cells:
        return "Loss: keine Position erkannt, keine lokale Aenderung"
    if not updates:
        return "Loss: keine Track-Zellen im Verlauf, keine lokale Aenderung"

    limited_cells = 0
    direct_cells = set(weighted_cells)
    for cell_key, drop in updates.items():
        direct_update = cell_key in direct_cells
        is_limit_cell = False
        if direct_update:
            state.cell_failures[cell_key] = state.cell_failures.get(cell_key, 0) + 1
            if state.cell_failures[cell_key] >= args.failure_limit_threshold:
                is_limit_cell = True
                before_limit = state.cell_limits.get(cell_key, args.max_gas)
                observed_gas = observed_gas_by_cell.get(cell_key, 0)
                if before_limit < args.max_gas:
                    next_limit = before_limit - args.failure_limit_step
                elif observed_gas > 0:
                    next_limit = observed_gas - args.failure_limit_step
                else:
                    next_limit = gas_for_position(state, local_drops, cell_key, args) - args.failure_limit_step
                next_limit = max(args.min_drive_gas, min(args.max_gas, next_limit))
                state.cell_limits[cell_key] = min(before_limit, next_limit)
                if state.cell_limits[cell_key] < before_limit:
                    limited_cells += 1

        if is_limit_cell:
            local_drops[cell_key] = max(0, local_drops.get(cell_key, 0))
        else:
            local_drops[cell_key] = min(args.max_gas, local_drops.get(cell_key, 0) + drop)
        state.known_cells.add(cell_key)
    state.lap_cells.clear()
    state.clean_laps_since_boost = 0
    state.temporary_gas = min(state.temporary_gas, gas_for_position(state, local_drops, fallback_cell, args))
    if curve_related:
        curve_cells = sum(1 for _cell, drop in weighted_cells.items() if drop > args.crash_drop)
        suffix = f"; Ursachen-Test {upstream_count} schnelle Zellen" if upstream_count else ""
        limit_text = f", {limited_cells} Limits gesetzt" if limited_cells else ""
        return f"Kurven-Loss: {tail_count} hintere Zellen, {curve_cells} Kurvenzellen, {len(updates)} Zellen langsamer{limit_text}{suffix}"
    if upstream_count:
        limit_text = f", {limited_cells} harte Limits" if limited_cells else ""
        return (
            f"Root-Cause-Test nach {state.losses_since_lap} Losses: "
            f"{tail_count} hintere + {upstream_count} schnelle Zellen davor, {len(updates)} Zellen langsamer{limit_text}"
        )
    limit_text = f", {limited_cells} harte Limits" if limited_cells else ""
    return f"Loss: {tail_count} hintere Pfadzellen / {len(updates)} Zellen langsamer{limit_text}"


def is_stopped(state: TrainerState, now: float, args: argparse.Namespace) -> bool:
    while state.motion_window and now - state.motion_window[0][0] > args.stopped_timeout:
        state.motion_window.popleft()
    if len(state.motion_window) < 2:
        return False

    oldest_t, _, _ = state.motion_window[0]
    if now - oldest_t < args.stopped_timeout * 0.85:
        return False

    xs = [item[1] for item in state.motion_window]
    ys = [item[2] for item in state.motion_window]
    movement = math.hypot(max(xs) - min(xs), max(ys) - min(ys))
    return movement <= args.stopped_distance_px


def handle_lap_crossing(
    state: TrainerState,
    args: argparse.Namespace,
    local_drops: dict[str, int],
    section: str,
    now: float,
) -> str:
    if section != "start_finish" or state.previous_section == "start_finish":
        return ""
    if state.last_start_cross_time and now - state.last_start_cross_time < args.min_lap_s:
        return ""

    state.last_start_cross_time = now
    if not state.lap_reference_seen:
        state.lap_reference_seen = True
        state.lap_cells.clear()
        return "Start/Ziel Referenz erkannt"

    state.completed_laps += 1
    state.losses_since_lap = 0
    state.clean_laps_since_boost += 1
    if state.clean_laps_since_boost < args.laps_per_boost:
        state.lap_cells.clear()
        return (
            f"Gute Kamera-Runde {state.clean_laps_since_boost}/{args.laps_per_boost}, "
            "noch kein Boost"
        )

    state.clean_laps_since_boost = 0
    return reward_successful_lap(
        state,
        local_drops,
        args,
        f"{args.laps_per_boost} gute Kamera-Runden geschafft",
    )


def gas_color(gas: int, max_gas: int) -> tuple[int, int, int]:
    ratio = 0.0 if max_gas <= 0 else max(0.0, min(1.0, gas / max_gas))
    if ratio < 0.35:
        return (0, 0, 230)
    if ratio < 0.65:
        return (0, 210, 255)
    return (70, 220, 70)


def draw_learning_map(
    frame,
    state: TrainerState,
    local_drops: dict[str, int],
    args: argparse.Namespace,
) -> None:
    cells = set(state.known_cells) | set(local_drops)
    if not cells:
        return

    overlay = frame.copy()
    for key in cells:
        try:
            cx, cy = parse_cell(key)
        except ValueError:
            continue
        x0 = cx * args.cell_size
        y0 = cy * args.cell_size
        x1 = x0 + args.cell_size
        y1 = y0 + args.cell_size
        target = gas_for_position(state, local_drops, key, args)
        color = gas_color(target, args.max_gas)
        cv2.rectangle(overlay, (x0, y0), (x1, y1), color, -1)
        border = (0, 0, 230) if local_drop_for_cell(local_drops, key, args.cell_radius) > 0 else (180, 180, 180)
        cv2.rectangle(frame, (x0, y0), (x1, y1), border, 1)
        cv2.putText(
            frame,
            f"{target}",
            (x0 + 5, y0 + 22),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.48,
            (255, 255, 255),
            1,
        )
    cv2.addWeighted(overlay, 0.18, frame, 0.82, 0, frame)


def draw_status(
    frame,
    state: TrainerState,
    local_drops: dict[str, int],
    section: str,
    cell_key: str,
    target_gas: int,
    speed_px_s: float,
    args: argparse.Namespace,
) -> None:
    color = SECTION_COLORS.get(section, (255, 255, 255))
    suffix = " DRY" if args.dry_run else ""
    drop = local_drop_for_cell(local_drops, cell_key, args.cell_radius)
    cv2.putText(
        frame,
        (
            f"AI{suffix} {state.mode} run={state.run_number} laps={state.completed_laps} "
            f"losses={state.loss_count} no-lap={state.losses_since_lap}"
        ),
        (20, 36),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.74,
        (255, 255, 255),
        2,
    )
    cv2.putText(
        frame,
        f"base={state.base_gas}% drop={drop}% gas={target_gas}% clean={state.clean_laps_since_boost}/{args.laps_per_boost} cell={cell_key or '-'} speed={speed_px_s:.0f}px/s",
        (20, 68),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.68,
        color,
        2,
    )
    cv2.putText(
        frame,
        state.last_event[:92],
        (20, 100),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.60,
        (0, 255, 255) if state.mode != "LOST" else (0, 0, 255),
        2,
    )
    if state.mode != "RUNNING":
        cv2.putText(
            frame,
            "Auto irgendwo aufsetzen, Regler auf 0, dann S/Leertaste. Q beendet. R reset.",
            (20, 132),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.58,
            (255, 255, 255),
            2,
        )


def write_row(
    rows: list[dict[str, int | float | str]],
    started_at: float,
    state: TrainerState,
    event: str,
    section: str,
    cell_key: str,
    target_gas: int,
    speed_px_s: float,
    car,
) -> None:
    x = ""
    y = ""
    area = ""
    if car is not None:
        x, y = car["center"]
        area = round(car["area"], 1)
    rows.append(
        {
            "time_s": round(time.monotonic() - started_at, 3),
            "mode": state.mode,
            "run": state.run_number,
            "laps": state.completed_laps,
            "losses": state.loss_count,
            "losses_since_lap": state.losses_since_lap,
            "event": event,
            "section": section,
            "cell": cell_key,
            "base_gas": state.base_gas,
            "target_gas": target_gas,
            "speed_px_s": round(speed_px_s, 1),
            "x": x,
            "y": y,
            "area": area,
        }
    )


def main() -> None:
    args = parse_args()
    args.max_gas = clamp_gas(args.max_gas, 100)
    args.start_gas = clamp_gas(args.start_gas, args.max_gas)
    args.cell_size = max(20, args.cell_size)

    state = TrainerState(base_gas=args.start_gas)
    (
        state.base_gas,
        local_drops,
        state.known_cells,
        state.cell_failures,
        state.cell_limits,
    ) = load_learning_map(args)
    profile_path = Path(args.profile_output)
    rows: list[dict[str, int | float | str]] = []
    started_at = time.monotonic()
    last_row_time = 0.0

    stepper = Stepper(args)
    stepper.open()

    cap = cv2.VideoCapture(args.camera, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    if not cap.isOpened():
        stepper.close()
        raise SystemExit(f"Kamera {args.camera} konnte nicht geoeffnet werden.")

    if not args.no_gui:
        cv2.namedWindow("AI Race Trainer", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("AI Race Trainer", args.width, args.height)

    ok, init_frame = cap.read()
    if ok:
        removed = filter_learning_to_track(state, local_drops, track_mask(init_frame), args)
        if removed:
            print(f"Off-Track-Lernzellen entfernt: {removed}")
            save_learning_map(profile_path, state, local_drops, args)

    print("AI Race Trainer bereit.")
    print("S/Leertaste = Start nach Auto-Aufsetzen, Q = Ende, R = Lernkarte resetten, M = Kartenbild speichern")
    print(f"Basisgas: {state.base_gas}%, lokale Stellen: {len(local_drops)}")

    if args.auto_start:
        ok, warmup_frame = cap.read()
        start_run(stepper, state, args, time.monotonic(), cap, warmup_frame if ok else None)

    try:
        while True:
            ok, frame = cap.read()
            now = time.monotonic()
            if not ok:
                print("Kein Kamerabild.")
                break

            road = track_mask(frame)
            car, _mask, candidates = find_car(
                frame,
                args.car,
                state.previous_detection,
                road,
                min_area=args.min_area,
                max_area=args.max_area,
                min_center_y=args.min_center_y,
                max_center_y=args.max_center_y,
                min_track_ratio=args.min_track_ratio,
            )

            section = "not_found"
            cell_key = ""
            speed_px_s = 0.0
            event = ""

            if car is not None:
                cx, cy = car["center"]
                section = section_for(cx, cy)
                cell_key = cell_for(cx, cy, args.cell_size)
                if is_track_cell(road, cell_key, args):
                    state.known_cells.add(cell_key)
                state.previous_detection = (cx, cy)
                state.last_seen_time = now
                if state.previous_center is not None and state.previous_time is not None:
                    dt = now - state.previous_time
                    if dt > 0:
                        px, py = state.previous_center
                        speed_px_s = math.hypot(cx - px, cy - py) / dt
                        if speed_px_s >= args.moving_speed_px_s:
                            state.has_moved_this_run = True

                if state.mode == "RUNNING" and state.launch_start_center is None:
                    state.launch_start_center = (cx, cy)
                if (
                    state.mode == "RUNNING"
                    and not state.has_moved_this_run
                    and state.launch_start_center is not None
                ):
                    sx, sy = state.launch_start_center
                    if math.hypot(cx - sx, cy - sy) >= args.launch_moved_distance_px:
                        state.has_moved_this_run = True

                state.motion_window.append((now, cx, cy))
                state.recent_path.append(
                    PathSample(
                        timestamp=now,
                        cell_key=cell_key,
                        section=section,
                        x=cx,
                        y=cy,
                        speed_px_s=speed_px_s,
                        gas=max(0, state.current_gas),
                    )
                )
                if state.mode == "RUNNING":
                    state.lap_cells.add(cell_key)
                history_s = max(args.crash_memory_s, args.root_cause_memory_s)
                while state.recent_path and now - state.recent_path[0].timestamp > history_s:
                    state.recent_path.popleft()

                if not is_stopped(state, now, args):
                    state.last_moving_time = now

                if state.mode == "RUNNING":
                    lap_event = handle_lap_crossing(state, args, local_drops, section, now)
                    if lap_event:
                        event = lap_event
                        state.last_event = lap_event
                        save_learning_map(profile_path, state, local_drops, args)
                        print(lap_event)

                state.previous_center = (cx, cy)
                state.previous_time = now
                state.previous_section = section
            else:
                state.motion_window.clear()

            target_gas = 0
            if state.mode == "RUNNING":
                running_time = now - state.run_started_at
                lost_by_detection = car is None and now - state.last_seen_time >= args.lost_timeout
                lost_by_standing = (
                    car is not None
                    and state.has_moved_this_run
                    and is_stopped(state, now, args)
                )
                loss_ready = running_time > args.start_grace

                if not state.has_moved_this_run:
                    if car is None:
                        target_gas = hold_or_minimum_gas(state, args)
                        state.last_event = "Warte auf Kamera-Erkennung vor dem Anfahren"
                    else:
                        if now - state.last_launch_boost_time >= args.launch_timeout:
                            before = state.temporary_gas
                            state.temporary_gas = clamp_gas(
                                min(before + args.launch_step, args.launch_max_gas),
                                args.max_gas,
                            )
                            state.last_launch_boost_time = now
                            if state.temporary_gas != before:
                                event = f"Anfahr-Boost temporaer: {before}% -> {state.temporary_gas}%"
                            else:
                                event = f"Anfahr-Boost temporaer bleibt bei {before}%"
                            state.last_event = event
                            print(event)
                        target_gas = max(args.min_drive_gas, state.temporary_gas)
                    stepper.gas(target_gas, state, now)
                elif loss_ready and lost_by_standing and state.current_gas < args.stall_boost_limit:
                    if now - state.last_stall_boost_time >= args.stopped_timeout:
                        before = state.temporary_gas
                        state.temporary_gas = clamp_gas(
                            min(
                                max(state.temporary_gas, state.current_gas) + args.stall_boost_step,
                                args.launch_max_gas,
                            ),
                            args.max_gas,
                        )
                        state.last_stall_boost_time = now
                        state.motion_window.clear()
                        event = f"Stall-Boost temporaer: {before}% -> {state.temporary_gas}%"
                        state.last_event = event
                        print(event)
                    target_gas = max(args.min_drive_gas, state.temporary_gas)
                    stepper.gas(target_gas, state, now)
                elif loss_ready and (lost_by_detection or lost_by_standing):
                    state.loss_count += 1
                    state.losses_since_lap += 1
                    fallback = cell_key
                    if not fallback and state.recent_path:
                        fallback = state.recent_path[-1].cell_key
                    event = apply_loss_to_recent_cells(state, local_drops, args, now, fallback, road)
                    reason = "nicht erkannt" if lost_by_detection else f"steht > {args.stopped_timeout:.1f}s"
                    state.last_event = f"{event} ({reason})"
                    stepper.gas(0, state, now, force=True)
                    stepper.send("release", force=True)
                    state.mode = "LOST"
                    target_gas = 0
                    save_learning_map(profile_path, state, local_drops, args)
                    print(state.last_event)
                else:
                    if car is None:
                        target_gas = hold_or_minimum_gas(state, args)
                    else:
                        target_gas = gas_for_position(state, local_drops, cell_key, args)
                        target_gas = max(args.min_drive_gas, target_gas)
                    stepper.gas(target_gas, state, now)
            else:
                if state.current_gas != 0:
                    stepper.gas(0, state, now, force=True)
                target_gas = 0

            if event or now - last_row_time >= 0.10:
                write_row(rows, started_at, state, event, section, cell_key, target_gas, speed_px_s, car)
                last_row_time = now

            if not args.no_gui:
                draw_learning_map(frame, state, local_drops, args)
                draw_car(frame, args.car, car, candidates)
                draw_status(frame, state, local_drops, section, cell_key, target_gas, speed_px_s, args)
                cv2.imshow("AI Race Trainer", frame)
                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):
                    break
                if key in (ord("s"), ord(" ")):
                    start_run(stepper, state, args, time.monotonic(), cap, frame)
                if key == ord("r"):
                    local_drops.clear()
                    state.base_gas = args.start_gas
                    state.completed_laps = 0
                    state.loss_count = 0
                    state.losses_since_lap = 0
                    state.known_cells.clear()
                    state.lap_cells.clear()
                    state.cell_failures.clear()
                    state.cell_limits.clear()
                    state.clean_laps_since_boost = 0
                    state.clean_boost_series = 0
                    state.last_event = f"Lernkarte reset: wieder {args.start_gas}% auf ganzer Strecke"
                    save_learning_map(profile_path, state, local_drops, args)
                    print(state.last_event)
                if key == ord("m"):
                    cv2.imwrite("ai_race_learning_map.jpg", frame)
                    state.last_event = "Lernkarte als ai_race_learning_map.jpg gespeichert"
                    print(state.last_event)
            elif not args.auto_start:
                raise SystemExit("--no-gui braucht --auto-start.")
    finally:
        try:
            stepper.gas(0, state, time.monotonic(), force=True)
            stepper.send("release", force=True)
        finally:
            cap.release()
            if not args.no_gui:
                cv2.destroyAllWindows()
            stepper.close()

    out = Path(args.output)
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "time_s",
                "mode",
                "run",
                "laps",
                "losses",
                "losses_since_lap",
                "event",
                "section",
                "cell",
                "base_gas",
                "target_gas",
                "speed_px_s",
                "x",
                "y",
                "area",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    save_learning_map(profile_path, state, local_drops, args)
    print(f"Log gespeichert: {out.resolve()}")
    print(f"Lernprofil gespeichert: {profile_path.resolve()}")


if __name__ == "__main__":
    main()
