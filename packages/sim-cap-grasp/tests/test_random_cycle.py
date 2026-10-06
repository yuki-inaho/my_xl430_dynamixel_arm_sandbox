import json

import numpy as np

from build_scene import ROOT
from random_cycle import reference
from random_plan import plan_target


def test_phase_reference_continuity_and_endpoints():
    protocol = json.loads((ROOT / "protocol.json").read_text())
    plan = plan_target([0, 0.18, 0.0575], protocol)
    plan["timing_s"] = protocol["timing_s"]
    for t in protocol["timing_s"].values():
        left = reference(plan, t - 1e-8)
        right = reference(plan, t + 1e-8)
        assert np.max(np.abs(left[1] - right[1])) < 1e-7
        assert abs(left[3] - right[3]) < 1e-7
    assert np.array_equal(reference(plan, 0)[1], [0.0, 0.0, 0.0, 0.0])
    assert np.array_equal(reference(plan, 22.5)[1], [0.0, 0.0, 0.0, 0.0])
    assert reference(plan, 11)[0] == "hold"
    assert reference(plan, 22.5)[0] == "standby_final"


def test_latched_setdown_reference_continuity():
    from random_cycle import interpolate, reference_with_setdown

    protocol = json.loads((ROOT / "protocol.json").read_text())
    plan = plan_target([0, 0.13, 0.0575], protocol)
    assert plan["status"] == "ACCEPTED"
    plan["timing_s"] = protocol["timing_s"]
    plan["pregrasp_fraction_on_lift"] = (
        protocol["planner"]["pregrasp_raise_m"] / protocol["planner"]["lift_raise_m"]
    )
    q, target = interpolate(plan, "lift", 0.15)
    latch = {"command_q": q.tolist(), "command_target_m": target.tolist(), "lift_fraction": 0.15}
    for key in ("lower_end", "release_end", "retract_end", "return_end"):
        t = plan["timing_s"][key]
        a = reference_with_setdown(plan, t - 1e-8, latch=latch)
        b = reference_with_setdown(plan, t + 1e-8, latch=latch)
        assert np.max(np.abs(a[1] - b[1])) < 1e-7
        assert np.linalg.norm(a[2] - b[2]) < 1e-8
    assert (
        np.max(
            np.abs(
                reference_with_setdown(plan, plan["timing_s"]["release_end"], latch=latch)[1] - q
            )
        )
        < 1e-12
    )


def test_prepared_interpolation_is_bit_exact():
    from random_cycle import prepare_reference

    protocol = json.loads((ROOT / "protocol.json").read_text())
    plan = plan_target([0, 0.18, 0.0575], protocol)
    plan["timing_s"] = protocol["timing_s"]
    times = np.linspace(0, 23, 100)
    original = [reference(plan, t) for t in times]
    prepare_reference(plan)
    for t, expected in zip(times, original, strict=True):
        actual = reference(plan, t)
        assert actual[0] == expected[0] and actual[3] == expected[3]
        assert np.array_equal(actual[1], expected[1])
        assert np.array_equal(actual[2], expected[2])
