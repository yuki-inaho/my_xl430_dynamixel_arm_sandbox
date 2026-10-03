"""Tests for the generic cadre core. Run: uv run pytest -q"""
import tempfile
from pathlib import Path

import pytest

from cadre import (Envelope, classify_screw, compare, verdict,
                   EquivalenceThresholds, parametric, PartIntent, Feature,
                   feature_descriptor, checks)
from cadre.probes import group_cylinder_holes


# ---- geometry (pure, no kernel) ----

def test_envelope_fit_and_ratio():
    small, big = Envelope(20, 34, 26), Envelope(28.5, 46.5, 34)
    # small fits inside a generous bbox, big does not
    assert small.fits_inside((30, 50, 40)).fits
    assert not big.fits_inside((25, 40, 30)).fits
    r = small.ratio_to(big)
    assert r["w_ratio"] == pytest.approx(1.425, abs=1e-3)
    assert r["dh_mm"] == pytest.approx(12.5, abs=1e-3)


@pytest.mark.parametrize("dia,expected", [
    (2.0, "M2-tap"), (2.4, "M2"), (2.8, "M2.5"), (3.4, "M3"), (9.9, None)])
def test_screw_classification(dia, expected):
    assert classify_screw(dia) == expected


# ---- equivalence gate (the heart of the equivalent-first workflow) ----

def _emit(env: Envelope, d: Path, name: str) -> Path:
    parametric.export(parametric.envelope_proxy(env), d / name, formats=("stl",))
    return d / f"{name}.stl"


def test_hole_grouping_dedupes_throughhole_faces_and_normalizes_sign():
    # A through-hole crosses two walls -> 2 collinear faces, identical axis pt,
    # but reported with opposite sign directions. Must collapse to 1 hole.
    cyls = [
        {"radius": 1.15, "axis_dir": [1.0, 0.0, 0.0], "axis_pt": [0.0, 5.0, 0.0]},
        {"radius": 1.15, "axis_dir": [-1.0, 0.0, 0.0], "axis_pt": [0.0, 5.0, 0.0]},
        # a genuinely separate hole on the same family (parallel axis):
        {"radius": 1.15, "axis_dir": [1.0, 0.0, 0.0], "axis_pt": [0.0, -5.0, 0.0]},
    ]
    fams = group_cylinder_holes(cyls)
    assert len(fams) == 1                      # one (radius, dir) family
    fam = fams[0]
    assert fam["axes"] == 2                    # two distinct axis lines
    assert fam["faces"] == 3                   # three raw cylindrical faces
    assert fam["screw"] == "M2"


# ---- functional checks (characterization / function tests) ----

def test_axes_collinear():
    same = checks.axes_collinear([0, 0, 0], [1, 0, 0], [5, 0, 0], [-1, 0, 0])
    assert same.passed                                  # same line, opposite sign dir
    offset = checks.axes_collinear([0, 0, 0], [1, 0, 0], [0, 2, 0], [1, 0, 0])
    assert not offset.passed                            # parallel but 2mm apart


def test_hole_pattern_match():
    a = [(0, 8, 0), (0, -8, 0), (8, 0, 0), (-8, 0, 0)]
    b = [(0.05, 8, 0), (0, -8.0, 0), (8, 0, 0.1), (-8, 0, 0)]
    assert checks.hole_pattern_match(a, b, tol_mm=0.15).passed
    assert not checks.hole_pattern_match(a, b, tol_mm=0.05).passed


# ---- design-intent layer (the human-readable latent) ----

def test_part_intent_yaml_roundtrip(tmp_path):
    pi = PartIntent(part="p", intent="demo", features=[
        Feature(name="m", type="servo_mount", servo="XL430",
                preserves=["output_axis"], constraints={"wall_mm": 4.0})],
        tests=["axes_collinear"])
    f = tmp_path / "p.yaml"
    pi.dump(f)
    back = PartIntent.load(f)
    assert back.part == "p"
    assert back.servo_mounts()[0].servo == "XL430"
    assert back.servo_mounts()[0].preserves == ["output_axis"]


