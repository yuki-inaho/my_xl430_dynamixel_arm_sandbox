"""Bounded opening of motor ID3 (elbow): one relative move, hold, return, torque off.

This is a separate, explicitly invoked command. The read-only observer and its guard are
unchanged; writes pass only through MotionPort and its single-motor envelope.
Specification: docs/id3_motion_spec.md (workdoc temp/workdoc_Oct03-2026_id3_open_10deg.md).
"""

import argparse
import hashlib
import json
import os
import signal
import sys
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Literal, Protocol

from beartype import beartype
from dynamixel_sdk import COMM_SUCCESS
from dynamixel_sdk.protocol2_packet_handler import Protocol2PacketHandler

from arm_observer.bus import open_bus
from arm_observer.configuration import load_config
from arm_observer.models import MotorTelemetry
from arm_observer.motion_guard import MotionPort, MotionViolation, WriteEnvelope, open_motion_bus
from arm_observer.output import report_stem
from arm_observer.reader import Reader, SdkReader, timestamp
from arm_observer.registers import BY_NAME

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MOTOR_ID = 3
IDS = (1, 2, 3, 4, 5)
OPEN_COUNTS = 114  # 10.01953125 deg at 4096 counts/rev
PROFILE_ACCELERATION = 1  # 214.577 rev/min^2
PROFILE_VELOCITY = 5  # 1.145 rev/min = 6.87 deg/s
GOAL_PWM = 350  # about 39.6 %, final PWM limiter in Position Control Mode
MIN_EVIDENCE_COUNTS, MAX_EVIDENCE_COUNTS = 20, 1024
FOLDED_TOLERANCE = 30
STABLE_SPAN = 2
JUMP_TOLERANCE = 10
REVERSE_TOLERANCE = 10
OVERSHOOT_TOLERANCE = 15
REACHED_TOLERANCE = 5
SETTLE_LIMIT = 25  # a settled error above this is abnormal, not gravity sag
EARLY_PROGRESS_S = 1.0
EARLY_PROGRESS_COUNTS = 15  # profile covers about 55 counts in the first second
STABLE_SAMPLES = 20
OTHER_MOTION_TOLERANCE = 20
FOLD_SIDE_MARGIN = 15  # toward the fold only the torque-on jump tolerance is needed
MAX_CORRECTION_COUNTS = 30  # outer-loop goal offset for load sag (P-only position control)
CORRECTION_ROUNDS = 3
FOLLOW_TIMEOUT_S = 6.0
HOLD_S = 2.0
SAMPLE_PERIOD_S = 0.05
START_SAMPLES = 5
SETTLE_SAMPLES = 3
TORQUE_OFF_ATTEMPTS = 3
MAX_CONSECUTIVE_MISSES = 2  # isolated SYNC_READ timeouts were seen (1 of 189 frames)
ID3_WRITES = {
    "torque": (64, 1),
    "profile_acceleration": (108, 4),
    "profile_velocity": (112, 4),
    "goal_pwm": (100, 2),
    "goal_position": (116, 4),
}
EXPECTED = {
    "model_number": 1060,
    "firmware_version": 42,
    "id": MOTOR_ID,
    "baud_rate": 3,
    "protocol_type": 2,
    "operating_mode": 3,
    "drive_mode": 0,
    "homing_offset": 0,
    "min_position_limit": 0,
    "max_position_limit": 4095,
    "status_return_level": 2,
}
RESTORED = ("goal_pwm", "profile_velocity", "profile_acceleration")
Event = dict[str, object]
Status = Literal["converged", "settled_off_target", "aborted", "refused"]


class MotionAbort(RuntimeError):
    """Stop now: torque goes off and settings are restored."""


class MotionRefused(RuntimeError):
    """A precondition failed before any write was sent."""


class MissedSample(MotionAbort):
    """Telemetry values are unknown because of a communication fault, not a device error."""


class StopRequested(MotionAbort):
    """A deferred SIGINT/SIGTERM/SIGHUP asked the run to stop; release still runs."""


@beartype
@dataclass(frozen=True, slots=True)
class Evidence:
    path: str
    sha256: str
    sign: int
    folded_count: int
    kind: str


@beartype
@dataclass(frozen=True, slots=True)
class Start:
    folded_counts: int
    others: tuple[tuple[int, int], ...]
    settings: tuple[tuple[str, int], ...]
    envelope: WriteEnvelope

    def setting(self, name: str) -> int:
        return dict(self.settings)[name]


