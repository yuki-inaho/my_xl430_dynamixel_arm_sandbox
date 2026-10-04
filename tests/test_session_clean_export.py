"""End-to-end exporter coverage through the real compact reader."""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/session-clean-export/scripts/bundle_clean_json.py"
spec = importlib.util.spec_from_file_location("clean_export", SCRIPT)
exporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exporter)


def raw_fixture(path, records):
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n")
    return path


def test_codex_api_user_is_exported(tmp_path):
    path = raw_fixture(tmp_path / "codex.jsonl", [
        {"type": "session_meta", "payload": {"id": "offline", "cwd": "offline"}},
        {"type": "response_item", "payload": {"type": "message", "role": "user",
            "content": [{"type": "input_text", "text": "API user must survive"}]}},
    ])
    _, events = exporter.extract(path, tmp_path, "codex")
    assert sum(e["kind"] == "api_user" for e in events) == 1


def test_repeated_codex_users_are_not_deduplicated(tmp_path):
    user = {"type": "response_item", "payload": {"type": "message", "role": "user",
            "content": [{"type": "input_text", "text": "repeat this instruction"}]}}
    path = raw_fixture(tmp_path / "codex.jsonl", [
        {"type": "session_meta", "payload": {"id": "offline", "cwd": "offline"}}, user, user
    ])
    _, events = exporter.extract(path, tmp_path, "repeat")
    assert sum(e["kind"] == "api_user" for e in events) == 2


def test_claude_user_and_midturn_queue_both_survive(tmp_path):
    records = [
        {"type": "user", "sessionId": "offline", "message": {
            "role": "user", "content": "Claude direct user"}},
        {"type": "queue-operation", "operation": "enqueue", "content": "during turn"},
        {"type": "queue-operation", "operation": "enqueue",
         "content": "<task-notification>background</task-notification>"},
    ]
    path = raw_fixture(tmp_path / "claude.jsonl", records)
    summary, events = exporter.extract(path, tmp_path, "claude")
    extra = exporter.supplemental(records, summary["format"])
    assert sum(e["kind"] == "user" for e in events) == 1
    assert [e["kind"] for e in extra] == ["mid_turn_user_message", "queued_system_notification"]


def test_missing_user_coverage_is_rejected():
    records = [{"type": "response_item", "payload": {
        "type": "message", "role": "user", "content": [{"type": "input_text", "text": "keep"}]}}]
    with pytest.raises(SystemExit):
        exporter.validate_user_coverage(records, "codex", [])


def test_codex_terminal_and_api_channels_are_both_covered(tmp_path):
    records = [
        {"type": "session_meta", "payload": {"id": "offline", "cwd": "offline"}},
        {"type": "event_msg", "payload": {"type": "user_message", "message": "terminal"}},
        {"type": "response_item", "payload": {"type": "message", "role": "user",
            "content": [{"type": "input_text", "text": "API"}]}},
    ]
    path = raw_fixture(tmp_path / "both.jsonl", records)
    summary, events = exporter.extract(path, tmp_path, "both")
    assert exporter.validate_user_coverage(records, summary["format"], events)["verified"]
    assert {e["kind"] for e in events} >= {"user", "api_user"}
