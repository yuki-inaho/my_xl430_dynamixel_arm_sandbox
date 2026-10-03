"""Run one native CAD operation in an isolated process."""

from __future__ import annotations

import argparse
import json

from common import study_run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("generate", "validate"))
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args(argv)
    run = study_run(args.run_id)
    if args.operation == "generate":
        from build_all_xl430 import generate_candidate

        generate_candidate(run)
        print(json.dumps({"execution": "generated_unaccepted_diagnostic"}))
    else:
        from validate import validate_candidate

        validate_candidate(run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
