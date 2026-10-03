"""Parametric emergency center-bolt idler for the shoulder XL430.

The source arm uses the ROBOTIS HN11-I101 idler on the side opposite the output
horn.  This printable part reproduces only the source CAD's axial support and
link pilot geometry.  It deliberately does not claim to reproduce the HN11-I101
bearing or hook mechanism.

Official HN11-I101 description:
https://www.robotis.us/products/hn11-i101-set

Generate:
    uv run python studies/xl430_lowcost/parts/emergency_center_bolt_idler.py
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import cadquery as cq
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps

from cadre import PartIntent


_HERE = Path(__file__).resolve()
_STUDY = _HERE.parents[1]
INTENT = _STUDY / "intent" / "emergency_center_bolt_idler.yaml"
DEFAULT_OUT = _HERE.parents[3] / "outputs" / "prototypes" / "emergency_center_bolt_idler"


def _features(intent: PartIntent) -> dict[str, dict]:
    return {feature.name: feature.constraints for feature in intent.features}


def make_emergency_idler(intent: PartIntent | None = None) -> cq.Workplane:
    """Build the adapter in its local frame, with the joint axis along +X.

    X=0 is the source XL430 idler mounting plane.  The support flange ends at
    X=3.5, where the link inner face sits.  The pilot extends through the 3 mm
    link wall and stands 0.25 mm proud so a washer clamps the adapter instead of
    clamping the rotating link.
    """
    intent = intent or PartIntent.load(INTENT)
    feature = _features(intent)
    flange = feature["support_flange"]
    pilot = feature["rotating_pilot"]
    fastener = feature["center_fastener"]
    relief = feature["motor_hook_relief"]

    flange_t = float(flange["thickness_mm"])
    pilot_extension = float(pilot["extension_from_flange_mm"])

    body = (
        cq.Workplane("YZ")
        .circle(float(flange["diameter_mm"]) / 2.0)
        .extrude(flange_t)
    )
    pilot_solid = (
        cq.Workplane("YZ")
        .circle(float(pilot["diameter_mm"]) / 2.0)
        .extrude(pilot_extension)
        .translate((flange_t, 0.0, 0.0))
    )
    body = body.union(pilot_solid)

    total_length = flange_t + pilot_extension
    center_bore = (
        cq.Workplane("YZ")
        .circle(float(fastener["clearance_diameter_mm"]) / 2.0)
        .extrude(total_length + 2.0)
        .translate((-1.0, 0.0, 0.0))
    )
    body = body.cut(center_bore)

    sx, sy, sz = (float(value) for value in relief["size_xyz_mm"])
    cx, cy, cz = (float(value) for value in relief["center_xyz_mm"])
    hook_notch = cq.Workplane("XY").box(sx, sy, sz).translate((cx, cy, cz))
    return body.cut(hook_notch)


def make_reference_washer(intent: PartIntent | None = None) -> cq.Workplane:
    """Return the simple washer used by the assembly clearance simulation."""
    intent = intent or PartIntent.load(INTENT)
    washer = _features(intent)["retaining_washer"]
    return (
        cq.Workplane("YZ")
        .circle(float(washer["outer_diameter_mm"]) / 2.0)
        .circle(float(washer["inner_diameter_mm"]) / 2.0)
        .extrude(float(washer["thickness_mm"]))
    )


def make_reference_bolt(intent: PartIntent | None = None) -> cq.Workplane:
    """Return an unthreaded M3x12 envelope for assembly clearance checking.

    The head underside is placed after the adapter and reference washer.  The
    shaft extends toward negative X into the source motor center hole.
    """
    intent = intent or PartIntent.load(INTENT)
    feature = _features(intent)
    flange = feature["support_flange"]
    pilot = feature["rotating_pilot"]
    fastener = feature["center_fastener"]
    washer = feature["retaining_washer"]
    adapter_length = float(flange["thickness_mm"]) + float(
        pilot["extension_from_flange_mm"]
    )
    head_x = adapter_length + float(washer["thickness_mm"])
    bolt_length = float(fastener["reference_bolt_length_mm"])
    shaft = (
        cq.Workplane("YZ")
        .circle(1.5)
        .extrude(bolt_length)
        .translate((head_x - bolt_length, 0.0, 0.0))
    )
    head = (
        cq.Workplane("YZ")
        .circle(float(fastener["reference_head_diameter_mm"]) / 2.0)
        .extrude(float(fastener["reference_head_height_mm"]))
        .translate((head_x, 0.0, 0.0))
    )
    # Visual socket only; the reference bolt has no modeled threads.
    socket = (
        cq.Workplane("YZ")
        .polygon(6, 2.5 / math.cos(math.pi / 6))
        .extrude(1.4)
        .translate((head_x + float(fastener["reference_head_height_mm"]) - 1.3, 0, 0))
    )
    return shaft.union(head).cut(socket)


def physical_properties(intent: PartIntent | None = None) -> dict:
    """Calculate nominal solid-PLA mass properties from the exact B-rep.

    OpenCascade returns volume in mm^3, center of mass in mm, and unit-density
    inertia in mm^5.  The exported values use URDF SI units: kg, m, kg*m^2.
    """
    intent = intent or PartIntent.load(INTENT)
    density_kg_m3 = float(_features(intent)["printed_material"]["density_kg_m3"])
    density_kg_mm3 = density_kg_m3 / 1.0e9
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(make_emergency_idler(intent).val().wrapped, props)
    center = props.CentreOfMass()
    matrix = props.MatrixOfInertia()
    inertia_scale = density_kg_mm3 * 1.0e-6
    inertia = {
        "ixx": float(matrix.Value(1, 1)) * inertia_scale,
        "ixy": float(matrix.Value(1, 2)) * inertia_scale,
        "ixz": float(matrix.Value(1, 3)) * inertia_scale,
        "iyy": float(matrix.Value(2, 2)) * inertia_scale,
        "iyz": float(matrix.Value(2, 3)) * inertia_scale,
        "izz": float(matrix.Value(3, 3)) * inertia_scale,
    }
    volume_mm3 = float(props.Mass())
    return {
        "material": "PLA",
        "density_kg_m3": density_kg_m3,
        "assumption": "solid nominal material; printed density and voids are process-dependent",
        "volume_mm3": volume_mm3,
        "mass_kg": volume_mm3 * density_kg_mm3,
        "center_of_mass_m": {
            "x": float(center.X()) / 1000.0,
            "y": float(center.Y()) / 1000.0,
            "z": float(center.Z()) / 1000.0,
        },
        "inertia_about_com_kg_m2": inertia,
    }


def render_urdf(properties: dict, mesh_filename: str) -> str:
    com = properties["center_of_mass_m"]
    inertia = properties["inertia_about_com_kg_m2"]
    return f'''<?xml version="1.0"?>
<robot name="emergency_center_bolt_idler_xl430">
  <material name="printed_orange">
    <color rgba="0.95 0.35 0.08 1.0"/>
  </material>
  <link name="emergency_center_bolt_idler_xl430">
    <inertial>
      <origin xyz="{com['x']:.12g} {com['y']:.12g} {com['z']:.12g}" rpy="0 0 0"/>
      <mass value="{properties['mass_kg']:.12g}"/>
      <inertia ixx="{inertia['ixx']:.12g}" ixy="{inertia['ixy']:.12g}" ixz="{inertia['ixz']:.12g}"
               iyy="{inertia['iyy']:.12g}" iyz="{inertia['iyz']:.12g}" izz="{inertia['izz']:.12g}"/>
    </inertial>
    <visual>
      <origin xyz="0 0 0" rpy="0 0 0"/>
      <geometry><mesh filename="{mesh_filename}" scale="0.001 0.001 0.001"/></geometry>
      <material name="printed_orange"/>
    </visual>
    <collision>
      <origin xyz="0 0 0" rpy="0 0 0"/>
      <geometry><mesh filename="{mesh_filename}" scale="0.001 0.001 0.001"/></geometry>
    </collision>
  </link>
</robot>
'''


def export(out: Path = DEFAULT_OUT) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    intent = PartIntent.load(INTENT)
    idler = make_emergency_idler(intent)
    washer = make_reference_washer(intent)
    bolt = make_reference_bolt(intent)
    properties = physical_properties(intent)
    paths = {
        "idler_step": out / "emergency_center_bolt_idler_xl430.step",
        "idler_stl": out / "emergency_center_bolt_idler_xl430.stl",
        "reference_washer_step": out / "reference_M3_wide_washer.step",
        "reference_bolt_step": out / "reference_M3x12_bolt_envelope.step",
        "physical_properties": out / "emergency_center_bolt_idler_xl430_physical_properties.json",
        "urdf": out / "emergency_center_bolt_idler_xl430.urdf",
    }
    cq.exporters.export(idler, str(paths["idler_step"]))
    cq.exporters.export(idler, str(paths["idler_stl"]))
    cq.exporters.export(washer, str(paths["reference_washer_step"]))
    cq.exporters.export(bolt, str(paths["reference_bolt_step"]))
    paths["physical_properties"].write_text(json.dumps(properties, indent=2) + "\n")
    paths["urdf"].write_text(render_urdf(properties, paths["idler_stl"].name))
    return {name: str(path.resolve()) for name, path in paths.items()}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    print(json.dumps(export(args.out), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
