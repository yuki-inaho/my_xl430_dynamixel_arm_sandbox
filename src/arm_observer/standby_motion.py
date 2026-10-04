"""Camera-reviewed staged standby; separate RAM guard, no absolute calibration claim."""
import argparse
import fcntl
import json
import signal
import termios
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from dynamixel_sdk import COMM_SUCCESS, PacketHandler, PortHandler
from dynamixel_sdk.protocol2_packet_handler import Protocol2PacketHandler

from arm_observer.bus import port_owners, validate_packet
from arm_observer.id3_motion import healthy, position
from arm_observer.motion_guard import WriteEnvelope, validate_write
from arm_observer.reader import SdkReader, timestamp
from arm_observer.registers import BY_NAME

IDS = (1, 2, 3, 4, 5)
ACTIVE = (2, 3, 4)
REGS = {"torque": (64, 1), "pwm": (100, 2), "acceleration": (108, 4),
        "velocity": (112, 4), "goal": (116, 4)}


@dataclass(frozen=True)
class Plan:
    baseline: tuple[int, ...]

    def __post_init__(self) -> None:
        if len(self.baseline) != 5 or any(type(p) is not int or not 0 <= p <= 4095
                                        for p in self.baseline):
            raise ValueError("Five exact single-turn baseline counts required")
        if not 1100 <= self.baseline[2] <= 1210 or not 3090 <= self.baseline[1] <= 3170:
            raise ValueError("Shoulder/elbow no longer match reviewed folded posture")
        for i, ref in ((0, 2062), (3, 2058), (4, 2059)):
            if abs(self.baseline[i] - ref) > 15:
                raise ValueError("Neutral/wrist baseline changed")

    def target(self, stage: str) -> tuple[int, ...]:
        offsets = {"elbow30": (341, 0), "elbow60": (682, 0),
                   "elbow72": (819, 0), "wrist10": (819, -114),
                   "wrist30": (819, -341), "return_wrist": (819, 0),
                   "return_elbow60": (682, 0), "return_elbow30": (341, 0),
                   "return_fold": (0, 0)}
        elbow, wrist = offsets[stage]
        b = self.baseline
        return (b[0], b[1], b[2] + elbow, b[3] + wrist, b[4])


class StandbyPort(PortHandler):
    """Three frozen per-run envelopes. Original ID3-only MotionPort is unchanged."""
    def __init__(self, device: str):
        super().__init__(device)
        self.envelopes: dict[int, WriteEnvelope] = {}

    def writePort(self, packet: list[int]) -> int:
        try:
            if len(packet) > 7 and packet[7] == 3:
                validate_write(packet, self.envelopes.get(packet[4]))
            else:
                validate_packet(packet)
        except Exception:
            self.is_using = False
            raise
        return super().writePort(packet)


@contextmanager
def open_standby_bus(device: str) -> Iterator[tuple[StandbyPort, Protocol2PacketHandler]]:
    owners = port_owners(device)
    if owners:
        raise RuntimeError(f"Serial owner(s): {owners}")
    port = StandbyPort(device)
    try:
        if not port.setBaudRate(1000000) or port.ser is None:
            raise RuntimeError("Cannot open 1 Mbps serial bus")
        port.ser.exclusive = True
        fcntl.ioctl(port.ser.fileno(), termios.TIOCEXCL)
        yield port, PacketHandler(2.0)
    finally:
        if port.is_open:
            port.closePort()


