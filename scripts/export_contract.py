"""Export an offline schema and fixtures; never open a serial interface."""

import json
from pathlib import Path

from arm_observer.contracts import stream_schema
from arm_observer.models import (
    ArmConfig,
    BusConfig,
    EndEvent,
    Fault,
    FrameEvent,
    Identity,
    MetadataEvent,
    MotorMetadata,
    MotorTelemetry,
    StreamSummary,
    TelemetryFrame,
)
from arm_observer.output import encode

ROOT = Path(__file__).resolve().parents[1]


def example_events() -> tuple[MetadataEvent, FrameEvent, EndEvent]:
    observed = "2026-10-03T00:00:00.000+09:00"
    config = ArmConfig(BusConfig("offline-fixture", 1000000, 2.0, (1, 2)))
    identity = Identity(1, 1060, 43, observed, 0)
    metadata = MetadataEvent((MotorMetadata(1, identity, "base", (), (), ()),), config, observed)
    first = MotorTelemetry(1, False, 0, -2048, -10, -20, -30, 92, 30, False, 1, 123, False, ())
    fault = Fault(2, "sync_read", -3001, 0, "Timeout; value unknown")
    missing = MotorTelemetry(
        2, None, None, None, None, None, None, None, None, None, None, None, False, (fault,)
    )
    frame = FrameEvent(
        TelemetryFrame(0, observed, observed, 123456, 5.0, 20.0, False, "sync", (first, missing))
    )
    end = EndEvent(StreamSummary(1, 1, 0, 0.05, 0.0, False, True))
    return metadata, frame, end


def main() -> None:
    contract = ROOT / "contracts/stream-v2.schema.json"
    contract.parent.mkdir(parents=True, exist_ok=True)
    contract.write_text(json.dumps(stream_schema(), indent=2) + "\n", encoding="utf-8")
    fixture = ROOT / "tests/fixtures"
    fixture.mkdir(parents=True, exist_ok=True)
    events = example_events()
    (fixture / "frame_v2.json").write_text(encode(events[1], pretty=True) + "\n", encoding="utf-8")
    (fixture / "stream_v2.jsonl").write_text(
        "\n".join(encode(event) for event in events) + "\n", encoding="utf-8"
    )
    print(contract)


if __name__ == "__main__":
    main()
