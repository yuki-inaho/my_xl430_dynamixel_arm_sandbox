"""Rebuild, validate, and fail closed before print packaging."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from common import (
    OUTPUT_ROOT,
    PART_NAMES,
    candidate_inventory,
    read_json,
    study_run,
    write_json,
)
from print_gate import assert_fresh_destination, evaluate


def run_worker(operation: str, run_id: str) -> None:
    command = [
        sys.executable,
        "-X",
        "faulthandler",
        "-u",
        str(Path(__file__).with_name("cad_worker.py")),
        operation,
        "--run-id",
        run_id,
    ]
    try:
        result = subprocess.run(command, timeout=1800, check=False)
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(f"CAD {operation} timed out; print is blocked") from error
    if result.returncode != 0:
        raise RuntimeError(
            f"CAD {operation} exited with code {result.returncode}; print is blocked"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    for name in ("rebuild", "validate", "print-package"):
        command = subcommands.add_parser(name)
        command.add_argument("--run-id", default="current")
        if name == "print-package":
            command.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    run = None
    try:
        run = study_run(args.run_id)
        if args.command == "print-package":
            assert_fresh_destination(args.output, quarantine=OUTPUT_ROOT / "unaccepted")
        if args.command == "rebuild":
            run_worker("generate", args.run_id)
        # Never trust an archived JSON when deciding whether packaging may run.
        run_worker("validate", args.run_id)
        report = read_json(run / "reports/validation.json")
        reasons = evaluate(report, candidate_inventory(run))
        if reasons:
            print(
                json.dumps(
                    {
                        "status": "unaccepted",
                        "print_status": "blocked",
                        "external_collision_count": report["static_interference"][
                            "external_collision_count"
                        ],
                        "supplier_internal_collision_count": report[
                            "static_interference"
                        ]["supplier_internal_collision_count"],
                        "reasons": reasons,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 2
        if args.command == "print-package":
            destination = args.output.resolve()
            destination.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary = tempfile.mkstemp(
                dir=destination.parent, suffix=".zip"
            )
            os.close(descriptor)
            try:
                with zipfile.ZipFile(
                    temporary, "w", compression=zipfile.ZIP_DEFLATED
                ) as archive:
                    for name in PART_NAMES:
                        for extension in ("step", "stl"):
                            path = run / f"CAD/parts/{name}.{extension}"
                            archive.write(path, f"parts/{path.name}")
                    archive.writestr(
                        "validation.json",
                        json.dumps(report, ensure_ascii=False, indent=2),
                    )
                if candidate_inventory(run) != report["candidate_sha256"]:
                    raise ValueError("Candidate changed during packaging")
                os.link(temporary, destination)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
        return 0
    except Exception as error:
        message = {
            "status": "blocked_validation_error",
            "print_status": "blocked",
            "error_type": type(error).__name__,
            "error": str(error),
        }
        if run is not None and run.is_dir():
            write_json(run / "reports/last_failure.json", message)
            write_json(run / "reports/print_gate.json", message)
        print(json.dumps(message, ensure_ascii=False, indent=2), file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
