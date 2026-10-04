"""Package sources, selected CAD, observations, results, and audit records.

Exclude environment/build caches, fonts, transient process identifiers, and
external uploads. Verify CRC and a per-file SHA256 manifest after extraction.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
import stat
import zipfile
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_PARTS = {".venv", ".git", ".pytest_cache", "__pycache__", "build", "build_nanobind"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".nbc", ".nbi", ".pid", ".ttf", ".otf", ".ttc", ".woff", ".woff2"}
MANIFEST_NAME = "docs/package_manifest.json"


def sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def included(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    return (
        path.is_file()
        and not path.is_symlink()
        and not (set(relative.parts) & EXCLUDED_PARTS)
        and path.suffix.lower() not in EXCLUDED_SUFFIXES
        and relative.as_posix() != MANIFEST_NAME
    )


def package(output: Path, extract_to: Path, validation_path: Path) -> dict:
    """Build and verify; refuse extraction over an existing nonempty directory."""
    output = output.resolve()
    extract_to = extract_to.resolve()
    if output.is_relative_to(ROOT) or extract_to.is_relative_to(ROOT):
        raise ValueError("Archive and extraction directory must be outside the source root")
    if extract_to.exists() and any(extract_to.iterdir()):
        raise FileExistsError(f"Extraction directory is not empty: {extract_to}")
    paths = sorted(path for path in ROOT.rglob("*") if included(path))
    manifest = {
        "schema_version": 1,
        "root": ROOT.name,
        "manifest_excludes_itself": True,
        "files": [
            {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size,
             "sha256": sha256(path)}
            for path in paths
        ],
    }
    manifest_path = ROOT / MANIFEST_NAME
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in paths + [manifest_path]:
            archive.write(path, (Path(ROOT.name) / path.relative_to(ROOT)).as_posix())
    extract_to.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise RuntimeError(f"CRC failure: {bad}")
        for member in archive.infolist():
            destination = (extract_to / member.filename).resolve()
            if not destination.is_relative_to(extract_to):
                raise ValueError(f"Unsafe archive member: {member.filename}")
            archive.extract(member, extract_to)
            # Python extraction does not retain executable permissions by default.
            mode = (member.external_attr >> 16) & 0o777
            if mode and destination.is_file():
                destination.chmod(mode)
    extracted_root = extract_to / ROOT.name
    extracted_manifest = json.loads((extracted_root / MANIFEST_NAME).read_text())
    for entry in extracted_manifest["files"]:
        path = extracted_root / entry["path"]
        if path.stat().st_size != entry["bytes"] or sha256(path) != entry["sha256"]:
            raise RuntimeError(f"Hash/size mismatch: {entry['path']}")
    actual_files = {p.relative_to(extracted_root).as_posix() for p in extracted_root.rglob("*") if p.is_file()}
    expected_files = {entry["path"] for entry in extracted_manifest["files"]} | {MANIFEST_NAME}
    if actual_files != expected_files:
        raise RuntimeError("Archive member set differs from manifest")
    result = {
        "timestamp_jst": datetime.now(ZoneInfo("Asia/Tokyo")).isoformat(timespec="seconds"),
        "archive": str(output),
        "archive_bytes": output.stat().st_size,
        "archive_sha256": sha256(output),
        "extracted_root": str(extracted_root),
        "file_count_including_manifest": len(actual_files),
        "crc_passed": True,
        "all_hashes_and_sizes_match": True,
        "member_set_matches_manifest": True,
        "fonts_included": False,
        "build_artifacts_included": False,
        "passed": True,
    }
    validation_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--extract-to", required=True, type=Path)
    parser.add_argument("--validation", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(package(args.output, args.extract_to, args.validation), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
