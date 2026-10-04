---
name: session-clean-export
description: Export a Claude Code or Codex session JSONL as one reviewed `*_clean.json` bundle (faithful agent-jsonl-compact events plus the records the extractor skips, secret redaction, input hash) and place it where the user wants, for example under diary/. Use for "会話を*_clean.jsonで保存", "agent jsonスキルでclean.jsonを作成", handoff conversation exports.
---

# Session clean export

Builds on the `agent-jsonl-compact-reader` skill (binary `agent-jsonl-compact`). Use this skill
when the user wants a single `*_clean.json` file of a conversation, typically for a handoff or
a diary record.

## Locate the session

- Claude Code: `~/.claude/projects/<cwd-slug>/<session-uuid>.jsonl`. The current session's
  uuid is the scratchpad or transcript directory name.
- Codex: `~/.codex/sessions/YYYY/MM/DD/rollout-*-<thread-id>.jsonl`.

The current session keeps growing; the script snapshots complete lines first, so the bundle
ends a few records before the final reply. Say so when reporting. A forked session file may
contain only the current branch plus a history pointer. Inspect that pointer and state the
covered branch/cutoff; do not claim the ancestor conversation was reconstructed unless those
source files were separately located, exported and checked.

## Export

```bash
python skills/session-clean-export/scripts/bundle_clean_json.py \
  --session <session.jsonl> --output diary/<date>_<agent>_session_<id>_clean.json --name <name>
```

The script runs `agent-jsonl-compact --channel both --no-dedup` without truncation and bundles
`summary`, the normalized `events`, and `supplemental_events`:

- Claude Code messages typed while a turn was running are stored only as `queue-operation`
  enqueue records and are not in the normalized events; they become `mid_turn_user_message`.
  Background task notifications use the same queue and become `queued_system_notification`.
- Codex code-mode `custom_tool_call` / `custom_tool_call_output` records are kept verbatim.
- Both Codex terminal and API channels are retained; API users are `api_user` events.
  Repeated user instructions are preserved. The script checks source/output user counts
  separately for each channel and refuses to export if coverage differs. Claude tool-result
  records are not mistaken for direct user text; queued user/system messages stay separate.

Secret-looking strings (GitHub/Anthropic/OpenAI/AWS/Slack tokens, bearer tokens) are replaced
with `[REDACTED:<type>]` and counted in `redactions`; private key material aborts the export.
The output is validated by reading it back.

## Check before keeping or committing

- Confirm the user's own messages are present, including mid-turn ones (search a few
  distinctive phrases in `events` and `supplemental_events`).
- Encrypted or omitted reasoning cannot be recovered; do not claim otherwise.
- The bundle contains conversation text and local paths. Commit it only when the user asked,
  and prefer a private remote; run the `git-commit-push` audit on it before pushing.
