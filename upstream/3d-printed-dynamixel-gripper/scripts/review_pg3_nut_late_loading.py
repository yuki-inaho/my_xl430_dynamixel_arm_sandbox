"""Challenge loading PG3 nuts after their hosts have entered the installed arm."""

import argparse
import json
from pathlib import Path

from gripper_design.pg2 import digest
from scripts.assembly_io import read_step
from scripts.review_pg3_nut_loading import preload_stages, review_loaded_nut
from scripts.review_pg3_slider_link_insertion import later_stages
from scripts.verify_pg3_service_stages import mechanism_stages


def late_stages(shapes):
    tools, bodies, preload = (
        mechanism_stages(shapes, horn_l_key=True),
        later_stages(shapes),
        preload_stages(shapes),
    )
    targets = {
        "G1": tools["G1_frame_case"][0],
        "G2": tools["G2_horn_drive"][0],
        "G3_R": bodies["G3_R"][0] | bodies["G3_R"][1],
        "G3_L": bodies["G3_L"][0] | bodies["G3_L"][1],
    }
    previous = {
        n: s
        for n, s in shapes.items()
        if n.startswith("ARM_") or n in {"PG3_XL430_fixed", "PG3_XL430_horn"}
    }
    stages = {}
    for group, target in targets.items():
        names = [n for n, (_, _, g) in preload.items() if g == group]
        if any(n not in shapes or s is not shapes[n] for n, s in target.items()):
            raise ValueError("late-loading target must retain saved geometry")
        if not names or not set(names) <= set(target) or set(names) & set(previous):
            raise ValueError("missing or already installed group nut")
        present = {n: s for n, s in target.items() if n not in names}
        if not set(previous) <= set(present):
            raise ValueError("prior components must remain for late loading")
        for name in names:
            mover = {name: shapes[name]}
            stages[name] = (mover, dict(present), group)
            present.update(mover)
        if set(present) != set(target):
            raise ValueError("final late-loading stage differs from canonical inventory")
        previous = present
    if set(stages) != set(preload):
        raise ValueError("incomplete late nut inventory")
    return stages


def fastening_envelopes(shapes):
    final = mechanism_stages(shapes, horn_l_key=True)["G6_fingers"][0] | {
        n: shapes[n] for n in ("PG3_pad_R", "PG3_pad_L")
    }
    expected = {n for n in shapes if not n.startswith("CAMERA_")}
    if set(final) != expected or any(final[n] is not shapes[n] for n in final):
        raise ValueError("final non-camera inventory mismatch")
    result = {}
    for name, (mover, _, group) in preload_stages(shapes).items():
        bolt = name.removesuffix("_nut") + "_bolt"
        if bolt not in final:
            raise ValueError("missing target bolt")
        result[name] = (mover, {n: s for n, s in final.items() if n not in {name, bolt}}, group)
    return result


def run(checkpoint, out, context="earliest"):
    builders = {"earliest": late_stages, "fastening_envelope": fastening_envelopes}
    if context not in builders:
        raise ValueError("explicit supported loading context required")
    if out.exists():
        raise FileExistsError(out)
    path = checkpoint / "arm_camera_mid_CANDIDATE.step"
    manifest = json.loads((checkpoint / "review.json").read_text())
    if digest(path) != manifest["output_sha256"][path.name]:
        raise ValueError("saved input SHA mismatch")
    rows = read_step(path)[2]
    shapes = {r.name: r.world for r in rows}
    if len(shapes) != len(rows):
        raise ValueError("ambiguous occurrence identity")
    report = {"assembly_sha256": digest(path), "stages": {}, "installation_approved": False}
    for name, (movers, obstacles, group) in builders[context](shapes).items():
        bolt = name.removesuffix("_nut") + "_bolt"
        if bolt in obstacles:
            raise ValueError("target bolt must not yet be inserted")
        result = review_loaded_nut(movers, obstacles)
        result["host_group"] = group
        result["target_bolt_not_inserted"] = bolt
        report["stages"][name] = result
        print(
            name,
            "late axial clear",
            result["supplemented_continuous_translation_volume_clear"],
            "upper",
            result["hex_enclosure"]["summed_overlap_upper_bound_mm3"],
            flush=True,
        )
    report["context"] = context
    report["scope"] = {
        "earliest": "fixed saved mid; hosts enter before this group of nuts; all prior arm parts retained",
        "fastening_envelope": "fixed saved mid; all non-camera parts retained except target nut/bolt; conservative superset of same-pose earlier assembly obstacles",
    }[context]
    report["limits"] = [
        "candidate late-loading sequence, not an accepted replacement for the assembly plan",
        "fastening envelope is an access bound, not proof that every other part can already be fastened",
        "failure of this -X30 approach does not disprove every lateral or curved route",
        "nominal nut proxies do not validate temporary holding, hand/tool access or printed fit",
        "camera and other arm poses are outside this check",
    ]
    report["checker_sha256"] = digest(Path(__file__))
    report["dependencies"] = {
        p: digest(Path(p))
        for p in (
            "scripts/review_pg3_nut_loading.py",
            "scripts/review_pg3_mechanism_insertion.py",
            "scripts/review_pg3_slider_link_insertion.py",
            "scripts/review_pg3_local_contacts.py",
            "scripts/verify_pg3_service_stages.py",
            "scripts/certify_pg3_insertion.py",
            "scripts/review_pg3.py",
            "scripts/assembly_io.py",
            "scripts/review_pg3_motion_clearance.py",
            "scripts/review_pg3_motor_partition.py",
            "scripts/review_pg3_pivot_stacks.py",
            "scripts/review_pg3_washer_contacts.py",
            "gripper_design/interface_envelopes.py",
            "gripper_design/rotational_envelopes.py",
            "gripper_design/pg2.py",
            "gripper_design/pg3.py",
            "gripper_design/pg3_installation.py",
            "uv.lock",
        )
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x") as stream:
        stream.write(json.dumps(report, indent=2) + "\n")
    return 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--context", choices=("earliest", "fastening_envelope"), default="earliest")
    args = parser.parse_args()
    raise SystemExit(run(args.checkpoint, args.out, args.context))
