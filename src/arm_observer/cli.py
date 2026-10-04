import argparse
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path
from uuid import uuid4

from beartype.roar import BeartypeCallHintViolation
from serial.tools import list_ports

from arm_observer.bus import open_bus
from arm_observer.configuration import load_config
from arm_observer.diagnostics import frame_lines, inspect_findings
from arm_observer.models import (
    ArmConfig,
    EndEvent,
    FrameEvent,
    InspectionReport,
    MetadataEvent,
    TelemetryFrame,
)
from arm_observer.observer import PollOptions, discover, observe, read_metadata
from arm_observer.output import JsonlSink, encode, report_stem, save_report
from arm_observer.reader import SdkReader

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only DYNAMIXEL arm observation")
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "config/arm.toml")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("ports", help="List USB serial interfaces without opening them")
    for name in ("scan", "metadata", "status", "watch"):
        command = commands.add_parser(name)
        command.add_argument("--device")
        command.add_argument("--baudrate", type=int)
        command.add_argument("--ids", nargs="+", type=int)
    commands.choices["metadata"].add_argument("--full", action="store_true")
    status = commands.choices["status"]
    status.add_argument("--samples", type=int, default=3)
    status.add_argument("--interval", type=float, default=0.25)
    status.add_argument("--scan", action="store_true")
    status.add_argument("--mode", choices=("sync", "unicast"), default="sync")
    status.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "reports")
    watch = commands.choices["watch"]
    watch.add_argument("--rate", type=float, default=20.0)
    watch.add_argument(
        "--duration", type=float, default=10.0, help="Seconds; 0 means run until count or Ctrl+C"
    )
    watch.add_argument("--count", type=int, default=0)
    watch.add_argument("--metadata-every", type=float, default=30.0)
    watch.add_argument("--mode", choices=("sync", "unicast"), default="sync")
    watch.add_argument("--output", type=Path)
    watch.add_argument("--format", choices=("text", "jsonl"), default="text")
    watch.add_argument("--quiet", action="store_true")
    return parser


def print_ports() -> int:
    for port in sorted(list_ports.comports(), key=lambda item: item.device):
        if port.device.startswith(("/dev/ttyUSB", "/dev/ttyACM")):
            print(f"{port.device}: {port.description}; {port.hwid}")
    for path in sorted(Path("/dev/serial/by-id").glob("*")):
        print(f"{path} -> {path.resolve()}")
    return 0


def run_scan(config: ArmConfig, full_scan: bool) -> int:
    with open_bus(config.bus.device, config.bus.baudrate) as (port, packet):
        ids = tuple(range(253)) if full_scan else config.bus.expected_ids
        identities = discover(SdkReader(port, packet), ids)
    for identity in identities:
        print(encode(identity))
    return 0 if identities else 2


def run_metadata(config: ArmConfig, full: bool) -> int:
    with open_bus(config.bus.device, config.bus.baudrate) as (port, packet):
        event = read_metadata(SdkReader(port, packet), config, full)
    print(encode(event, pretty=True))
    return 2 if any(motor.faults for motor in event.metadata) else 0


@dataclass(slots=True)
class SnapshotCapture:
    metadata: MetadataEvent | None = None
    frames: list[TelemetryFrame] = field(default_factory=list)

    def emit(self, event: MetadataEvent | FrameEvent) -> None:
        if isinstance(event, MetadataEvent):
            self.metadata = event
        else:
            self.frames.append(event.frame)


def run_status(config: ArmConfig, args: argparse.Namespace) -> int:
    if not 1 <= args.samples <= 20 or not 0 <= args.interval <= 10:
        raise ValueError("Use 1..20 samples and an interval of 0..10 seconds")
    rate = 1 / args.interval if args.interval else 200.0
    options = PollOptions(float(rate), 0.0, args.samples, 0.0, args.mode)
    capture = SnapshotCapture()
    identities = ()
    with open_bus(config.bus.device, config.bus.baudrate) as (port, packet):
        reader = SdkReader(port, packet)
        if args.scan:
            identities = discover(reader, tuple(range(253)))
        summary = observe(reader, config, options, capture.emit, full_metadata=True)
    if capture.metadata is None:
        raise RuntimeError("Metadata acquisition did not complete")
    frames = tuple(capture.frames)
    notes = inspect_findings(capture.metadata, frames)
    report = InspectionReport(capture.metadata, identities, frames, notes, True)
    paths = save_report(report, args.output_dir)
    for frame in frames:
        print("\n".join(frame_lines(FrameEvent(frame))))
    print(f"JSON: {paths.json}\nMarkdown: {paths.markdown}\nPort closed: True")
    if summary.interrupted:
        return 130
    return 2 if any(note.level == "error" for note in notes) else 0


class WatchSink:
    def __init__(self, sink: JsonlSink, display: bool):
        self.sink, self.display = sink, display
        self.acquisition_id = str(uuid4())

    def emit(self, event: MetadataEvent | FrameEvent) -> None:
        if isinstance(event, MetadataEvent):
            event = replace(event, simulated=False, acquisition_id=self.acquisition_id)
        self.sink.emit(event)
        if self.display and isinstance(event, FrameEvent):
            print("\n".join(frame_lines(event)), flush=True)


def run_watch(config: ArmConfig, args: argparse.Namespace) -> int:
    options = PollOptions(args.rate, args.duration, args.count, args.metadata_every, args.mode)
    path = args.output or PROJECT_ROOT / "reports" / (report_stem("watch") + ".jsonl")
    path.parent.mkdir(parents=True, exist_ok=True)
    mirror = sys.stdout if args.format == "jsonl" else None
    with path.open("x", encoding="utf-8") as file:
        sink = JsonlSink(file, mirror)
        output = WatchSink(sink, not args.quiet and args.format == "text")
        with open_bus(config.bus.device, config.bus.baudrate) as (port, packet):
            summary = observe(SdkReader(port, packet), config, options, output.emit)
        summary = replace(summary, port_closed=True)
        sink.emit(EndEvent(summary))
    print(
        f"JSONL: {path}; frames={summary.frames}; incomplete={summary.incomplete_frames}; "
        f"achieved_hz={summary.achieved_rate_hz:.2f}; late={summary.deadline_misses}; "
        "port_closed=True",
        file=sys.stderr,
    )
    if summary.interrupted:
        return 130
    return 2 if summary.incomplete_frames or summary.frames == 0 else 0


def dispatch(config: ArmConfig, args: argparse.Namespace) -> int:
    match args.command:
        case "scan":
            return run_scan(config, args.ids is None)
        case "metadata":
            return run_metadata(config, args.full)
        case "status":
            return run_status(config, args)
        case "watch":
            return run_watch(config, args)
        case _:
            raise ValueError("Unknown command")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "ports":
        return print_ports()
    try:
        ids = None if args.ids is None else tuple(args.ids)
        config = load_config(args.config, args.device, args.baudrate, ids)
        return dispatch(config, args)
    except (OSError, RuntimeError, ValueError, KeyError, BeartypeCallHintViolation) as exc:
        print(f"Observation failed: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Interrupted; serial port closed.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
