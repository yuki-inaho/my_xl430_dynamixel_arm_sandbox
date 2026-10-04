"""Real SDK outgoing packets for supported release without a baseline-return motion."""


import pytest
from test_pose_capture_motion import setup

from arm_observer import photo_supported_release


def release_module(monkeypatch):
    return photo_supported_release


def test_supported_release_turns_all_off_before_restoring(monkeypatch):
    m = release_module(monkeypatch)
    _, c, serial, events = setup()
    c.enable_photo()
    c.move_photo(c.target([0, -2, 30, 0, 0]))
    old = len(serial.writes())
    m.release_supported(c, support_confirmed=True)
    writes = serial.writes()[old:]
    assert writes[:5] == [(i, 64, 0) for i in reversed(range(1, 6))]
    assert all(serial.torque(i) == 0 for i in range(1, 6))
    assert all(c.read(i, ("goal_pwm",))["goal_pwm"] == 885 for i in range(1, 6))
    assert all(c.read(i, ("profile_velocity",))["profile_velocity"] == 0 for i in range(1, 6))
    assert {a for _, a, _ in writes} == {64, 100, 108, 112, 116}
    assert events[-1]["kind"] == "external_supported_release"


def test_missing_support_refuses_before_writes(monkeypatch):
    m = release_module(monkeypatch)
    _, c, serial, _ = setup()
    c.enable_photo()
    old = len(serial.writes())
    with pytest.raises(RuntimeError, match="External weight support"):
        m.release_supported(c, support_confirmed=False)
    assert len(serial.writes()) == old


def test_unconfirmed_off_never_restores_unlimited_profiles(monkeypatch):
    m = release_module(monkeypatch)
    _, c, serial, _ = setup()
    c.enable_photo()
    old = len(serial.writes())
    original_read = c.read
    def read(mid, names):
        return {"torque_enable": 1} if names == ("torque_enable",) else original_read(mid, names)
    monkeypatch.setattr(c, "read", read)
    with pytest.raises(RuntimeError, match="OFF unconfirmed"):
        m.release_supported(c, support_confirmed=True)
    assert all(address == 64 for _, address, _ in serial.writes()[old:])
