from __future__ import annotations

import argparse
import contextlib
import csv
import json
import queue
import statistics
import threading
import time
import webbrowser
from dataclasses import dataclass, field
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import StringIO
from typing import Any
from urllib.parse import urlparse

try:
    from carreralib import ControlUnit, connection
    from carreralib.connection import TimeoutError as CarreraTimeout
except ModuleNotFoundError as exc:
    raise SystemExit(
        "carreralib fehlt. Installiere zuerst die Abhaengigkeiten mit:\n"
        "  .\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt"
    ) from exc


DEFAULT_DEVICE = "C5:7D:F4:7A:AC:42"
CAR_COUNT = 2
MAX_TIMESTAMP = 2**32


def format_ms(value: int | None) -> str:
    if value is None:
        return "-"
    minutes, remainder = divmod(value, 60_000)
    seconds, millis = divmod(remainder, 1000)
    if minutes:
        return f"{minutes}:{seconds:02d}.{millis:03d}"
    return f"{seconds}.{millis:03d}"


@dataclass
class LapEvent:
    id: int
    car: int
    lap: int
    lap_ms: int
    cu_timestamp_ms: int
    sector: int
    wall_time: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "car": self.car,
            "lap": self.lap,
            "lap_ms": self.lap_ms,
            "lap_time": format_ms(self.lap_ms),
            "cu_timestamp_ms": self.cu_timestamp_ms,
            "sector": self.sector,
            "wall_time": self.wall_time,
        }


@dataclass
class DriverState:
    address: int
    last_timestamp_ms: int | None = None
    laps: list[LapEvent] = field(default_factory=list)
    fuel: int | None = None
    pit: bool = False

    @property
    def car(self) -> int:
        return self.address + 1

    def add_start_pass(self, timestamp_ms: int) -> None:
        self.last_timestamp_ms = timestamp_ms

    def add_lap(self, event: LapEvent) -> None:
        self.laps.append(event)
        self.last_timestamp_ms = event.cu_timestamp_ms

    def as_dict(self) -> dict[str, Any]:
        values = [lap.lap_ms for lap in self.laps]
        best = min(values) if values else None
        avg = round(statistics.mean(values)) if values else None
        total = sum(values) if values else None
        return {
            "car": self.car,
            "address": self.address,
            "laps": len(values),
            "last_lap_ms": values[-1] if values else None,
            "last_lap": format_ms(values[-1]) if values else "-",
            "best_lap_ms": best,
            "best_lap": format_ms(best),
            "avg_lap_ms": avg,
            "avg_lap": format_ms(avg),
            "total_time_ms": total,
            "total_time": format_ms(total),
            "last_timestamp_ms": self.last_timestamp_ms,
            "fuel": self.fuel,
            "pit": self.pit,
            "armed": self.last_timestamp_ms is not None,
            "active": self.last_timestamp_ms is not None or bool(values),
        }


@dataclass
class TimeTrialLap:
    driver: int
    driver_name: str
    lap: int
    lap_ms: int
    cu_timestamp_ms: int
    wall_time: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "driver": self.driver,
            "driver_name": self.driver_name,
            "lap": self.lap,
            "lap_ms": self.lap_ms,
            "lap_time": format_ms(self.lap_ms),
            "cu_timestamp_ms": self.cu_timestamp_ms,
            "wall_time": self.wall_time,
        }


@dataclass
class TimeTrialRun:
    driver: int
    name: str
    target_laps: int
    status: str = "waiting"
    start_timestamp_ms: int | None = None
    last_timestamp_ms: int | None = None
    started_at: str = ""
    finished_at: str = ""
    laps: list[TimeTrialLap] = field(default_factory=list)

    def start(self) -> None:
        self.status = "waiting"
        self.start_timestamp_ms = None
        self.last_timestamp_ms = None
        self.started_at = ""
        self.finished_at = ""
        self.laps = []

    def arm_from_timer(self, timestamp_ms: int) -> None:
        self.status = "running"
        self.start_timestamp_ms = timestamp_ms
        self.last_timestamp_ms = timestamp_ms
        self.started_at = datetime.now().isoformat(timespec="seconds")

    def add_lap(self, lap_ms: int, timestamp_ms: int) -> TimeTrialLap:
        lap = TimeTrialLap(
            driver=self.driver,
            driver_name=self.name,
            lap=len(self.laps) + 1,
            lap_ms=lap_ms,
            cu_timestamp_ms=timestamp_ms,
            wall_time=datetime.now().isoformat(timespec="seconds"),
        )
        self.laps.append(lap)
        self.last_timestamp_ms = timestamp_ms
        if len(self.laps) >= self.target_laps:
            self.status = "done"
            self.finished_at = lap.wall_time
        return lap

    def as_dict(self) -> dict[str, Any]:
        values = [lap.lap_ms for lap in self.laps]
        total = sum(values) if values else None
        avg = round(statistics.mean(values)) if values else None
        best = min(values) if values else None
        return {
            "driver": self.driver,
            "name": self.name,
            "status": self.status,
            "status_label": {
                "waiting": "wartet auf erste Durchfahrt",
                "running": "faehrt",
                "done": "fertig",
            }.get(self.status, self.status),
            "target_laps": self.target_laps,
            "laps": len(values),
            "complete": len(values) >= self.target_laps,
            "total_time_ms": total,
            "total_time": format_ms(total),
            "avg_lap_ms": avg,
            "avg_lap": format_ms(avg),
            "best_lap_ms": best,
            "best_lap": format_ms(best),
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "lap_events": [lap.as_dict() for lap in self.laps],
        }


