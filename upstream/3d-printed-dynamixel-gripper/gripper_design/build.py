from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import cadquery as cq

from camera_jig.build import ARM, collision_rows, common_volume, envelope_hardware
from camera_jig.build import build_parts as build_camera_parts
from gripper_design.parallel_jaw import (
    ParallelJawParameters,
    build_parallel_jaw,
    jaw_state,
)
from scripts.assembly_io import Occurrence
from scripts.step_cache import read_rows

ROOT = Path(__file__).resolve().parents[1]
REPLACED_SOURCE_UNITS = ("P06_fixed_gripper_XL430", "P07_moving_gripper_XL430")
J6_OUTPUT_FRAME = cq.Location(cq.Vector(18.8, 234.9, 164.6), cq.Vector(1, 1, 1), 120)


@dataclass(frozen=True)
class TerminalPose:
    theta_rad: float
    opening_mm: float
    interface_pitch_circle_diameter_mm: float
    source_occurrence_count: int
    occurrence_coverage: dict[str, int]
    retained_source_units: tuple[str, ...]
    replaced_source_units: tuple[str, ...]
    jaw_shapes: dict[str, cq.Shape]
    camera_shapes: dict[str, cq.Shape]
    mass_kg: None
    volume_centroid_mm: tuple[float, float, float]
    center_of_mass_status: str
    fastener_status: str
    tool_status: str
    output_contact_distance_mm: float
    output_contact_area_probe_mm2: float
    fabrication_approved: bool


@lru_cache(maxsize=1)
def _source_rows() -> tuple[Occurrence, ...]:
    return tuple(read_rows(ARM))


def build_terminal_pose(
    *,
    theta_rad: float,
    parameters: ParallelJawParameters | None = None,
) -> TerminalPose:
    parameters = parameters or ParallelJawParameters()
    state = jaw_state(parameters, theta_rad)
    local_jaw = build_parallel_jaw(parameters, theta_rad=theta_rad)
    jaw_shapes = {name: shape.moved(J6_OUTPUT_FRAME) for name, shape in local_jaw.items()}
    camera_shapes = build_camera_parts()
    rows = _source_rows()
    coverage = {"solid": 0, "shell": 0, "wire": 0, "empty": 0}
    for row in rows:
        coverage[_shape_kind(row.world)] += 1
    retained_units = sorted({_unit_name(row.name) for row in rows} - set(REPLACED_SOURCE_UNITS))
    centroid = _volume_centroid([*jaw_shapes.values(), *camera_shapes.values()])
    output_motor = next(row.world for row in rows if row.name == "M06_ref00")
    output_contact_distance = jaw_shapes["base"].distance(output_motor)
    probe_mm = 0.01
    output_contact_area = (
        common_volume(jaw_shapes["base"].translate((-probe_mm, 0, 0)), output_motor) / probe_mm
    )
    return TerminalPose(
        theta_rad=theta_rad,
        opening_mm=state.measured_opening_mm,
        interface_pitch_circle_diameter_mm=parameters.output_pitch_circle_diameter_mm,
        source_occurrence_count=len(rows),
        occurrence_coverage=coverage,
        retained_source_units=tuple(retained_units),
        replaced_source_units=REPLACED_SOURCE_UNITS,
        jaw_shapes=jaw_shapes,
        camera_shapes=camera_shapes,
        mass_kg=None,
        volume_centroid_mm=centroid,
        center_of_mass_status="volume_centroid_only_density_unknown",
        fastener_status="candidate_unpurchased",
        tool_status="nominal_envelope_only",
        output_contact_distance_mm=output_contact_distance,
        output_contact_area_probe_mm2=output_contact_area,
        fabrication_approved=False,
    )


def terminal_pose_set(
    parameters: ParallelJawParameters | None = None,
) -> dict[str, TerminalPose]:
    parameters = parameters or ParallelJawParameters()
    return {
        "minimum": build_terminal_pose(theta_rad=parameters.theta_min_rad, parameters=parameters),
        "center": build_terminal_pose(theta_rad=0.0, parameters=parameters),
        "maximum": build_terminal_pose(theta_rad=parameters.theta_max_rad, parameters=parameters),
    }