class Controller:
    def __init__(self, port: StandbyPort, packet: Protocol2PacketHandler,
                 emit: Callable[[dict], None], clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep,
                 stop_requested: Callable[[], bool] = lambda: False):
        self.port, self.packet = port, packet
        self.reader = SdkReader(port, packet)
        self.emit, self.clock, self.sleep = emit, clock, sleep
        self.stop_requested = stop_requested
        self.plan: Plan | None = None
        self.saved: dict[int, dict[str, int]] = {}
        self.enabled: set[int] = set()
        self.current: tuple[int, ...] = ()
        self.goal: tuple[int, ...] = ()
        self.stage = "unprepared"

    def event(self, kind: str, **values: object) -> None:
        self.emit({"at": timestamp(), "kind": kind, **values})

    def read(self, mid: int, names: tuple[str, ...]) -> dict[str, int]:
        batch = self.reader.registers(mid, tuple(BY_NAME[n] for n in names))
        values = {r.name: r.value for r in batch.readings}
        if batch.faults or any(r.device_alert for r in batch.readings):
            raise RuntimeError(f"ID{mid} metadata fault")
        if any(type(values.get(n)) is not int for n in names):
            raise RuntimeError(f"ID{mid} missing metadata")
        return {n: int(values[n]) for n in names}

    def sample(self) -> tuple[int, ...]:
        if self.stop_requested():
            raise RuntimeError("Stop requested")
        motors = healthy(self.reader.telemetry(IDS, "sync"))
        positions = tuple(position(motors[mid]) for mid in IDS)
        for mid in IDS:
            m = motors[mid]
            if m.torque_enabled != (mid in self.enabled):
                raise RuntimeError(f"ID{mid} torque unexpectedly changed")
            self.check_environment(mid, m.temperature_c, m.voltage_raw)
        if self.plan:
            for mid in (1, 5):
                if abs(positions[mid - 1] - self.plan.baseline[mid - 1]) > 15:
                    raise RuntimeError(f"Passive ID{mid} moved")
        self.current = positions
        self.event("sample", stage=self.stage, positions=positions,
                   torque={str(mid): motors[mid].torque_enabled for mid in IDS})
        return positions

    @staticmethod
    def check_environment(mid: int, temperature: int | None, voltage: int | None) -> None:
        if temperature is None or temperature >= 60:
            raise RuntimeError(f"ID{mid} temperature unsafe/unknown")
        if voltage is None or not 65 <= voltage <= 140:
            raise RuntimeError(f"ID{mid} voltage unsafe/unknown")

    def prepare(self, resume: dict | None = None) -> Plan:
        if resume is not None:
            if resume.get("active_ids") != list(ACTIVE):
                raise RuntimeError("Resume is not this controller's plan")
            self.enabled = set(ACTIVE)
        names = ("id", "model_number", "secondary_id", "operating_mode", "drive_mode",
                 "homing_offset", "min_position_limit", "max_position_limit",
                 "profile_acceleration", "profile_velocity", "goal_pwm")
        for mid in IDS:
            values = self.read(mid, names)
            expected = {"id": mid, "model_number": 1060, "secondary_id": 255,
                        "operating_mode": 3, "drive_mode": 0, "homing_offset": 0}
            if any(values[n] != v for n, v in expected.items()):
                raise RuntimeError(f"ID{mid} identity/mode/direction/alias changed")
            self.saved[mid] = values
        observed = self.stable_start()
        self.plan = Plan(tuple(resume["baseline"]) if resume is not None else observed)
        if resume is not None:
            self.check_resume_settings(resume)
        b = self.plan.baseline
        for mid, low, high in ((2, b[1] - 30, b[1] + 30),
                               (3, b[2] - 15, b[2] + 854),
                               (4, b[3] - 376, b[3] + 30)):
            s = self.saved[mid]
            if not s["min_position_limit"] <= low <= high <= s["max_position_limit"]:
                raise RuntimeError("Plan exceeds hardware position limit")
            self.port.envelopes[mid] = WriteEnvelope(mid, low, high,
                frozenset({1, s["profile_acceleration"]}),
                frozenset({5, s["profile_velocity"]}), frozenset({350, s["goal_pwm"]}))
        self.goal = observed
        self.stage = "prepared"
        self.event("plan", baseline=b, calibration_verified=False,
                   route=self.saved, active_ids=list(ACTIVE), final_policy="hold; never auto OFF")
        return self.plan

    def check_resume_settings(self, resume: dict) -> None:
        original = {int(k): v for k, v in resume["route"].items()}
        for mid in IDS:
            expected = dict(original[mid])
            if mid in ACTIVE:
                expected.update(profile_acceleration=1, profile_velocity=5, goal_pwm=350)
            if self.saved[mid] != expected:
                raise RuntimeError("Settings changed since stopped run")
        self.saved = original

    def stable_start(self) -> tuple[int, ...]:
        frames = [self.sample() for _ in range(5)]
        if any(max(f[i] for f in frames) - min(f[i] for f in frames) > 3
               for i in range(5)):
            raise RuntimeError("Arm is moving before torque enable")
        return frames[-1]

    def write(self, mid: int, name: str, value: int) -> None:
        address, size = REGS[name]
        result, error = getattr(self.packet, f"write{size}ByteTxRx")(
            self.port, mid, address, value)
        if result != COMM_SUCCESS or error:
            raise RuntimeError(f"ID{mid} write {name} failed: {result}/{error}")
        self.event("write", motor_id=mid, name=name, value=value)

    def enable(self) -> None:
        if self.plan is None:
            raise RuntimeError("Not prepared")
        self.stage = "enabling"
        for mid in ACTIVE:
            for name, value in (("acceleration", 1), ("velocity", 5), ("pwm", 350),
                                ("goal", self.plan.baseline[mid - 1])):
                self.write(mid, name, value)
            self.enabled.add(mid)  # reply loss may still mean torque became ON
            self.write(mid, "torque", 1)
            p = self.sample()
            if any(abs(p[i] - self.plan.baseline[i]) > 15 for i in range(5)):
                raise RuntimeError("Arm jumped on torque enable")
        self.stage = "holding_baseline"
        self.event("holding", positions=self.current)

    def start_or_resume(self, resume: dict | None) -> None:
        if resume is None:
            self.enable()
        else:
            self.stage = "holding_resumed"
            self.event("holding", positions=self.current, resumed=True)

    def move(self, stage: str) -> None:
        if self.plan is None or self.enabled != set(ACTIVE):
            raise RuntimeError("Prepared and all three holding motors required")
        target = self.plan.target(stage)
        origin = self.sample()
        self.check_stage_origin(origin, target, self.plan.baseline)
        self.stage, self.goal = stage, target
        for mid in ACTIVE:
            self.write(mid, "goal", target[mid - 1])
        started, recent, corrected = self.clock(), [], set()
        while True:
            p = self.sample()
            elapsed = self.clock() - started
            for mid in ACTIVE:
                self.check_follow(mid, p[mid - 1], origin[mid - 1], target[mid - 1], elapsed)
            recent = [*recent, p][-5:]
            if self.settled(recent, target):
                self.event("reached", stage=stage, target=target, positions=p)
                return
            if elapsed >= 1:
                self.compensate(recent, target, corrected)
            if elapsed > 18:
                raise RuntimeError("Stage deadline")
            self.sleep(0.05)

    def compensate(self, recent: list[tuple[int, ...]], target: tuple[int, ...],
                   corrected: set[int]) -> None:
        if len(recent) < 5:
            return
        for mid in ACTIVE:
            i = mid - 1
            error = target[i] - recent[-1][i]
            span = max(r[i] for r in recent) - min(r[i] for r in recent)
            if mid not in corrected and span <= 3 and 20 < abs(error) <= 50:
                offset = max(-30, min(30, error))
                self.write(mid, "goal", target[i] + offset)
                corrected.add(mid)
                self.event("load_compensation", motor_id=mid, offset=offset,
                           true_target=target[i], measured=recent[-1][i])

    @staticmethod
    def check_stage_origin(origin: tuple[int, ...], target: tuple[int, ...],
                           baseline: tuple[int, ...]) -> None:
        if abs(origin[1] - baseline[1]) > 20:
            raise RuntimeError("Holding ID2 drift before stage")
        if any(abs(target[i] - origin[i]) > 376 for i in range(5)):
            raise RuntimeError("Stage skips a 30 degree review")

    @staticmethod
    def check_follow(mid: int, p: int, origin: int, target: int, elapsed: float) -> None:
        delta, progress = target - origin, p - origin
        if abs(delta) <= 20:
            if abs(p - target) > 20:
                raise RuntimeError(f"Holding ID{mid} drift")
            return
        sign = 1 if delta > 0 else -1
        if progress * sign < -10 or (p - target) * sign > 15:
            raise RuntimeError(f"ID{mid} reverse/overshoot")
        if elapsed >= 1 and progress * sign < 3:
            raise RuntimeError(f"ID{mid} no progress")

    @staticmethod
    def settled(recent: list[tuple[int, ...]], target: tuple[int, ...]) -> bool:
        return len(recent) == 5 and all(abs(recent[-1][i] - target[i]) <= 20
            and max(r[i] for r in recent) - min(r[i] for r in recent) <= 3
            for i in (1, 2, 3))

    def freeze(self, reason: str) -> None:
        """Hold available healthy present counts; never release an unsupported arm."""
        self.port.is_using = False
        self.port.clearPort()
        self.stage = "stopped_hold"
        self.safe_event("stop", reason=reason, enabled=sorted(self.enabled))
        for mid in sorted(self.enabled):
            try:
                count = self.read(mid, ("present_position",))["present_position"]
                self.write(mid, "goal", count)
            except Exception as exc:
                self.safe_event("stop_hold_fault", motor_id=mid, error=str(exc))

    def safe_event(self, kind: str, **values: object) -> None:
        try:
            self.event(kind, **values)
        except Exception:
            pass  # damaged evidence output must not prevent emergency holding writes

    def release_supported(self) -> None:
        if self.plan is None or self.stage != "return_fold":
            raise RuntimeError("Return to baseline and verify support before release")
        p = self.sample()
        if any(abs(p[i] - self.plan.baseline[i]) > 20 for i in range(5)):
            raise RuntimeError("Not at original stable posture")
        for mid in reversed(ACTIVE):
            self.write(mid, "torque", 0)
            if self.read(mid, ("torque_enable",))["torque_enable"] != 0:
                raise RuntimeError(f"ID{mid} OFF not confirmed")
            self.enabled.remove(mid)
        self.verify_release(p)
        self.restore_ram()
        self.event("released_supported", positions=self.current, all_torque_off=True)

    def verify_release(self, prior: tuple[int, ...]) -> None:
        frames = [self.sample() for _ in range(10)]
        if any(abs(f[i] - prior[i]) > 20 for f in frames for i in range(5)):
            raise RuntimeError("Arm shifted after torque OFF")

    def restore_ram(self, ids: tuple[int, ...] = ACTIVE) -> None:
        for mid in ids:
            for name, register in (("pwm", "goal_pwm"), ("velocity", "profile_velocity"),
                                   ("acceleration", "profile_acceleration")):
                self.write(mid, name, self.saved[mid][register])
                if self.read(mid, (register,))[register] != self.saved[mid][register]:
                    raise RuntimeError("RAM restore mismatch")