@dataclass
class TimeTrialState:
    target_laps: int = 10
    phase: str = "idle"
    current_driver: int | None = None
    car_address: int | None = None
    runs: list[TimeTrialRun] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.runs:
            self.runs = [
                TimeTrialRun(driver=1, name="Fahrer 1", target_laps=self.target_laps),
                TimeTrialRun(driver=2, name="Fahrer 2", target_laps=self.target_laps),
            ]

    def start_first_driver(self) -> None:
        self.phase = "driver1_waiting"
        self.current_driver = 0
        self.car_address = None
        for run in self.runs:
            run.start()

    def start_second_driver(self) -> bool:
        if self.phase != "driver1_done":
            return False
        self.phase = "driver2_waiting"
        self.current_driver = 1
        self.runs[1].start()
        return True

    def handle_timer(self, timer: ControlUnit.Timer, min_lap_ms: int) -> TimeTrialLap | None:
        if self.current_driver is None:
            return None
        if self.car_address is None:
            self.car_address = timer.address
        elif timer.address != self.car_address:
            return None

        run = self.runs[self.current_driver]
        if run.last_timestamp_ms is None:
            run.arm_from_timer(timer.timestamp)
            self.phase = f"driver{run.driver}_running"
            return None

        lap_ms = timer.timestamp - run.last_timestamp_ms
        if lap_ms < 0:
            lap_ms += MAX_TIMESTAMP
        if lap_ms < min_lap_ms:
            return None

        lap = run.add_lap(lap_ms, timer.timestamp)
        if run.status == "done":
            if self.current_driver == 0:
                self.phase = "driver1_done"
                self.current_driver = None
            else:
                self.phase = "complete"
                self.current_driver = None
        return lap

    def result(self) -> dict[str, Any]:
        if not all(len(run.laps) >= self.target_laps for run in self.runs):
            return {"complete": False}

        run_a, run_b = self.runs
        total_winner = min(self.runs, key=lambda run: sum(lap.lap_ms for lap in run.laps))
        avg_winner = min(
            self.runs,
            key=lambda run: statistics.mean([lap.lap_ms for lap in run.laps]),
        )
        total_delta = abs(sum(lap.lap_ms for lap in run_a.laps) - sum(lap.lap_ms for lap in run_b.laps))
        avg_delta = abs(
            round(statistics.mean([lap.lap_ms for lap in run_a.laps]))
            - round(statistics.mean([lap.lap_ms for lap in run_b.laps]))
        )
        return {
            "complete": True,
            "total_winner": total_winner.name,
            "avg_winner": avg_winner.name,
            "total_delta_ms": total_delta,
            "total_delta": format_ms(total_delta),
            "avg_delta_ms": avg_delta,
            "avg_delta": format_ms(avg_delta),
        }

    def as_dict(self) -> dict[str, Any]:
        phase_labels = {
            "idle": "kein Duell aktiv",
            "driver1_waiting": "Fahrer 1: erste Durchfahrt",
            "driver1_running": "Fahrer 1 faehrt",
            "driver1_done": "Fahrer 1 fertig",
            "driver2_waiting": "Fahrer 2: erste Durchfahrt",
            "driver2_running": "Fahrer 2 faehrt",
            "complete": "Duell fertig",
        }
        current_run = self.runs[self.current_driver] if self.current_driver is not None else None
        lap_events = []
        for run in self.runs:
            lap_events.extend(lap.as_dict() for lap in run.laps)
        return {
            "target_laps": self.target_laps,
            "phase": self.phase,
            "phase_label": phase_labels.get(self.phase, self.phase),
            "current_driver": None if current_run is None else current_run.driver,
            "current_driver_name": "" if current_run is None else current_run.name,
            "car": None if self.car_address is None else self.car_address + 1,
            "can_start_next": self.phase == "driver1_done",
            "runs": [run.as_dict() for run in self.runs],
            "laps": lap_events,
            "result": self.result(),
        }


