"""Audit what a commit would publish: secrets, key material, oversized or generated files.

Run from the repository root after `git add`:
  python precommit_audit.py [--max-mb 5] [--block-mb 50] [--json report.json]
It inspects the staged blobs (`git diff --cached`), never the working tree, and only reads.
Exit 0 = no blocker, 1 = blocker found (secret, private key, file >= block size), 2 = git error.
Warnings (large files, e-mail addresses, home paths, conversation exports, binaries) are
reported for a human decision; they do not fail the audit.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import PurePosixPath

SECRETS = {
    "github_token": r"gh[pousr]_[A-Za-z0-9]{20,}",
    "anthropic_key": r"sk-ant-[A-Za-z0-9_-]{20,}",
    "openai_key": r"sk-(?:proj-)?[A-Za-z0-9]{32,}",
    "aws_access_key": r"AKIA[0-9A-Z]{16}",
    "slack_token": r"xox[abposr]-[A-Za-z0-9-]{10,}",
    "bearer_token": r"Bearer [A-Za-z0-9._~+/-]{20,}=*",
    "password_assignment": r"(?i)\b(?:password|passwd|secret|api_key)\s*[:=]\s*['\"][^'\"\s]{8,}",
}
PRIVATE_KEY = r"-----BEGIN [A-Z ]*PRIVATE KEY-----"
EMAIL = r"\b[A-Za-z0-9._%+-]{2,}@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}\b"
EMAIL_ALLOW = ("noreply@anthropic.com", "git@github.com")
HOME = r"/home/[A-Za-z0-9._-]+/|/Users/[A-Za-z0-9._-]+/"
GENERATED = (".venv/", "__pycache__/", ".pytest_cache/", ".ruff_cache/", "node_modules/",
             "/target/", ".serena/", ".playwright-cli/", ".DS_Store", ".env")


def git(*args: str) -> bytes:
    return subprocess.run(["git", *args], check=True, capture_output=True).stdout


def staged() -> list[str]:
    out = git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z")
    return [name for name in out.decode().split("\0") if name]


def scan_text(text: str) -> dict:
    found = {label: len(re.findall(p, text)) for label, p in SECRETS.items()}
    emails = [e for e in re.findall(EMAIL, text) if e not in EMAIL_ALLOW]
    return {"secrets": {k: v for k, v in found.items() if v},
            "private_key": bool(re.search(PRIVATE_KEY, text)),
            "emails": sorted(set(emails))[:5], "home_paths": len(re.findall(HOME, text))}


def audit(path: str, warn_bytes: int, block_bytes: int) -> dict:
    blob = git("show", f":{path}")
    entry: dict = {"path": path, "bytes": len(blob), "blockers": [], "warnings": []}
    if len(blob) >= block_bytes:
        entry["blockers"].append("file at or above the block size")
    elif len(blob) >= warn_bytes:
        entry["warnings"].append("large file")
    if any(marker in f"/{path}" for marker in GENERATED):
        entry["warnings"].append("generated or tool-state path")
    if PurePosixPath(path).name.endswith(("_clean.json", ".clean.jsonl", ".transcript.md")):
        entry["warnings"].append("conversation export: review before publishing")
    if b"\0" in blob[:8192]:
        entry["warnings"].append("binary")
        return entry
    found = scan_text(blob.decode("utf-8", errors="replace"))
    if found["secrets"]:
        entry["blockers"].append(f"secret-like strings {found['secrets']}")
    if found["private_key"]:
        entry["blockers"].append("private key material")
    if found["emails"]:
        entry["warnings"].append(f"e-mail addresses {found['emails']}")
    if found["home_paths"]:
        entry["warnings"].append(f"{found['home_paths']} absolute home paths")
    return entry


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-mb", type=float, default=5.0)
    parser.add_argument("--block-mb", type=float, default=50.0)
    parser.add_argument("--json", dest="json_path")
    args = parser.parse_args()
    try:
        names = staged()
        entries = [audit(n, int(args.max_mb * 2**20), int(args.block_mb * 2**20)) for n in names]
    except subprocess.CalledProcessError as exc:
        print(f"git failed: {exc.stderr.decode(errors='replace').strip()}", file=sys.stderr)
        return 2
    blockers = [e for e in entries if e["blockers"]]
    warnings = [e for e in entries if e["warnings"]]
    report = {"staged_files": len(entries), "staged_bytes": sum(e["bytes"] for e in entries),
              "blockers": blockers, "warnings": warnings}
    if args.json_path:
        with open(args.json_path, "w", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
    print(json.dumps({"staged_files": report["staged_files"],
                      "staged_mb": round(report["staged_bytes"] / 2**20, 2),
                      "blockers": len(blockers), "warnings": len(warnings)}))
    for entry in blockers + warnings:
        print(f"{'BLOCK' if entry['blockers'] else 'warn '} {entry['path']}: "
              f"{'; '.join(entry['blockers'] + entry['warnings'])}")
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
