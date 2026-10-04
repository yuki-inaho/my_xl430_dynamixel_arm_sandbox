"""Explicit ID5-only open/close session; RAM envelope, monitored holds, no squeezing.

See docs/GRIPPER_ID5_CONSTRAINTS.md and the Oct04 gripper workdoc. Commands are
atomically replaced text files, consumed once; cameras have separate owners.
"""

import argparse
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from dynamixel_sdk import COMM_SUCCESS

from arm_observer.configuration import load_config
from arm_observer.id3_motion import MotionAbort, deferred_signals, healthy, position
from arm_observer.models import MotorTelemetry
from arm_observer.motion_guard import MotionPort, WriteEnvelope, open_motion_bus
from arm_observer.reader import Reader, SdkReader, timestamp
from arm_observer.registers import BY_NAME

IDS = (1, 2, 3, 4, 5)
RESTORED = ("goal_pwm", "profile_acceleration", "profile_velocity")
PROFILE = dict(goal_pwm=310, profile_acceleration=1, profile_velocity=3)
OFFSETS = {"10": 114, "20": 228, "40": 455, "close": 0}
IDENTITY = dict(
    model_number=1060,
    firmware_version=43,
    operating_mode=3,
    drive_mode=0,
    homing_offset=0,
    protocol_type=2,
    status_return_level=2,
)


@dataclass(frozen=True)
class Start:
    positions: tuple[int, ...]
    settings: tuple[tuple[str, int], ...]
    closed_count: int = 2067

    @property
    def closed(self) -> int:
        return self.closed_count

    def envelope(self) -> WriteEnvelope:
        settings = dict(self.settings)
        return WriteEnvelope(
            5,
            self.closed,
            2668,
            frozenset({1, settings["profile_acceleration"]}),
            frozenset({3, settings["profile_velocity"]}),
            frozenset({PROFILE["goal_pwm"], settings["goal_pwm"]}),
        )


def registers(reader: Reader, mid: int, names: tuple[str, ...]) -> dict[str, int]:
    batch = reader.registers(mid, tuple(BY_NAME[n] for n in names))
    values = {r.name: r.value for r in batch.readings}
    if batch.faults or any(r.device_alert for r in batch.readings):
        raise MotionAbort(f"ID{mid} metadata faults/alert")
    if any(type(values.get(n)) is not int for n in names):
        raise MotionAbort(f"ID{mid} incomplete metadata")
    return values


def check_route(reader: Reader, mid: int) -> None:
    identity = reader.identity(mid)
    route = registers(reader, mid, ("id", "secondary_id", "model_number"))
    if (
        identity is None
        or identity.device_error
        or identity.faults
        or identity.model_number != 1060
        or route["id"] != mid
        or route["model_number"] != 1060
        or route["secondary_id"] != 255
    ):
        raise MotionAbort(f"ID{mid} identity/alias check failed")


def stable_positions(frames: list[dict[int, MotorTelemetry]]) -> tuple[int, ...]:
    for mid in IDS:
        counts = [position(f[mid]) for f in frames]
        if max(counts) - min(counts) > 2:
            raise MotionAbort("starting pose not stable")
    return tuple(position(frames[-1][mid]) for mid in IDS)


def start_frames(reader: Reader) -> list[dict[int, MotorTelemetry]]:
    frames = [healthy(reader.telemetry(IDS, "sync")) for _ in range(3)]
    if any(m.torque_enabled for f in frames for m in f.values()):
        raise MotionAbort("fresh supported starting pose must have all five OFF")
    return frames


def validate_window(start: Start) -> None:
    closed, settings = start.closed, dict(start.settings)
    if abs(closed - 2064) > 100 or closed + 455 > 2668:
        raise MotionAbort(f"closed count {closed} outside photo-referenced start")
    if settings["min_position_limit"] > closed or settings["max_position_limit"] < 2668:
        raise MotionAbort("candidate window outside motor position limits")
    if not closed <= start.positions[4] <= 2668:
        raise MotionAbort("fresh ID5 count outside preserved closed-reference window")


