"""Assembly-order regression fixtures; nominal geometry is not hardware approval."""
from copy import deepcopy
from pathlib import Path
import sys

import cadquery as cq
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "studies/xl430_lowcost"))
import assembly_sequence as sequence


def fixture():
    cube = cq.Workplane().box(1, 1, 1).val()
    parts = {"base": cube.translate((0, 10, 0)), "part": cube}
    plan = {
        "required_parts": ["base", "part"], "initially_installed": ["base"],
        "initial_fixture_reason": "Rigid single-part fixture",
        "stages": [{"id": "insert", "moving": "part", "requires": ["base"],
                    "offsets_mm": [[10, 0, 0], [0, 0, 0]], "max_step_mm": 1.}]}
    return parts, plan


def test_clear_sampled_path_does_not_approve_continuous_path_or_engineering():
    parts, plan = fixture()
    result = sequence.validate_sequence(parts, plan)
    assert result["sampled_clear"]
    assert result["installed_final"] == ["base", "part"]
    assert result["stages"][0]["sample_count"] == 11
    assert not result["continuous_path_verified"]
    assert not result["engineering_approved"]


def test_obstacle_on_path_is_checked_automatically():
    parts, plan = fixture()
    parts["base"] = parts["part"].translate((5, 0, 0))
    result = sequence.validate_sequence(parts, plan)
    assert not result["sampled_clear"]
    collisions = result["stages"][0]["collisions"]
    assert any(r["offset_mm"] == [5., 0., 0.] and r["obstacle"] == "base"
               and r["volume_mm3"] > .9 for r in collisions)


def test_later_stage_cannot_ignore_previously_inserted_part():
    parts, plan = fixture()
    parts["second"] = parts["part"].translate((-5, 0, 0))
    plan["required_parts"].append("second")
    plan["stages"].append({"id": "second", "moving": "second", "requires": ["part"],
                           "offsets_mm": [[10, 0, 0], [0, 0, 0]], "max_step_mm": 1.})
    result = sequence.validate_sequence(parts, plan)
    assert not result["sampled_clear"]
    assert any(c["obstacle"] == "part" for c in result["stages"][1]["collisions"])


def test_saved_pose_collision_is_not_skipped():
    parts, plan = fixture()
    parts["base"] = parts["part"]
    result = sequence.validate_sequence(parts, plan)
    assert not result["sampled_clear"]
    assert any(c["offset_mm"] == [0., 0., 0.] for c in result["stages"][0]["collisions"])


def test_narrow_between_sample_obstacle_does_not_produce_continuous_approval():
    parts, plan = fixture()
    parts["part"] = cq.Workplane().box(.1, .1, .1).val()
    parts["base"] = parts["part"].translate((.5, 0, 0))
    result = sequence.validate_sequence(parts, plan)
    assert result["sampled_clear"]
    assert not result["continuous_path_verified"]
    assert not result["engineering_approved"]


@pytest.mark.parametrize("mutate", [
    lambda p: p["stages"][0].update(moving="unknown"),
    lambda p: p["stages"][0].update(requires=["part"]),
    lambda p: p["stages"][0].update(offsets_mm=[[10, 0, 0], [1, 0, 0]]),
    lambda p: p["stages"][0].update(offsets_mm=[[0, 0, 0]]),
    lambda p: p["stages"][0].update(offsets_mm=[[float("nan"), 0, 0], [0, 0, 0]]),
    lambda p: p["stages"][0].update(max_step_mm=0),
    lambda p: p["stages"][0].update(max_step_mm=float("inf")),
    lambda p: p["stages"][0].update(max_step_mm=True),
    lambda p: p["stages"][0].update(exclude=["base"]),
    lambda p: p["stages"][0].update(obstacles=[]),
    lambda p: p.update(initially_installed=["base", "base"]),
    lambda p: p.update(required_parts=["base", "part", "part"]),
    lambda p: p.update(required_parts=["base"]),
    lambda p: p.update(stages=[]),
    lambda p: p.update(initial_fixture_reason=""),
    lambda p: p["stages"].append(deepcopy(p["stages"][0])),
])
def test_invalid_or_incomplete_sequence_is_rejected(mutate):
    parts, plan = fixture()
    mutate(plan)
    with pytest.raises(ValueError):
        sequence.validate_sequence(parts, plan)


def test_catalog_part_omitted_from_required_inventory_cannot_disappear():
    parts, plan = fixture()
    parts["forgotten_washer"] = parts["part"].translate((0, 50, 0))
    with pytest.raises(ValueError, match="inventory"):
        sequence.validate_sequence(parts, plan)


def test_surface_only_obstacle_is_not_silently_ignored():
    parts, plan = fixture()
    parts["base"] = parts["base"].Faces()[0]
    with pytest.raises(ValueError, match="solid"):
        sequence.validate_sequence(parts, plan)


def test_boolean_failure_propagates_instead_of_becoming_zero_interference(monkeypatch):
    parts, plan = fixture()
    parts["base"] = parts["part"].translate((5, 0, 0))
    def broken(*args):
        raise RuntimeError("kernel failure fixture")
    monkeypatch.setattr(sequence, "_intersection_volume", broken)
    with pytest.raises(RuntimeError, match="kernel failure"):
        sequence.validate_sequence(parts, plan)


def test_initial_fixture_collision_is_reported():
    parts, plan = fixture()
    parts["bad_anchor"] = parts["base"]
    plan["required_parts"].append("bad_anchor")
    plan["initially_installed"].append("bad_anchor")
    result = sequence.validate_sequence(parts, plan)
    assert not result["sampled_clear"]
    assert result["initial_collisions"][0]["volume_mm3"] > .9