@beartype
@dataclass(frozen=True, slots=True)
class Outcome:
    status: Status
    reason: str
    target: int | None = None
    final_error_counts: int | None = None
    start_counts: int | None = None
    torque_on_counts: int | None = None
    sign: int | None = None
    return_error_counts: int | None = None
    correction_counts: int = 0
    torque_off_confirmed: bool | None = None
    release_problems: tuple[str, ...] = ()
    interrupted: bool = False


@beartype
@dataclass(frozen=True, slots=True)
class Release:
    torque_off_confirmed: bool
    problems: tuple[str, ...]


def counts(sample: dict, key: str = "position_counts") -> int:
    value = sample[key]
    if type(value) is not int:
        raise ValueError(f"direction evidence {key} must be an integer")
    return value


def sample_shape_problem(samples: tuple[object, object]) -> str | None:
    if not all(isinstance(sample, dict) for sample in samples):
        return "direction evidence samples must be objects"
    before, after = samples
    assert isinstance(before, dict) and isinstance(after, dict)
    if before.get("mode") != 3 or after.get("mode") != 3:
        return "direction evidence must come from Position Control Mode (3)"
    newer = after.get("sequence")
    if type(newer) is not int or not newer > before.get("sequence", 2**63):
        return "direction evidence after-sample must be newer than its before-sample"
    return None


def sample_source_problem(samples: tuple[dict, dict]) -> str | None:
    if any(sample["simulated"] is not False for sample in samples):
        return "direction evidence must come from hardware, not synthetic input"
    if any(sample["motor_id"] != MOTOR_ID for sample in samples):
        return "direction evidence must observe ID3"
    if any(samples[0][key] != samples[1][key] for key in ("session_id", "context_fingerprint")):
        return "direction evidence samples come from different sessions or settings"
    return None


def sample_problem(record: dict) -> str | None:
    samples = (record["before"], record["after"])
    problem = sample_shape_problem(samples) or sample_source_problem(samples)
    if problem:
        return problem
    folded = samples[0].get("physical_confirmed") is True
    opened = record["physical_change_confirmed"] is True
    if not (folded and opened) or record["physical_change_reported"] != "opening":
        return "direction evidence lacks the physical folded/opening confirmations"
    return None


def delta_problem(record: dict, sign: object, delta: object) -> str | None:
    if type(delta) is not int or not MIN_EVIDENCE_COUNTS <= abs(delta) < MAX_EVIDENCE_COUNTS:
        return "direction evidence delta is jitter-sized or ambiguous"
    observed = counts(record["after"]) - counts(record["before"])
    if (observed + 2048) % 4096 - 2048 != delta:  # mode 3 shortest difference
        return "direction evidence delta disagrees with its recorded counts"
    if type(sign) is not int or sign != (1 if delta > 0 else -1):
        return "direction evidence sign is inconsistent with its delta"
    return None


def cad_sign_problem(record: dict) -> str | None:
    sign = record.get("opening_count_sign")
    if record.get("motor_id") != MOTOR_ID or type(sign) is not int or sign not in (1, -1):
        return "CAD direction evidence must give an integer +-1 sign for ID3"
    if (record.get("derivation") or {}).get("opening_count_sign") != sign:
        return "CAD direction evidence sign differs from its derivation"
    return None


def cad_problem(record: dict) -> str | None:
    folded, read = record.get("folded_count"), record.get("folded_read") or {}
    if type(folded) is not int or read.get("folded_count") != folded or not read.get("frames"):
        return "CAD direction evidence needs the folded count from a completed READ"
    return cad_source_problem(record.get("sources")) or cad_sign_problem(record)


def cad_source_problem(sources: object) -> str | None:
    if not isinstance(sources, dict) or not sources:
        return "CAD direction evidence must list its hashed CAD sources"
    for name, digest in sources.items():
        path = Path(name)
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            return f"CAD source {name} is missing or its hash differs"
    return None


def load_evidence(path: Path) -> Evidence:
    raw = path.read_bytes()
    record = json.loads(raw)
    if not isinstance(record, dict):
        raise ValueError("direction evidence must be a JSON object")
    digest = hashlib.sha256(raw).hexdigest()
    if record.get("kind") == "cad_derivation":
        problem = cad_problem(record)
        if problem:
            raise ValueError(problem)
        return Evidence(str(path), digest, record["opening_count_sign"],
                        record["folded_count"], "cad_derivation")
    if "kind" in record:
        raise ValueError(f"unknown direction evidence kind {record['kind']!r}")
    sign, delta = record["opening_count_sign"], record["delta_counts"]
    problem = sample_problem(record) or delta_problem(record, sign, delta)
    if problem or type(sign) is not int or type(delta) is not int:
        raise ValueError(problem or "direction evidence sign/delta must be integers")
    return Evidence(str(path), digest, sign, counts(record["before"]), "paired_observation")