def prepare(reader: Reader, closed_count: int) -> Start:
    for mid in IDS:
        check_route(reader, mid)
    settings = registers(
        reader, 5, (*IDENTITY, *RESTORED, "min_position_limit", "max_position_limit")
    )
    if any(settings[n] != v for n, v in IDENTITY.items()):
        raise MotionAbort(f"ID5 configuration mismatch: {settings}")
    frames = start_frames(reader)
    start = Start(stable_positions(frames), tuple(settings.items()), closed_count)
    validate_window(start)
    guard(frames[-1], start, active=False)
    return start


def check_health(m: MotorTelemetry) -> None:
    if m.temperature_c is None or m.temperature_c >= 55:
        raise MotionAbort(f"ID{m.motor_id} temperature unsafe/unknown")
    if m.voltage_raw is None or not 80 <= m.voltage_raw <= 140:
        raise MotionAbort(f"ID{m.motor_id} voltage unsafe/unknown")


def guard(motors: dict[int, MotorTelemetry], start: Start, *, active: bool) -> int:
    for mid, original in zip(IDS, start.positions, strict=True):
        m = motors[mid]
        check_health(m)
        if mid != 5 and (m.torque_enabled or abs(position(m) - original) > 15):
            raise MotionAbort(f"ID{mid} changed while only ID5 authorized")
    m = motors[5]
    count = position(m)
    if not start.closed - 5 <= count <= 2673 or abs(m.load_raw or 0) > 370:
        raise MotionAbort("ID5 position/load outside run limits")
    if active and not m.torque_enabled:
        raise MotionAbort("ID5 lost torque")
    return count


@dataclass
class Progress:
    target: int
    origin: int
    began: float
    last: int
    progressed_at: float
    stable: int = 0
    stationary_count: int | None = None

    def check_direction(self, count: int) -> None:
        sign = 1 if self.target >= self.origin else -1
        if sign * (count - self.origin) < -10 or sign * (count - self.target) > 15:
            raise MotionAbort("ID5 reverse/overshoot")

    def observe(self, count: int, now: float, velocity: int | None) -> bool:
        error = abs(count - self.target)
        if now - self.began > 18:
            raise MotionAbort("ID5 waypoint deadline")
        self.check_direction(count)
        if abs(count - self.last) >= 4:
            self.last, self.progressed_at = count, now
        if error > 25 and now - self.progressed_at > 1.5:
            raise MotionAbort("ID5 stalled; no squeezing or force correction")
        if self.stationary_count is None or abs(count - self.stationary_count) > 2:
            self.stationary_count, self.stable = count, 0
        self.stable = self.stable + 1 if error <= 25 and velocity == 0 else 0
        return self.stable >= 10


