"""Regression cases from the STEP/browser review, independent of hole-family counts."""
import json
import os
from pathlib import Path
import subprocess
import sys

import cadquery as cq
import pytest

from cadre import cylinder_faces

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "studies/xl430_lowcost"
sys.path.insert(0, str(STUDY))

import domain
from parts import _partlib, elbow_to_wrist
from measure_section import measure_elbow_seats


@pytest.mark.parametrize("axis", ["X", "Y", "Z"])
@pytest.mark.parametrize("into", [-1, 1])
def test_blind_seat_opens_on_face_and_keeps_floor(axis, into):
    body = cq.Workplane("XY").box(20, 20, 20)
    face = -into * 10.0
    result = _partlib.blind_seat(body, (0, 0, 0), 4, 3, face, axis, into)
    solid = result.val()
    index = "XYZ".index(axis)

    def inside(depth):
        point = [0.0, 0.0, 0.0]
        point[index] = face + into * depth
        return solid.isInside(cq.Vector(*point))

    assert not inside(0.1), "the opening must reach the declared face"
    assert not inside(2.9), "the specified depth must be empty"
    assert inside(3.1), "material must remain behind the blind recess"
    assert body.val().Volume() - solid.Volume() == pytest.approx(12 * 3.141592653589793)


@pytest.mark.parametrize("motor", [domain.XL330, domain.XL430])
def test_elbow_prototype_recess_entry_and_floor(motor):
    solid = elbow_to_wrist.make_elbow_to_wrist(motor).val()
    # Off the four smaller holes: only the large prototype pocket is probed.
    assert not solid.isInside(cq.Vector(11, 41.9, 18.94))
    assert not solid.isInside(cq.Vector(11, 38.1, 18.94))
    assert solid.isInside(cq.Vector(11, 37.9, 18.94))
    # The screw bores continue below the pocket but must not pierce the wall.
    assert not solid.isInside(cq.Vector(5, 36.1, 19))
    assert solid.isInside(cq.Vector(5, 35.9, 19))


def test_probe_distinguishes_outer_cylinder_from_inner_bore(tmp_path):
    ring = cq.Workplane("XY").circle(10).circle(2).extrude(4)
    path = tmp_path / "ring.step"
    cq.exporters.export(ring, str(path))
    report = cylinder_faces(path)
    by_radius = {face["radius"]: face for face in report["cylinders"]}
    assert by_radius[10]["surface_sense"] == "convex"
    assert by_radius[2]["surface_sense"] == "concave"
    assert by_radius[2]["axial_range_mm"] == pytest.approx([0, 4])
    assert [f["diameter"] for f in report["bore_families"]] == [4]
    assert [f["diameter"] for f in report["outer_cylinder_families"]] == [20]


def test_original_elbow_round_top_is_not_a_horn_bore():
    report = cylinder_faces(elbow_to_wrist.REAL_STEP)
    round_tops = [c for c in report["cylinders"] if c["diameter"] == 18.124]
    assert len(round_tops) == 2
    assert all(c["surface_sense"] == "convex" for c in round_tops)
    assert sorted(c["axial_range_mm"] for c in round_tops) == [[6.5, 9.5], [39.0, 42.0]]
    assert all(f["diameter"] != 18.124 for f in report["bore_families"])


@pytest.mark.parametrize("plane", ["XY", "XZ", "YZ"])
@pytest.mark.parametrize("height", [-3., 3.])
def test_native_cylinder_sense_does_not_depend_on_surface_parameterization(plane, height):
    from cadre.probes import _raw_cylinders
    from cadre.geometry import DEFAULT_SCREW_BANDS
    outer = cq.Workplane(plane).circle(12).extrude(height)
    holes = cq.Workplane(plane).pushPoints([(8, 0), (0, 8), (-8, 0), (0, -8)]).circle(1).extrude(height)
    part = outer.cut(holes).val()
    assert part.isValid() and len(part.Solids()) == 1
    cylinders, _, _ = _raw_cylinders([part], DEFAULT_SCREW_BANDS)
    outside = [c for c in cylinders if c["radius"] == 12]
    inside = [c for c in cylinders if c["radius"] == 1]
    assert len(outside) == 1 and len(inside) == 4
    assert all(c["surface_sense"] == "convex" for c in outside)
    assert all(c["surface_sense"] == "concave" for c in inside)