class Actuator(Protocol):
    def set_envelope(self, envelope: WriteEnvelope) -> None: ...
    def recover(self) -> None: ...
    def write(self, name: str, value: int, allow_alert: bool = False) -> None: ...


class Id3Actuator:
    """Named ID3 RAM writes only; each status packet must report success without alert."""

    def __init__(self, port: MotionPort, packet: Protocol2PacketHandler):
        self.port = port
        self.packet = packet

    def set_envelope(self, envelope: WriteEnvelope) -> None:
        self.port.envelope = envelope

    def recover(self) -> None:
        # An interrupted SDK transaction leaves the port marked busy; release must still send.
        self.port.is_using = False
        self.port.clearPort()

    def write(self, name: str, value: int, allow_alert: bool = False) -> None:
        address, size = ID3_WRITES[name]
        writer = getattr(self.packet, f"write{size}ByteTxRx")
        try:
            result, error = writer(self.port, MOTOR_ID, address, value)
        except (MotionViolation, ValueError) as exc:
            raise MotionAbort(f"write {name}={value} refused by the motion guard: {exc}") from exc
        if result != COMM_SUCCESS:
            raise MotionAbort(f"write {name}={value} failed: {self.packet.getTxRxResult(result)}")
        # Alert (0x80) reports a latched hardware error; release writes still apply with it.
        if error & 0x7F or (error and not allow_alert):
            raise MotionAbort(f"write {name}={value} status error: {error:#04x}")


class MotionLog:
    def __init__(self, emit: Callable[[Event], None], monotonic: Callable[[], float]):
        self.emit, self.monotonic = emit, monotonic
        self.origin = monotonic()

    def event(self, kind: str, **fields: object) -> None:
        elapsed = round(self.monotonic() - self.origin, 4)
        self.emit({"kind": kind, "t": elapsed, "at": timestamp(), **fields})


def position(motor: MotorTelemetry) -> int:
    if motor.position_counts is None:
        raise MotionAbort(f"ID{motor.motor_id} position is unknown")
    return motor.position_counts


def healthy(motors: tuple[MotorTelemetry, ...]) -> dict[int, MotorTelemetry]:
    found = {motor.motor_id: motor for motor in motors}
    for motor_id in IDS:
        motor = found.get(motor_id)
        if motor is not None and (motor.hardware_error or motor.device_alert):
            raise MotionAbort(f"hardware error or alert on ID{motor_id}")
    for motor_id in IDS:
        motor = found.get(motor_id)
        if motor is None or not motor.complete:
            raise MissedSample(f"incomplete telemetry for ID{motor_id}")
    return found


def sample_event(stage: str, motors: dict[int, MotorTelemetry]) -> Event:
    id3 = motors[MOTOR_ID]
    return {
        "stage": stage,
        "positions": {str(mid): motors[mid].position_counts for mid in IDS},
        "torque": {str(mid): motors[mid].torque_enabled for mid in IDS},
        "id3": {"velocity_raw": id3.velocity_raw, "pwm_raw": id3.pwm_raw,
                "load_raw": id3.load_raw, "moving_status": id3.moving_status,
                "voltage_raw": id3.voltage_raw, "temperature_c": id3.temperature_c},
    }


