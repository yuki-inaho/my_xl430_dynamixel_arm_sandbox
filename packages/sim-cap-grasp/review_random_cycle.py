"""Synthetic adversarial controls for the new full-cycle evaluator only.

Works on temporary copies of a successful raw trace. The original dynamics and
its files are never modified; these controls are not physical trial evidence.
Run via the task's visible fixed-job console.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import mujoco
import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("trial", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root, trial = args.root.resolve(), args.trial.resolve()
    sys.path.insert(0, str(root))
    from audit_random_trial import iter_contact_lines
    from random_cycle import evaluate_cycle

    protocol = json.loads((trial / "protocol.json").read_text())
    metadata = json.loads((trial / "metadata.json").read_text())
    plan = json.loads((trial / "plan.json").read_text())
    policy = json.loads((trial / "collision_pairs.json").read_text())
    model = mujoco.MjModel.from_xml_path(str(trial / "scene.xml"))
    with np.load(trial / "states.npz", allow_pickle=False) as archive:
        original_states = {k: archive[k] for k in archive.files}
    rows = [json.loads(line) for line in iter_contact_lines(trial, {})]
    qa = int(model.joint("cad_j2").qposadr[0])
    va = int(model.joint("cad_j2").dofadr[0])
    capqa = int(model.jnt_qposadr[model.body_jntadr[model.body("cap").id]])
    final_start = int(
        np.flatnonzero(
            original_states["time"]
            >= protocol["timing_s"]["final_end"]
            - protocol["return_criteria"]["settling_interval_s"]
            - 1e-9
        )[0]
    )
    finger = next(g["name"] for g in policy["geoms"] if g["category"] == "softtip")
    cases = []

    def check(
        name,
        edit_states=None,
        edit_metadata=None,
        edit_contacts=None,
        expected="FAILURE",
        reason=None,
    ):
        states = {k: v.copy() for k, v in original_states.items()}
        meta = copy.deepcopy(metadata)
        if edit_states:
            edit_states(states)
        if edit_metadata:
            edit_metadata(meta)
        # Temporary files exist only for this test. Mesh references are made
        # explicit solely so moving the copy does not create a false failure.
        with tempfile.TemporaryDirectory(
            prefix="review-cycle-control-", dir=args.output.parent
        ) as temporary:
            directory = Path(temporary)
            tree = ET.parse(trial / "scene.xml")
            compiler = tree.getroot().find("compiler")
            original_meshdir = Path(compiler.get("meshdir", "."))
            if not original_meshdir.is_absolute():
                original_meshdir = (trial / original_meshdir).resolve()
            compiler.set("meshdir", str(original_meshdir))
            tree.write(directory / "scene.xml", encoding="unicode")
            for filename, content in (
                ("protocol.json", protocol),
                ("metadata.json", meta),
                ("plan.json", plan),
            ):
                (directory / filename).write_text(json.dumps(content))
            np.savez_compressed(directory / "states.npz", **states)
            with (directory / "contacts.jsonl").open("w") as handle:
                for i, row in enumerate(rows):
                    out = copy.deepcopy(row) if edit_contacts and i >= final_start else row
                    if edit_contacts and i >= final_start:
                        edit_contacts(out)
                    handle.write(json.dumps(out) + "\n")
            try:
                result = evaluate_cycle(directory, {"status": "SUCCESS", "reason_codes": []})
                passed = result["status"] == expected and (
                    reason is None or reason in result["reason_codes"]
                )
                entry = {
                    "name": name,
                    "pass": passed,
                    "expected": expected,
                    "actual": result["status"],
                    "expected_reason": reason,
                    "actual_reasons": result["reason_codes"],
                }
            except Exception as error:  # noqa: BLE001 -- Record counterexample failure without hiding other controls.
                entry = {
                    "name": name,
                    "pass": False,
                    "expected": expected,
                    "actual": "UNCAUGHT_EXCEPTION",
                    "exception": f"{type(error).__name__}: {error}",
                }
        cases.append(entry)
        print(json.dumps(entry), flush=True)

    check("unmodified_cycle_baseline", expected="SUCCESS")
    check(
        "wrong_initial_standby",
        lambda s: s["qpos"].__setitem__((0, qa), 0.1),
        reason="STANDBY_RESET_INVALID",
    )
    check(
        "nonzero_initial_velocity",
        lambda s: s["qvel"].__setitem__((0, va), 0.1),
        reason="STANDBY_RESET_INVALID",
    )
    check(
        "late_return_position_error",
        lambda s: s["qpos"].__setitem__((final_start + 5, qa), 0.02),
        reason="STANDBY_RETURN_FAILED",
    )
    check(
        "transient_return_velocity_error",
        lambda s: s["qvel"].__setitem__((final_start + 5, va), 0.04),
        reason="STANDBY_RETURN_FAILED",
    )
    check(
        "bad_initial_cap_target",
        lambda s: s["qpos"].__setitem__((0, capqa), s["qpos"][0, capqa] + 0.01),
        reason="TARGET_RESET_INVALID",
    )
    check(
        "cap_outside_full_footprint",
        lambda s: s["cap_position"].__setitem__(
            (slice(final_start, None), 0), plan["support_center_m"][0] + 0.025
        ),
        reason="RELEASE_PLACEMENT_FAILED",
    )
    check(
        "cap_bottom_below_support",
        lambda s: s["cap_position"].__setitem__(
            (final_start + 5, 2), s["cap_position"][final_start + 5, 2] - 0.002
        ),
        reason="RELEASE_PLACEMENT_FAILED",
    )

    def remove_support(row):
        row["contacts"] = [
            c for c in row["contacts"] if {c["geom1"], c["geom2"]} != {"cap_geom", "box"}
        ]

    check("no_final_box_support", edit_contacts=remove_support, reason="RELEASE_PLACEMENT_FAILED")

    def add_finger(row):
        row["contacts"].append(
            {
                "geom1": "cap_geom",
                "geom2": finger,
                "force": [0.1, 0, 0, 0, 0, 0],
                "distance": -0.00001,
            }
        )

    check(
        "lingering_final_finger_contact",
        edit_contacts=add_finger,
        reason="RELEASE_PLACEMENT_FAILED",
    )
    check(
        "runtime_pose_write_flag",
        edit_metadata=lambda m: m.update(runtime_pose_writes=True),
        reason="MODEL_INVALID",
    )

    def truncate(s):
        for key in s:
            s[key] = s[key][:-1000]

    check("incomplete_final_cycle", truncate, reason="CYCLE_INCOMPLETE")
    report = {
        "pass": all(c["pass"] for c in cases),
        "tests": cases,
        "source_trial": str(trial),
        "mutated_original": False,
        "scope": "Synthetic isolated cycle-evaluator controls, not dynamics or held-out grasp outcomes",
    }
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps(report, indent=2, allow_nan=False), flush=True)
    raise SystemExit(0 if report["pass"] else 1)


if __name__ == "__main__":
    main()