def export_terminal_set(out: Path) -> dict[str, Any]:
    out.mkdir(parents=True, exist_ok=False)
    rows = _source_rows()
    retained = [row for row in rows if row.name not in REPLACED_SOURCE_UNITS]
    reports = {}
    for pose_name, pose in terminal_pose_set().items():
        assembly = cq.Assembly(name=f"ALL_XL430_TERMINAL_{pose_name.upper()}_UNVALIDATED")
        for row in retained:
            assembly.add(row.world, name=f"source_{row.index}_{row.name}", color=row.color)
        for name, shape in pose.camera_shapes.items():
            assembly.add(shape, name=f"CAMERA_{name}", color=cq.Color(0.13, 0.62, 0.7))
        for name, shape in pose.jaw_shapes.items():
            assembly.add(shape, name=f"PARALLEL_JAW_{name}", color=cq.Color(0.82, 0.47, 0.12))
        for name, shape in envelope_hardware().items():
            assembly.add(shape, name=f"CAMERA_FASTENER_{name}", color=cq.Color(0.5, 0.51, 0.53))
        output_step = out / f"terminal_{pose_name}_UNVALIDATED.step"
        assembly.save(str(output_step))

        source_obstacles = {f"{row.index}:{row.path}": row.world for row in retained}
        candidates = {**pose.camera_shapes, **pose.jaw_shapes}
        non_solid_evidence = []
        source_hits, source_errors = collision_rows(
            candidates,
            source_obstacles,
            non_solid_evidence=non_solid_evidence,
        )
        candidate_hits = []
        candidate_errors = []
        for first, second in itertools.combinations(candidates, 2):
            hits, errors = collision_rows({first: candidates[first]}, {second: candidates[second]})
            candidate_hits.extend(hits)
            candidate_errors.extend(errors)
        reports[pose_name] = {
            "theta_rad": pose.theta_rad,
            "opening_mm": pose.opening_mm,
            "interface_pitch_circle_diameter_mm": pose.interface_pitch_circle_diameter_mm,
            "contains_rejected_pcd12_interface": False,
            "source_occurrence_count": pose.source_occurrence_count,
            "occurrence_coverage": pose.occurrence_coverage,
            "replaced_source_units": list(pose.replaced_source_units),
            "retained_source_units": list(pose.retained_source_units),
            "source_collisions": source_hits,
            "source_boolean_errors": source_errors,
            "candidate_collisions": candidate_hits,
            "candidate_boolean_errors": candidate_errors,
            "output_contact": {
                "distance_mm": pose.output_contact_distance_mm,
                "probe_area_mm2": pose.output_contact_area_probe_mm2,
                "status": "geometric_contact_candidate_not_fastener_proof",
            },
            "non_solid_static_separation_evidence_count": len(non_solid_evidence),
            "mass_kg": pose.mass_kg,
            "volume_centroid_mm": pose.volume_centroid_mm,
            "center_of_mass_status": pose.center_of_mass_status,
            "fastener_status": pose.fastener_status,
            "tool_status": pose.tool_status,
            "assembly_sequence_status": "camera_sequence_checked_jaw_sequence_not_checked",
            "cable_status": "reserved_anchors_route_unknown",
            "physical_mapping_status": "unconfirmed",
            "local_geometry_status": "diagnostic_only",
            "full_arm_operation_status": "not_approved",
            "fabrication_approved": False,
            "powered_operation_approved": False,
            "output_step": output_step.name,
            "output_step_sha256": _sha(output_step),
        }
    report = {
        "schema_version": 1,
        "scope": "all-XL430 R3 terminal diagnostic; P06/P07 replaced; not fabrication approval",
        "input_arm": str(ARM.relative_to(ROOT)),
        "input_arm_sha256": _sha(ARM),
        "poses": reports,
        "fabrication_approved": False,
        "powered_operation_approved": False,
    }
    report_path = out / "validation.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    return report


def _shape_kind(shape: cq.Shape) -> str:
    if shape.Solids():
        return "solid"
    if shape.Shells():
        return "shell"
    if shape.Wires():
        return "wire"
    return "empty"


def _unit_name(name: str) -> str:
    if "_ref" in name and name.startswith("M"):
        return name.split("_ref", 1)[0]
    return name


def _volume_centroid(shapes: list[cq.Shape]) -> tuple[float, float, float]:
    weighted = cq.Vector(0, 0, 0)
    total = 0.0
    for shape in shapes:
        volume = float(shape.Volume())
        weighted += shape.Center() * volume
        total += volume
    if total <= 0:
        raise ValueError("terminal candidate has no positive-volume geometry")
    center = weighted / total
    return center.toTuple()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = export_terminal_set(args.out)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