@dataclass(slots=True)
class Tracker:
    target: int
    sign: int
    origin: int
    others: dict[int, int]
    started: float
    early_progress: int = EARLY_PROGRESS_COUNTS  # 0 disables the early-progress check
    settle_limit: int = SETTLE_LIMIT
    overshoot_reference: int | None = None  # the true target when the goal is offset
    recent: list[int] = field(default_factory=list)

    def check_others(self, motors: dict[int, MotorTelemetry]) -> None:
        for motor_id, start in self.others.items():
            motor = motors[motor_id]
            if motor.torque_enabled:
                raise MotionAbort(f"ID{motor_id} torque turned ON")
            moved = position(motor) - start
            if abs(moved) > OTHER_MOTION_TOLERANCE:
                raise MotionAbort(f"ID{motor_id} moved {moved} counts")

    def check_id3(self, position: int, elapsed: float) -> None:
        progress = (position - self.origin) * self.sign
        if progress < -REVERSE_TOLERANCE:
            raise MotionAbort(f"ID3 moved against the commanded direction to {position}")
        reference = self.target if self.overshoot_reference is None else self.overshoot_reference
        if (position - reference) * self.sign > OVERSHOOT_TOLERANCE:
            raise MotionAbort(f"ID3 overshot the target to {position}")
        if self.early_progress and elapsed >= EARLY_PROGRESS_S and progress < self.early_progress:
            raise MotionAbort(f"ID3 no progress ({progress} counts after {elapsed:.2f} s): "
                              "blocked or wrong direction")

    def converged(self, counts: int, profile_ongoing: bool) -> bool:
        self.recent = [*self.recent, counts][-STABLE_SAMPLES:]
        if len(self.recent) < STABLE_SAMPLES or profile_ongoing:
            return False
        if max(self.recent) - min(self.recent) > STABLE_SPAN:
            return False
        if abs(counts - self.target) > self.settle_limit:
            raise MotionAbort(f"ID3 settled far from the target at {counts} (target {self.target})")
        return True

    def update(self, motors: dict[int, MotorTelemetry], now: float) -> bool:
        id3 = motors[MOTOR_ID]
        counts = position(id3)
        self.check_others(motors)
        self.check_id3(counts, now - self.started)
        if self.converged(counts, bool((id3.moving_status or 0) & 2)):
            return True
        if now - self.started > FOLLOW_TIMEOUT_S:
            raise MotionAbort(f"ID3 following timeout at {counts} (target {self.target})")
        return False


