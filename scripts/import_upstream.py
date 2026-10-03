"""Copy upstream source snapshots without importing or executing their code."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "low_cost_robot": ("scripts", "low_cost_robot", "docs"),
    "3d-printed-dynamixel-gripper": (
        "scripts",
        "gripper_design",
        "camera_jig",
        "simulation",
        "specs",
        "docs",
    ),
}
EXTENSIONS = {
    ".py",
    ".md",
    ".toml",
    ".yaml",
    ".yml",
    ".json",
    ".html",
    ".txt",
    ".lock",
    ".sh",
    ".js",
    ".xml",
    ".urdf",
}
EXCLUDED_DIRECTORIES = {
    ".venv",
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "node_modules",
    "build",
    "dist",
    "outputs",
    "reports",
    "temp",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    manifest = {
        "captured_at": datetime.now().astimezone().isoformat(),
        "purpose": "Source snapshots only; upstream code was not executed",
        "included_extensions": sorted(EXTENSIONS),
        "excluded_directories": sorted(EXCLUDED_DIRECTORIES),
        "binary_cad_and_generated_outputs_copied": False,
        "sources": [],
    }
    for name, directories in SOURCES.items():
        source_root = ROOT.parent / name
        if not source_root.is_dir():
            raise RuntimeError(f"Missing upstream project: {source_root}")
        revision = subprocess.run(
            ["git", "-C", str(source_root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        record = {
            "name": name,
            "source_root": str(source_root),
            "git_head": revision.stdout.strip() or None,
            "includes_current_worktree_files": True,
            "files": [],
            "excluded": [],
        }
        roots = [(source_root / "skills", ROOT / "skills/imported" / name)]
        roots.extend(
            (source_root / directory, ROOT / "upstream" / name / directory)
            for directory in directories
        )
        for source, target in roots:
            if not source.exists():
                continue
            for path in sorted(source.rglob("*")):
                relative = path.relative_to(source)
                if any(part in EXCLUDED_DIRECTORIES for part in relative.parts):
                    continue
                if path.is_dir():
                    continue
                if path.is_symlink() or path.suffix.lower() not in EXTENSIONS:
                    record["excluded"].append(str(path.relative_to(source_root)))
                    continue
                destination = target / relative
                copy_file(path, destination, record, source_root)
        for name_in_root in ("README.md", "pyproject.toml", "uv.lock", "LICENSE", "LICENSE.md"):
            source = source_root / name_in_root
            if source.is_file():
                copy_file(source, ROOT / "upstream" / name / name_in_root, record, source_root)
        manifest["sources"].append(record)
        print(
            f"{name}: {len(record['files'])} files copied; "
            f"{len(record['excluded'])} non-source files omitted"
        )
    destination = ROOT / "upstream/import_manifest.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(destination)


def copy_file(source: Path, destination: Path, record: dict, source_root: Path) -> None:
    source_hash = digest(source)
    if destination.exists() and digest(destination) != source_hash:
        raise RuntimeError(f"Refusing to overwrite a different snapshot: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    destination_hash = digest(destination)
    if destination_hash != source_hash:
        raise RuntimeError(f"Copy verification failed: {destination}")
    record["files"].append(
        {
            "source": str(source.relative_to(source_root)),
            "destination": str(destination.relative_to(ROOT)),
            "sha256": destination_hash,
            "bytes": destination.stat().st_size,
        }
    )


if __name__ == "__main__":
    main()
