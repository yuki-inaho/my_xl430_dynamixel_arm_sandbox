"""Compare intrinsic bolt-circle geometry, NOT assembly placement or threads."""

import argparse
import hashlib
import json
from pathlib import Path

import cadquery as cq
import numpy as np
from cadre.probes import cylinder_surface_sense
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Cylinder

from scripts.assembly_io import bounds, read_step


def bores(shape, radius, axis, center, front_only=False):
    records = []
    for idx, face in enumerate(shape.Faces()):
        surface = BRepAdaptor_Surface(face.wrapped)
        if surface.GetType() != GeomAbs_Cylinder:
            continue
        cyl = surface.Cylinder()
        direction = np.array(cyl.Axis().Direction().Coord())
        if abs(abs(direction @ axis) - 1) > 1e-6 or abs(cyl.Radius() - radius) > 1e-6:
            continue
        if cylinder_surface_sense(face) != "concave":
            continue
        point = np.array(cyl.Location().Coord())
        offset = point - center
        radial = offset - (offset @ axis) * axis
        # Restrict R3 to the output-side circular interface, not case/PCB bores.
        if front_only and (bounds(face)[1] <= center[1] or np.linalg.norm(radial) > 10.5):
            continue
        if any(np.linalg.norm(radial - r["radial_vector_mm"]) < 1e-6 for r in records):
            continue
        records.append(
            {
                "face_index": idx,
                "radial_vector_mm": radial.tolist(),
                "radius_from_axis_mm": float(np.linalg.norm(radial)),
                "face_bounds_mm": bounds(face),
                "bore_radius_mm": radius,
            }
        )
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--delivery", type=Path, required=True)
    parser.add_argument("--r3", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    artifact = (
        args.delivery
        / "skills/cad-reverse-parametric/outputs/gripper_camera_lateral/unaccepted/20260922-r1"
    )
    bridge_path = artifact / "CAD/parts/wrist_camera_bridge.step"
    bridge = cq.importers.importStep(str(bridge_path)).val()
    step = args.r3 / "arm_XL430_R3.step"
    _, _, rows = read_step(step)
    motor = next(r for r in rows if r.name == "M05_ref00")
    joint = next(r for r in json.loads((args.r3 / "joints.json").read_text()) if r["name"] == "J5")
    center, axis = np.array(joint["centre_mm"]), np.array(joint["axis"])
    old_center = np.array([0.750000268220905, -19.999999791407, 14.75])
    old = bores(bridge, 1.15, np.array([0, 1, 0]), old_center)
    new = bores(motor.world, 1.0, axis, center, front_only=True)
    assert len(old) == len(new) == 4, (len(old), len(new))
    record = {
        "scope": "Intrinsic pattern-size comparison, not mounted coaxiality or a thread claim",
        "source_hashes": {
            str(p): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [bridge_path, step, args.r3 / "joints.json"]
        },
        "r3_source_occurrence": motor.path,
        "r3_source_name": "DC11_A01_DUMMY:1 (manifest M05_ref00); output side, not ref07 idler",
        "donor_bridge_bores": old,
        "r3_output_side_bores": new,
        "donor_pitch_circle_diameter_mm": 2 * np.mean([r["radius_from_axis_mm"] for r in old]),
        "r3_pitch_circle_diameter_mm": 2 * np.mean([r["radius_from_axis_mm"] for r in new]),
        "best_possible_coaxial_radial_mismatch_mm": min(r["radius_from_axis_mm"] for r in new)
        - max(r["radius_from_axis_mm"] for r in old),
        "assembly_compatible": False,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x") as stream:
        json.dump(record, stream, indent=2)
    print(
        json.dumps(
            {
                k: v
                for k, v in record.items()
                if k not in ("source_hashes", "donor_bridge_bores", "r3_output_side_bores")
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