class Session:
    def __init__(self, reader: Reader, actuator: Actuator, log: MotionLog,
                 monotonic: Callable[[], float], sleep: Callable[[float], None],
                 stop_requested: Callable[[], bool] = lambda: False):
        self.reader, self.actuator, self.log = reader, actuator, log
        self.monotonic, self.sleep = monotonic, sleep
        self.stop_requested = stop_requested
        self.attempted = False

    def sample(self, stage: str) -> dict[int, MotorTelemetry]:
        if self.stop_requested():
            raise StopRequested(f"stop requested by a signal during {stage}")
        for attempt in range(MAX_CONSECUTIVE_MISSES + 1):
            try:
                motors = healthy(self.reader.telemetry(IDS, "sync"))
            except MissedSample as exc:
                # Unknown values are never used; an isolated loss is re-read at once.
                self.log.event("missed_sample", stage=stage, attempt=attempt, reason=str(exc))
                continue
            self.log.event("sample", **sample_event(stage, motors))
            return motors
        raise MotionAbort(f"communication lost for {MAX_CONSECUTIVE_MISSES + 1} consecutive "
                          f"samples during {stage}")

    def write(self, name: str, value: int) -> None:
        if self.stop_requested():
            raise StopRequested(f"stop requested before write {name}={value}")
        self.attempted = True
        self.actuator.write(name, value)
        self.log.event("write", name=name, value=value, status="ok")

    def safe_event(self, kind: str, **fields: object) -> None:
        try:
            self.log.event(kind, **fields)
        except Exception:  # noqa: BLE001 - logging must never block the torque-off path
            pass

    def pace(self, deadline: float) -> float:
        """Sleep to this sample deadline and return the next; a late sample resets the grid."""
        now = self.monotonic()
        if now < deadline:
            self.sleep(deadline - now)
            return deadline + SAMPLE_PERIOD_S
        return now + SAMPLE_PERIOD_S

    def follow(self, stage: str, tracker: Tracker) -> int:
        samples, deadline = 0, self.monotonic() + SAMPLE_PERIOD_S
        while True:
            motors = self.sample(stage)
            samples += 1
            if tracker.update(motors, self.monotonic()):
                found = position(motors[MOTOR_ID])
                elapsed = max(self.monotonic() - tracker.started, 1e-9)
                self.log.event("converged", stage=stage, position=found,
                               error=found - tracker.target, samples=samples,
                               elapsed_s=round(elapsed, 3),
                               achieved_hz=round((samples - 1) / elapsed, 2))
                return found
            deadline = self.pace(deadline)

    def hold(self, settled: int, others: dict[int, int]) -> None:
        tracker = Tracker(settled, 1, settled, others, self.monotonic())
        end = self.monotonic() + HOLD_S
        deadline = self.monotonic() + SAMPLE_PERIOD_S
        while self.monotonic() < end:
            motors = self.sample("hold")
            tracker.check_others(motors)
            found = position(motors[MOTOR_ID])
            if abs(found - settled) > REACHED_TOLERANCE:
                raise MotionAbort(f"ID3 drifted from {settled} while holding ({found})")
            deadline = self.pace(deadline)

    def torque_on_position(self, start: Start, others: dict[int, int]) -> int:
        tracker = Tracker(start.folded_counts, 1, start.folded_counts, others, self.monotonic())
        counts = start.folded_counts
        for _ in range(SETTLE_SAMPLES):
            self.sleep(SAMPLE_PERIOD_S)
            motors = self.sample("torque_on")
            tracker.check_others(motors)
            if motors[MOTOR_ID].torque_enabled is not True:
                raise MotionAbort("ID3 torque did not turn on")
            # Every sample is checked: a re-based or misplaced goal shows up before it is corrected.
            counts = position(motors[MOTOR_ID])
            if abs(counts - start.folded_counts) > JUMP_TOLERANCE:
                raise MotionAbort(f"ID3 jump {counts - start.folded_counts} counts at torque on")
        return counts

    def execute(self, start: Start, evidence: Evidence) -> Outcome:
        self.actuator.set_envelope(start.envelope)
        for name, value in (("profile_acceleration", PROFILE_ACCELERATION),
                            ("profile_velocity", PROFILE_VELOCITY), ("goal_pwm", GOAL_PWM),
                            ("goal_position", start.folded_counts), ("torque", 1)):
            self.write(name, value)
        others = dict(start.others)
        p1 = self.torque_on_position(start, others)
        target = p1 + evidence.sign * OPEN_COUNTS
        if not start.envelope.goal_low <= target <= start.envelope.goal_high:
            raise MotionAbort(f"target {target} outside the motion window")
        self.write("goal_position", target)
        opened = self.follow("open", Tracker(target, evidence.sign, p1, others, self.monotonic()))
        opened, correction = self.correct(target, opened, evidence.sign, others, start)
        self.hold(opened, others)
        if not start.envelope.goal_low <= p1 <= start.envelope.goal_high:
            raise MotionAbort(f"return goal {p1} outside the motion window")
        self.write("goal_position", p1)
        returned = self.follow("return",
                               Tracker(p1, -evidence.sign, opened, others, self.monotonic()))
        error = opened - target
        status: Status = "converged" if abs(error) <= REACHED_TOLERANCE else "settled_off_target"
        reason = "" if status == "converged" else f"settled {error} counts from the target"
        return Outcome(status, reason, target, error, start.folded_counts, p1, evidence.sign,
                       returned - p1, correction)

    def correct(self, target: int, settled: int, sign: int, others: dict[int, int],
                start: Start) -> tuple[int, int]:
        """Offset the goal by the measured sag; a blocked or capped correction just stops."""
        goal = target
        for _ in range(CORRECTION_ROUNDS):
            error = settled - target
            proposed = goal - error
            within = start.envelope.goal_low <= proposed <= start.envelope.goal_high
            if abs(error) <= REACHED_TOLERANCE or abs(proposed - target) > MAX_CORRECTION_COUNTS:
                break
            if not within:
                break
            goal = proposed
            self.write("goal_position", goal)
            tracker = Tracker(goal, sign, settled, others, self.monotonic(), early_progress=0,
                              settle_limit=SETTLE_LIMIT + MAX_CORRECTION_COUNTS,
                              overshoot_reference=target)
            settled = self.follow("correct", tracker)
        return settled, goal - target

    def guarded_write(self, name: str, value: int, problems: list[str]) -> bool:
        try:
            self.actuator.write(name, value, allow_alert=True)
        except BaseException as exc:  # noqa: BLE001 - every release step must be attempted
            problems.append(f"{name}={value}: {type(exc).__name__}: {exc}")
            return False
        self.safe_event("write", name=name, value=value, status="ok")
        return True

    def guarded_read(self, name: str, problems: list[str]) -> int | None:
        try:
            return self.reader.registers(MOTOR_ID, (BY_NAME[name],)).value(name)
        except BaseException as exc:  # noqa: BLE001
            problems.append(f"read {name}: {type(exc).__name__}: {exc}")
            return None

    def torque_off(self, problems: list[str]) -> bool:
        for _ in range(TORQUE_OFF_ATTEMPTS):
            try:
                self.actuator.recover()
            except BaseException as exc:  # noqa: BLE001
                problems.append(f"recover: {type(exc).__name__}: {exc}")
            if self.guarded_write("torque", 0, problems):
                state = self.guarded_read("torque_enable", problems)
                if state == 0:
                    return True
                problems.append(f"torque_enable read back {state}")
        return False

    def park_goal(self, start: Start, problems: list[str]) -> None:
        present = self.guarded_read("present_position", problems)
        window = start.envelope
        if present is None or not window.goal_low <= present <= window.goal_high:
            problems.append(f"goal not parked: present {present} outside the motion window")
            return
        # A later torque-on by any tool then holds still instead of seeking an old goal.
        self.guarded_write("goal_position", present, problems)

    def final_torque(self, problems: list[str]) -> dict[str, bool | None]:
        try:
            motors = self.reader.telemetry(IDS, "sync")
        except BaseException as exc:  # noqa: BLE001
            problems.append(f"final torque read: {type(exc).__name__}: {exc}")
            return {}
        states = {str(motor.motor_id): motor.torque_enabled for motor in motors}
        if any(state is not False for state in states.values()):
            problems.append(f"final torque states not all OFF: {states}")
        return states

    def release(self, start: Start) -> Release:
        problems: list[str] = []
        if not self.attempted:
            # Nothing was sent: only confirm that ID3 still reads torque OFF.
            states = self.final_torque(problems)
            confirmed = states.get(str(MOTOR_ID)) is False
            self.safe_event("released", torque_off_confirmed=confirmed, problems=problems,
                            final_torque=states, writes_sent=False)
            return Release(confirmed, tuple(problems))
        confirmed = self.torque_off(problems)
        states = self.final_torque(problems)
        if confirmed and states.get(str(MOTOR_ID)) is True:
            problems.append("final SYNC_READ shows ID3 torque ON despite the read-back")
            confirmed = False
        if confirmed:
            self.park_goal(start, problems)
            for name in RESTORED:
                self.guarded_write(name, start.setting(name), problems)
        self.safe_event("released", torque_off_confirmed=confirmed, problems=problems,
                        final_torque=states)
        return Release(confirmed, tuple(problems))


