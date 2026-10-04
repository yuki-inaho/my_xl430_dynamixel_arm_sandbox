---
name: git-commit-push
description: Commit and push a local workspace safely, including a never-committed repository and a remote the user just created (for example a pasted GitHub quick-setup block). Audits staged content for secrets, key material, oversized or generated files and conversation exports, stages by purpose, writes attributed commit messages, pushes without force and verifies the remote. Use for "commit & push", "コミットしてpush", "ここにpushして", "リポジトリ作ったのでpush".
---

# Git commit and push

Use when the user asks to commit and push, including the first push of a workspace that has
never been committed. The user may create the remote themselves; this skill covers everything
else. Do not create, rename, delete or change the visibility of remote repositories unless the
user explicitly asks.

## 1. Inspect before touching anything

```bash
rtk proxy git status --short --branch
rtk proxy git log --oneline -5          # "does not have any commits yet" means a first commit
rtk proxy git remote -v
rtk proxy git config user.name; rtk proxy git config user.email
```

Check whether other agents or people are working in the same tree (running agent processes,
recently staged files you did not stage, new commits on the branch). Never reset, stash, or
overwrite their changes; commit only paths you can account for. Keep unrelated repositories
(for example a neighbouring project you also edited) out unless the user asked for them.

## 2. Translate a pasted quick-setup block

GitHub's "create a new repository" page suggests `echo "# name" >> README.md`, `git init`,
`git add README.md`, `git commit -m "first commit"`, `git branch -M main`,
`git remote add origin <url>` and `git push -u origin main`. Treat that as the target URL and
branch, not as commands to replay: appending to an existing README or committing only the
README would be wrong. Keep the existing history and files, ensure the branch is `main`, add or
verify `origin`, then commit and push the real content.

## 3. Check the remote before the first push

```bash
rtk proxy gh repo view OWNER/REPO --json visibility,isEmpty,defaultBranchRef
rtk proxy git ls-remote <url>            # empty output means an empty remote
```

- If the remote is public, confirm nothing private is about to be published: copies of
  private repositories, conversation logs, local credentials. Ask before pushing such content
  to a public repository.
- If the remote is not empty and shares no history with the local branch, stop and ask.
  Never `--force` unless the user explicitly asks for it.

## 4. Prepare ignore rules and stage by purpose

Ignore virtualenvs, caches, build outputs and local tool state (`.venv/`, `__pycache__/`,
`.pytest_cache/`, `.ruff_cache/`, `target/`, `.serena/`, `.playwright-cli/`, `.env`). Keep
project-local skills and records the user wants versioned. Stage explicit paths, then review:

```bash
rtk proxy git add <paths>
rtk proxy git diff --cached --stat | tail -5
rtk proxy python skills/git-commit-push/scripts/precommit_audit.py --json /tmp/audit.json
```

The audit reads only staged blobs. Blockers (secret-like strings, private keys, files at or
above the block size, default 50 MB; GitHub rejects files above 100 MB) must be fixed before
committing. Warnings (large files, e-mail addresses, absolute home paths, conversation
exports, binaries) need a deliberate decision. Conversation exports are only committed when
the user asked for them, and only to a private remote unless they say otherwise.

Before the first commit there is no HEAD: `git restore --staged` and `git reset <path>` fail,
so unstage with `git rm --cached <path>`. Run each commit as its own step and check its exit
status; never chain a commit after a step that can fail with `;`, or the next commit will
swallow everything still staged. If that happens before pushing, `git update-ref -d HEAD`
removes a mistaken root commit while keeping the index; inspect, then commit again.

For a first commit of a large workspace, split commits by purpose when it helps review
(source and tests, records and reports, exported conversations). Do not invent history that
did not happen; a single initial commit is fine when the parts are intertwined.

## 5. Commit message

Use a concise imperative summary (Conventional Commits style when the repo uses it), a body
that lists what is included and what was deliberately excluded, and the attribution trailer
lines required by the environment (for example `Co-Authored-By: ...`). Pass the message with
a heredoc so line breaks survive. Never use `--no-verify` to skip hooks; fix the hook failure.

## 6. Push and verify

```bash
rtk proxy git push -u origin main
rtk proxy git status -sb                  # "## main...origin/main" with no ahead/behind
rtk proxy git ls-remote origin            # remote head equals `git rev-parse HEAD`
```

If HTTPS authentication fails, run `gh auth setup-git` (or use the URL the user gave); if SSH
fails with publickey, switch the remote to HTTPS rather than generating keys. Report the
pushed commits (hash and subject), the remote URL and visibility, what was excluded and why,
and anything left untracked or unpushed.
