"""Manual current-pose holding only, with downward PWM limits and slow RAM profiles."""

import time
from dataclasses import asdict

from arm_observer.id3_motion import healthy, position
from arm_observer.motion_guard import MotionViolation, WriteEnvelope
from arm_observer.standby_motion import IDS, REGS, Controller, StandbyPort


class PoseGuiPort(StandbyPort):
    permitted: tuple[int, int, int, int] | None = None

    def writePort(self, packet: list[int]) -> int:
        if len(packet) > 7 and packet[7] == 3:
            size = len(packet) - 12
            address = packet[8] | packet[9] << 8
            value = int.from_bytes(bytes(packet[10:10 + size]), "little")
            if (packet[4], address, size, value) != self.permitted:
                self.is_using = False
                raise MotionViolation("GUI permits only the current explicit transaction")
        return super().writePort(packet)


class PoseGuiController(Controller):
    port: PoseGuiPort

    def snapshot(self) -> dict:
        motors = self.reader.telemetry(IDS, "sync")
        if len(motors) != 5 or any(not m.complete for m in motors):
            raise RuntimeError("Incomplete motor telemetry; state is UNKNOWN")
        result = {"at": self.clock(), "observed_at": time.time(),
                  "motors": [asdict(m) for m in motors]}
        self.event("gui_sample", **result)
        return result

    def routes(self) -> dict[int, dict[str, int]]:
        names = ("id", "model_number", "secondary_id", "operating_mode", "drive_mode",
                 "homing_offset", "min_position_limit", "max_position_limit",
                 "profile_acceleration", "profile_velocity", "goal_pwm")
        values = {mid: self.read(mid, names) for mid in IDS}
        expected = {"model_number": 1060, "secondary_id": 255, "operating_mode": 3,
                    "drive_mode": 0, "homing_offset": 0}
        for mid, route in values.items():
            if route["id"] != mid or any(route[n] != v for n, v in expected.items()):
                raise RuntimeError(f"ID{mid} identity/mode/alias changed")
        return values

    def exact_write(self, mid: int, name: str, value: int) -> None:
        address, size = REGS[name]
        self.port.envelopes[mid] = WriteEnvelope(
            mid, value if name == "goal" else 0, value if name == "goal" else 0,
            frozenset({1}) if name == "acceleration" else frozenset(),
            frozenset({6}) if name == "velocity" else frozenset(),
            frozenset({value}) if name == "pwm" and 1 <= value <= (
                310 if mid == 5 else 350) else frozenset())
        self.port.permitted = (mid, address, size, value)
        try:
            self.write(mid, name, value)
        finally:
            self.port.permitted = None
            self.port.envelopes.clear()

    def torque(self, enabled: bool, *, support_confirmed: bool) -> dict:
        if not support_confirmed:
            raise RuntimeError("Support the arm/camera weight before torque switching")
        routes = self.routes()  # primary/secondary identities before any write
        if enabled:
            self.enable_current(routes)
        else:
            for mid in reversed(IDS):
                self.exact_write(mid, "torque", 0)
                if self.read(mid, ("torque_enable",))["torque_enable"] != 0:
                    raise RuntimeError(f"ID{mid} OFF was not confirmed")
        result = self.snapshot()
        if any(m["torque_enabled"] != enabled for m in result["motors"]):
            raise RuntimeError("Partial torque change; check each motor")
        self.event("gui_torque_confirmed", enabled=enabled, support_confirmed=True)
        return result

    def enable_current(self, routes: dict[int, dict[str, int]]) -> None:
        frames = []
        for _ in range(3):
            motors = healthy(self.reader.telemetry(IDS, "sync"))
            for mid, motor in motors.items():
                self.check_environment(mid, motor.temperature_c, motor.voltage_raw)
                if motor.velocity_raw != 0:
                    raise RuntimeError("Arm must be stationary before ON")
            frames.append(motors)
            self.sleep(0.1)
        for mid in IDS:
            observed = [position(f[mid]) for f in frames]
            if max(observed) - min(observed) > 3:
                raise RuntimeError(f"ID{mid} is not stable")
        # Validate every OFF axis before changing any of them.
        for mid in IDS:
            if frames[-1][mid].torque_enabled:
                continue
            r = routes[mid]
            if not 1 <= r["goal_pwm"] <= 885:
                raise RuntimeError(f"ID{mid} PWM profile invalid; no settings changed")
        for mid in IDS:
            if frames[-1][mid].torque_enabled:
                continue  # preserve loaded supporting goals of already-ON motors
            state = self.read(mid, ("torque_enable", "present_position"))
            current = state["present_position"]
            r = routes[mid]
            if (state["torque_enable"] != 0 or not 0 <= current <= 4095
                    or not r["min_position_limit"] <= current <= r["max_position_limit"]
                    or abs(current - position(frames[-1][mid])) > 3):
                raise RuntimeError(f"ID{mid} changed before ON")
            for name, register, value in (
                ("pwm", "goal_pwm", min(r["goal_pwm"], 310 if mid == 5 else 350)),
                ("acceleration", "profile_acceleration", 1),
                ("velocity", "profile_velocity", 6),
            ):
                if r[register] != value:
                    self.exact_write(mid, name, value)
                    if self.read(mid, (register,))[register] != value:
                        raise RuntimeError(f"ID{mid} holding profile readback failed")
            self.exact_write(mid, "goal", current)
            if self.read(mid, ("goal_position",))["goal_position"] != current:
                raise RuntimeError(f"ID{mid} parked goal not confirmed")
            self.exact_write(mid, "torque", 1)
            after = self.read(mid, ("torque_enable", "present_position"))
            if after["torque_enable"] != 1 or abs(after["present_position"] - current) > 15:
                raise RuntimeError(f"ID{mid} ON/jump check failed; support and inspect")
