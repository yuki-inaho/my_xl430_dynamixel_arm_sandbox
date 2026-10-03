# Review Loop Lessons

Use these lessons when coordinating Codex with another CLI agent.

## Output Capture

- `tmux capture-pane` is convenient but scrollback-bound. It can miss earlier parts of a long Claude response.
- Prefer asking the reviewer to write `temp/<review-name>.md` or to use Claude Code `/copy`.
- Clipboard capture works well when a graphical clipboard is available. Try `xclip`, `wl-paste`, `xsel`, then `pbpaste`.
- If clipboard capture fails, ask the reviewer for a short verdict restatement and separately preserve detailed findings in a file.

## Message Transport

- agmsg is useful for peer-agent messaging, but scripts should be called sequentially. Parallel `join.sh`, `send.sh`, or `inbox.sh` calls can hit lock or config races.
- Use `delivery.sh set off` for a Claude session that should not be interrupted while doing a focused review.
- Use `delivery.sh set monitor` only when live inbound messages are part of the workflow.

## Auth And Environment

- Claude Code sessions can inherit broken auth-related environment variables from the parent shell.
- If startup reports invalid credentials, restart with the bad variable unset. Do not print token values into logs or final answers.

## Review Hygiene

- A reviewer verdict is not a substitute for local diff review.
- Treat direct edits by another agent as untrusted until `git diff` is inspected.
- Keep review output, adopted/rejected findings, and final validation in a workdoc or git note.

## Repository Hygiene

- Generated local agent directories such as `.codex/`, `.claude/`, `.agents/`, `.playwright-cli/`, `.serena/`, and copied sample assets should not be included in application commits unless the project intentionally tracks them.
- When a local tool creates hooks or settings, record the reason in the workdoc and keep those files ignored when they are machine-local.
