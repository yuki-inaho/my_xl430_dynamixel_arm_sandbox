"""Regression checks for actual release geometry, plus deliberately broken controls.

Run from the package directory: python -m pytest -q source/test_revision.py
Rebuild first after changing design parameters; exported report tests must agree.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import cadquery as cq
import numpy as np
import pytest
import trimesh

from assembly_io import bounds
from rebuild import (
    DEFAULT_OUTPUT_DIR,
    DEFAULT_REFERENCE_DIR,
    ROOT,
    HOLES_YZ,
    WRIST_HOLES,
    build_geometry,
    reinforce_extension,
    require_single_solid,
    solid_volume,
    verify_sources,
)
from validate import extension_rims

RELEASE = Path(os.environ.get("CAD_RELEASE_DIR", str(DEFAULT_OUTPUT_DIR))).resolve()


@pytest.fixture(scope="session")
def build():
    return build_geometry(DEFAULT_REFERENCE_DIR)


@pytest.fixture(scope="session")
def report():
    return json.loads((RELEASE / "reports/validation.json").read_text())


@pytest.mark.parametrize(
    "name",
    [
        "base_idler_clearance",
        "elbow_to_wrist_standoff",
        "elbow_to_wrist_extension_round",
        "shoulder_rotation_unchanged",
        "shoulder_to_elbow_unchanged",
        "gripper_static_unchanged",
        "gripper_moving_unchanged",
    ],
)
def test_saved_part_is_valid_single_solid_and_closed_mesh(name):
    base = RELEASE / "CAD/parts" / name
    shape = cq.importers.importStep(str(base.with_suffix(".step"))).val()
    assert shape.isValid()
    assert len(shape.Solids()) == 1
    mesh = trimesh.load_mesh(base.with_suffix(".stl"), process=True)
    assert mesh.is_watertight and mesh.is_winding_consistent and mesh.volume > 0
    assert abs(mesh.volume / solid_volume(shape) - 1) < 0.005


@pytest.mark.parametrize("key", ["extension", "wrist"])
def test_additive_revision_never_removes_original_material(key, build):
    name = {
        "extension": "elbow_to_wrist_extension_round",
        "wrist": "elbow_to_wrist_standoff",
    }[key]
    assert solid_volume(build.local_sources[key].cut(build.parts[name])) < 1e-4


@pytest.mark.parametrize("key", ["extension", "base", "wrist"])
def test_changes_stay_inside_declared_local_masks(key, report):
    record = report["preservation"][key]
    assert record["removed_outside_mask_mm3"] < 1e-4
    assert record["added_outside_mask_mm3"] < 1e-4


@pytest.mark.parametrize("index", range(8))
def test_actual_exported_rim_and_opening(index, report):
    record = report["extension_rims"][index]
    assert record["outer_rim_mm"] >= 2.5 - 1e-5
    assert record["through_ear_verified"]


@pytest.mark.parametrize("x,y", WRIST_HOLES)
def test_wrist_integral_standoffs_keep_bore_open_and_have_wall(x, y, build):
    shape = build.parts["elbow_to_wrist_standoff"]
    assert not shape.isInside(cq.Vector(x, y, -1.5))
    assert shape.isInside(cq.Vector(x + 1.5, y, -1.5))
    assert shape.isInside(cq.Vector(x + 2.5, y, -1.5))
    assert not shape.isInside(cq.Vector(x + 2.8, y, -1.5))


def test_base_relief_open_and_mount_axes_retained(build):
    shape = build.parts["base_idler_clearance"]
    for point in [(0, 68, 0.1), (0, 68, 2.9), (8, 68, 1.5), (0, 76, 1.5)]:
        assert not shape.isInside(cq.Vector(*point))
    assert solid_volume(shape.cut(build.local_sources["base"])) < 1e-4
    assert (
        np.max(np.abs(np.array(bounds(shape)) - bounds(build.local_sources["base"])))
        < 1e-5
    )


@pytest.mark.parametrize("index", range(5))
def test_measured_mate_patterns_aligned(index, report):
    mate = report["mating_checks"][index]
    assert mate["axis_count"] == mate["expected_axis_count"]
    assert mate["max_projected_axis_error_mm"] < 1e-5


def test_roundtrip_has_one_target_not_overlay(report):
    assert report["original_solid_count"] == report["reloaded_solid_count"] == 117
    assert report["reloaded_leaf_count"] == 161
    assert report["checks"]["assembly_count_preserved_no_overlay"]


def test_base_is_not_in_distal_moving_group(build):
    assert (
        build.revised_locations[build.base_index].toTuple()
        == build.original[build.base_index].loc.toTuple()
    )


def test_purchased_geometries_are_not_modified(build):
    changed = {build.target_index, build.base_index, build.wrist_index}
    for row in build.original:
        if row.index not in changed:
            assert build.revised_shapes[row.index] is row.shape


def test_all_pairs_no_physical_conflict_or_new_reference_overlap(report):
    collisions = json.loads((RELEASE / "reports/assembly_collisions.json").read_text())
    assert collisions["revised"]["total_pairs"] == 6555
    assert collisions["physical_assembly_intersections"] == []
    assert collisions["new_intersections"] == []
    assert collisions["increased_intersections"] == []
    assert len(collisions["resolved_intersections"]) == 5
    assert all(h["supplier_internal"] for h in collisions["revised"]["intersections"])


def test_gripper_mesh_repair_is_explicit_and_bounded():
    data = json.loads((RELEASE / "reports/mesh_export.json").read_text())[
        "gripper_moving_unchanged"
    ]
    assert data["temporary_copy_repaired"] and data["source_step_unchanged"]
    assert data["radial_relief_mm"] <= 1e-5
    assert data["temporary_copy_removed_volume_mm3"] < 0.01
    assert data["temporary_copy_added_volume_mm3"] < 1e-6


def test_reference_hashes_and_scope(report):
    assert verify_sources(DEFAULT_REFERENCE_DIR) == report["input_sha256"]
    assert "Full XL430 conversion" in report["not_verified"]
    assert report["geometry_checks_passed"]


@pytest.mark.parametrize("bad_rim", [-1, 0, 2.49, 3.01, float("nan"), float("inf")])
def test_unsupported_parameters_fail_closed(bad_rim, build):
    with pytest.raises(ValueError):
        reinforce_extension(build.local_sources["extension"], bad_rim)


def test_disconnected_overlay_is_rejected(build):
    separated = cq.Compound.makeCompound(
        [
            build.parts["elbow_to_wrist_extension_round"],
            cq.Solid.makeBox(2, 2, 2, cq.Vector(100, 100, 100)),
        ]
    )
    with pytest.raises(ValueError):
        require_single_solid(separated, "deliberate_overlay")


def test_closed_counterbore_entry_is_detected(build):
    shape = build.parts["elbow_to_wrist_extension_round"]
    y, z = HOLES_YZ[0]
    blocked = shape.fuse(
        cq.Solid.makeCylinder(3, 0.3, cq.Vector(17.3, y, z), cq.Vector(1, 0, 0))
    ).clean()
    # A blind cap must fail the entry test, even though B-rep remains valid.
    assert blocked.isValid()
    assert not all(r["through_ear_verified"] for r in extension_rims(blocked))


def test_wrong_reference_revision_is_rejected(tmp_path):
    (tmp_path / "arm.step").write_text("not the inspected source")
    with pytest.raises(ValueError):
        verify_sources(tmp_path)


def test_cli_invalid_parameters_do_not_publish_normal_cad(tmp_path):
    destination = tmp_path / "failed_output"
    process = subprocess.run(
        [
            sys.executable,
            str(ROOT / "source/rebuild.py"),
            "--out",
            str(destination),
            "--rim-mm",
            "3.1",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert process.returncode == 2
    assert not (destination / "CAD/follower_geometry_checked.step").exists()
