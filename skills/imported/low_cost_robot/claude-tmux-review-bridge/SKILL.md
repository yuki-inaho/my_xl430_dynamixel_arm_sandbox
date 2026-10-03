---
name: claude-tmux-review-bridge
description: Run and document tmux-hosted Claude Code review loops from Codex, including dangerous/model selection, agmsg or tmux message delivery, robust long-output capture with /copy or files, review triage, retesting, git notes, and reusable postmortem tips. Use when asked to have Claude review work from a background tmux session, coordinate Codex-Claude handoff, capture Claude output reliably, or improve review-loop workdocs.
---

# Claude Tmux Review Bridge

Use this skill to run a peer review loop where Codex drives or coordinates a Claude Code session in tmux, then triages findings back into the repository. Keep the workflow reproducible: prompts, reviewer output, adopted changes, rejected changes, tests, and notes should all be recoverable without relying on a visible terminal scrollback.

## Workflow

1. Confirm scope and repository state.
   - Read local agent instructions first.
   - Check `git status --short --branch` in every repository that may be edited.
   - If the project requires a command wrapper such as `rtk`, use it for every shell command.

2. Choose the communication path.
   - Prefer `agmsg` when both agents are registered and the task benefits from ongoing message exchange.
   - Use direct tmux input for a one-shot review prompt.
   - For long reviewer output, prefer file output or Claude Code `/copy`; use `tmux capture-pane` only as a fallback.

3. Start or reuse a Claude Code tmux session.
   - Start in the target repository, not the coordinator repository.
   - If an explicit model or unsafe mode is requested, pass those flags exactly.
   - If Claude fails with invalid credentials caused by an inherited environment variable, restart without that variable. Do not print token values.

   ```bash
   tmux new-session -d -s <session> -c <target-repo> \
     'env -u CLAUDE_CODE_OAUTH_TOKEN claude --dangerously-skip-permissions --model fable'
   ```

4. Send prompts safely.
   - Write substantial prompts to a file first.
   - Use `tmux load-buffer` and `tmux paste-buffer` rather than shell-quoting a large prompt inline.
   - Include the exact files, requested verdict format, tests already run, and expected severity format.

5. Capture the reviewer response without truncation.
   - Best: ask Claude to write its review to a repository-local temp file and then read that file.
   - Good: ask Claude to use `/copy`, then read the system clipboard from Codex.
   - Fallback: use a large tmux history and `capture-pane`, but treat it as incomplete until checked.

   Clipboard readers to try in order:

   ```bash
   xclip -selection clipboard -o
   wl-paste
   xsel --clipboard --output
   pbpaste
   ```

6. If using agmsg, use only agmsg scripts.
   - Never directly edit agmsg DB, config, or team files.
   - Run `join.sh`, `whoami.sh`, `team.sh`, `send.sh`, `inbox.sh`, and `delivery.sh`.
   - Avoid parallel agmsg writes or join operations; sequential calls avoid SQLite/team-config races.
   - For Codex, prefer `turn` or `off` delivery. For Claude Code, use `monitor` only when the session should receive live messages.

7. Triage findings before editing.
   - Classify each item as adopted, rejected, or deferred.
   - Adopt only findings that are in scope, justified by code, and worth the change.
   - If Claude edits files directly, Codex must inspect the diff before accepting it.

8. Revalidate after adopted changes.
   - Rerun the narrow test first.
   - Rerun broader test/build checks when shared runtime, config, or user-facing behavior changed.
   - Record warnings separately from failures.

9. Record evidence.
   - Update the workdoc with review prompt path, reviewer verdict, adopted/rejected items, tests, cleanup, and residual risks.
   - Add git notes when useful for long review context that should not clutter the commit message.
   - Keep generated local agent files out of commits unless the user explicitly wants them tracked.

## Git Notes

Use git notes for review provenance, not for essential build instructions. A good note includes:

- reviewer identity and model
- workdoc/design doc paths
- high-signal test results
- adopted findings
- known caveats

Recommended pattern:

```bash
git notes add -m "$(cat <note-file>)" <commit>
git push origin refs/notes/commits
```

If a note already exists, append or force only after reading it:

```bash
git notes show <commit>
git notes append -m "$(cat <note-file>)" <commit>
```

## Reusable Lessons

Read `references/review-loop-lessons.md` when planning or debugging a review loop.
