"""Create an all-XL430 print package only after fresh validation acceptance.

Thin wrapper around ``source/study.py print-package`` so the fail-closed gate
and archive logic exist in exactly one place. The command re-runs the B-rep
scan against the current candidate and exits 2 while it remains unaccepted.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SOURCE_DIR = Path(__file__).resolve().parent / "source"
sys.path.insert(0, str(SOURCE_DIR))

from study import main as study_main  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default="current")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    return study_main(
        ["print-package", "--run-id", args.run_id, "--output", str(args.output)]
    )


if __name__ == "__main__":
    raise SystemExit(main())
