"""Actual trimmed geometry, not axis labels alone, defines a mounting interface."""
import hashlib
import json
from pathlib import Path
import sys

import cadquery as cq
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "studies/xl430_lowcost"))
import mount_interfaces as mounts


def plate(radius=8., diameter=2., z=-3.):
    part = cq.Workplane("XY").circle(12).extrude(3).val().translate((0, 0, z))
    for x, y in [(radius, 0), (0, radius), (-radius, 0), (0, -radius)]:
        part = part.cut(cq.Solid.makeCylinder(diameter / 2, 5, cq.Vector(x, y, z - 1)))
    return part


def compare(motor=None, link=None, **kwargs):
    return mounts.inspect_interface(
        motor if motor is not None else plate(),
        link if link is not None else plate(diameter=2.4, z=0),
        motor_z=0., link_z=0., side=1, motor_diameter=2., link_diameter=2.4,
        radial_window=(5., 9.), **kwargs)


def test_concave_bores_only_full_precision_and_trimmed_span():
    shape = plate().translate((.000123456789, 0, 0))
    holes = mounts.extract_bores(shape, seat_z=0., diameter=2., radial_window=(5., 9.))
    assert len(holes) == 4
    assert max(h["xy_mm"][0] for h in holes) == pytest.approx(8.000123456789, abs=1e-10, rel=0)
    assert all(h["z_range_mm"] == pytest.approx([-3., 0.]) for h in holes)
    assert mounts.extract_bores(shape, seat_z=0., diameter=24., radial_window=(0., 1.)) == []


def test_matching_interfaces_pass_geometry_only():
    result = compare()
    assert result["geometry_status"] == "pass"
    assert result["pattern"]["max_offset_mm"] < 1e-9
    assert result["contact_area_mm2"] > 400
    assert not result["engineering_approved"]
    assert result["thread_engagement_status"] == "unknown"


def test_same_axes_but_separated_seats_fail():
    result = mounts.inspect_interface(plate(), plate(diameter=2.4, z=1.),
        motor_z=0., link_z=1., side=1, motor_diameter=2., link_diameter=2.4,
        radial_window=(5., 9.))
    assert result["pattern"]["max_offset_mm"] < 1e-9
    assert result["seat_offset_mm"] == pytest.approx(1.)
    assert result["contact_area_mm2"] == 0
    assert result["geometry_status"] == "fail"


def test_r6_pattern_cannot_match_r8_despite_center_axis_coincidence():
    result = compare(link=plate(radius=6., diameter=2.4, z=0.))
    assert result["pattern"]["max_offset_mm"] == pytest.approx(2.)
    assert result["geometry_status"] == "fail"


def test_one_link_hole_cannot_serve_four_expected_holes():
    a = [{"xy_mm": [float(x), 0.]} for x in range(4)]
    b = [{"xy_mm": [0., 0.]} for _ in range(4)]
    with pytest.raises(ValueError, match="duplicate"):
        mounts.match_pattern(a, b)


def test_pattern_assignment_is_one_to_one_not_independent_nearest_neighbor():
    a = [{"xy_mm": [x, 0.]} for x in (0., 1., 2., 3.)]
    b = [{"xy_mm": [x, 0.]} for x in (0., 10., 11., 12.)]
    result = mounts.match_pattern(a, b)
    assert len({p["link_index"] for p in result["pairs"]}) == 4
    assert result["max_offset_mm"] >= 9.


def test_missing_plane_is_unknown_not_zero_area_success():
    result = mounts.inspect_interface(plate(), plate(diameter=2.4, z=0.),
        motor_z=.1, link_z=.1, side=1, motor_diameter=2., link_diameter=2.4,
        radial_window=(5., 9.))
    assert result["geometry_status"] == "unknown"


def test_coincident_nonopposing_faces_fail():
    result = compare(link=plate(diameter=2.4))
    assert result["geometry_status"] == "fail"
    assert not result["opposing_normals"]


def test_absent_bores_cannot_vacuously_pass():
    result = compare(link=cq.Workplane("XY").circle(12).extrude(3).val())
    assert result["geometry_status"] == "unknown"


def test_rejects_non_solid_input():
    with pytest.raises(ValueError, match="solid"):
        compare(link=plate().Faces()[0])


def test_source_sha_mismatch_fails_before_parsing_cad(tmp_path):
    (tmp_path / "CAD").mkdir()
    (tmp_path / "reports").mkdir()
    data = b"changed CAD, intentionally not a STEP file"
    (tmp_path / "CAD/arm_all_XL430_static_UNACCEPTED.step").write_bytes(data)
    report = {"candidate_sha256": {
        "CAD/arm_all_XL430_static_UNACCEPTED.step": hashlib.sha256(b"old CAD").hexdigest()}}
    (tmp_path / "reports/validation.json").write_text(json.dumps(report))
    with pytest.raises(ValueError, match="source CAD"):
        mounts.inspect_run(tmp_path)