class Session:
    def __init__(self, reader: Reader, port: MotionPort, packet, output: Path, closed_count: int):
        self.reader, self.port, self.packet, self.output = reader, port, packet, output
        self.start = prepare(reader, closed_count)
        self.log = (output / "motion.jsonl").open("x")
        self.port.envelope = self.start.envelope()
        self.emit("prepared", start=asdict(self.start))

    def emit(self, kind: str, **fields):
        event = dict(kind=kind, at=timestamp(), host_unix_s=time.time(), **fields)
        self.log.write(json.dumps(event) + "\n")
        self.log.flush()
        if kind != "sample":
            print(json.dumps(event), flush=True)

    def write(self, name: str, value: int, *, allow_alert: bool = False):
        register = BY_NAME[name]
        result, error = getattr(self.packet, f"write{register.size}ByteTxRx")(
            self.port, 5, register.address, value
        )
        self.emit("write", motor_id=5, name=name, value=value, result=result, error=error)
        if result != COMM_SUCCESS or error & 0x7F or (error and not allow_alert):
            raise MotionAbort(f"ID5 {name} WRITE failed: result={result}, error={error}")

    def sample(self, active: bool = True) -> tuple[int, MotorTelemetry]:
        motors = healthy(self.reader.telemetry(IDS, "sync"))
        self.emit("sample", motors=[asdict(m) for m in motors.values()])
        return guard(motors, self.start, active=active), motors[5]

    def enable(self):
        self.write("goal_position", self.start.positions[4])
        for name, value in PROFILE.items():
            self.write(name, value)
        self.write("torque_enable", 1)
        for _ in range(3):
            count, _ = self.sample()
            if abs(count - self.start.positions[4]) > 10:
                raise MotionAbort("ID5 torque-on jump")
            time.sleep(0.05)

    def follow(self, command: str, stopped):
        target = self.start.closed + OFFSETS[command]
        origin, _ = self.sample()
        now = time.monotonic()
        progress = Progress(target, origin, now, origin, now)
        self.write("goal_position", target)
        while True:
            if stopped():
                raise MotionAbort("operator stop")
            count, m = self.sample()
            if progress.observe(count, time.monotonic(), m.velocity_raw):
                break
            time.sleep(0.05)
        accepted = count
        until = time.monotonic() + 2.5
        while time.monotonic() < until:
            if stopped():
                raise MotionAbort("operator stop")
            count, _ = self.sample()
            if abs(count - accepted) > 12:
                raise MotionAbort("ID5 drift during camera settle")
            time.sleep(0.05)
        self.emit(
            "ready",
            command=command,
            target=target,
            actual=count,
            status="converged" if abs(count - target) <= 12 else "settled_off_target",
        )
        return count

    def release(self):
        # Even when interrupted, the next instruction is OFF; never restore PWM while ON.
        self.port.is_using = False
        self.port.clearPort()
        self.write("torque_enable", 0, allow_alert=True)
        values = registers(self.reader, 5, ("torque_enable", "present_position"))
        if values["torque_enable"] != 0:
            raise MotionAbort("ID5 OFF could not be verified; restoration prohibited")
        current = values["present_position"]
        if self.port.envelope is not None and self.port.envelope.goal_low <= current <= 2668:
            self.write("goal_position", current)
        for name in RESTORED:
            self.write(name, dict(self.start.settings)[name])
        final = registers(self.reader, 5, ("torque_enable", *RESTORED))
        if final != {"torque_enable": 0, **{n: dict(self.start.settings)[n] for n in RESTORED}}:
            raise MotionAbort("ID5 RAM restoration mismatch")
        self.sample(active=False)
        self.emit("released", final=final)


def run(session: Session, command_file: Path, stopped) -> None:
    session.enable()
    target = session.start.positions[4]
    session.emit("ready", command="initial", target=target, actual=target)
    last_command_at = time.monotonic()
    while not stopped():
        count, _ = session.sample()
        if abs(count - target) > 12:
            raise MotionAbort("ID5 drift during review hold")
        if time.monotonic() - last_command_at > 120:
            raise MotionAbort("camera review deadline")
        if command_file.exists():
            command = command_file.read_text().strip()
            command_file.unlink()
            if command == "finish":
                return
            if command not in OFFSETS:
                raise MotionAbort(f"unknown command: {command}")
            target = session.follow(command, stopped)
            last_command_at = time.monotonic()
        time.sleep(0.05)
    raise MotionAbort("operator stop")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config/arm.toml"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--direction-evidence", type=Path, required=True)
    parser.add_argument(
        "--closed-count",
        type=int,
        required=True,
        help="preserved photo-observed touching count, not the current count",
    )
    args = parser.parse_args(argv)
    config = load_config(args.config)
    if not args.execute:
        print("No hardware accessed. --execute is required.")
        return 0
    evidence = json.loads(args.direction_evidence.read_text())
    expected = dict(
        motor_id=5, positive_opens=True, confirmed_by_user=True, closed_count=args.closed_count
    )
    if any(evidence.get(k) != v for k, v in expected.items()):
        raise ValueError("No confirmed ID5 positive-opening photo pairing")
    args.output.mkdir(parents=True, exist_ok=False)
    command_file = args.output / "command.txt"
    session = None
    result = 0
    with deferred_signals(), open_motion_bus(config.bus.device, config.bus.baudrate) as bus:
        port, packet = bus
        with deferred_signals() as stop:
            try:
                session = Session(
                    SdkReader(port, packet), port, packet, args.output, args.closed_count
                )
                run(session, command_file, stop.requested)
            except Exception as exc:  # noqa: BLE001 - every fault must reach ID5 release
                print(f"ABORT: {exc}", flush=True)
                result = 2
            finally:
                if session is not None:
                    try:
                        session.release()
                    except Exception as exc:  # noqa: BLE001 - report unverified release
                        print(f"RELEASE FAILED: {exc}", flush=True)
                        result = 3
                    session.log.close()
    print(json.dumps(dict(exit_code=result, port_closed=True)), flush=True)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
