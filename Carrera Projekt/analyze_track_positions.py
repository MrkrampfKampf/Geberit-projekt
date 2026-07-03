from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass
class Sample:
    time_s: float
    x: int
    y: int
    area: float
    speed_px_s: float = 0.0
    section: str = ""
    distance_px: float = 0.0


SECTION_COLORS = {
    "bottom_straight": (80, 220, 80),
    "right_curve": (60, 180, 255),
    "top_straight": (255, 220, 80),
    "left_curve": (255, 120, 80),
    "s_curve": (220, 80, 255),
    "start_finish": (255, 255, 255),
    "transition": (160, 160, 160),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Erstellt aus Kamerapositionen eine einfache Carrera-Streckenkarte."
    )
    parser.add_argument("--input", default="dual_car_positions.csv")
    parser.add_argument("--car", default="orange")
    parser.add_argument("--background", default="dual_record_last_frame.jpg")
    parser.add_argument("--analysis-output", default="track_position_analysis.csv")
    parser.add_argument("--section-output", default="track_section_stats.csv")
    parser.add_argument("--overlay-output", default="track_map_overlay.jpg")
    parser.add_argument("--heatmap-output", default="track_speed_heatmap.jpg")
    parser.add_argument("--summary-output", default="track_summary.md")
    parser.add_argument("--max-step-px", type=float, default=190.0)
    return parser.parse_args()


def load_samples(path: Path, car: str) -> list[Sample]:
    rows: list[Sample] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if row["car"] != car:
                continue
            rows.append(
                Sample(
                    time_s=float(row["time_s"]),
                    x=int(float(row["x"])),
                    y=int(float(row["y"])),
                    area=float(row["area"]),
                )
            )
    return sorted(rows, key=lambda sample: sample.time_s)


def smooth_samples(samples: list[Sample]) -> list[Sample]:
    if len(samples) < 5:
        return samples

    smoothed: list[Sample] = []
    for index, sample in enumerate(samples):
        start = max(0, index - 1)
        end = min(len(samples), index + 2)
        xs = sorted(item.x for item in samples[start:end])
        ys = sorted(item.y for item in samples[start:end])
        mid = len(xs) // 2
        smoothed.append(
            Sample(
                time_s=sample.time_s,
                x=xs[mid],
                y=ys[mid],
                area=sample.area,
            )
        )
    return smoothed


def section_for(x: int, y: int) -> str:
    if 500 <= x <= 620 and 330 <= y <= 520:
        return "start_finish"
    if x >= 1060:
        return "right_curve"
    if x <= 205:
        return "left_curve"
    if y >= 385 and 205 < x < 1060:
        return "bottom_straight"
    if y <= 255 and 500 < x < 1060:
        return "top_straight"
    if 205 < x <= 560 and y < 385:
        return "s_curve"
    return "transition"


def annotate_samples(samples: list[Sample], max_step_px: float) -> list[Sample]:
    if not samples:
        return []

    result = [samples[0]]
    result[0].section = section_for(result[0].x, result[0].y)

    total_distance = 0.0
    previous = result[0]
    for sample in samples[1:]:
        dt = sample.time_s - previous.time_s
        dist = math.hypot(sample.x - previous.x, sample.y - previous.y)

        # Large jumps are almost always momentary color confusion, not real motion.
        if dt <= 0 or dist > max_step_px:
            continue

        total_distance += dist
        sample.speed_px_s = dist / dt
        sample.distance_px = total_distance
        sample.section = section_for(sample.x, sample.y)
        result.append(sample)
        previous = sample

    return result


def write_analysis(path: Path, samples: list[Sample]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["time_s", "x", "y", "speed_px_s", "section", "distance_px"],
        )
        writer.writeheader()
        for sample in samples:
            writer.writerow(
                {
                    "time_s": round(sample.time_s, 3),
                    "x": sample.x,
                    "y": sample.y,
                    "speed_px_s": round(sample.speed_px_s, 1),
                    "section": sample.section,
                    "distance_px": round(sample.distance_px, 1),
                }
            )


def section_stats(samples: list[Sample]) -> dict[str, dict[str, float]]:
    grouped: dict[str, list[Sample]] = defaultdict(list)
    for sample in samples:
        if sample.speed_px_s > 0:
            grouped[sample.section].append(sample)

    stats: dict[str, dict[str, float]] = {}
    for section, values in grouped.items():
        speeds = [sample.speed_px_s for sample in values]
        stats[section] = {
            "count": len(values),
            "avg_speed_px_s": sum(speeds) / len(speeds),
            "min_speed_px_s": min(speeds),
            "max_speed_px_s": max(speeds),
        }
    return stats