class LapState:
    def __init__(self, min_lap_ms: int, sector: int) -> None:
        self.lock = threading.Lock()
        self.min_lap_ms = min_lap_ms
        self.sector = sector
        self.running = True
        self.started_at = datetime.now().isoformat(timespec="seconds")
        self.connected = False
        self.status = "starting"
        self.device = ""
        self.requested_device = ""
        self.firmware = ""
        self.last_message_at = ""
        self.last_error = ""
        self.start_light = 0
        self.display = 0
        self.mode = 0
        self._drivers = [DriverState(address=index) for index in range(CAR_COUNT)]
        self._events: list[LapEvent] = []
        self._next_event_id = 1
        self._last_timer_key: tuple[int, int, int] | None = None
        self._ignore_timers_until = 0.0
        self._time_trial = TimeTrialState(target_laps=10)

    def _clear_lap_tracking_locked(self, ignore_seconds: float) -> None:
        self._drivers = [DriverState(address=index) for index in range(CAR_COUNT)]
        self._events = []
        self._next_event_id = 1
        self._last_timer_key = None
        self._ignore_timers_until = time.monotonic() + ignore_seconds
        self.started_at = datetime.now().isoformat(timespec="seconds")

    def reset_laps(self, ignore_seconds: float = 1.0, reset_time_trial: bool = True) -> None:
        with self.lock:
            self._clear_lap_tracking_locked(ignore_seconds)
            if reset_time_trial:
                self._time_trial = TimeTrialState(target_laps=10)
            self.status = "reset"

    def start_time_trial(self, ignore_seconds: float = 1.0) -> None:
        with self.lock:
            self._clear_lap_tracking_locked(ignore_seconds)
            self._time_trial = TimeTrialState(target_laps=10)
            self._time_trial.start_first_driver()
            self.status = "time trial"

    def prepare_time_trial_driver(self, ignore_seconds: float = 1.0) -> None:
        with self.lock:
            self._clear_lap_tracking_locked(ignore_seconds)
            self.status = "time trial"

    def start_next_time_trial_driver(self, ignore_seconds: float = 1.0) -> bool:
        with self.lock:
            if not self._time_trial.start_second_driver():
                return False
            self._clear_lap_tracking_locked(ignore_seconds)
            self.status = "time trial"
            return True

    def set_connecting(self, requested_device: str) -> None:
        with self.lock:
            self.requested_device = requested_device
            self.status = "connecting"
            self.connected = False
            self.last_error = ""

    def set_connected(self, device: str, firmware: str | None) -> None:
        with self.lock:
            self.connected = True
            self.device = device
            self.firmware = firmware or "-"
            self.status = "connected"
            self.last_error = ""
            self.last_message_at = datetime.now().isoformat(timespec="seconds")

    def set_disconnected(self, error: Exception | str) -> None:
        with self.lock:
            self.connected = False
            self.status = "disconnected"
            self.last_error = str(error)
            self.last_message_at = datetime.now().isoformat(timespec="seconds")

    def handle_status(self, status: ControlUnit.Status) -> None:
        with self.lock:
            self.start_light = status.start
            self.display = min(status.display, CAR_COUNT)
            self.mode = status.mode
            for driver, fuel in zip(self._drivers, status.fuel):
                driver.fuel = fuel
            for driver, pit in zip(self._drivers, status.pit):
                driver.pit = bool(pit)
            self.status = "connected"
            self.connected = True
            self.last_message_at = datetime.now().isoformat(timespec="seconds")

    def handle_timer(self, timer: ControlUnit.Timer) -> LapEvent | None:
        if self.sector and timer.sector != self.sector:
            return None
        if timer.address < 0 or timer.address >= len(self._drivers):
            return None

        key = (timer.address, timer.timestamp, timer.sector)
        with self.lock:
            if time.monotonic() < self._ignore_timers_until:
                self.status = "reset"
                self.connected = True
                self.last_message_at = datetime.now().isoformat(timespec="seconds")
                return None
            if key == self._last_timer_key:
                return None
            self._last_timer_key = key
            self._time_trial.handle_timer(timer, self.min_lap_ms)
            driver = self._drivers[timer.address]
            if driver.last_timestamp_ms is None:
                driver.add_start_pass(timer.timestamp)
                self.status = "first pass"
                self.connected = True
                self.last_message_at = datetime.now().isoformat(timespec="seconds")
                return None

            lap_ms = timer.timestamp - driver.last_timestamp_ms
            if lap_ms < 0:
                lap_ms += MAX_TIMESTAMP
            if lap_ms < self.min_lap_ms:
                self.last_message_at = datetime.now().isoformat(timespec="seconds")
                return None

            event = LapEvent(
                id=self._next_event_id,
                car=driver.car,
                lap=len(driver.laps) + 1,
                lap_ms=lap_ms,
                cu_timestamp_ms=timer.timestamp,
                sector=timer.sector,
                wall_time=datetime.now().isoformat(timespec="seconds"),
            )
            self._next_event_id += 1
            driver.add_lap(event)
            self._events.append(event)
            self.status = "lap"
            self.connected = True
            self.last_message_at = event.wall_time
            return event

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            drivers = [driver.as_dict() for driver in self._drivers]
            events = [event.as_dict() for event in self._events]
            active = [driver for driver in drivers if driver["active"]]
            leaderboard = sorted(
                active,
                key=lambda row: (-row["laps"], row["total_time_ms"] or 10**12, row["car"]),
            )
            return {
                "connected": self.connected,
                "status": self.status,
                "requested_device": self.requested_device,
                "device": self.device,
                "firmware": self.firmware,
                "last_message_at": self.last_message_at,
                "last_error": self.last_error,
                "started_at": self.started_at,
                "min_lap_ms": self.min_lap_ms,
                "sector": self.sector,
                "start_light": self.start_light,
                "display": self.display,
                "mode": self.mode,
                "car_count": CAR_COUNT,
                "drivers": drivers,
                "leaderboard": leaderboard,
                "events": events,
                "event_count": len(events),
                "time_trial": self._time_trial.as_dict(),
            }

    def csv_text(self) -> str:
        with self.lock:
            output = StringIO()
            writer = csv.DictWriter(
                output,
                fieldnames=[
                    "id",
                    "car",
                    "lap",
                    "lap_ms",
                    "lap_time",
                    "cu_timestamp_ms",
                    "sector",
                    "wall_time",
                ],
            )
            writer.writeheader()
            for event in self._events:
                writer.writerow(event.as_dict())
            return output.getvalue()


