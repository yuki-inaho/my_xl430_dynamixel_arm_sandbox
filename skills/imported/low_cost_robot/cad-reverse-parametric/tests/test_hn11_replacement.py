"""TDD checks for the printed HN11-I101 M2 heat-set idler replacement.

The replacement preserves the source idler envelope and converts the four
0-degree PCD16 fastening holes into blind heat-set insert seats that open on the
outer (link-side) face.  Insert dimensions stay provisional until the physical
ESJNNK M2 insert or its drawing is measured.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "studies" / "xl430_lowcost"
PARTS = STUDY / "parts"
for path in (STUDY, PARTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _module():
    module = _load("hn11_m2_idler", PARTS / "hn11_m2_idler.py")
    if not module.SOURCE_STEP.is_file():
        pytest.skip(f"source HN11 STEP not available: {module.SOURCE_STEP}")
    return module


def test_hn11_rotor_is_single_valid_solid():
    module = _module()
    source = module.load_source_rotor()
    rotor = module.make_rotor()
    assert rotor.isValid()
    assert len(rotor.Solids()) == 1
    # Net change is small: fill 0-degree counterbores, then bore blind seats.
    assert abs(rotor.Volume() - source.Volume()) < 40.0


def test_hn11_insert_seats_are_blind_at_pcd16_on_outer_face():
    module = _module()
    rotor = module.make_rotor()
    spec = module.insert_spec()
    seats = module.seat_features(rotor)
    assert len(seats) == 4, seats
    for seat in seats:
        assert seat["diameter_mm"] == pytest.approx(spec["insert_bore_diameter_mm"], abs=0.01)
        assert seat["radial_mm"] == pytest.approx(spec["pcd_mm"] / 2.0, abs=0.05)
        assert seat["floor_mm"] >= spec["minimum_floor_mm"] - 1e-6
        assert seat["opens_toward"] == "outer"
        assert seat["blind"] is True


@pytest.mark.parametrize("overrides", [
    {"insert_outer_diameter_mm": 0.0},
    {"insert_outer_diameter_mm": 4.5},
    {"insert_length_mm": 2.0},
    {"insert_length_mm": 5.0},
    {"insert_bore_diameter_mm": 3.2},
    {"insert_bore_depth_mm": 3.1},
    {"minimum_floor_mm": -0.1},
])
def test_hn11_insert_dimensions_reject_invalid_values(overrides):
    module = _module()
    with pytest.raises(ValueError):
        module.validate_insert_dimensions(**overrides)


def test_hn11_insert_dimensions_accept_valid_and_stay_unconfirmed():
    module = _module()
    spec = module.validate_insert_dimensions()
    assert spec["confirmed"] is False
    assert spec["insert_bore_depth_mm"] <= 3.5 - spec["minimum_floor_mm"] + 1e-9


def test_hn11_step_roundtrip_preserves_parts(tmp_path):
    module = _module()
    import cadquery as cq

    rotor = module.make_rotor()
    path = tmp_path / "rotor.step"
    cq.exporters.export(rotor, str(path))
    reopened = cq.importers.importStep(str(path)).val()
    assert len(reopened.Solids()) == 1
    source_box = rotor.BoundingBox()
    reopened_box = reopened.BoundingBox()
    assert reopened_box.xlen == pytest.approx(source_box.xlen, abs=1e-3)
    assert reopened_box.zlen == pytest.approx(source_box.zlen, abs=1e-3)


def test_hn11_coupon_has_intended_blind_holes():
    module = _module()
    coupon = module.make_coupon()
    spec = module.coupon_spec()
    holes = module.coaxial_cylinder_faces(coupon)
    for diameter in spec["hole_diameters_mm"]:
        assert any(abs(c["diameter_mm"] - diameter) < 0.05 for c in holes), diameter


def test_hn11_coupon_pip_identification():
    module = _module()
    coupon = module.make_coupon()
    spec = module.coupon_spec()
    diameters = [float(v) for v in spec["hole_diameters_mm"]]
    pips = [c for c in module.coaxial_cylinder_faces(coupon)
            if abs(c["diameter_mm"] - 1.4) < 0.05]
    assert len(pips) == sum(range(1, len(diameters) + 1))
    sx, _, _ = (float(v) for v in spec["block_xyz_mm"])
    start = -sx / 2.0 + 4.0
    step = (sx - 8.0) / (len(diameters) - 1)
    for i, diameter in enumerate(diameters):
        x0 = start + i * step
        near = [p for p in pips if abs(p["axis_pt"][0] - x0) <= 3.5]
        assert len(near) == i + 1, (diameter, len(near))


def test_hn11_source_sha_verification():
    module = _module()
    expected = module._source_block()["step_sha256"]
    assert module.verify_source_sha() == expected
    with pytest.raises(ValueError):
        module.verify_source_sha("deadbeef")


def test_hn11_cap_matches_source_cap(): 
    module = _module()
    cap = module.make_cap()
    source = module.load_source_cap()
    assert cap.isValid() and len(cap.Solids()) == 1
    assert cap.Volume() == pytest.approx(source.Volume(), rel=1e-9)


import functools  # noqa: E402


@functools.lru_cache(maxsize=1)
def _fit_report():
    validator = _load("validate_hn11_replacement", STUDY / "validate_hn11_replacement.py")
    return validator.validate(sweep_step_deg=90)


def test_hn11_replacement_clears_target_joint_sweep():
    report = _fit_report()
    assert len(report["instances"]) == 2
    for entry in report["instances"]:
        assert entry["new_interference"] == []
        assert entry["link_sweep_max_mm3"] == 0.0
        assert entry["negative_control_detected"] is True
        assert entry["face_alignment_ok"] is True
        residual = entry["register_residual_deg"]
        assert residual is not None and min(residual, 90.0 - residual) < 2.0
        # the source onset overlap must be reported, not hidden
        assert "source_rotor_intersections" in entry
        assert entry["idler_mount_status"] in (
            "idler_side_screw_pattern", "no_idler_side_screw_pattern")


def test_hn11_replacement_detects_axial_shift_negative():
    report = _fit_report()
    assert all(entry["negative_control_detected"] for entry in report["instances"])


def test_hn11_replacement_r3_six_instances():
    r3_path = os.environ.get("HN11_R3_ASSEMBLY")
    if not r3_path:
        pytest.skip("set HN11_R3_ASSEMBLY to the R3 arm STEP to run this check")
    validator = _load("validate_hn11_replacement_r3",
                      STUDY / "validate_hn11_replacement.py")
    report = validator.validate(Path(r3_path), sweep_step_deg=90,
                                reference_assembly=validator.DEFAULT_ASSEMBLY)
    assert len(report["instances"]) == 6
    for entry in report["instances"]:
        assert entry["new_interference"] == []
        assert entry["link_sweep_max_mm3"] == 0.0
        assert entry["negative_control_detected"] is True
        assert entry["face_alignment_ok"] is True
        assert entry["idler_mount_status"] in (
            "idler_side_screw_pattern", "no_idler_side_screw_pattern")
        if entry["idler_mount_status"] == "idler_side_screw_pattern":
            assert entry["screw_analysis"] is not None
    # 6 printed sets are a quantity requirement; joint-fit verification is only
    # claimed for the instances with an idler-side screw pattern.
    assert report["status"] in ("pass", "incomplete")


def _validator_module():
    return _load("validate_hn11_replacement_synthetic",
                 STUDY / "validate_hn11_replacement.py")


def _disk(radius=10.25, thickness=3.5, pcd=16.0, hole_d=2.5, count=4, angle0=0.0):
    import cadquery as cq
    import math

    shape = cq.Workplane("XY").circle(radius).extrude(thickness).val()
    for k in range(count):
        ang = math.radians(angle0 + k * 90.0)
        x, y = pcd / 2.0 * math.cos(ang), pcd / 2.0 * math.sin(ang)
        shape = shape.cut(cq.Solid.makeCylinder(
            hole_d / 2.0, thickness + 2.0, cq.Vector(x, y, -1.0), cq.Vector(0, 0, 1)))
    return shape.clean()


def test_hn11_rotation_zero_is_identity_and_axis_point_invariant():
    import cadquery as cq

    validator = _validator_module()
    disk = _disk()
    pt = cq.Vector(0, 0, 1.75)
    axis = cq.Vector(0, 0, 1)
    moved = validator._rotate_in_place(disk, pt, axis, 0.0)
    assert moved.BoundingBox().zmin == pytest.approx(disk.BoundingBox().zmin, abs=1e-6)
    assert moved.BoundingBox().xlen == pytest.approx(disk.BoundingBox().xlen, abs=1e-6)
    invariant = validator._xform_point(
        cq.Location(cq.Vector(0, 0, 0), axis, 90.0), cq.Vector(0, 0, 5.0))
    assert invariant.x == pytest.approx(0.0, abs=1e-9)
    assert invariant.z == pytest.approx(5.0, abs=1e-9)


def test_hn11_rotation_detects_known_interference():
    import cadquery as cq

    validator = _validator_module()
    disk = cq.Workplane("XY").circle(10.25).extrude(3.5).val()
    tab = cq.Workplane("XY").box(3, 3, 3.5).translate((11.5, 0, 1.75)).val()
    part = disk.fuse(tab).clean()
    # obstacle sits outside the disk radius, inside the tab only
    obstacle = cq.Workplane("XY").box(1.5, 3, 3.5).translate((11.5, 0, 1.75)).val()
    pt = cq.Vector(0, 0, 1.75)
    axis = cq.Vector(0, 0, 1)
    at_zero = validator._rotate_in_place(part, pt, axis, 0.0)
    assert at_zero.intersect(obstacle).Volume() > 5.0
    at_ninety = validator._rotate_in_place(part, pt, axis, 90.0)
    assert at_ninety.intersect(obstacle).Volume() < 1e-6


def test_hn11_coaxial_feature_counts_four_holes():
    import cadquery as cq

    validator = _validator_module()
    plate = _disk()
    features = validator._coaxial_features(
        plate, cq.Vector(0, 0, 1.75), cq.Vector(0, 0, 1),
        rmin=1.2, rmax=1.3, radial_max=9.0)
    assert len(features) == 1
    assert features[0]["count"] == 4
    assert len(features[0]["angles_deg"]) == 4
    three = _disk(count=3)
    features3 = validator._coaxial_features(
        three, cq.Vector(0, 0, 1.75), cq.Vector(0, 0, 1),
        rmin=1.2, rmax=1.3, radial_max=9.0)
    assert features3[0]["count"] == 3


def test_hn11_register_detects_45_degree_hole_error():
    import cadquery as cq

    validator = _validator_module()
    ours = _disk(hole_d=2.5, angle0=0.0)
    target_ok = _disk(hole_d=4.5, angle0=0.0)
    target_rot = _disk(hole_d=4.5, angle0=45.0)
    pt = cq.Vector(0, 0, 1.75)
    axis = cq.Vector(0, 0, 1)

    def residual(target):
        seat = validator._seat_angle(ours, pt, axis)
        counter = validator._family_angle(target, pt, axis, 4.5)
        return (seat - counter) % 90.0

    assert min(residual(target_ok), 90.0 - residual(target_ok)) < 2.0
    assert residual(target_rot) == pytest.approx(45.0, abs=2.0)


def test_hn11_signed_axis_faces_the_counterbore_side():
    import cadquery as cq
    import math

    validator = _validator_module()
    thickness = 3.5
    disk = cq.Workplane("XY").circle(10.25).extrude(thickness).val()
    for k in range(4):
        ang = math.radians(k * 90.0)
        x, y = 8.0 * math.cos(ang), 8.0 * math.sin(ang)
        counterbore = cq.Solid.makeCylinder(
            2.25, 2.0, cq.Vector(x, y, thickness - 2.0), cq.Vector(0, 0, 1))
        hole = cq.Solid.makeCylinder(
            1.0, thickness + 2.0, cq.Vector(x, y, -1.0), cq.Vector(0, 0, 1))
        disk = disk.cut(counterbore).cut(hole)
    disk = disk.clean()
    pt = cq.Vector(0, 0, thickness / 2.0)
    for direction in (cq.Vector(0, 0, 1), cq.Vector(0, 0, -1)):
        signed = validator._signed_axis(disk, pt, direction)
        assert signed.z > 0.9, "axis must point from the outer face toward the counterbores"