def write_section_stats(path: Path, stats: dict[str, dict[str, float]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["section", "count", "avg_speed_px_s", "min_speed_px_s", "max_speed_px_s"],
        )
        writer.writeheader()
        for section, values in sorted(stats.items()):
            writer.writerow(
                {
                    "section": section,
                    "count": values["count"],
                    "avg_speed_px_s": round(values["avg_speed_px_s"], 1),
                    "min_speed_px_s": round(values["min_speed_px_s"], 1),
                    "max_speed_px_s": round(values["max_speed_px_s"], 1),
                }
            )


def speed_color(speed: float, min_speed: float, max_speed: float) -> tuple[int, int, int]:
    if max_speed <= min_speed:
        ratio = 0.0
    else:
        ratio = max(0.0, min(1.0, (speed - min_speed) / (max_speed - min_speed)))
    value = np.uint8([[round(ratio * 255)]])
    bgr = cv2.applyColorMap(value, cv2.COLORMAP_TURBO)[0][0]
    return int(bgr[0]), int(bgr[1]), int(bgr[2])


def draw_legend(image: np.ndarray, min_speed: float, max_speed: float) -> None:
    x0, y0 = 20, 22
    width, height = 260, 18
    for i in range(width):
        color = speed_color(min_speed + (max_speed - min_speed) * i / width, min_speed, max_speed)
        cv2.line(image, (x0 + i, y0), (x0 + i, y0 + height), color, 1)
    cv2.rectangle(image, (x0, y0), (x0 + width, y0 + height), (255, 255, 255), 1)
    cv2.putText(
        image,
        f"Speed px/s {min_speed:.0f} -> {max_speed:.0f}",
        (x0, y0 + 42),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (255, 255, 255),
        2,
    )


def create_overlay(background_path: Path, samples: list[Sample], out_path: Path) -> None:
    image = cv2.imread(str(background_path))
    if image is None:
        width = max(sample.x for sample in samples) + 40
        height = max(sample.y for sample in samples) + 40
        image = np.zeros((height, width, 3), dtype=np.uint8)

    speeds = [sample.speed_px_s for sample in samples if sample.speed_px_s > 0]
    min_speed = min(speeds) if speeds else 0.0
    max_speed = max(speeds) if speeds else 1.0

    overlay = image.copy()
    for a, b in zip(samples, samples[1:]):
        color = speed_color(b.speed_px_s, min_speed, max_speed)
        cv2.line(overlay, (a.x, a.y), (b.x, b.y), color, 4, cv2.LINE_AA)

    for sample in samples[:: max(1, len(samples) // 120)]:
        color = SECTION_COLORS.get(sample.section, (255, 255, 255))
        cv2.circle(overlay, (sample.x, sample.y), 4, color, -1, cv2.LINE_AA)

    label_positions = {
        "left_curve": (60, 310),
        "s_curve": (330, 245),
        "top_straight": (740, 165),
        "right_curve": (1110, 330),
        "bottom_straight": (720, 460),
        "start_finish": (515, 350),
    }
    for section, pos in label_positions.items():
        color = SECTION_COLORS.get(section, (255, 255, 255))
        cv2.putText(overlay, section, pos, cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2)

    draw_legend(overlay, min_speed, max_speed)
    cv2.imwrite(str(out_path), overlay)


def create_heatmap(background_path: Path, samples: list[Sample], out_path: Path) -> None:
    image = cv2.imread(str(background_path))
    if image is None:
        return

    heat = np.zeros(image.shape[:2], dtype=np.float32)
    for sample in samples:
        cv2.circle(heat, (sample.x, sample.y), 18, float(sample.speed_px_s), -1)
    heat = cv2.GaussianBlur(heat, (0, 0), 15)
    normalized = cv2.normalize(heat, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    colored = cv2.applyColorMap(normalized, cv2.COLORMAP_TURBO)
    blended = cv2.addWeighted(image, 0.65, colored, 0.35, 0)
    cv2.imwrite(str(out_path), blended)


def write_summary(path: Path, samples: list[Sample], stats: dict[str, dict[str, float]]) -> None:
    duration = samples[-1].time_s - samples[0].time_s if len(samples) > 1 else 0.0
    distance = samples[-1].distance_px if samples else 0.0
    lines = [
        "# Track Summary",
        "",
        f"- Samples: {len(samples)}",
        f"- Duration: {duration:.2f} s",
        f"- Camera path distance: {distance:.0f} px",
        "",
        "## Sections",
        "",
        "| Section | Samples | Avg px/s | Min px/s | Max px/s |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for section, values in sorted(stats.items()):
        lines.append(
            "| {} | {} | {:.1f} | {:.1f} | {:.1f} |".format(
                section,
                int(values["count"]),
                values["avg_speed_px_s"],
                values["min_speed_px_s"],
                values["max_speed_px_s"],
            )
        )

    lines.extend(
        [
            "",
            "## Meaning",
            "",
            "This is the first local learning layer: it converts camera x/y points into rough track sections.",
            "Later, when the Pico W can control the trigger, these sections become the places where the driving agent changes throttle.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    raw = load_samples(Path(args.input), args.car)
    if not raw:
        raise SystemExit(f"Keine Daten fuer Auto {args.car!r} in {args.input}")

    samples = annotate_samples(smooth_samples(raw), max_step_px=args.max_step_px)
    stats = section_stats(samples)

    write_analysis(Path(args.analysis_output), samples)
    write_section_stats(Path(args.section_output), stats)
    create_overlay(Path(args.background), samples, Path(args.overlay_output))
    create_heatmap(Path(args.background), samples, Path(args.heatmap_output))
    write_summary(Path(args.summary_output), samples, stats)

    print(f"Raw samples: {len(raw)}")
    print(f"Used samples: {len(samples)}")
    print(f"Sections: {', '.join(sorted(stats))}")
    print(f"Wrote: {args.analysis_output}")
    print(f"Wrote: {args.section_output}")
    print(f"Wrote: {args.overlay_output}")
    print(f"Wrote: {args.heatmap_output}")
    print(f"Wrote: {args.summary_output}")


if __name__ == "__main__":
    main()
