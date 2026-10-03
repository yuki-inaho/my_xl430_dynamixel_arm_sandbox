"""Import or inspect PG2 without executing donor Python. Run as -m scripts.review_pg2."""

import argparse
import importlib.metadata
import json
import platform
import shutil
from pathlib import Path

from gripper_design.pg2 import (
    digest,
    import_archive,
    inspect_saved_assembly,
    slider_state,
    verify_intake,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    intake = sub.add_parser("import")
    intake.add_argument("archive", type=Path)
    intake.add_argument("--out", type=Path, required=True)
    review = sub.add_parser("review")
    review.add_argument("--source", type=Path, required=True)
    review.add_argument("--out", type=Path, required=True)
    review.add_argument("--render", action="store_true")
    args = parser.parse_args()
    if args.command == "import":
        receipt = import_archive(args.archive, args.out)
        print(json.dumps({k: v for k, v in receipt.items() if k != "files"}, indent=2))
        return 0
    receipt = verify_intake(args.source)
    args.out.mkdir(parents=True, exist_ok=False)
    code_files = (
        Path(__file__),
        Path(__file__).parents[1] / "gripper_design/pg2.py",
        Path(__file__).with_name("assembly_io.py"),
        Path(__file__).with_name("render_cad.py"),
    )
    provenance = args.out / "provenance"
    provenance.mkdir()
    for path in code_files:
        shutil.copy2(path, provenance / path.name)
    shutil.copy2(args.source.parent / "intake.json", provenance / "intake.json")
    reports = []
    for name, angle in (
        ("PG2_open", 30),
        ("PG2_mid", 90),
        ("PG2_closed", 140),
        ("PG2_camera_optional", 30),
    ):
        report, shapes = inspect_saved_assembly(args.source / "CAD" / f"{name}.step", angle)
        reports.append(report)
        (args.out / f"{name}.json").write_text(json.dumps(report, indent=2) + "\n")
        print(
            f"{name}: {report['occurrence_count']} occurrences, {report['pair_count']} pairs",
            flush=True,
        )
        if args.render:
            from scripts.render_cad import render

            colors = [
                (
                    shape,
                    (0.85, 0.32, 0.13)
                    if "jaw" in n
                    else (0.2, 0.65, 0.48)
                    if "link" in n
                    else (0.5, 0.55, 0.6),
                )
                for n, shape in shapes.items()
            ]
            for view, direction in {
                "X": (1, 0, 0),
                "Y": (0, 1, 0),
                "Z": (0, 0, 1),
                "iso": (1, 1, 1),
            }.items():
                render(colors, args.out / f"{name}_{view}.png", direction, size=(800, 600))
    issues = [
        {"assembly": Path(r["path"]).name, **pair}
        for r in reports
        for pair in r["pairs"]
        if pair["status"] != "PASS"
    ]
    payload = {
        "schema_version": 1,
        "variant": "pg2_upright_crank_slider_r5",
        "scope": "independent_saved_STEP_four_poses_not_full_arm_or_continuous_sweep",
        "archive_sha256": receipt["archive_sha256"],
        "runtime": {
            "python": platform.python_version(),
            **{n: importlib.metadata.version(n) for n in ("cadquery", "cadquery-ocp")},
        },
        "code_sha256": {str(p): digest(p) for p in code_files},
        "assemblies": [
            {k: v for k, v in r.items() if k not in {"occurrences", "pairs"}} for r in reports
        ],
        "analytic_motion": [slider_state(a) for a in range(30, 141)],
        "issues": issues,
        "camera_parent_in_donor": "PG2_frame_not_P05",
        "arm_from_pg2_transform": None,
        "fabrication_approved": False,
        "powered_operation_approved": False,
        "whole_arm_fit_approved": False,
        "status": "FAIL"
        if any(r["geometry_status"] == "FAIL" for r in reports)
        or any(p["status"] in {"FAIL", "ERROR"} for p in issues)
        else "UNKNOWN",
        "artifacts_sha256": {
            str(p.relative_to(args.out)): digest(p) for p in args.out.rglob("*") if p.is_file()
        },
    }
    (args.out / "review.json").write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps({"status": payload["status"], "unresolved_pairs": len(issues)}, indent=2))
    return 2  # Diagnostic review is not a release gate; UNKNOWN must not be success.


if __name__ == "__main__":
    raise SystemExit(main())
