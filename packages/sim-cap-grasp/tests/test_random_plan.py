import json
import math

import mujoco
import numpy as np

from build_scene import MODEL, ROOT, place_reset
from random_plan import analytic_ik, plan_target, proposal_targets


def test_analytic_fk_roundtrip():
    model = mujoco.MjModel.from_xml_path(str(MODEL / "scene.xml"))
    data = mujoco.MjData(model)
    for deg in ([0, -8, -5, -53], [85, -15, 25, -90], [-135, 5, 35, -80]):
        q = np.deg2rad(deg)
        place_reset(model, data, q, 50)
        target = data.site_xpos[model.site("grip").id].copy()
        results = analytic_ik(model, target, math.radians(-50), q)
        assert results
        assert results[0]["position_error_m"] < 1e-9
        assert np.max(np.abs(np.asarray(results[0]["q"]) - q)) < 1e-6


def test_unreachable_rejected():
    model = mujoco.MjModel.from_xml_path(str(MODEL / "scene.xml"))
    assert not analytic_ik(model, [2, 2, 2], math.radians(-50))


def test_sampling_deterministic_and_broad():
    protocol = json.loads((ROOT / "protocol.json").read_text())
    a = proposal_targets(protocol, 71, 100)
    assert np.array_equal(a, proposal_targets(protocol, 71, 100))
    assert (a[:, :2].min(axis=0) < -0.25).all()
    assert (a[:, :2].max(axis=0) > 0.25).all()
    assert (a[:, 2] == 0.0575).all()


def test_original_target_path_has_fixed_standby():
    protocol = json.loads((ROOT / "protocol.json").read_text())
    result = plan_target([0, 0.18, 0.0575], protocol)
    assert result["status"] == "ACCEPTED", result
    assert result["standby_q"] == [0.0, 0.0, 0.0, 0.0]
    assert result["support_center_m"] == [0.0, 0.18, 0.025]
    assert result["ik_endpoints_feasible"]
    assert not result["forbidden_contacts"]