def read_settings(reader: Reader) -> dict[str, int]:
    names = (*EXPECTED, *RESTORED)
    batch = reader.registers(MOTOR_ID, tuple(BY_NAME[name] for name in names))
    values = {reading.name: reading.value for reading in batch.readings}
    if batch.faults or any(name not in values for name in names):
        raise MotionRefused("ID3 metadata read is incomplete")
    if any(reading.device_alert for reading in batch.readings):
        raise MotionRefused("ID3 metadata read carries a device alert")
    for name, expected in EXPECTED.items():
        if values[name] != expected:
            raise MotionRefused(f"ID3 {name}={values[name]} (expected {expected})")
    return values


def envelope_for(folded: int, sign: int, settings: dict[str, int]) -> WriteEnvelope:
    target = folded + sign * OPEN_COUNTS
    if not settings["min_position_limit"] <= target <= settings["max_position_limit"]:
        raise MotionRefused(f"target {target} outside the ID3 position limits")
    fold_end = folded - sign * FOLD_SIDE_MARGIN
    open_end = target + sign * (MAX_CORRECTION_COUNTS + 5)
    low = max(settings["min_position_limit"], min(fold_end, open_end))
    high = min(settings["max_position_limit"], max(fold_end, open_end))
    return WriteEnvelope(MOTOR_ID, low, high,
                         frozenset({PROFILE_ACCELERATION, settings["profile_acceleration"]}),
                         frozenset({PROFILE_VELOCITY, settings["profile_velocity"]}),
                         frozenset({GOAL_PWM, settings["goal_pwm"]}))


def start_frames(session: Session) -> list[dict[int, MotorTelemetry]]:
    frames = []
    for _ in range(START_SAMPLES):
        frames.append(session.sample("start"))
        session.sleep(SAMPLE_PERIOD_S)
    if any(motor.torque_enabled for frame in frames for motor in frame.values()):
        raise MotionRefused("a motor already has torque ON")
    return frames


def folded_start(frames: list[dict[int, MotorTelemetry]], evidence: Evidence) -> int:
    positions = [position(frame[MOTOR_ID]) for frame in frames]
    if max(positions) - min(positions) > STABLE_SPAN:
        raise MotionRefused(f"ID3 is not stable at start: {positions}")
    folded = positions[-1]
    if abs(folded - evidence.folded_count) > FOLDED_TOLERANCE:
        raise MotionRefused(f"ID3 {folded} is not at the folded count {evidence.folded_count}")
    return folded


