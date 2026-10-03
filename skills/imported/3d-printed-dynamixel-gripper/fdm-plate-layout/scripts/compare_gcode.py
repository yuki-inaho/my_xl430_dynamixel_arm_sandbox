"""Compare actual OrcaSlicer plate toolpaths without executing G-code."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
from itertools import pairwise
from pathlib import Path

OBJECT = re.compile(r"^; printing object (.+?) id:")
SETTING = re.compile(r"^; ([a-zA-Z_][a-zA-Z_0-9]*) = (.*)$")
TIME = re.compile(r"^; estimated printing time \(normal mode\) = (.+)$", re.MULTILINE)
FILAMENT = re.compile(r"^; filament used \[cm3\] = ([\d.]+)$", re.MULTILINE)
LAYERS = re.compile(r"^; total layer number: (\d+)$", re.MULTILINE)


def entry(value: str) -> tuple[str, Path]:
    name, sep, filename = value.partition("=")
    if not sep or not name or not filename:
        raise argparse.ArgumentTypeError("Use LABEL=PATH")
    path = Path(filename)
    if not path.is_file():
        raise argparse.ArgumentTypeError(f"File not found: {path}")
    return name, path


def seconds(value: str) -> int:
    found = re.fullmatch(r"(?:(\d+)h )?(?:(\d+)m )?(\d+)s", value.strip())
    if not found:
        raise ValueError(f"Unrecognized OrcaSlicer time: {value}")
    hours, minutes, secs = (int(part or 0) for part in found.groups())
    return hours * 3600 + minutes * 60 + secs


def hull(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    ordered = sorted({(round(x, 2), round(y, 2)) for x, y in points})
    if len(ordered) < 3:
        return ordered

    def cross(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    lower, upper = [], []
    for point in ordered:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)
    for point in reversed(ordered):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    return lower[:-1] + upper[:-1]


def xy_path(
    command: str, start: dict[str, float], end: dict[str, float], values: dict[str, float]
) -> tuple[list[tuple[float, float]], float]:
    origin = (start["X"], start["Y"])
    destination = (end["X"], end["Y"])
    if command not in ("G2", "G3"):
        return [origin, destination], math.dist(origin, destination)
    if "I" not in values or "J" not in values:
        raise ValueError("G2/G3 arcs require I/J center offsets")
    center_x = origin[0] + values["I"]
    center_y = origin[1] + values["J"]
    radius = math.dist(origin, (center_x, center_y))
    if radius <= 0:
        raise ValueError("G2/G3 arc radius must be positive")
    start_angle = math.atan2(origin[1] - center_y, origin[0] - center_x)
    end_angle = math.atan2(destination[1] - center_y, destination[0] - center_x)
    sweep = (
        (start_angle - end_angle) % math.tau
        if command == "G2"
        else (end_angle - start_angle) % math.tau
    )
    if math.isclose(sweep, 0, abs_tol=1e-7):
        sweep = math.tau
    length = radius * sweep
    steps = max(1, math.ceil(sweep / math.radians(10)), math.ceil(length))
    direction = -1 if command == "G2" else 1
    points = [origin]
    for index in range(1, steps):
        angle = start_angle + direction * sweep * index / steps
        points.append((center_x + radius * math.cos(angle), center_y + radius * math.sin(angle)))
    points.append(destination)
    return points, length


def parse(path: Path) -> dict:
    source = path.read_bytes()
    content = source.decode("utf-8", errors="replace")
    settings = {}
    objects = {}
    xyz = {axis: 0.0 for axis in "XYZ"}
    absolute_xyz, relative_e, absolute_e = True, False, 0.0
    active, role, first_z = None, "Custom", None
    travel_xy = 0.0
    arc_commands = 0
    for line in content.splitlines():
        if match := OBJECT.match(line):
            active = match.group(1)
            objects.setdefault(
                active,
                {
                    "body_points": [],
                    "first_layer": [],
                    "support_e_mm": 0.0,
                    "body_e_mm": 0.0,
                    "body_z_min": math.inf,
                    "body_z_max": -math.inf,
                    "body_z_levels": set(),
                },
            )
        elif line.startswith("; stop printing object "):
            active = None
        if line.startswith(";TYPE:"):
            role = line[6:].strip()
        if match := SETTING.match(line):
            settings[match.group(1)] = match.group(2)
        code = line.split(";", 1)[0].strip()
        if not code:
            continue
        words = code.split()
        command = words[0]
        if command in ("G90", "G91"):
            absolute_xyz = command == "G90"
            continue
        if command in ("M82", "M83"):
            relative_e = command == "M83"
            continue
        if command not in ("G0", "G1", "G2", "G3", "G92"):
            continue
        values = {}
        for word in words[1:]:
            if word[0] in "XYZEFIJ" and len(word) > 1:
                try:
                    values[word[0]] = float(word[1:])
                except ValueError:
                    pass
        if command == "G92":
            for axis in "XYZ":
                if axis in values:
                    xyz[axis] = values[axis]
            if "E" in values:
                absolute_e = values["E"]
            continue
        start = xyz.copy()
        for axis in "XYZ":
            if axis in values:
                xyz[axis] = values[axis] if absolute_xyz else xyz[axis] + values[axis]
        delta_e = 0.0
        if "E" in values:
            if relative_e:
                delta_e = values["E"]
            else:
                delta_e = values["E"] - absolute_e
                absolute_e = values["E"]
        if command in ("G2", "G3"):
            arc_commands += 1
        points, xy_distance = xy_path(command, start, xyz, values)
        if active and xy_distance > 1e-5 and delta_e <= 0:
            travel_xy += xy_distance
        if not active or role == "Custom" or xy_distance <= 1e-5 or delta_e <= 0:
            continue
        part = objects[active]
        is_support = role.lower().startswith("support")
        if is_support:
            part["support_e_mm"] += delta_e
        else:
            part["body_e_mm"] += delta_e
            part["body_points"].extend(points)
            part["body_z_min"] = min(part["body_z_min"], xyz["Z"])
            part["body_z_max"] = max(part["body_z_max"], xyz["Z"])
            part["body_z_levels"].add(round(xyz["Z"], 3))
        if first_z is None:
            first_z = xyz["Z"]
        if abs(xyz["Z"] - first_z) < 0.001:
            part["first_layer"].extend(
                ((begin, finish), is_support) for begin, finish in pairwise(points)
            )

    if not objects or any(not part["body_points"] for part in objects.values()):
        raise ValueError(f"Object toolpaths missing in {path}")
    if not (time_match := TIME.search(content)) or not (filament_match := FILAMENT.search(content)):
        raise ValueError(f"OrcaSlicer time/filament metadata missing in {path}")
    summary = {
        "gcode": str(path.resolve()),
        "sha256": hashlib.sha256(source).hexdigest(),
        "time_seconds": seconds(time_match.group(1)),
        "time_text": time_match.group(1),
        "filament_cm3": float(filament_match.group(1)),
        "layer_count": int(LAYERS.search(content).group(1)) if LAYERS.search(content) else None,
        "travel_xy_mm": round(travel_xy, 2),
        "arc_commands": arc_commands,
        "settings": settings,
        "objects": objects,
    }
    return summary


def public_summary(data: dict, filament_diameter: float, slicer_result: Path | None) -> dict:
    area = math.pi * (filament_diameter / 2) ** 2
    items = {}
    for name, part in data["objects"].items():
        points = part["body_points"]
        xs, ys = zip(*points)
        items[name] = {
            "body_xy_bounds_mm": [
                round(min(xs), 2),
                round(min(ys), 2),
                round(max(xs), 2),
                round(max(ys), 2),
            ],
            "body_z_bounds_mm": [round(part["body_z_min"], 3), round(part["body_z_max"], 3)],
            "body_z_level_count": len(part["body_z_levels"]),
            "support_deposit_cm3_approx": round(part["support_e_mm"] * area / 1000, 3),
            "first_layer_segments": len(part["first_layer"]),
        }
    result = {
        key: data[key]
        for key in (
            "gcode",
            "sha256",
            "time_seconds",
            "time_text",
            "filament_cm3",
            "layer_count",
            "travel_xy_mm",
            "arc_commands",
        )
    }
    result["support_deposit_cm3_approx"] = round(
        sum(part["support_e_mm"] for part in data["objects"].values()) * area / 1000, 3
    )
    result["objects"] = items
    if slicer_result:
        raw = json.loads(slicer_result.read_text())
        result["slicer"] = {
            "return_code": raw.get("return_code"),
            "plate_count": len(raw.get("sliced_plates", [])),
            "warnings": [
                plate.get("warning_message")
                for plate in raw.get("sliced_plates", [])
                if plate.get("warning_message")
            ],
        }
    return result


def plot(runs: dict[str, dict], report: dict, bed: tuple[float, float], destination: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    from matplotlib.patches import Patch, Polygon, Rectangle

    names = sorted(next(iter(runs.values()))["objects"])
    colors = {name: plt.get_cmap("tab20")(index % 20) for index, name in enumerate(names)}
    figure, axes = plt.subplots(1, len(runs), figsize=(8 * len(runs), 10), squeeze=False)
    for ax, (label, run) in zip(axes[0], runs.items()):
        ax.add_patch(Rectangle((0, 0), *bed, fill=False, edgecolor="black", linewidth=1.4))
        for index, name in enumerate(names, 1):
            part = run["objects"][name]
            boundary = hull(part["body_points"])
            if len(boundary) >= 3:
                ax.add_patch(Polygon(boundary, facecolor=colors[name], alpha=0.2, edgecolor="none"))
                ax.plot(*zip(*(boundary + [boundary[0]])), color=colors[name], linewidth=1.1)
            segments = [segment for segment, is_support in part["first_layer"] if not is_support]
            supports = [segment for segment, is_support in part["first_layer"] if is_support]
            if segments:
                ax.add_collection(LineCollection(segments, colors=[colors[name]], linewidths=0.25))
            if supports:
                ax.add_collection(LineCollection(supports, colors="#777777", linewidths=0.35))
            bounds = report["runs"][label]["objects"][name]["body_xy_bounds_mm"]
            ax.text(
                (bounds[0] + bounds[2]) / 2,
                (bounds[1] + bounds[3]) / 2,
                str(index),
                ha="center",
                va="center",
                fontsize=9,
                weight="bold",
                bbox={
                    "facecolor": "white",
                    "edgecolor": colors[name],
                    "boxstyle": "round,pad=0.15",
                },
            )
        values = report["runs"][label]
        ax.set_title(
            f"{label}\n{values['time_text']}  |  {values['filament_cm3']:.2f} cm3"
            f"  |  support ~{values['support_deposit_cm3_approx']:.2f} cm3"
        )
        ax.set(xlim=(0, bed[0]), ylim=(0, bed[1]), xlabel="X (mm)", ylabel="Y (mm)")
        ax.set_aspect("equal")
        ax.grid(alpha=0.16)
    prefix = os.path.commonprefix(names)
    prefix = prefix[: prefix.rfind("_") + 1] if "_" in prefix else ""
    legend = [
        f"{index} {name.removeprefix(prefix).removesuffix('.stl').replace('_', ' ')}"
        for index, name in enumerate(names, 1)
    ]
    handles = [Patch(facecolor=colors[name], edgecolor=colors[name]) for name in names]
    figure.legend(
        handles,
        legend,
        loc="lower center",
        bbox_to_anchor=(0.5, 0.015),
        ncol=4,
        fontsize=9,
        frameon=False,
    )
    figure.suptitle(
        "OrcaSlicer plate layout from deposited toolpaths (gray: first-layer support)",
        y=0.98,
    )
    figure.tight_layout(rect=(0, 0.17, 1, 0.86))
    figure.savefig(destination, dpi=160)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gcode", action="append", type=entry, required=True, metavar="LABEL=PATH")
    parser.add_argument("--result", action="append", type=entry, default=[], metavar="LABEL=PATH")
    parser.add_argument("--bed", type=float, nargs=2, default=(220, 220), metavar=("X", "Y"))
    parser.add_argument("--filament-diameter", type=float, default=1.75)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.filament_diameter <= 0 or any(size <= 0 for size in args.bed):
        parser.error("Bed dimensions and filament diameter must be positive")
    files = dict(args.gcode)
    results = dict(args.result)
    if len(files) != len(args.gcode) or len(results) != len(args.result):
        parser.error("Labels must be unique")
    runs = {label: parse(path) for label, path in files.items()}
    expected = set(next(iter(runs.values()))["objects"])
    for label, run in runs.items():
        if set(run["objects"]) != expected:
            raise ValueError(f"Different object inventory: {label}")
    common_settings = set.intersection(*(set(run["settings"]) for run in runs.values()))
    differing_settings = sorted(
        key for key in common_settings if len({run["settings"][key] for run in runs.values()}) > 1
    )
    first = next(iter(runs.values()))
    changed_body_z = sorted(
        name
        for name in expected
        if any(
            run["objects"][name]["body_z_levels"] != first["objects"][name]["body_z_levels"]
            for run in runs.values()
        )
    )
    report = {
        "bed_mm": list(args.bed),
        "filament_diameter_mm": args.filament_diameter,
        "object_count": len(expected),
        "different_embedded_settings": differing_settings,
        "different_body_z_profiles": changed_body_z,
        "runs": {
            label: public_summary(run, args.filament_diameter, results.get(label))
            for label, run in runs.items()
        },
    }
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / "comparison.json").write_text(json.dumps(report, indent=2) + "\n")
    plot(runs, report, tuple(args.bed), args.out / "comparison.png")
    print(
        json.dumps(
            {
                "output": str(args.out.resolve()),
                "object_count": len(expected),
                "different_embedded_settings": differing_settings,
                "different_body_z_profiles": changed_body_z,
                "runs": {
                    label: {
                        key: values[key]
                        for key in ("time_text", "filament_cm3", "support_deposit_cm3_approx")
                    }
                    for label, values in report["runs"].items()
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