def test_nondivisible_segments_include_waypoints_and_enforce_spacing():
    points = sequence.sample_offsets([[2, 0, -2.5], [2, 0, 0], [0, 0, 0]], 1.)
    assert points[0] == [2., 0., -2.5]
    assert points[-1] == [0., 0., 0.]
    assert [2., 0., 0.] in points
    assert all((cq.Vector(*a)-cq.Vector(*b)).Length <= 1.+1e-12
               for a, b in zip(points, points[1:]))


def test_replacement_cannot_remove_the_motor_body_as_a_clearance_workaround():
    prefix = "/motor/"
    suffixes = ["DC11_A01_IDLER_DUMMY:1", "DC11_A01_IDLER_CAP_DUMMY:1",
                "DC11_A01_IDLER_SCREW:1/ref", "DC11_A01_IDLER_SCREW:1/solid", "CASE:1"]
    rows = [{"name": str(i), "logical_path": prefix+s} for i, s in enumerate(suffixes)]
    config = {"source_motor_path": prefix, "removed_source_parts": ["0", "1", "2", "3"]}
    assert sequence.replacement_inventory(config, rows)[1] == {"0", "1", "2", "3"}
    config["removed_source_parts"].append("4")
    with pytest.raises(ValueError, match="exactly"):
        sequence.replacement_inventory(config, rows)


def test_nominal_candidate_does_not_claim_thread_or_preload_verification():
    import yaml
    from parts.external_center_support import make_parts
    config = yaml.safe_load(sequence.CONFIG.read_text())["candidate"]
    parts, stack = make_parts(config)
    assert set(parts) == {"tube", "guide", "washer", "bolt"}
    assert stack["washer_to_guide_axial_gap_mm"] == pytest.approx(.3)
    assert not stack["thread_engagement_verified"]
    assert not stack["preload_and_tolerances_verified"]
    assert sequence._intersection_volume(parts["guide"], parts["washer"]) < 1e-4
    config["tube"]["length_mm"] = 7.
    parts, stack = make_parts(config)
    assert stack["washer_to_guide_axial_gap_mm"] < 0
    assert sequence._intersection_volume(parts["guide"], parts["washer"]) > 1.


def candidate_fixture():
    import yaml
    from parts.external_center_support import make_parts
    config = yaml.safe_load(sequence.CONFIG.read_text())["candidate"]
    parts, _ = make_parts(config)
    return config, parts


def test_exact_axial_sweep_catches_thin_between_sample_obstacle():
    from parts import external_center_support as support
    config, parts = candidate_fixture()
    washer = parts["washer"]
    b = washer.BoundingBox()
    wall = cq.Workplane().box(.1, .1, .1).translate(
        ((b.xmin+b.xmax)/2+2, config["axis_yz_mm"][0]+5, config["axis_yz_mm"][1])).val()
    assert sequence._intersection_volume(washer, wall) == 0
    assert sequence._intersection_volume(washer.translate((4,0,0)), wall) == 0
    sweep = support.make_insertion_sweeps(config, 4)["washer"]
    assert sequence._intersection_volume(sweep, wall) > 1e-4
    plan = {"initially_installed": ["wall"], "stages": [
        {"id": "washer", "moving": "washer", "offsets_mm": [[4,0,0],[0,0,0]]}]}
    result = sequence.continuous_accessory_checks({"washer": washer, "wall": wall}, plan, config)
    assert result[0]["supported"] and result[0]["continuous_clear"] is False
    assert result[0]["collisions"][0]["obstacle"] == "wall"


def test_axial_sweeps_cover_original_and_all_translated_poses():
    from parts import external_center_support as support
    config, parts = candidate_fixture()
    sweeps = support.make_insertion_sweeps(config, 4)
    for name, part in parts.items():
        assert sweeps[name].BoundingBox().xmax == pytest.approx(part.BoundingBox().xmax+4)
        assert sweeps[name].BoundingBox().xmin == pytest.approx(part.BoundingBox().xmin)
        for offset in (0., .125, 2.75, 4.):
            remainder = part.translate((offset,0,0)).cut(sweeps[name])
            assert sum(s.Volume() for s in remainder.Solids()) < 1e-4


@pytest.mark.parametrize("waypoints, supported", [
    ([[4,0,0],[0,0,0]], True),
    ([[0,4,0],[0,0,0]], False),
    ([[-4,0,0],[0,0,0]], False),
    ([[4,1,0],[4,0,0],[0,0,0]], False),
])
def test_continuous_checker_does_not_claim_other_directions(waypoints, supported):
    config, generated = candidate_fixture()
    parts = {"washer": generated["washer"], "base": cq.Workplane().box(1,1,1).val()}
    plan = {"initially_installed": ["base"], "stages": [
        {"id": "washer", "moving": "washer", "offsets_mm": waypoints}]}
    result = sequence.continuous_accessory_checks(parts, plan, config)
    assert result[0]["supported"] is supported
    assert result[0]["continuous_clear"] is (True if supported else None)


def test_sweep_definition_cannot_be_reused_for_a_different_shape():
    config, generated = candidate_fixture()
    parts = {"washer": generated["washer"].translate((1,0,0)), "base": cq.Workplane().box(1,1,1).val()}
    plan = {"initially_installed": ["base"], "stages": [
        {"id": "washer", "moving": "washer", "offsets_mm": [[4,0,0],[0,0,0]]}]}
    with pytest.raises(ValueError, match="sweep definition"):
        sequence.continuous_accessory_checks(parts, plan, config)