class CarreraWorker(threading.Thread):
    def __init__(
        self,
        state: LapState,
        device: str,
        timeout: float,
        reconnect_delay: float,
    ) -> None:
        super().__init__(daemon=True)
        self.state = state
        self.device = device
        self.timeout = timeout
        self.reconnect_delay = reconnect_delay
        self.commands: queue.Queue[tuple[int, str]] = queue.Queue()
        self.command_lock = threading.Lock()
        self.command_generation = 0

    def run(self) -> None:
        while self.state.running:
            resolved_device = ""
            try:
                self.state.set_connecting(self.device)
                resolved_device = self._resolve_device()
                with contextlib.closing(ControlUnit(resolved_device, timeout=self.timeout)) as cu:
                    firmware = cu.version()
                    self.state.set_connected(resolved_device, firmware)
                    self._poll_loop(cu)
            except Exception as exc:  # noqa: BLE/serial backends raise different types.
                self.state.set_disconnected(exc)
                self._sleep_or_stop(self.reconnect_delay)

    def reset(self) -> None:
        self.state.reset_laps()
        self._enqueue("reset")

    def clear(self) -> None:
        self.state.reset_laps()
        self._enqueue("clear")

    def start_race(self) -> None:
        self._enqueue("start")

    def start_time_trial(self) -> None:
        self.state.start_time_trial()
        self._enqueue("time_trial_start")

    def start_next_time_trial_driver(self) -> None:
        if self.state.start_next_time_trial_driver():
            self._enqueue("time_trial_next")

    def _enqueue(self, command: str) -> None:
        with self.command_lock:
            self.command_generation += 1
            generation = self.command_generation
            self._clear_pending_commands()
            self.commands.put((generation, command))

    def _clear_pending_commands(self) -> None:
        while True:
            try:
                self.commands.get_nowait()
            except queue.Empty:
                return

    def _command_is_current(self, generation: int) -> bool:
        with self.command_lock:
            return generation == self.command_generation

    def _resolve_device(self) -> str:
        if self.device.lower() != "auto":
            return self.device
        found = list(connection.scan())
        if not found:
            raise RuntimeError("Kein AppConnect/Control_Unit per Bluetooth oder COM gefunden")
        return found[0][0]

    def _poll_loop(self, cu: ControlUnit) -> None:
        while self.state.running:
            self._run_commands(cu)
            try:
                msg = cu.poll()
            except CarreraTimeout:
                continue

            if isinstance(msg, ControlUnit.Timer):
                self.state.handle_timer(msg)
            elif isinstance(msg, ControlUnit.Status):
                self.state.handle_status(msg)

    def _run_commands(self, cu: ControlUnit) -> None:
        while True:
            try:
                generation, command = self.commands.get_nowait()
            except queue.Empty:
                return
            if not self._command_is_current(generation):
                continue
            if command == "reset":
                self._discard_pending_timers(cu)
                cu.reset()
                with contextlib.suppress(Exception):
                    cu.clrpos()
                self._discard_pending_timers(cu)
                if self._command_is_current(generation):
                    self.state.reset_laps(ignore_seconds=1.0)
            elif command == "clear":
                if self._command_is_current(generation):
                    self.state.reset_laps(ignore_seconds=1.0)
            elif command == "start":
                cu.start()
            elif command == "time_trial_start":
                self._discard_pending_timers(cu)
                cu.reset()
                with contextlib.suppress(Exception):
                    cu.clrpos()
                self._discard_pending_timers(cu)
                if self._command_is_current(generation):
                    self.state.start_time_trial(ignore_seconds=1.0)
            elif command == "time_trial_next":
                self._discard_pending_timers(cu)
                cu.reset()
                with contextlib.suppress(Exception):
                    cu.clrpos()
                self._discard_pending_timers(cu)
                if self._command_is_current(generation):
                    self.state.prepare_time_trial_driver(ignore_seconds=1.0)

    def _discard_pending_timers(self, cu: ControlUnit) -> None:
        status_count = 0
        for _ in range(40):
            if not self.state.running:
                return
            try:
                msg = cu.poll()
            except CarreraTimeout:
                return
            if isinstance(msg, ControlUnit.Status):
                self.state.handle_status(msg)
                status_count += 1
                if status_count >= 2:
                    return
            else:
                status_count = 0

    def _sleep_or_stop(self, seconds: float) -> None:
        deadline = time.monotonic() + seconds
        while self.state.running and time.monotonic() < deadline:
            time.sleep(0.1)


