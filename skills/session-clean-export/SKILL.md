---
name: session-clean-export
description: Export a Claude Code or Codex session JSONL, or a selected OpenCode SQLite conversation, as a reviewed `*_clean.json` bundle with user coverage, secret redaction and snapshot hash. Use for "会話を*_clean.jsonで保存", "agent jsonスキルでclean.jsonを作成", handoff conversation exports.
---

# Session clean export

Builds on the `agent-jsonl-compact-reader` skill (binary `agent-jsonl-compact`). Use this skill
when the user wants a single `*_clean.json` file of a conversation, typically for a handoff or
a diary record.

## Locate the session

- Claude Code: `~/.claude/projects/<cwd-slug>/<session-uuid>.jsonl`. The current session's
  uuid is the scratchpad or transcript directory name.
- Codex: `~/.codex/sessions/YYYY/MM/DD/rollout-*-<thread-id>.jsonl`.
- OpenCode: `~/.local/share/opencode/opencode.db`。タイトル、時刻、ツールの対象パスを
  読取専用SQLで照合してsession IDを特定する。directoryだけでは対象projectを判別できない。

## OpenCode SQLiteの場合

`agent-jsonl-compact` はSQLiteや `opencode export` の単一JSONに対応しない。
JSONLへの偽装やbinaryの成功扱いをせず、専用adapterを使用する。

```bash
python skills/session-clean-export/scripts/bundle_opencode_sqlite.py \
  --database ~/.local/share/opencode/opencode.db --session-id <session-id> \
  --output temp/<session-id>_clean.json
```

原本はmode=roで開き、単一transactionで選択sessionのtext/toolとmessage metadataを保存。
質問ツールの選択回答や途中のユーザー発言も保持し、ユーザー件数を照合する。
reasoning/step metadataは明示的に除外・計数し、JSONL bundleと異なるschemaを付ける。
hashは選択snapshotを対象とし、DB全体のhashとは表記しない。秘密伏字処理は共通関数を使う。
ツール失敗や未完了の最終messageも残し、完了回答がないログを完了済みと扱わない。
実行後は件数・cutoff・選択回答を確認し、ユーザーが求めた保存先へ移す。

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

## Large reviewed bundles

Keep the requested complete `*_clean.json` locally. For an explicitly authorized private
push, a large faithful bundle can be gzip-compressed without removing messages or images.
If the compressed file still exceeds the repository audit limit, split its bytes into
ordered parts below that limit (for example 25 MB each). Save a manifest with original and
compressed SHA256, each ordered part's size/hash, source snapshot, user coverage, redaction
counts and cutoff. Concatenate parts, decompress, and check the restored JSON SHA256 before
committing. Preserve the original locally; stage only the manifest and parts. Document the
restore command and state that the snapshot ends before the final reply. Do not hide a
secret by compressing it: perform the normal redaction/private-key/coverage check first.
