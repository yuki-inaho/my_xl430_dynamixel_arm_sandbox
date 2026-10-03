"""JSON/Markdown are boundary formats, not the application's internal data model."""

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import NamedTuple, TextIO

from arm_observer.models import (
    EndEvent,
    FrameEvent,
    Identity,
    InspectionReport,
    MetadataEvent,
)

WireRecord = MetadataEvent | FrameEvent | EndEvent | InspectionReport | Identity


def encode(record: WireRecord, pretty: bool = False) -> str:
    return json.dumps(asdict(record), allow_nan=False, indent=2 if pretty else None)


class ReportPaths(NamedTuple):
    json: Path
    markdown: Path


def report_stem(prefix: str) -> str:
    return prefix + datetime.now().astimezone().strftime("_%Y%m%dT%H%M%S_%f%z")


def render_markdown(report: InspectionReport) -> str:
    lines = [
        "# Read-only DYNAMIXEL Snapshot v2",
        "",
        f"Metadata captured: {report.metadata.observed_at}",
        "",
        f"Port closed: {report.port_closed}. No motor settings were changed.",
        "",
        "| ID | Model | Firmware | Proposed Role | Metadata Errors |",
        "|---|---:|---:|---|---:|",
    ]
    for motor in report.metadata.metadata:
        identity = motor.identity
        model = identity.model_number if identity else "unknown"
        firmware = identity.firmware_version if identity else "unknown"
        lines.append(
            f"| {motor.motor_id} | {model} | {firmware} | "
            f"{motor.proposed_role} | {len(motor.faults)} |"
        )
    lines.extend(["", "## Findings", ""])
    lines.extend(
        f"- {finding.level}: ID {finding.motor_id}: {finding.message}"
        for finding in report.findings
    )
    for motor in report.metadata.metadata:
        lines.extend(
            [
                "",
                f"## ID {motor.motor_id} Registers",
                "",
                "| Name | Address | Bytes | Memory | Raw | Decoded | Alert |",
                "|---|---:|---:|---|---:|---:|---|",
            ]
        )
        lines.extend(
            f"| {value.name} | {value.address} | {value.size} | {value.memory} | "
            f"{value.raw} | {value.value} | {value.device_alert} |"
            for value in motor.registers
        )
        lines.extend(["", f"Skipped firmware-dependent fields: {motor.skipped_registers}."])
    lines.extend(
        [
            "",
            "## Telemetry",
            "",
            "| Sequence | ID | Torque | Position Counts | RPM | Voltage V | Temp C | "
            "Error | Complete |",
            "|---:|---:|---|---:|---:|---:|---:|---:|---|",
        ]
    )
    for frame in report.frames:
        lines.extend(
            f"| {frame.sequence} | {motor.motor_id} | {motor.torque_enabled} | "
            f"{motor.position_counts} | {motor.velocity_rpm} | {motor.voltage_v} | "
            f"{motor.temperature_c} | {motor.hardware_error} | {motor.complete} |"
            for motor in frame.motors
        )
    lines.extend(
        [
            "",
            "Full errors and timestamps are in the JSON report. "
            "Unknown values are null, not zero. These are sequential samples, "
            "not proof of simultaneous measurement or physical joint calibration.",
            "",
        ]
    )
    return "\n".join(lines)


def save_report(report: InspectionReport, directory: Path) -> ReportPaths:
    directory.mkdir(parents=True, exist_ok=True)
    stem = report_stem("status")
    paths = ReportPaths(directory / f"{stem}.json", directory / f"{stem}.md")
    with paths.json.open("x", encoding="utf-8") as output:
        output.write(encode(report, pretty=True) + "\n")
    with paths.markdown.open("x", encoding="utf-8") as output:
        output.write(render_markdown(report))
    return paths


class JsonlSink:
    def __init__(self, file: TextIO, mirror: TextIO | None = None):
        self.file, self.mirror = file, mirror

    def emit(self, event: MetadataEvent | FrameEvent | EndEvent) -> None:
        line = encode(event) + "\n"
        self.file.write(line)
        self.file.flush()
        if self.mirror is not None:
            self.mirror.write(line)
            self.mirror.flush()
