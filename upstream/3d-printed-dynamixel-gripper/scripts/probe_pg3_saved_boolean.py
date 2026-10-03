"""Diagnose saved crank Boolean failures without healing or accepting the part."""

import argparse
import importlib.metadata
import json
from pathlib import Path

import cadquery as cq
from OCP.BOPAlgo import BOPAlgo_ArgumentAnalyzer
from OCP.BRepClass3d import BRepClass3d_SolidClassifier

from gripper_design.pg2 import digest
from gripper_design.pg3 import PG3Model, to_arm
from scripts.assembly_io import read_step
from scripts.review_pg3_local_contacts import reexpress


def analyze_argument(shape):
    analyzer = BOPAlgo_ArgumentAnalyzer()
    analyzer.SetShape1(shape.wrapped)
    analyzer.SelfInterMode = True
    analyzer.SmallEdgeMode = True
    analyzer.RebuildFaceMode = True
    analyzer.CurveOnSurfaceMode = True
    analyzer.Perform()
    orientations = []
    for solid in shape.Solids():
        classifier = BRepClass3d_SolidClassifier(solid.wrapped)
        classifier.PerformInfinitePoint(1e-7)
        orientations.append(
            {"orientation": str(solid.wrapped.Orientation()), "infinite": str(classifier.State())}
        )
    # Return measurements, not PASS: fault-free inputs can still fail Booleans.
    return {
        "topology_valid": shape.isValid(),
        "argument_analyzer_has_errors": analyzer.HasErrors(),
        "argument_faults": [
            {"status": str(r.GetCheckStatus()), "faulty_shapes": len(list(r.GetFaultyShapes1()))}
            for r in analyzer.GetCheckResult()
        ],
        "orientations": orientations,
        "volume_mm3": shape.Volume(),
        "self_cut_mm3": sum(abs(s.Volume()) for s in shape.cut(shape.copy()).Solids()),
        "self_common_mm3": sum(abs(s.Volume()) for s in shape.intersect(shape.copy()).Solids()),
        "installation_approved": False,
    }


def run(checkpoint, out):
    if out.exists():
        raise FileExistsError(out)
    manifest_path = checkpoint / "review.json"
    manifest = json.loads(manifest_path.read_text())
    model = PG3Model()
    box = cq.Solid.makeBox(4, 4, 4)
    report = {
        "scope": "crank_input_validity_and_independent_copy_identity_only_not_collision_clearance",
        "checker_sha256": digest(Path(__file__)),
        "dependencies": {
            p: digest(Path(p))
            for p in (
                "scripts/assembly_io.py",
                "scripts/review_pg3_local_contacts.py",
                "gripper_design/pg2.py",
                "gripper_design/pg3.py",
            )
        },
        "versions": {p: importlib.metadata.version(p) for p in ("cadquery", "cadquery-ocp")},
        "manifest_sha256": digest(manifest_path),
        "enabled_argument_checks": ["SelfInter", "SmallEdge", "RebuildFace", "CurveOnSurface"],
        "infinite_point_tolerance_mm": 1e-7,
        "geometry_healed": False,
        "boolean_tolerances_changed": False,
        "controls": {
            "box": analyze_argument(box),
            "overlapping_solids": analyze_argument(
                cq.Compound.makeCompound([box, box.translate((2, 0, 0))])
            ),
        },
        "source_neutral": analyze_argument(model.neutral["crank"]),
        "poses": {},
        "installation_approved": False,
    }
    for label, angle in (("open", 25), ("mid", 90), ("closed", 135)):
        path = checkpoint / f"arm_camera_{label}_CANDIDATE.step"
        if digest(path) != manifest["output_sha256"][path.name]:
            raise ValueError(f"checkpoint hash mismatch: {path}")
        matches = [r.world for r in read_step(path)[2] if r.name == "PG3_crank"]
        if len(matches) != 1:
            raise ValueError("exactly one PG3_crank occurrence required")
        shape = matches[0]
        row = {
            "assembly_sha256": digest(path),
            "relative_mechanism_angle_deg": angle,
            "memory_world": analyze_argument(to_arm(model.at(angle)["crank"])),
            "saved_world": analyze_argument(shape),
            "saved_local": analyze_argument(reexpress(shape, angle)),
        }
        report["poses"][label] = row
        print(label, json.dumps(row), flush=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x") as stream:
        stream.write(json.dumps(report, indent=2) + "\n")
    return 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(run(args.checkpoint, args.out))
