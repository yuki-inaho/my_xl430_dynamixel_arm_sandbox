"""Check the reviewed, privacy-sanitized D405 intake without CAD dependencies."""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = "studies/low-profile-20260926/integration/manifest.json"


def verify(root, manifest):
    root = Path(root).resolve()
    records = json.loads(Path(manifest).read_text(encoding="utf-8"))["files"]
    seen, errors = set(), []
    for record in records:
        name = record["path"]
        relative = PurePosixPath(name)
        if relative.is_absolute() or ".." in relative.parts or "\\" in name or name in seen:
            raise ValueError("Unsafe or duplicate manifest entry")
        seen.add(name)
        path = root / relative
        if path.is_symlink() or not path.resolve().is_relative_to(root) or not path.is_file():
            errors.append({"path": name, "error": "missing or unsafe path"})
            continue
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if path.stat().st_size != record["bytes"] or digest != record["sha256"]:
            errors.append({"path": name, "error": "content changed"})
    return {
        "status": "FAIL" if errors else "PASS",
        "files": len(seen),
        "errors": errors,
        "scope": "Recorded intake files only; not a signature or fabrication approval",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    try:
        result = verify(args.root, args.manifest or args.root / MANIFEST)
    except (OSError, ValueError, KeyError, TypeError):
        result = {"status": "FAIL", "error": "Invalid or unreadable intake manifest"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
