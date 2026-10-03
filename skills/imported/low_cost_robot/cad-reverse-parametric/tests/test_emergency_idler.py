"""Regression checks for the temporary XL430 center-bolt idler."""
from __future__ import annotations

import importlib.util
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pytest

from cadre import PartIntent


ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "studies" / "xl430_lowcost"
PARTS = STUDY / "parts"
ASSEMBLY_IO = ROOT / "studies" / "follower_geometry_revision" / "source"
for path in (STUDY, PARTS, ASSEMBLY_IO):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_emergency_idler_is_single_valid_solid():
    model = _load("emergency_center_bolt_idler", PARTS / "emergency_center_bolt_idler.py")
    shape = model.make_emergency_idler().val()
    assert shape.isValid()
    assert len(shape.Solids()) == 1
    assert shape.Volume() > 1200.0


def test_emergency_idler_clears_source_pose_and_sampled_local_rotation():
    validator = _load("validate_emergency_idler", STUDY / "validate_emergency_idler.py")
    report, context = validator.validate(sweep_step_deg=5)
    assert report["status"] == "pass", report
    assert report["interference"]["max_sweep_intersection_mm3"] == 0.0
    assert report["interference"]["adapter_vs_retained_motor"] == []
    assert report["dimensions"]["radial_clearance_mm"] == pytest.approx(0.25)
    assert report["dimensions"]["axial_clearance_mm"] == pytest.approx(0.25)
    assert report["checks"]["reference_bolt_clearance"]
    assert report["checks"]["new_parts_vs_whole_source_static"]
    assert report["boltability"]["reference_bolt_in_smooth_bore_mm"] == pytest.approx(3.55)
    assert report["boltability"]["reference_bolt_bottom_clearance_mm"] == pytest.approx(0.95)
    assert report["boltability"]["thread_engagement_verified"] is False

    full_arm = validator.build_full_arm(context)
    removed = []
    for row in context["rows"]:
        name = f"source_{row.index:03d}_{row.name}"
        if row.path.startswith(validator.MOTOR_PREFIX) and any(
            token in row.path for token in validator.REPLACED_TOKENS
        ):
            assert name not in full_arm.objects
            removed.append(row)
        else:
            # The original B-rep, orientation and assembly placement must survive.
            assert full_arm.objects[name].obj.wrapped.IsEqual(row.world.wrapped)
    assert len(removed) == 4
    assert len(full_arm.children) == len(context["rows"]) - len(removed) + 3
    for name, key in (("emergency_printed_idler", "adapter"),
                      ("reference_wide_washer", "washer"),
                      ("reference_M3x12_bolt_envelope", "bolt")):
        assert full_arm.objects[name].obj.wrapped.IsEqual(context[key].wrapped)


@pytest.mark.parametrize("feature,key,value,failed_check", [
    ("rotating_pilot", "extension_from_flange_mm", 3.0, "axial_clearance"),
    ("rotating_pilot", "diameter_mm", 9.9, "radial_clearance"),
    ("motor_hook_relief", "center_xyz_mm", [0.3, 0, 20], "motor_intersection"),
    ("center_fastener", "reference_bolt_length_mm", 14.0, "reference_bolt_bottom_clearance"),
    ("center_fastener", "reference_bolt_length_mm", 8.0, "reference_bolt_bore_overlap"),
])
def test_rejects_binding_and_bottoming_variants(feature, key, value, failed_check):
    validator = _load("validate_emergency_idler_negative", STUDY / "validate_emergency_idler.py")
    intent = PartIntent.load(PARTS.parent / "intent/emergency_center_bolt_idler.yaml")
    spec = next(item.constraints for item in intent.features if item.name == feature)
    spec[key] = value
    report, _ = validator.validate(sweep_step_deg=90, intent=intent)
    assert report["status"] == "fail"
    assert report["checks"][failed_check] is False


def test_emergency_idler_pla_properties_and_urdf_are_physical():
    model = _load("emergency_center_bolt_idler_physics", PARTS / "emergency_center_bolt_idler.py")
    properties = model.physical_properties()
    assert properties["material"] == "PLA"
    assert 0.0015 < properties["mass_kg"] < 0.0017
    inertia = properties["inertia_about_com_kg_m2"]
    matrix = np.array([
        [inertia["ixx"], inertia["ixy"], inertia["ixz"]],
        [inertia["ixy"], inertia["iyy"], inertia["iyz"]],
        [inertia["ixz"], inertia["iyz"], inertia["izz"]],
    ])
    assert np.all(np.linalg.eigvalsh(matrix) > 0.0)
    urdf = model.render_urdf(properties, "emergency_center_bolt_idler_xl430.stl")
    root = ET.fromstring(urdf)
    assert root.tag == "robot"
    mesh = root.find("./link/visual/geometry/mesh")
    assert mesh is not None
    assert mesh.attrib["scale"] == "0.001 0.001 0.001"