HTML = r"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Carrera Rundenzeiten</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #111314;
      --panel: #1a1d1f;
      --panel-2: #202427;
      --line: #33383d;
      --text: #f4f4f1;
      --muted: #aeb4b9;
      --good: #50c878;
      --warn: #e0aa3e;
      --bad: #dc5f5f;
      --cyan: #3cb9d7;
      --orange: #ef7c2f;
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: Arial, Helvetica, sans-serif;
      font-size: 15px;
      letter-spacing: 0;
    }

    header {
      display: grid;
      grid-template-columns: minmax(220px, 1fr) auto;
      gap: 14px;
      align-items: center;
      padding: 14px 18px;
      border-bottom: 1px solid var(--line);
      background: #151719;
      position: sticky;
      top: 0;
      z-index: 4;
    }

    h1 {
      margin: 0;
      font-size: 22px;
      font-weight: 700;
      line-height: 1.1;
    }

    .subline {
      margin-top: 5px;
      color: var(--muted);
      font-size: 13px;
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
    }

    .actions {
      display: flex;
      gap: 8px;
      align-items: center;
      flex-wrap: wrap;
      justify-content: flex-end;
    }

    button,
    a.button {
      min-height: 36px;
      padding: 0 12px;
      border: 1px solid var(--line);
      background: var(--panel-2);
      color: var(--text);
      border-radius: 6px;
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      font-weight: 700;
      white-space: nowrap;
    }

    button.primary { border-color: #4f8f62; background: #214b2d; }
    button.danger { border-color: #8b4141; background: #512626; }
    button:disabled { opacity: .55; cursor: wait; }

    main {
      display: grid;
      grid-template-columns: minmax(320px, 390px) minmax(0, 1fr);
      min-height: calc(100vh - 66px);
    }

    aside {
      border-right: 1px solid var(--line);
      background: #151719;
      padding: 16px;
    }

    section {
      padding: 16px 18px 22px;
    }

    .status {
      display: grid;
      gap: 10px;
      margin-bottom: 18px;
    }

    .status-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding-bottom: 9px;
      border-bottom: 1px solid var(--line);
    }

    .label { color: var(--muted); font-size: 12px; text-transform: uppercase; }
    .value { font-weight: 700; text-align: right; overflow-wrap: anywhere; }

    .dot {
      width: 10px;
      height: 10px;
      border-radius: 50%;
      background: var(--bad);
      display: inline-block;
      margin-right: 7px;
    }

    .dot.on { background: var(--good); }
    .dot.wait { background: var(--warn); }

    .summary-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
      margin-bottom: 18px;
    }

    .metric {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 12px;
      min-height: 78px;
    }

    .metric strong {
      display: block;
      margin-top: 7px;
      font-size: 26px;
      line-height: 1;
    }

    .drivers {
      display: grid;
      gap: 8px;
    }

    .driver {
      display: grid;
      grid-template-columns: 54px 1fr 82px;
      gap: 10px;
      align-items: center;
      min-height: 54px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--panel);
      padding: 9px 10px;
    }

    .driver.active { border-color: #52636b; }
    .car-badge {
      width: 42px;
      height: 34px;
      display: grid;
      place-items: center;
      border-radius: 5px;
      background: #2f3539;
      font-weight: 800;
      color: white;
    }

    .driver:nth-child(1) .car-badge { background: var(--orange); }
    .driver:nth-child(2) .car-badge { background: var(--cyan); }
    .driver-main {
      display: grid;
      gap: 3px;
      min-width: 0;
    }

    .driver-main strong {
      font-size: 17px;
      overflow-wrap: anywhere;
    }

    .driver-main span,
    .driver-side span {
      color: var(--muted);
      font-size: 12px;
    }

    .driver-side {
      text-align: right;
      display: grid;
      gap: 2px;
    }

    .tables {
      display: grid;
      gap: 20px;
    }

    .table-wrap {
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--panel);
    }

    h2 {
      margin: 0 0 10px;
      font-size: 18px;
    }

    table {
      width: 100%;
      border-collapse: collapse;
      min-width: 620px;
    }

    th, td {
      padding: 10px 12px;
      border-bottom: 1px solid var(--line);
      text-align: right;
      white-space: nowrap;
    }

    th {
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      background: #181b1d;
      position: sticky;
      top: 0;
      z-index: 1;
    }

    td:first-child,
    th:first-child {
      text-align: left;
    }

    tr:last-child td { border-bottom: 0; }
    .empty { color: var(--muted); padding: 18px; }
    .error { color: #ffb4b4; overflow-wrap: anywhere; }

    .duel-panel {
      border-top: 1px solid var(--line);
      border-bottom: 1px solid var(--line);
      padding: 16px 0;
      margin: 18px 0;
    }

    .duel-actions {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin-bottom: 12px;
    }

    .duel-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
      margin: 12px 0;
    }

    .duel-stat {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 10px;
      min-height: 64px;
    }

    .duel-stat strong {
      display: block;
      margin-top: 5px;
      font-size: 20px;
      line-height: 1.1;
      overflow-wrap: anywhere;
    }

    .trial-runs {
      display: grid;
      gap: 8px;
      margin-top: 10px;
    }

    .trial-run {
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--panel);
      padding: 10px;
      display: grid;
      gap: 8px;
    }

    .trial-run.active { border-color: var(--warn); }
    .trial-run.done { border-color: var(--good); }

    .trial-run-head {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: baseline;
    }

    .trial-run-head span {
      color: var(--muted);
      font-size: 12px;
      text-align: right;
    }

    .trial-run-values {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 8px;
      color: var(--muted);
      font-size: 12px;
    }

    .trial-run-values strong {
      display: block;
      color: var(--text);
      font-size: 15px;
      margin-top: 3px;
    }

    .trial-result {
      min-height: 44px;
      color: var(--muted);
      overflow-wrap: anywhere;
    }

    .trial-result strong {
      color: var(--text);
    }

    @media (max-width: 920px) {
      header {
        grid-template-columns: 1fr;
      }

      .actions {
        justify-content: flex-start;
      }

      main {
        grid-template-columns: 1fr;
      }

      aside {
        border-right: 0;
        border-bottom: 1px solid var(--line);
      }
    }

    @media (max-width: 520px) {
      header, aside, section { padding-left: 12px; padding-right: 12px; }
      h1 { font-size: 20px; }
      .summary-grid { grid-template-columns: 1fr; }
      .duel-grid { grid-template-columns: 1fr; }
      .driver { grid-template-columns: 46px 1fr 74px; }
      .car-badge { width: 36px; }
    }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>Carrera Rundenzeiten</h1>
      <div class="subline">
        <span id="connectionText">Verbinde...</span>
        <span id="deviceText"></span>
        <span id="firmwareText"></span>
      </div>
    </div>
    <div class="actions">
      <button id="startButton" class="primary">Start</button>
      <button id="resetButton" class="danger">Reset</button>
      <a id="exportButton" class="button" href="/api/export.csv">CSV</a>
    </div>
  </header>
  <main>
    <aside>
      <div class="status">
        <div class="status-row">
          <span class="label">Status</span>
          <span class="value"><span id="statusDot" class="dot"></span><span id="statusValue">-</span></span>
        </div>
        <div class="status-row">
          <span class="label">Letzte Meldung</span>
          <span class="value" id="lastMessage">-</span>
        </div>
        <div class="status-row">
          <span class="label">Runden</span>
          <span class="value" id="totalLaps">0</span>
        </div>
        <div class="status-row">
          <span class="label">Beste Runde</span>
          <span class="value" id="bestLap">-</span>
        </div>
        <div class="status-row">
          <span class="label">Startampel</span>
          <span class="value" id="startLight">0</span>
        </div>
        <div class="status-row">
          <span class="label">Filter</span>
          <span class="value" id="filterText">-</span>
        </div>
      </div>

      <div class="summary-grid">
        <div class="metric">
          <span class="label">Fuehrung</span>
          <strong id="leaderCar">-</strong>
        </div>
        <div class="metric">
          <span class="label">Letzte Runde</span>
          <strong id="latestLap">-</strong>
        </div>
      </div>

      <div class="duel-panel">
        <h2>10 Runden Duell</h2>
        <div class="duel-actions">
          <button id="trialStartButton" class="primary">Duell neu</button>
          <button id="trialNextButton">Fahrer 2 starten</button>
        </div>
        <div class="duel-grid">
          <div class="duel-stat">
            <span class="label">Phase</span>
            <strong id="trialPhase">-</strong>
          </div>
          <div class="duel-stat">
            <span class="label">Auto</span>
            <strong id="trialCar">-</strong>
          </div>
          <div class="duel-stat">
            <span class="label">Fortschritt</span>
            <strong id="trialProgress">-</strong>
          </div>
          <div class="duel-stat">
            <span class="label">Gewinner</span>
            <strong id="trialWinner">-</strong>
          </div>
        </div>
        <div id="trialRuns" class="trial-runs"></div>
        <div id="trialResult" class="trial-result"></div>
      </div>

      <h2>Autos 1-2</h2>
      <div id="drivers" class="drivers"></div>
      <p id="errorText" class="error"></p>
    </aside>

    <section>
      <div class="tables">
        <div>
          <h2>Duell-Runden</h2>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Fahrer</th>
                  <th>Runde</th>
                  <th>Zeit</th>
                  <th>CU ms</th>
                  <th>Uhrzeit</th>
                </tr>
              </thead>
              <tbody id="trialLapsBody"></tbody>
            </table>
            <div id="trialLapsEmpty" class="empty">Noch kein 10-Runden-Duell gestartet.</div>
          </div>
        </div>

        <div>
          <h2>Wertung</h2>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Auto</th>
                  <th>Runden</th>
                  <th>Letzte</th>
                  <th>Beste</th>
                  <th>Schnitt</th>
                  <th>Gesamt</th>
                </tr>
              </thead>
              <tbody id="leaderboardBody"></tbody>
            </table>
            <div id="leaderboardEmpty" class="empty">Noch keine Runde.</div>
          </div>
        </div>

        <div>
          <h2>Alle Runden</h2>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  <th>Auto</th>
                  <th>Runde</th>
                  <th>Zeit</th>
                  <th>CU ms</th>
                  <th>Sektor</th>
                  <th>Uhrzeit</th>
                </tr>
              </thead>
              <tbody id="eventsBody"></tbody>
            </table>
            <div id="eventsEmpty" class="empty">Noch keine Durchfahrt mit kompletter Runde.</div>
          </div>
        </div>
      </div>
    </section>
  </main>

  <script>
    const statusDot = document.getElementById('statusDot');
    const statusValue = document.getElementById('statusValue');
    const connectionText = document.getElementById('connectionText');
    const deviceText = document.getElementById('deviceText');
    const firmwareText = document.getElementById('firmwareText');
    const lastMessage = document.getElementById('lastMessage');
    const totalLaps = document.getElementById('totalLaps');
    const bestLap = document.getElementById('bestLap');
    const startLight = document.getElementById('startLight');
    const filterText = document.getElementById('filterText');
    const leaderCar = document.getElementById('leaderCar');
    const latestLap = document.getElementById('latestLap');
    const driversEl = document.getElementById('drivers');
    const leaderboardBody = document.getElementById('leaderboardBody');
    const eventsBody = document.getElementById('eventsBody');
    const leaderboardEmpty = document.getElementById('leaderboardEmpty');
    const eventsEmpty = document.getElementById('eventsEmpty');
    const errorText = document.getElementById('errorText');
    const resetButton = document.getElementById('resetButton');
    const startButton = document.getElementById('startButton');
    const trialStartButton = document.getElementById('trialStartButton');
    const trialNextButton = document.getElementById('trialNextButton');
    const trialPhase = document.getElementById('trialPhase');
    const trialCar = document.getElementById('trialCar');
    const trialProgress = document.getElementById('trialProgress');
    const trialWinner = document.getElementById('trialWinner');
    const trialRuns = document.getElementById('trialRuns');
    const trialResult = document.getElementById('trialResult');
    const trialLapsBody = document.getElementById('trialLapsBody');
    const trialLapsEmpty = document.getElementById('trialLapsEmpty');

    function setBusy(button, busy) {
      button.disabled = busy;
    }

    async function postAction(path, button) {
      setBusy(button, true);
      try {
        await fetch(path, {method: 'POST'});
        await refresh();
      } finally {
        setBusy(button, false);
      }
    }

    resetButton.addEventListener('click', () => postAction('/api/reset', resetButton));
    startButton.addEventListener('click', () => postAction('/api/start', startButton));
    trialStartButton.addEventListener('click', () => postAction('/api/time-trial/start', trialStartButton));
    trialNextButton.addEventListener('click', () => postAction('/api/time-trial/next', trialNextButton));

    function row(cells) {
      return '<tr>' + cells.map(value => `<td>${value}</td>`).join('') + '</tr>';
    }

    function esc(value) {
      return String(value ?? '-').replace(/[&<>"']/g, char => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
      }[char]));
    }

    function renderDrivers(drivers) {
      driversEl.innerHTML = drivers.map(driver => `
        <div class="driver ${driver.active ? 'active' : ''}">
          <div class="car-badge">${driver.car}</div>
          <div class="driver-main">
            <strong>${driver.last_lap}</strong>
            <span>Best ${driver.best_lap} | Avg ${driver.avg_lap}</span>
          </div>
          <div class="driver-side">
            <strong>${driver.laps}</strong>
            <span>Runden</span>
          </div>
        </div>
      `).join('');
    }

    function renderLeaderboard(items) {
      leaderboardBody.innerHTML = items.map(driver => row([
        `Auto ${driver.car}`,
        driver.laps,
        driver.last_lap,
        driver.best_lap,
        driver.avg_lap,
        driver.total_time
      ])).join('');
      leaderboardEmpty.style.display = items.length ? 'none' : 'block';
    }

    function renderEvents(events) {
      const newest = [...events].reverse();
      eventsBody.innerHTML = newest.map(event => row([
        event.id,
        `Auto ${event.car}`,
        event.lap,
        `<strong>${event.lap_time}</strong>`,
        event.cu_timestamp_ms,
        event.sector,
        esc(event.wall_time.replace('T', ' '))
      ])).join('');
      eventsEmpty.style.display = events.length ? 'none' : 'block';
    }

    function renderTimeTrial(trial) {
      trialPhase.textContent = trial.phase_label;
      trialCar.textContent = trial.car ? `Auto ${trial.car}` : '-';
      trialNextButton.disabled = !trial.can_start_next;

      const activeRun = trial.current_driver ? trial.runs.find(run => run.driver === trial.current_driver) : null;
      if (activeRun && trial.phase !== 'idle' && trial.phase !== 'complete') {
        trialProgress.textContent = `${activeRun.name}: ${activeRun.laps}/${trial.target_laps}`;
      } else if (trial.phase === 'driver1_done') {
        trialProgress.textContent = `${trial.runs[0].name}: ${trial.runs[0].laps}/${trial.target_laps}`;
      } else if (trial.phase === 'complete') {
        trialProgress.textContent = `${trial.target_laps}/${trial.target_laps} + ${trial.target_laps}/${trial.target_laps}`;
      } else {
        trialProgress.textContent = '-';
      }

      if (trial.result.complete) {
        trialWinner.textContent = trial.result.total_winner;
        trialResult.innerHTML = `Gesamt: <strong>${esc(trial.result.total_winner)}</strong> mit ${trial.result.total_delta} Vorsprung. Schnitt: <strong>${esc(trial.result.avg_winner)}</strong> mit ${trial.result.avg_delta} Vorsprung.`;
      } else if (trial.phase === 'driver1_done') {
        trialWinner.textContent = '-';
        trialResult.textContent = 'Fahrer 1 ist fertig. Jetzt Auto zurueckstellen und Fahrer 2 starten.';
      } else {
        trialWinner.textContent = '-';
        trialResult.textContent = '';
      }

      trialRuns.innerHTML = trial.runs.map(run => `
        <div class="trial-run ${trial.current_driver === run.driver ? 'active' : ''} ${run.complete ? 'done' : ''}">
          <div class="trial-run-head">
            <strong>${esc(run.name)}</strong>
            <span>${esc(run.status_label)} | ${run.laps}/${run.target_laps}</span>
          </div>
          <div class="trial-run-values">
            <div>Gesamt<strong>${run.total_time}</strong></div>
            <div>Schnitt<strong>${run.avg_lap}</strong></div>
            <div>Beste<strong>${run.best_lap}</strong></div>
          </div>
        </div>
      `).join('');

      trialLapsBody.innerHTML = trial.laps.map(lap => row([
        esc(lap.driver_name),
        lap.lap,
        `<strong>${lap.lap_time}</strong>`,
        lap.cu_timestamp_ms,
        esc(lap.wall_time.replace('T', ' '))
      ])).join('');
      trialLapsEmpty.style.display = trial.laps.length ? 'none' : 'block';
    }

    function render(data) {
      statusDot.className = 'dot ' + (data.connected ? 'on' : (data.status === 'connecting' ? 'wait' : ''));
      statusValue.textContent = data.status;
      connectionText.textContent = data.connected ? 'Verbunden' : 'Nicht verbunden';
      deviceText.textContent = data.device || data.requested_device || '';
      firmwareText.textContent = data.firmware ? `Firmware ${data.firmware}` : '';
      lastMessage.textContent = (data.last_message_at || '-').replace('T', ' ');
      totalLaps.textContent = data.event_count;
      startLight.textContent = data.start_light;
      filterText.textContent = `Sektor ${data.sector || 'alle'} | min ${data.min_lap_ms} ms`;

      const allLapTimes = data.events.map(event => event.lap_ms);
      if (allLapTimes.length) {
        const best = data.events.reduce((a, b) => a.lap_ms <= b.lap_ms ? a : b);
        bestLap.textContent = `Auto ${best.car} ${best.lap_time}`;
        const latest = data.events[data.events.length - 1];
        latestLap.textContent = latest.lap_time;
      } else {
        bestLap.textContent = '-';
        latestLap.textContent = '-';
      }

      leaderCar.textContent = data.leaderboard.length ? `Auto ${data.leaderboard[0].car}` : '-';
      errorText.textContent = data.last_error || '';
      renderDrivers(data.drivers);
      renderTimeTrial(data.time_trial);
      renderLeaderboard(data.leaderboard);
      renderEvents(data.events);
    }

    async function refresh() {
      const response = await fetch('/api/state', {cache: 'no-store'});
      render(await response.json());
    }

    refresh();
    setInterval(refresh, 500);
  </script>