def test_cylinder_sense_rejects_non_cylinder():
    from cadre.probes import cylinder_surface_sense
    with pytest.raises(ValueError, match="cylindrical face"):
        cylinder_surface_sense(cq.Workplane().box(1, 1, 1).val().Faces()[0])


def test_cylinder_sense_reports_unknown_for_unusable_normal(monkeypatch):
    from cadre.probes import cylinder_surface_sense
    face = next(f for f in cq.Workplane().circle(1).extrude(2).val().Faces()
                if f.geomType() == "CYLINDER")
    monkeypatch.setattr(cq.Face, "normalAt", lambda *args: cq.Vector(0, 0, 0))
    assert cylinder_surface_sense(face) == "unknown"


def test_cylinder_sense_propagates_kernel_failure(monkeypatch):
    from cadre.probes import cylinder_surface_sense
    face = next(f for f in cq.Workplane().circle(1).extrude(2).val().Faces()
                if f.geomType() == "CYLINDER")
    def broken(*args):
        raise RuntimeError("normal evaluation fixture failure")
    monkeypatch.setattr(cq.Face, "normalAt", broken)
    with pytest.raises(RuntimeError, match="fixture failure"):
        cylinder_surface_sense(face)


def test_section_measurement_rejects_buried_pocket(tmp_path):
    body = cq.Workplane("XY").box(29, 9, 31, centered=(False, False, False)).translate((0, 33, 0))
    buried = cq.Workplane("XZ").circle(9.062).extrude(4).translate((11, 38, 18.94))
    broken = _partlib.drill(body.cut(buried), [(3, 3.1, 0)], 2.3, "Z")
    path = tmp_path / "buried.step"
    cq.exporters.export(broken, str(path))
    assert not measure_elbow_seats(path)


def test_section_measurement_accepts_open_prototype_pocket(tmp_path):
    path = tmp_path / "open.step"
    cq.exporters.export(elbow_to_wrist.make_elbow_to_wrist(domain.XL330), str(path))
    assert measure_elbow_seats(path)


def test_elbow_cli_runs_cleanly_and_blocks_non_equivalent_swap(tmp_path):
    env = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    result = subprocess.run(
        [sys.executable, str(STUDY / "parts/elbow_to_wrist.py"),
         "--out", str(tmp_path), "--samples", "128"],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=180,
    )
    assert result.returncode == 2, result.stderr
    report = json.loads(result.stdout)
    assert report["status"] == "blocked_non_equivalent"
    assert report["C_A1_gap_to_real"]["equivalent"] is False
    assert report["swap_exported"] is False
    assert not list(tmp_path.glob("*xl430*"))


def test_elbow_explicit_prototype_does_not_claim_acceptance(tmp_path, capsys):
    code = elbow_to_wrist.main([
        "--out", str(tmp_path), "--samples", "128", "--export-prototype",
    ])
    report = json.loads(capsys.readouterr().out)
    assert code == 2
    assert report["status"] == "blocked_non_equivalent"
    assert report["swap_exported"] is True
    assert (tmp_path / "elbow_to_wrist_xl430_prototype.step").exists()
    assert not (tmp_path / "elbow_to_wrist_xl430.step").exists()


def test_elbow_missing_reference_does_not_export_swap(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(elbow_to_wrist, "REAL_STEP", tmp_path / "missing.step")
    code = elbow_to_wrist.main(["--out", str(tmp_path / "out"), "--samples", "128"])
    report = json.loads(capsys.readouterr().out)
    assert code == 2
    assert report["status"] == "blocked_missing_reference"
    assert report["swap_exported"] is False
