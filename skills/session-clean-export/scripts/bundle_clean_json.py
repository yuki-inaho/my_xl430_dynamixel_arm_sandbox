"""Export one agent session JSONL as a single reviewed `*_clean.json` bundle.

Uses `agent-jsonl-compact` (faithful defaults) for the normalized events and adds the
records it does not extract:
- Claude Code: messages typed while a turn was running (`queue-operation` enqueue).
- Codex: code-mode `custom_tool_call` / `custom_tool_call_output` response items.
Secret-looking strings are redacted; the bundle records what was redacted and the input hash.

Usage:
  python bundle_clean_json.py --session <raw.jsonl> --output <dir>/<name>_clean.json [--name N]
No network access; the session file is only read (a complete-line snapshot is taken first).
"""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path

SECRETS = {
    "github_token": r"gh[pousr]_[A-Za-z0-9]{20,}",
    "anthropic_key": r"sk-ant-[A-Za-z0-9_-]{20,}",
    "openai_key": r"sk-(?:proj-)?[A-Za-z0-9]{32,}",
    "aws_access_key": r"AKIA[0-9A-Z]{16}",
    "slack_token": r"xox[abposr]-[A-Za-z0-9-]{10,}",
    "bearer_token": r"Bearer [A-Za-z0-9._~+/-]{20,}=*",
}
PRIVATE_KEY = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")


def snapshot(session: Path, workdir: Path) -> tuple[Path, bytes]:
    raw = session.read_bytes()
    complete = raw[: raw.rfind(b"\n") + 1]  # a live session may end with a partial line
    path = workdir / "session.snapshot.jsonl"
    path.write_bytes(complete)
    return path, complete


def extract(path: Path, workdir: Path, name: str) -> tuple[dict, list[dict]]:
    tool = shutil.which("agent-jsonl-compact")
    if tool is None:
        raise SystemExit("agent-jsonl-compact not found (see agent-jsonl-compact-reader skill)")
    out = workdir / "extracts"
    subprocess.run([tool, "-i", str(path), "-o", str(out), "--name", name,
                    "--format-out", "jsonl", "--channel", "both", "--no-dedup"],
                   check=True, capture_output=True)
    summary = json.loads((out / f"{name}.summary.json").read_text())
    lines = (out / f"{name}.clean.jsonl").read_text().splitlines()
    events = [json.loads(line) for line in lines if line.strip()]
    if len(events) != summary["kept_events"]:
        raise SystemExit("extractor event count mismatch")
    records = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    validate_user_coverage(records, summary["format"], events)
    return summary, events


def user_record_kind(record: dict, fmt: str) -> str | None:
    payload = record.get("payload", {})
    if fmt == "codex":
        if (record.get("type") == "response_item" and payload.get("type") == "message"
                and payload.get("role") == "user"):
            return "api_user"
        if record.get("type") == "event_msg" and payload.get("type") == "user_message":
            return "user"
    if fmt == "claude_code" and record.get("type") == "user":
        content = record.get("message", {}).get("content", [])
        if isinstance(content, str) or any(block.get("type") == "text" for block in content):
            return "user"
    return None


def validate_user_coverage(records: list[dict], fmt: str, events: list[dict]) -> dict:
    expected = Counter(kind for record in records if (kind := user_record_kind(record, fmt)))
    observed = Counter(e["kind"] for e in events if e["kind"] in ("user", "api_user"))
    if expected != observed:
        raise SystemExit(f"user coverage mismatch: source={dict(expected)}, "
                         f"output={dict(observed)}")
    return {"expected": dict(expected), "observed": dict(observed), "verified": True}


def supplemental(records: list[dict], fmt: str) -> list[dict]:
    extra = []
    for number, record in enumerate(records, 1):
        payload = record.get("payload", {})
        if fmt == "codex" and record.get("type") == "response_item" and payload.get(
            "type"
        ) in ("custom_tool_call", "custom_tool_call_output"):
            extra.append({"kind": payload["type"], "ts": record.get("timestamp"),
                          "source_line": number, "payload": payload})
        elif (fmt == "claude_code" and record.get("type") == "queue-operation"
              and record.get("operation") == "enqueue"):
            text = record.get("content") or ""
            # The same queue carries background-task notifications; keep them apart.
            kind = ("queued_system_notification" if text.lstrip().startswith("<task-notification>")
                    else "mid_turn_user_message")
            extra.append({"kind": kind, "ts": record.get("timestamp"), "source_line": number,
                          "text": text})
    return extra


def redact(text: str) -> tuple[str, Counter]:
    if PRIVATE_KEY.search(text):
        raise SystemExit("private key material found; refusing to export")
    counts: Counter = Counter()
    for label, pattern in SECRETS.items():
        text, found = re.subn(pattern, f"[REDACTED:{label}]", text)
        counts[label] += found
    return text, counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--name", default="session")
    args = parser.parse_args()
    if not args.output.name.endswith("_clean.json"):
        raise SystemExit("output name must end with _clean.json")
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        path, raw = snapshot(args.session, work)
        summary, events = extract(path, work, args.name)
    records = [json.loads(line) for line in raw.splitlines() if line.strip()]
    extra = supplemental(records, summary["format"])
    document = {
        "schema": "agent-conversation-clean-bundle/v1",
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source": {"session": str(args.session), "sha256": hashlib.sha256(raw).hexdigest(),
                   "bytes": len(raw), "records": len(records)},
        "extractor": {"name": "agent-jsonl-compact", "defaults": "faithful (no truncation)",
                      "channel": "both", "deduplicate": False},
        "user_coverage": validate_user_coverage(records, summary["format"], events),
        "summary": summary, "events": events, "supplemental_events": extra,
        "coverage_notes": [
            "Normalized events come from agent-jsonl-compact with faithful defaults.",
            "supplemental_events hold records the extractor skips (mid-turn user messages "
            "for Claude Code, code-mode tool records for Codex).",
            "Encrypted or omitted reasoning is not recoverable.",
            "The snapshot holds complete lines only; later records are outside the cutoff.",
            "Contains conversation text and local paths; review before sharing.",
        ],
    }
    text, counts = redact(json.dumps(document, ensure_ascii=False, indent=1))
    document = json.loads(text)
    document["redactions"] = dict(counts)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, ensure_ascii=False, indent=1) + "\n")
    json.loads(args.output.read_text())  # read-back validation
    print(json.dumps({"output": str(args.output), "events": len(events),
                      "supplemental": len(extra), "redactions": dict(counts),
                      "bytes": args.output.stat().st_size}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
