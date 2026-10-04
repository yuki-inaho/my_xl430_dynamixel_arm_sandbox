"""Audit owned-source syntax, whitespace, image sizes, and optional input hashes.

This is a narrow executable check, not a substitute for Ruff, Black, a static
checker, or the unexecuted nanobind build. Its JSON records that distinction.
"""
from __future__ import annotations

import argparse
import ast
from datetime import datetime
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OWNED_DIRECTORIES = ("src", "cpp", "scripts", "tests")
SOURCE_SUFFIXES = {".py", ".cpp", ".hpp", ".sh"}


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def audit(original_input_dir: Path | None = None) -> dict:
    failures: list[str] = []
    source_paths = sorted(
        path
        for directory in OWNED_DIRECTORIES
        for path in (ROOT / directory).rglob("*")
        if path.is_file() and path.suffix in SOURCE_SUFFIXES
    )
    python_count = 0
    for path in source_paths:
        source = path.read_text(encoding="utf-8")
        if path.suffix == ".py":
            try:
                ast.parse(source, filename=str(path))
                compile(source, str(path), "exec", dont_inherit=True)
                python_count += 1
            except (SyntaxError, ValueError) as error:
                failures.append(f"{path.relative_to(ROOT)}: {error}")
        for number, line in enumerate(source.splitlines(), start=1):
            if line.rstrip(" \t") != line:
                failures.append(f"{path.relative_to(ROOT)}:{number}: trailing whitespace")
        if source and not source.endswith("\n"):
            failures.append(f"{path.relative_to(ROOT)}: missing final newline")

    image_sizes = {}
    for name in ("overlay.png", "raw_geometry_overlay.png", "cad_view.png", "silhouette_error.png"):
        with Image.open(ROOT / "results" / name) as image:
            image.load()
            image_sizes[name] = list(image.size)
            if image.size != (652, 367):
                failures.append(f"{name}: unexpected image size {image.size}")

    input_checks = []
    if original_input_dir is not None:
        for entry in json.loads((ROOT / "docs/input_hashes.json").read_text()):
            path = original_input_dir / entry["name"]
            passed = path.is_file() and path.stat().st_size == entry["bytes"] and digest(path) == entry["sha256"]
            input_checks.append({"name": entry["name"], "unchanged": passed})
            if not passed:
                failures.append(f"original input modified or unavailable: {entry['name']}")

    photo_hash = digest(ROOT / "inputs/standby.jpg")
    recorded = next(entry for entry in json.loads((ROOT / "docs/input_hashes.json").read_text())
                    if entry["name"] == "standby.jpg")
    if photo_hash != recorded["sha256"]:
        failures.append("portable input photograph does not match original hash")

    return {
        "timestamp_jst": datetime.now(ZoneInfo("Asia/Tokyo")).isoformat(timespec="seconds"),
        "owned_source_file_count": len(source_paths),
        "python_syntax_checked_count": python_count,
        "whitespace_checked": True,
        "image_sizes": image_sizes,
        "portable_photo_matches_original": photo_hash == recorded["sha256"],
        "original_inputs": input_checks,
        "external_linter_executed": False,
        "external_formatter_executed": False,
        "static_type_checker_executed": False,
        "nanobind_build_verified": False,
        "warning": "These checks do not certify unavailable formatter/linter/type-checker/nanobind tools.",
        "failures": failures,
        "passed": not failures,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original-input-dir", type=Path)
    args = parser.parse_args()
    result = audit(args.original_input_dir)
    output = ROOT / "docs/code_quality.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
