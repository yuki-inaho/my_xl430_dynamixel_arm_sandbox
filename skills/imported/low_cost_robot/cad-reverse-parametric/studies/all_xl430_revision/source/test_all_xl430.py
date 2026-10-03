"""Regression tests for the all-XL430 prototype and its fail-closed gate.

Synthetic fixtures exercise gate behavior only; they are not CAD approval.
The real candidate is regenerated and scanned by ``source/study.py`` and the
evidence is recorded in ``README_ja.md``.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import cadquery as cq
import pytest
from OCP.BRepAdaptor import BRepAdaptor_Surface

SOURCE_DIR = Path(__file__).resolve().parent
STUDY_DIR = SOURCE_DIR.parent
CADRE_ROOT = STUDY_DIR.parents[1]

sys.path.insert(0, str(SOURCE_DIR))

from collisions import bbox_overlaps, common_volume, original_unit  # noqa: E402
from common import (  # noqa: E402
    PART_NAMES,
    PENDING_CHECKS,
    STUDY_ID,
    VOLUME_TOLERANCE_MM3,
    candidate_inventory,
    check_reference_hashes,
    read_json,
    sha256,
    study_run,
    write_json,
)
from print_gate import assert_fresh_destination, evaluate  # noqa: E402

INVENTORY = {"CAD/example.step": "synthetic-test-hash-not-a-real-CAD-approval"}


def synthetic_good() -> dict:
    return {
        "study_id": STUDY_ID,
        "candidate_sha256": INVENTORY.copy(),
        "acceptance_state": "accepted_for_print",
        "static_interference": {
            "complete": True,
            "errors": [],
            "leaf_count": 217,
            "motor_occurrence_count": 6,
            "boolean_candidate_pairs": 1,
            "boolean_attempted_pairs": 1,
            "external_collision_count": 0,
            "external_collisions": [],
            "volume_tolerance_mm3": VOLUME_TOLERANCE_MM3,
        },
        "parts": {
            name: {
                "valid_brep": True,
                "solid_count": 1,
                "stl_watertight": True,
                "stl_positive_volume": True,
                "all_xl430_compatible": True,
            }
            for name in PART_NAMES
        },
        "required_checks": {
            name: {
                "status": "passed",
                "evidence": "SYNTHETIC TEST ONLY",
                "candidate_sha256": INVENTORY.copy(),
            }
            for name in PENDING_CHECKS
        },
    }


def test_synthetic_fully_evidenced_gate_can_pass():
    assert evaluate(synthetic_good(), INVENTORY) == []


@pytest.mark.parametrize("count", [1, 54])
def test_remaining_collision_blocks(count):
    report = synthetic_good()
    report["static_interference"].update(
        external_collision_count=count, external_collisions=[{}] * count
    )
    assert f"external_collisions_remaining:{count}" in evaluate(report, INVENTORY)


@pytest.mark.parametrize("count", [None, True, -1, 0.0, "0", float("nan")])
def test_bad_count_type_or_value_fails_closed(count):
    report = synthetic_good()
    report["static_interference"]["external_collision_count"] = count
    assert "invalid_collision_count_or_missing_pair_evidence" in evaluate(
        report, INVENTORY
    )


def test_editing_count_to_zero_does_not_hide_pairs():
    report = synthetic_good()
    report["static_interference"]["external_collisions"] = [{}] * 54
    assert evaluate(report, INVENTORY)


@pytest.mark.parametrize("value", [None, False, "true"])
def test_incomplete_check_blocks(value):
    report = synthetic_good()
    report["static_interference"]["complete"] = value
    assert "collision_check_incomplete_or_failed" in evaluate(report, INVENTORY)


def test_boolean_error_blocks_even_with_zero_count():
    report = synthetic_good()
    report["static_interference"]["errors"] = [{"error": "Boolean failed"}]
    assert evaluate(report, INVENTORY)


def test_old_mixed_baseline_pass_is_rejected():
    report = synthetic_good()
    report["study_id"] = "mixed_baseline"
    assert "wrong_study_or_baseline_report" in evaluate(report, INVENTORY)


def test_stale_candidate_hash_blocks():
    assert "stale_or_missing_candidate_hashes" in evaluate(
        synthetic_good(), {"CAD/example.step": "changed"}
    )


@pytest.mark.parametrize(
    "field", ["static_interference", "parts", "required_checks", "candidate_sha256"]
)
def test_missing_required_sections_block(field):
    report = synthetic_good()
    del report[field]
    assert evaluate(report, INVENTORY)


def test_zero_collision_does_not_auto_accept():
    report = synthetic_good()
    report["acceptance_state"] = "unaccepted"
    assert "candidate_is_unaccepted" in evaluate(report, INVENTORY)


def test_unchanged_mixed_part_geometry_not_xl430_fit():
    report = synthetic_good()
    for item in report["parts"].values():
        item["all_xl430_compatible"] = None
    reasons = evaluate(report, INVENTORY)
    assert (
        len([r for r in reasons if r.startswith("all_xl430_part_fit_unverified:")]) == 7
    )


@pytest.mark.parametrize("check", PENDING_CHECKS)
def test_missing_same_revision_engineering_evidence_blocks(check):
    report = synthetic_good()
    report["required_checks"][check]["candidate_sha256"] = {"CAD/example.step": "old"}
    assert f"missing_same_revision_evidence:{check}" in evaluate(report, INVENTORY)


def test_inflated_tolerance_cannot_clear_interference():
    report = synthetic_good()
    report["static_interference"]["volume_tolerance_mm3"] = 9999
    assert "changed_or_missing_collision_tolerance" in evaluate(report, INVENTORY)


def test_partial_boolean_scan_blocks():
    report = synthetic_good()
    report["static_interference"]["boolean_attempted_pairs"] = 0
    assert "not_all_candidates_checked" in evaluate(report, INVENTORY)


@pytest.mark.parametrize(
    "run_id", ["../print", "/tmp/output", "a/b", "..", ".", "", "name\\path"]
)
def test_generation_cannot_escape_quarantine(tmp_path, run_id):
    with pytest.raises(ValueError):
        study_run(run_id, root=tmp_path)


def test_generation_rejects_quarantine_symlink(tmp_path):
    outside = tmp_path / "release"
    outside.mkdir()
    (tmp_path / "unaccepted").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        study_run("current", root=tmp_path)


def test_generation_rejects_run_symlink(tmp_path):
    (tmp_path / "unaccepted").mkdir()
    outside = tmp_path / "release"
    outside.mkdir()
    (tmp_path / "unaccepted/current").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        study_run("current", root=tmp_path)


def test_existing_print_file_not_overwritten(tmp_path):
    path = tmp_path / "already.zip"
    path.write_bytes(b"older artifact")
    with pytest.raises(FileExistsError):
        assert_fresh_destination(path, quarantine=tmp_path / "unaccepted")
    assert path.read_bytes() == b"older artifact"


def test_print_output_cannot_alias_quarantine(tmp_path):
    with pytest.raises(ValueError):
        assert_fresh_destination(
            tmp_path / "unaccepted/print.zip", quarantine=tmp_path / "unaccepted"
        )


def test_modified_reference_is_rejected(tmp_path):
    reference = tmp_path / "reference/input.step"
    reference.parent.mkdir()
    reference.write_bytes(b"before")
    manifest = tmp_path / "input_sha256.json"
    write_json(manifest, {"input.step": sha256(reference)})
    reference.write_bytes(b"after")
    with pytest.raises(ValueError, match="Reference missing or changed"):
        check_reference_hashes(
            manifest_path=manifest, reference_dir=tmp_path / "reference"
        )


def test_reference_traversal_is_rejected(tmp_path):
    outside = tmp_path / "outside.step"
    outside.write_bytes(b"content")
    manifest = tmp_path / "input_sha256.json"
    write_json(manifest, {"../outside.step": sha256(outside)})
    reference = tmp_path / "reference"
    reference.mkdir()
    with pytest.raises(ValueError, match="Reference missing or unsafe"):
        check_reference_hashes(manifest_path=manifest, reference_dir=reference)


def test_json_rejects_nonfinite_data(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text('{"value": NaN}')
    with pytest.raises(ValueError):
        read_json(path)


def test_atomic_report_cannot_write_nonfinite_data(tmp_path):
    path = tmp_path / "result.json"
    with pytest.raises(ValueError):
        write_json(path, {"volume": float("nan")})
    assert not path.exists()


def test_cli_unknown_run_does_not_create_print_zip(tmp_path):
    output = tmp_path / "should_not_exist.zip"
    process = subprocess.run(
        [
            sys.executable,
            str(SOURCE_DIR / "study.py"),
            "print-package",
            "--run-id",
            "missing_test_run",
            "--output",
            str(output),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert process.returncode == 3
    assert not output.exists()
    assert "blocked_validation_error" in process.stderr


def test_cli_has_no_force_or_skip_switch(tmp_path):
    process = subprocess.run(
        [sys.executable, str(SOURCE_DIR / "study.py"), "rebuild", "--force"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert process.returncode != 0
    assert "unrecognized arguments" in process.stderr


def test_generator_is_import_safe():
    import build_all_xl430

    assert callable(build_all_xl430.generate_candidate)
    assert not (STUDY_DIR / "unaccepted/missing_test_run").exists()


REPLACEMENT_OCCURRENCES = (
    ("J3", "/Robot Arm v14/XL,XC-330 v1:6"),
    ("J4", "/Robot Arm v14/XL,XC-330 v1:7"),
    ("J5_GRIPPER", "/Robot Arm v14/gripper v9:1/XL,XC-330 v1:1"),
    ("J6", "/Robot Arm v14/XL,XC-330 v1:8"),
)


@pytest.fixture(scope="module")
def real_prototype():
    from build_all_xl430 import build_prototype

    return build_prototype()


def _idler_axis(shape, outer_radius):
    cylinders = [BRepAdaptor_Surface(f.wrapped).Cylinder()
                 for f in shape.Faces() if f.geomType() == "CYLINDER"]
    outer = [c for c in cylinders if abs(c.Radius()-outer_radius) < 1e-5]
    assert outer, "Missing dedicated idler outside cylinder"
    axis = outer[0].Axis()
    point = cq.Vector(axis.Location().X(), axis.Location().Y(), axis.Location().Z())
    direction = cq.Vector(axis.Direction().X(), axis.Direction().Y(), axis.Direction().Z())
    return point, direction


@pytest.mark.parametrize("tag,path", REPLACEMENT_OCCURRENCES)
def test_replacement_axis_preserves_actual_baseline_idler(real_prototype, tag, path):
    baseline = real_prototype.baseline
    originals = [r for r in baseline.original if r.path.startswith(path+"/")
                 and r.name == "DC15_A01_HORN_IDLE2_DUMMY:1"]
    assert len(originals) == 1
    original = originals[0]
    old_shape = original.shape.moved(baseline.revised_locations[original.index])
    replacement = real_prototype.assembly.objects[tag+"_XL430_07_DC11_A01_IDLER_DUMMY_1"]
    new_shape = replacement.obj.moved(replacement.loc)
    old_point, old_direction = _idler_axis(old_shape, 8.0)
    new_point, new_direction = _idler_axis(new_shape, 10.25)
    assert abs(old_direction.dot(new_direction)) == pytest.approx(1, abs=1e-8)
    displacement = new_point-old_point
    radial = displacement-old_direction*displacement.dot(old_direction)
    assert radial.Length < 1e-5, f"{tag}: radial axis error {radial.Length} mm"


@pytest.mark.parametrize("tag,path", REPLACEMENT_OCCURRENCES)
def test_replacement_leaf_placement_and_shape_match_baseline(real_prototype, tag, path):
    from build_all_xl430 import REFERENCE_XL430, read_assembly_nodes
    from common import REFERENCE_DIR

    baseline = real_prototype.baseline
    nodes = read_assembly_nodes(REFERENCE_DIR / "arm.step")
    originals = [r for r in baseline.original if r.path.startswith(path+"/")]
    assert len(originals) == 21
    # Infer the module movement from the baseline leaves, not TARGETS' shift list.
    moves = [baseline.revised_locations[r.index]*r.loc.inverse for r in originals]
    reference_rows = {r.path: r for r in baseline.original}
    replacements = [m for m in real_prototype.manifest if m.get("target_occurrence") == path]
    assert len(replacements) == 35
    for move in moves:
        expected_top = move*nodes[path]
        for item in replacements:
            donor = reference_rows[item["reference_leaf"]]
            expected = expected_top*nodes[REFERENCE_XL430].inverse*donor.loc
            actual = real_prototype.assembly.objects[item["name"]]
            assert actual.obj.isSame(donor.shape), "Replacement reshaped a supplier part"
            a, b = actual.loc.wrapped.Transformation(), expected.wrapped.Transformation()
            assert [a.Value(i,j) for i in range(1,4) for j in range(1,5)] == pytest.approx(
                [b.Value(i,j) for i in range(1,4) for j in range(1,5)], abs=1e-8
            ), f"{tag}: incorrect placement for {item['name']}"


def test_replacement_keeps_all_other_geometry_and_locations(real_prototype):
    assert len(real_prototype.manifest) == 217
    kept = [m for m in real_prototype.manifest if m["action"] == "kept_from_geometry_revision"]
    assert len(kept) == 77
    for item in kept:
        index = item["source_index"]
        actual = real_prototype.assembly.objects[item["name"]]
        assert actual.obj.isSame(real_prototype.baseline.revised_shapes[index])
        assert actual.loc.toTuple() == real_prototype.baseline.revised_locations[index].toTuple()


def test_extra_unvalidated_part_file_blocks_inventory(tmp_path):
    part_directory = tmp_path / "CAD/parts"
    part_directory.mkdir(parents=True)
    for name in PART_NAMES:
        for extension in ("step", "stl"):
            (part_directory / f"{name}.{extension}").write_bytes(b"test fixture")
    (part_directory / "unreviewed.stl").write_bytes(b"extra")
    with pytest.raises(ValueError, match="Unexpected, missing or extra"):
        candidate_inventory(tmp_path)


def test_native_worker_crash_is_blocking(monkeypatch):
    import study

    monkeypatch.setattr(
        study.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], -11),
    )
    with pytest.raises(RuntimeError, match="exited with code -11"):
        study.run_worker("validate", "current")


def test_native_worker_timeout_is_blocking(monkeypatch):
    import study

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], 1800)

    monkeypatch.setattr(study.subprocess, "run", timeout)
    with pytest.raises(RuntimeError, match="timed out"):
        study.run_worker("validate", "current")


def test_cli_worker_failure_does_not_create_zip(monkeypatch, tmp_path):
    import study

    run = tmp_path / "unaccepted/current"
    run.mkdir(parents=True)
    output = tmp_path / "forbidden.zip"
    monkeypatch.setattr(study, "study_run", lambda run_id: run)

    def failure(*args):
        raise RuntimeError("CAD validate exited with code -11; print is blocked")

    monkeypatch.setattr(study, "run_worker", failure)
    assert study.main(["print-package", "--output", str(output)]) == 3
    assert not output.exists()
    assert read_json(run / "reports/print_gate.json")["print_status"] == "blocked"


def test_common_volume_positive():
    left = cq.Solid.makeBox(2, 2, 2)
    right = cq.Solid.makeBox(2, 2, 2, cq.Vector(1, 0, 0))
    volume, _ = common_volume(left, right)
    assert volume == pytest.approx(4.0, abs=1e-8)


def test_common_volume_separated():
    left = cq.Solid.makeBox(1, 1, 1)
    right = cq.Solid.makeBox(1, 1, 1, cq.Vector(3, 0, 0))
    volume, _ = common_volume(left, right)
    assert volume == pytest.approx(0.0, abs=1e-8)


def test_tangent_boxes_not_volume_collisions():
    assert not bbox_overlaps([0, 0, 0, 1, 1, 1], [1, 0, 0, 2, 1, 1])


def test_overlapping_boxes_reach_narrow_phase():
    assert bbox_overlaps([0, 0, 0, 2, 2, 2], [1, 1, 1, 3, 3, 3])


def test_two_motors_are_not_one_supplier_unit():
    left = original_unit("/Robot Arm v14/XL-430_new v1:1/case")
    right = original_unit("/Robot Arm v14/XL-430_new v1:2/case")
    assert left != right


def test_bracket_is_not_a_supplier_internal_part():
    bracket = "/Robot Arm v14/XL330_to_XL330_straight v5:1/connector:1"
    assert original_unit(bracket) == bracket
    assert bracket != original_unit("/Robot Arm v14/XL,XC-330 v1:8/case")