def test_feature_descriptor_shape():
    brep = {"name": "x", "bbox_mm": [1, 2, 3], "solids": 1,
            "hole_families": [{"radius": 1.2, "diameter": 2.4, "screw": "M2",
                               "axis_dir": [1, 0, 0], "axes": 2, "faces": 4,
                               "centers": [[0, 8, 0], [0, -8, 0]]}]}
    d = feature_descriptor(brep, adjacent_parts=["XL430"], filename_hint="hint")
    assert d["part"] == "x" and d["filename_hint"] == "hint"
    assert len(d["cylindrical_axes"]) == 2
    assert d["cylindrical_axes"][0]["screw"] == "M2"


def test_cylinder_faces_recovers_holes_from_generated_step(tmp_path):
    # Generate a plate with 4 known holes, then recover them via B-rep inspection.
    from cadre import cylinder_faces, brep_available
    if not brep_available():
        import pytest as _pt
        _pt.skip("cadquery/OCP not available")
    centers = [(0, 8), (0, -8), (8, 0), (-8, 0)]
    plate = parametric.adapter_plate(centers, hole_diameter=2.4,
                                     plate_w=30, plate_h=30, thickness=4)
    step = tmp_path / "plate.step"
    parametric.export(plate, tmp_path / "plate", formats=("step",))
    r = cylinder_faces(step)
    assert r["available"] and r["solids"] == 1
    assert r["bbox"]["xlen"] == pytest.approx(30, abs=0.1)
    holes = [c for c in r["cylinders"] if c["screw"] == "M2"]
    assert len(holes) == 4                       # 4 absolute hole faces recovered
    # absolute centers match the design pattern (±8 cross), not collapsed to origin
    xy = sorted((round(c["axis_pt"][0]), round(c["axis_pt"][1])) for c in holes)
    assert xy == [(-8, 0), (0, -8), (0, 8), (8, 0)]


def test_edge_records_and_length_match_classify_step_edges(tmp_path):
    from cadre import brep_available, edge_records, match_edge_lengths
    if not brep_available():
        import pytest as _pt
        _pt.skip("cadquery/OCP not available")
    centers = [(0, 8), (0, -8), (8, 0), (-8, 0)]
    plate = parametric.adapter_plate(centers, hole_diameter=2.4,
                                     plate_w=30, plate_h=30, thickness=4)
    step = tmp_path / "plate.step"
    parametric.export(plate, tmp_path / "plate", formats=("step",))

    r = edge_records(step)
    assert r["available"] and r["edge_count"] >= 16
    circle_edges = [e for e in r["edges"] if e["curve_type"] == "circle"]
    assert circle_edges
    hole_edge = circle_edges[0]
    assert hole_edge["circle"]["radius"] == pytest.approx(1.2, abs=0.01)
    assert any(f["surface_type"] == "cylinder"
               for f in hole_edge.get("adjacent_faces", []))

    m = match_edge_lengths(step, [hole_edge["length"]], tolerance=1e-6, limit=3)
    first = m["queries"][0]["matches"][0]
    assert first["index"] == hole_edge["index"]
    assert first["within_tolerance"] is True


def test_equivalence_gate_distinguishes_same_vs_different():
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        a = _emit(Envelope(28.5, 46.5, 34), d, "a")
        b = _emit(Envelope(28.5, 46.5, 34), d, "b")     # identical
        c = _emit(Envelope(20, 34, 26), d, "c")          # different
        same = compare(a, b, samples=4000)
        diff = compare(a, c, samples=4000)
        assert verdict(same, EquivalenceThresholds())["equivalent"] is True
        assert verdict(diff, EquivalenceThresholds())["equivalent"] is False


def test_equiv_cli_can_fail_on_non_equivalent():
    from cadre.cli import main as cli_main

    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        a = _emit(Envelope(28.5, 46.5, 34), d, "a")
        b = _emit(Envelope(28.5, 46.5, 34), d, "b")
        c = _emit(Envelope(20, 34, 26), d, "c")

        assert cli_main([
            "equiv", str(a), str(b), "--samples", "1000", "--fail-on-non-equivalent"
        ]) == 0
        assert cli_main([
            "equiv", str(a), str(c), "--samples", "1000", "--fail-on-non-equivalent"
        ]) == 2