</body>
</html>
"""


def make_handler(state: LapState, worker: CarreraWorker):
    class LapTimeHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            return

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path in ("/", "/index.html"):
                self._send_text(HTTPStatus.OK, HTML, "text/html; charset=utf-8")
                return
            if parsed.path == "/api/state":
                self._send_json(state.snapshot())
                return
            if parsed.path == "/api/export.csv":
                self._send_text(
                    HTTPStatus.OK,
                    state.csv_text(),
                    "text/csv; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=carrera_laps.csv"},
                )
                return
            self.send_error(HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/api/reset":
                worker.reset()
                self._send_json({"ok": True})
                return
            if parsed.path == "/api/clear":
                worker.clear()
                self._send_json({"ok": True})
                return
            if parsed.path == "/api/start":
                worker.start_race()
                self._send_json({"ok": True})
                return
            if parsed.path == "/api/time-trial/start":
                worker.start_time_trial()
                self._send_json({"ok": True})
                return
            if parsed.path == "/api/time-trial/next":
                worker.start_next_time_trial_driver()
                self._send_json({"ok": True})
                return
            self.send_error(HTTPStatus.NOT_FOUND)

        def _send_json(self, payload: dict[str, Any]) -> None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def _send_text(
            self,
            status: HTTPStatus,
            text: str,
            content_type: str,
            headers: dict[str, str] | None = None,
        ) -> None:
            data = text.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            for key, value in (headers or {}).items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(data)

    return LapTimeHandler


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lokale Carrera-AppConnect-Rundenzeitnahme.")
    parser.add_argument(
        "device",
        nargs="?",
        default=DEFAULT_DEVICE,
        help=f"AppConnect-Adresse, COM-Port oder auto. Standard: {DEFAULT_DEVICE}",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8780)
    parser.add_argument("--timeout", type=float, default=0.35)
    parser.add_argument("--reconnect-delay", type=float, default=3.0)
    parser.add_argument("--min-lap-ms", type=int, default=800)
    parser.add_argument(
        "--sector",
        type=int,
        default=1,
        help="1 = Start/Ziel, 0 = alle Timer-Sektoren",
    )
    parser.add_argument("--no-browser", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    state = LapState(min_lap_ms=args.min_lap_ms, sector=args.sector)
    worker = CarreraWorker(
        state=state,
        device=args.device,
        timeout=args.timeout,
        reconnect_delay=args.reconnect_delay,
    )
    worker.start()

    server = ThreadingHTTPServer((args.host, args.port), make_handler(state, worker))
    url = f"http://{args.host}:{args.port}/"
    print(f"Carrera Rundenzeiten: {url}")
    print(f"AppConnect: {args.device}")
    print("Mit Ctrl+C beenden.")
    if not args.no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        state.running = False
        server.server_close()


if __name__ == "__main__":
    main()