def prepare(session: Session, evidence: Evidence) -> Start:
    settings = read_settings(session.reader)
    frames = start_frames(session)
    folded = folded_start(frames, evidence)
    others = tuple((mid, position(frames[-1][mid])) for mid in IDS if mid != MOTOR_ID)
    envelope = envelope_for(folded, evidence.sign, settings)
    kept = tuple((name, settings[name]) for name in RESTORED)
    start = Start(folded, others, kept, envelope)
    session.log.event("start", folded_counts=folded, others=dict(others), settings=settings,
                      envelope=envelope_event(envelope))
    return start


def envelope_event(envelope: WriteEnvelope) -> Event:
    return {"motor_id": envelope.motor_id, "goal_low": envelope.goal_low,
            "goal_high": envelope.goal_high,
            "profile_acceleration": sorted(envelope.profile_acceleration),
            "profile_velocity": sorted(envelope.profile_velocity),
            "goal_pwm": sorted(envelope.goal_pwm)}


def plan_event(evidence: Evidence) -> Event:
    return {"evidence": asdict(evidence), "motor_id": MOTOR_ID, "open_counts": OPEN_COUNTS,
            "profile_acceleration": PROFILE_ACCELERATION, "profile_velocity": PROFILE_VELOCITY,
            "goal_pwm": GOAL_PWM, "reached_tolerance": REACHED_TOLERANCE,
            "stable_samples": STABLE_SAMPLES, "follow_timeout_s": FOLLOW_TIMEOUT_S,
            "hold_s": HOLD_S, "spec": "docs/id3_motion_spec.md"}


def run_motion(reader: Reader, actuator: Actuator, evidence: Evidence,
               emit: Callable[[Event], None], monotonic: Callable[[], float],
               sleep: Callable[[float], None],
               stop_requested: Callable[[], bool] = lambda: False) -> Outcome:
    log = MotionLog(emit, monotonic)
    session = Session(reader, actuator, log, monotonic, sleep, stop_requested)
    session.safe_event("plan", **plan_event(evidence))
    try:
        start = prepare(session, evidence)
    except (MotionRefused, MotionAbort) as exc:
        outcome = Outcome("refused", str(exc), interrupted=isinstance(exc, StopRequested))
        session.safe_event("outcome", **asdict(outcome))
        return outcome
    outcome = Outcome("aborted", "release did not complete", sign=evidence.sign)
    try:
        outcome = session.execute(start, evidence)
    except (KeyboardInterrupt, StopRequested) as exc:
        outcome = Outcome("aborted", f"interrupted: {exc}", sign=evidence.sign,
                          interrupted=True)
        session.safe_event("abort", reason=outcome.reason)
    except Exception as exc:  # noqa: BLE001 - abort, communication and logging failures alike
        outcome = Outcome("aborted", f"{type(exc).__name__}: {exc}", sign=evidence.sign)
        session.safe_event("abort", reason=outcome.reason)
    finally:
        released = session.release(start)
    outcome = replace(outcome, torque_off_confirmed=released.torque_off_confirmed,
                      release_problems=released.problems)
    session.safe_event("outcome", **asdict(outcome))
    return outcome


def exit_code(outcome: Outcome) -> int:
    if outcome.torque_off_confirmed is False:
        return 3
    if outcome.interrupted:
        return 130
    return 0 if outcome.status == "converged" else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Open motor ID3 by about 10 degrees, then return")
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "config/arm.toml")
    parser.add_argument("--evidence", type=Path, required=True,
                        help="hardware direction observation JSON from the viewer helper")
    parser.add_argument("--execute", action="store_true",
                        help="send the bounded ID3 writes; default is a read-only dry run")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "reports")
    return parser


class DryRunActuator:
    def set_envelope(self, envelope: WriteEnvelope) -> None:
        raise MotionAbort("dry run: no envelope")

    def recover(self) -> None:
        return None

    def write(self, name: str, value: int, allow_alert: bool = False) -> None:
        raise MotionAbort("dry run: no writes")


def dry_run(device: str, baudrate: int, evidence: Evidence) -> int:
    events: list[Event] = []
    with termination_as_interrupt(), open_bus(device, baudrate) as (port, packet):
        log = MotionLog(events.append, time.monotonic)
        session = Session(SdkReader(port, packet), DryRunActuator(), log,
                          time.monotonic, time.sleep)
        try:
            start = prepare(session, evidence)
        except (MotionRefused, MotionAbort) as exc:
            print(f"Dry run refused: {exc}; port closed after this block", file=sys.stderr)
            return 2
    print(json.dumps({"dry_run": "ok", "folded_counts": start.folded_counts,
                      "target_estimate": start.folded_counts + evidence.sign * OPEN_COUNTS,
                      "envelope": [start.envelope.goal_low, start.envelope.goal_high],
                      "port_closed": True}))
    return 0


