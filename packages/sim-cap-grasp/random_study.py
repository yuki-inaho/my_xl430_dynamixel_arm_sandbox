"""Fixed offline study orchestration and reviewer-owned evidence entry points."""

import argparse
import json
import sys
from pathlib import Path

from build_scene import ROOT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=[
            "review-planner",
            "audit-single",
            "development",
            "freeze",
            "qualification",
            "workspace-map",
            "audit-batch",
            "review-cycle",
            "diagnose-setdown",
            "compress-completed",
            "diagnose-transfer",
        ],
        required=True,
    )
    parser.add_argument("--trial", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--name")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if args.mode == "review-planner":
        import review_random_planner

        sys.argv = [
            "review_random_planner.py",
            str(ROOT),
            "--output",
            str(ROOT / "evidence/independent-planner-review.json"),
        ]
        review_random_planner.main()
    elif args.mode == "audit-single":
        from audit_random_trial import audit_trial

        trial = args.trial.resolve()
        protocol = json.loads((trial / "protocol.json").read_text())
        plan = json.loads((trial / "plan.json").read_text())
        result = audit_trial(
            trial,
            plan["target_m"],
            protocol["standby"]["arm_q_rad"],
            protocol["standby"]["jaw_theta_deg"],
            return_criteria=protocol["return_criteria"],
            timing=protocol["timing_s"],
            approach_offset_m=protocol["planner"]["grip_z_offset_m"],
        )
        args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
        print(json.dumps(result, indent=2, allow_nan=False), flush=True)
        raise SystemExit(0 if result["audit_pass"] else 1)
    elif args.mode == "review-cycle":
        import review_random_cycle

        sys.argv = [
            "review_random_cycle.py",
            str(ROOT),
            str(ROOT / "results/dev-center-v2"),
            "--output",
            str(ROOT / "evidence/independent-cycle-controls.json"),
        ]
        review_random_cycle.main()
    elif args.mode == "diagnose-setdown":
        from diagnose_setdown import main as diagnose

        diagnose()
    elif args.mode == "compress-completed":
        from trace_io import compress_contacts

        for path in sorted((ROOT / "results").rglob("contacts.jsonl")):
            if (path.parent / "result.json").exists():
                storage = compress_contacts(path.parent)
                print(
                    "LOSSLESS",
                    path.parent,
                    storage["contacts"]["uncompressed_bytes"],
                    storage["contacts"]["compressed_bytes"],
                    flush=True,
                )
    elif args.mode == "diagnose-transfer":
        from diagnose_transfer import main as diagnose

        diagnose()
    elif args.mode in ("development", "qualification"):
        from batch import run_batch

        result = run_batch(args.name, args.seed, args.mode, min(4, max(1, args.workers)))
        raise SystemExit(0 if result["status"] == "PASS" else 1)
    elif args.mode == "freeze":
        from batch import freeze

        freeze(args.name, args.seed)
    elif args.mode == "workspace-map":
        from batch import workspace_map

        workspace_map()
    elif args.mode == "audit-batch":
        import audit_random_batch

        sys.argv = [
            "audit_random_batch.py",
            str(ROOT / "results" / args.name / "index.json"),
            "--root",
            str(ROOT),
            "--protocol",
            str(ROOT / "protocol.json"),
            "--output",
            str(args.output),
            "--workers",
            str(args.workers),
        ]
        audit_random_batch.main()


if __name__ == "__main__":
    main()