def load_resume(path: Path) -> dict:
    records = [json.loads(line) for line in path.read_text().splitlines()]
    plans = [r for r in records if r["kind"] == "plan"]
    if len(plans) != 1 or not any(r["kind"] == "stop" for r in records):
        raise RuntimeError("Only a logged stopped standby run can resume")
    if any(r["kind"] == "released_supported" for r in records):
        raise RuntimeError("Already released; fresh start required")
    return plans[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--device", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--resume-from", type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    command = args.output_dir / "command.txt"
    stop = [False]
    def requested(_signum: int, _frame: object) -> None:
        stop[0] = True
    signal.signal(signal.SIGINT, requested)
    signal.signal(signal.SIGTERM, requested)
    with (args.output_dir / "events.jsonl").open("x") as log:
        def emit(event: dict) -> None:
            log.write(json.dumps(event, ensure_ascii=False) + "\n")
            log.flush()
            if event["kind"] != "sample":
                print(json.dumps(event, ensure_ascii=False), flush=True)
        with open_standby_bus(args.device) as (port, packet):
            controller = Controller(port, packet, emit, stop_requested=lambda: stop[0])
            resume = load_resume(args.resume_from) if args.resume_from else None
            controller.prepare(resume)
            if not args.execute:
                return 0
            try:
                controller.start_or_resume(resume)
                while not stop[0]:
                    if command.exists():
                        action = command.read_text().strip()
                        command.unlink()
                        if action == "release_supported":
                            controller.release_supported()
                            return 0
                        if action == "stop":
                            break
                        controller.move(action)
                    else:
                        controller.sample()
                        if any(abs(controller.current[i] - controller.goal[i]) > 20
                               for i in (1, 2, 3)):
                            raise RuntimeError("Standby holding drift")
                        controller.sleep(0.05)
            except BaseException as exc:
                controller.freeze(f"{type(exc).__name__}: {exc}")
                return 2
            controller.freeze("stop requested")
            return 2


if __name__ == "__main__":
    raise SystemExit(main())
