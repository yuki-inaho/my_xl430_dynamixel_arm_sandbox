"""One real-SDK offline boundary/round-trip check for the mounted-gripper probe."""
import importlib.util
import json
from contextlib import contextmanager
from functools import partial
from pathlib import Path

import pytest
from dynamixel_sdk import PacketHandler
from test_id3_motion import FakeClock
from xl430_emulator import EmuSerial, put

from arm_observer.motion_guard import MotionViolation
from arm_observer.standby_motion import StandbyPort


def test_probe_preserves_jaw_pwm_boundary_and_returns_supported_off():
    spec = importlib.util.spec_from_file_location(
        "cap_probe", Path(__file__).resolve().parents[1] / "scripts/cap_grasp_probe.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    port = StandbyPort("offline-emulator")
    port.ser = EmuSerial(positions=(2021, 3537, 1133, 3390, 2091), step=12)
    port.is_open, port.baudrate, port.tx_time_per_byte = True, 1000000, 0.01
    clock = FakeClock()
    controller = module.ProbeController(
        port, PacketHandler(2.0), lambda _: None, clock.monotonic, clock.sleep
    )
    controller.prepare_photo()
    with pytest.raises(MotionViolation):
        controller.packet.write2ByteTxRx(port, 5, 100, 350)
    assert not port.ser.writes()
    controller.enable_photo()
    assert controller.read(5, ("goal_pwm",))["goal_pwm"] == 310
    controller.move_photo(controller.target((0, 0, 15, 0, 0)))
    assert controller.current[2] > 1250
    controller.return_and_release()
    assert all(port.ser.torque(mid) == 0 for mid in range(1, 6))
    assert all(controller.read(mid, ("goal_pwm",))["goal_pwm"] == 885 for mid in range(1, 6))


def test_new_axis_move_preserves_static_loaded_elbow_and_still_detects_drift(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    from cap_grasp_stages import ReachController

    port = StandbyPort("offline-emulator")
    port.ser = EmuSerial(positions=(2021, 3537, 1133, 3390, 2091), step=12)
    port.is_open, port.baudrate, port.tx_time_per_byte = True, 1000000, 0.01
    clock = FakeClock()
    c = ReachController(port, PacketHandler(2), lambda _: None, clock.monotonic, clock.sleep)
    c.prepare_photo()
    c.enable_photo()
    c.move_photo(c.target((0, 0, 60, 0, 0)))
    motor = port.ser.motors[3]
    motor.step = lambda _: None
    put(motor.t, 132, 4, 1790)  # static offset26 from raw goal1816; accepted origin was1791
    c.hold_reference = (2021, 3537, 1791, 3390, 2091)
    writes = len(port.ser.writes())
    c.move_photo(c.target((0, -10, 60, 0, 0)))
    assert c.current[2] == 1790
    assert not any(mid == 3 and address == 116
                   for mid, address, _ in port.ser.writes()[writes:])
    put(motor.t, 132, 4, 1760)
    with pytest.raises(RuntimeError, match="holding drift"):
        c.hold(0.1)
    raw_support = c.goal[2]
    c.freeze("observed holding drift")
    assert c.read(3, ("goal_position",))["goal_position"] == raw_support


def test_return_only_output_revision_is_id2_scoped_and_restores_off(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    import cap_recovery_output as cli
    from cap_grasp_stages import WideRecoveryController

    port = StandbyPort("offline-emulator")
    port.ser = EmuSerial(positions=(2021, 3537, 1133, 3390, 2091), step=12)
    port.is_open, port.baudrate, port.tx_time_per_byte = True, 1000000, 0.01
    clock, events = FakeClock(), []
    factory = partial(WideRecoveryController, clock=clock.monotonic, sleep=clock.sleep)
    c = factory(port, PacketHandler(2), events.append)
    c.prepare_photo()
    c.enable_photo()
    c.move_photo((2021, 3537, 1133, 3380, 2091))
    c.move_photo((1509, 2851, 1133, 3380, 2091))
    c.freeze("original failed return")
    source = tmp_path / "held.jsonl"
    source.write_text("\n".join(json.dumps(e) for e in events) + "\n")

    @contextmanager
    def bus(_):
        yield port, PacketHandler(2)

    monkeypatch.setattr(cli, "open_standby_bus", bus)
    monkeypatch.setattr(cli, "WideRecoveryController", factory)
    monkeypatch.setattr(cli, "stop_handler", lambda: lambda: False)
    monkeypatch.setattr(cli, "capture_pair", lambda *_: None)
    monkeypatch.setattr("sys.argv", ["recovery", "--output", str(tmp_path / "out"),
                                     "--resume-log", str(source), "--execute"])
    assert cli.main() == 0
    assert (2, 100, 395) in port.ser.writes()
    assert not any(mid != 2 and address == 100 and value == 395
                   for mid, address, value in port.ser.writes())
    assert all(port.ser.torque(mid) == 0 for mid in range(1, 6))
    assert all(c.read(mid, ("goal_pwm",))["goal_pwm"] == 885 for mid in range(1, 6))
