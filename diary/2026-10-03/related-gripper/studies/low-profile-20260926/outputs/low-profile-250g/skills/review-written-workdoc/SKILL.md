---
name: review-written-workdoc
description: >-
  Review Japanese workdoc Markdown files for whether another user or agent can
  understand the context and execute the work without ambiguity. Use when the
  user says review_written_workdoc, asks to review or audit a workdoc, 作業書,
  作業計画書, 作業記録, or asks whether goal analysis, work elements, definitions
  of done, atomic checklists, phase separation, TDD guidance, error handling, and
  traceability are self-consistent, self-contained, and well-defined. By default,
  after reviewing, apply safe improvements to the workdoc unless the user
  explicitly asks for review-only/no-edit behavior.
---

# Review Written Workdoc

Review an existing workdoc as an audit agent, then improve it by default. Prioritize whether another agent can execute the work without hidden context, ambiguous steps, or missing completion criteria.

## Required Reference

Read `references/review-rubric.md` before reviewing. Use it as the canonical checklist for scoring and findings.

## Workflow

1. Read local repository instructions first, including `AGENTS.md`, `CODEX.md`, and any referenced files. Follow command wrappers such as `rtk` when required.
2. Locate the target workdoc:
   - If the user gives a path, review that file.
   - If the user does not give a path, search `temp/` for `workdoc_*.md` and review the newest one by modification time.
   - If multiple likely files exist and no intent is clear, state the candidates and choose the newest only when that is a reasonable assumption.
3. Read the whole target workdoc. If needed, inspect nearby repository files referenced by the document to verify whether commands, paths, tests, and claims are concrete.
4. Review for executable clarity, not prose polish. Treat missing context, vague steps, untestable completion criteria, mixed phases, and traceability gaps as findings.
5. Lead with findings ordered by severity. Use file references with exact lines when possible.
6. Decide an initial overall verdict:
   - `PASS`: Another agent can execute the work with only minor improvements.
   - `PASS_WITH_NOTES`: Usable, but has non-blocking clarity or audit gaps.
   - `REVISE`: Ambiguities or missing details would likely block execution.
   - `FAIL`: The workdoc is not self-contained or materially contradicts the requested goal.
7. Unless the user explicitly asks for review-only/no-edit behavior, edit the workdoc after the review:
   - For `PASS`, do not edit unless there are obvious safe typos or formatting issues.
   - For `PASS_WITH_NOTES`, apply safe clarity/audit improvements when they do not change scope.
   - For `REVISE` or `FAIL`, fix all actionable Blocker and Major findings that can be resolved from repository context.
   - Do not invent fake completed results. If a finding requires user judgment or unavailable information, leave it as an explicit assumption/open question rather than guessing.
8. Re-read the patched workdoc and re-check the main rubric items. Report the final verdict after edits, the applied changes, and any residual findings.
9. If the user explicitly asks for review-only/no-edit behavior, do not edit. Report findings and recommended patch scope only.

## Review Priorities

Evaluate the document against these questions:

- Is the user's direct goal stated in plain language, with explicit success criteria?
- Is the goal decomposed into subgoals that map to phases, checklist items, tests, and definition of done?
- Can another agent understand the repository context, target files, commands, dependencies, and constraints without reading the original chat?
- Are planning, research, implementation, verification, and recording phases separated?
- Are checklist items atomic, ordered, verifiable, and written as one operation per step?
- Does each step include operation, expected result, test/TDD guidance, and error handling?
- Are uv and justfile expectations explicit when the project uses Python or has a `justfile`?
- Are implicit fallbacks avoided, with explicit blockage handling instead?
- Does the document support audit traceability through IDs, evidence locations, command outputs, and work log instructions?
- Is the definition of done specific enough to decide completion objectively?

## Output Format

Use this format unless the user asks for another one:

```markdown
**Verdict:** <PASS | PASS_WITH_NOTES | REVISE | FAIL>

**Mode:** <review-and-fix | review-only>

**Findings**
- <Severity> [<file>:<line>] <問題>
  <なぜ作業者/監査者にとって問題か。>
  <具体的な修正案。>

**Applied Changes**
- <自動修正した場合は、変更した章・内容・理由。review-onlyまたは修正なしなら「なし」。>

**Residual Findings**
- <修正後にも残る問題。なければ「なし」。>

**Coverage Notes**
- ゴール要求分析: <adequate / partial / missing>
- サブゴールと作業要素の対応: <adequate / partial / missing>
- 完了の定義: <adequate / partial / missing>
- チェックリスト原子性: <adequate / partial / missing>
- TDD/検証可能性: <adequate / partial / missing>
- エラー時対処: <adequate / partial / missing>
- トレーサビリティ: <adequate / partial / missing>

**Open Questions**
- <作業開始前に確認すべきこと。なければ「なし」。>

**Recommended Patch Scope**
- <残修正がある場合、どの章をどう直すべきか。なければ「なし」。>
```

Severity labels:

- `Blocker`: Another agent is likely unable to start or complete the work.
- `Major`: Work can start, but ambiguity or missing evidence can cause wrong implementation or audit failure.
- `Minor`: Usability issue that should be improved but does not block execution.

## Editing Policy

Default behavior is review-and-fix. When editing the workdoc:

- Preserve the user's intent and the original template structure.
- Fix missing context by adding concrete repository facts, paths, commands, tests, and expected outputs.
- Replace broad checklist items with the required atomic action format.
- Keep work record caution notes intact.
- Do not invent fake completed results. Mark unknowns as explicit assumptions or investigation steps.
- Prefer narrow, auditable patches over rewriting the whole document.
- Do not apply edits when the user says review-only, no-edit, audit only, レビューだけ, or equivalent.
- If a fix would require choosing between multiple valid product directions, do not guess. Add an explicit open question or assumption instead.