class StopFlag:
    """Signal handler that only records the first signal; it never raises."""

    def __init__(self) -> None:
        self.signal: int | None = None

    def __call__(self, signum: int, frame: object) -> None:
        if self.signal is None:
            self.signal = signum

    def requested(self) -> bool:
        return self.signal is not None


@contextmanager
def deferred_signals(restore: bool = True) -> Iterator[StopFlag]:
    """From before the first write until the verdict is printed, signals cannot interrupt
    release or reporting; the supervision loop polls the flag and stops cleanly. The CLI
    keeps the handlers (restore=False) so no window reopens before the process exits."""
    flag = StopFlag()
    previous = {sig: signal.signal(sig, flag)
                for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}
    try:
        yield flag
    finally:
        if restore:
            for sig, handler in previous.items():
                signal.signal(sig, handler)


@contextmanager
def termination_as_interrupt() -> Iterator[None]:
    """Route SIGTERM/SIGHUP into the KeyboardInterrupt path so release still runs."""
    def interrupt(signum: int, frame: object) -> None:
        raise KeyboardInterrupt(f"signal {signum}")

    previous = {sig: signal.signal(sig, interrupt) for sig in (signal.SIGTERM, signal.SIGHUP)}
    try:
        yield
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def write_summary(log_path: Path, outcome: Outcome) -> Path:
    path = log_path.with_name(log_path.name.removesuffix(".jsonl") + ".summary.json")
    partial = path.with_name(path.name + ".tmp")
    text = json.dumps({"log": str(log_path), **asdict(outcome)}, ensure_ascii=False, indent=2)
    partial.write_text(text + "\n", encoding="utf-8")
    os.replace(partial, path)
    return path


def say(stream_name: str, text: str) -> bool:
    """Best-effort line output; a broken stream is replaced so the exit flush cannot fail."""
    try:
        print(text, file=getattr(sys, stream_name), flush=True)
        return True
    except OSError:
        setattr(sys, stream_name, open(os.devnull, "w"))
        return False


def report(path: Path, outcome: Outcome, flag: StopFlag) -> int:
    """Verdict first; summary and stdout are best-effort and cannot hide it."""
    code = exit_code(outcome)
    if outcome.torque_off_confirmed is False:
        say("stderr", "WARNING: ID3 torque OFF is NOT confirmed. Press the supply OUTPUT OFF now.")
    if flag.requested():
        say("stderr", f"Signal {flag.signal} was handled as a stop request.")
    try:
        summary: str | None = str(write_summary(path, outcome))
    except OSError as exc:
        summary = None
        say("stderr", f"Summary write failed: {exc}")
    say("stdout", json.dumps({"log": str(path), "summary": summary, **asdict(outcome),
                              "port_closed": True, "exit_code": code}, ensure_ascii=False))
    return code


def open_log(path: Path):
    return path.open("x", encoding="utf-8")


def execute(device: str, baudrate: int, evidence: Evidence, output_dir: Path,
            restore_signals: bool = True) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / (report_stem("id3_motion") + ".jsonl")
    with deferred_signals(restore_signals) as flag:
        file = open_log(path)
        try:
            def emit(event: Event) -> None:
                file.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")
                file.flush()

            with open_motion_bus(device, baudrate) as (port, packet):
                outcome = run_motion(SdkReader(port, packet), Id3Actuator(port, packet),
                                     evidence, emit, time.monotonic, time.sleep, flag.requested)
            try:
                emit({"kind": "closed", "port_closed": True, "at": timestamp()})
            except OSError as exc:
                say("stderr", f"Log write failed after port closure: {exc}")
        finally:
            try:
                file.close()
            except OSError as exc:  # buffered bytes of a full disk; the verdict still stands
                say("stderr", f"Log close failed: {exc}")
        return report(path, outcome, flag)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = load_config(args.config)
        if config.bus.expected_ids != IDS:
            raise ValueError(f"expected IDs {IDS} in the configuration")
        evidence = load_evidence(args.evidence)
        if not args.execute:
            return dry_run(config.bus.device, config.bus.baudrate, evidence)
        return execute(config.bus.device, config.bus.baudrate, evidence, args.output_dir,
                       restore_signals=False)
    except (OSError, RuntimeError, ValueError, KeyError) as exc:
        print(f"ID3 motion failed: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        # The execute path keeps record-only handlers, so this comes from the dry run or
        # from configuration/evidence loading, before any motor write.
        say("stderr", "Interrupted before any motor write; the port is closed.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
