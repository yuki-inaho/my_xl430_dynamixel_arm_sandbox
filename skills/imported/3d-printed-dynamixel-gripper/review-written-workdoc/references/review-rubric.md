# Review Rubric For Written Workdocs

Use this rubric to review a workdoc for self-consistency, self-containment, and operational clarity.

## 1. Context Completeness

The workdoc is adequate only if another agent can understand the task without the original chat.

Check:

- The direct user goal is restated in plain language.
- The work directory, repository name, and relevant project type are identified.
- Target files, directories, modules, commands, and tests are concrete.
- Required tools are explicit, especially `uv`, `just`, Docker, linters, formatters, and test runners.
- Constraints are explicit: no implicit fallback, DRY/KISS/SOLID, t-wada TDD, traceability, and auditability.

Finding triggers:

- Blocker: The target task or repository context is unclear.
- Major: Important files, commands, or assumptions are generic placeholders.
- Minor: Context exists but could be easier to scan.

## 2. Goal Requirement Analysis

The document must connect user intent to executable work.

Check:

- The goal analysis appears directly under `## 1. 作業目的`.
- It contains intuitive user purpose, explicit requirements, implicit constraints, non-goals, success criteria, risks, and assumptions.
- The analysis is specific to the requested task, not template boilerplate.
- Success criteria are objective and testable.

Finding triggers:

- Blocker: No goal analysis, or it contradicts the work plan.
- Major: Missing success criteria, non-goals, or constraints.
- Minor: Correct content exists but traceability labels are weak.

## 3. Subgoal And Traceability Mapping

Work elements must be traceable from goal to evidence.

Check:

- Subgoals have IDs such as `SG-1`.
- Requirements or constraints have trace IDs such as `TR-1`.
- Phases, checklist items, tests, commands, and definition-of-done items refer to those IDs.
- Evidence expectations are clear: logs, test commands, changed files, screenshots, or work record entries.

Finding triggers:

- Blocker: No way to tell whether a requirement is covered.
- Major: IDs exist but are not connected to concrete steps or evidence.
- Minor: Mapping exists but is sparse or inconsistent in naming.

## 4. Phase Separation

Planning, research, implementation, verification, and recording must not be mixed.

Check:

- Research/design steps inspect and decide; they do not perform code changes.
- Implementation steps are only after research/design gates.
- Verification steps run tests, lint, format, type checks, E2E, or manual checks.
- Work record instructions are separate from action steps and preserve caution notes.

Finding triggers:

- Blocker: The order could cause unsafe implementation before required discovery.
- Major: Implementation tasks are embedded in research or verification is mixed with coding.
- Minor: Headings are slightly unclear but execution order is still safe.

## 5. Atomic Checklist Quality

Every checklist item should be one unambiguous operation.

Required form:

```markdown
### 手順 n: <目的を端的に>
- [ ] 🖐 **操作**: <コマンド／編集内容など>
- [ ] 🔎 **確認**: <期待結果>
- [ ] 🧪 **テスト**: <テストケース名／初期失敗・後成功の確認方法>
- [ ] 🛠 **エラー時対処**: <代表的なエラーと解決策>
```

Check:

- Each step performs one operation.
- Dependencies are ordered.
- Expected results are concrete.
- Test/TDD guidance is present or explicitly justified as not applicable.
- Error handling is specific, not "確認する" only.

Finding triggers:

- Blocker: Checklist is missing or too vague to execute.
- Major: Steps combine multiple operations, omit tests, or omit expected results.
- Minor: Steps are usable but could be split further.

## 6. TDD And Verification

Testing guidance should let an agent observe fail-to-pass behavior when feasible.

Check:

- New behavior has named tests or test files.
- The expected initial failure is described before implementation.
- The passing command is concrete, preferably `uv run pytest ...`.
- Quality gates are explicit: lint, format, type checks, build, or project-specific just targets.
- Manual verification has expected observations.

Finding triggers:

- Blocker: There is no credible verification for user-facing or risky changes.
- Major: Tests are generic commands without target, expected result, or fail-to-pass plan.
- Minor: Verification exists but could be narrower or faster.

## 7. Error Handling And No Implicit Fallback

Errors must be anticipated and routed through explicit decisions.

Check:

- Common command failures have likely causes and next steps.
- Missing files, missing dependencies, absent Git repository, absent justfile, or absent uv lock are handled explicitly.
- The document does not say to silently use an alternative path, tool, or behavior.
- Blockers instruct the agent to record evidence and ask/stop when necessary.

Finding triggers:

- Blocker: The plan depends on silent fallback or hidden assumptions.
- Major: Error handling is present but too generic to guide recovery.
- Minor: Rare error cases are not covered.

## 8. Definition Of Done

Completion criteria must be objective.

Check:

- Each item is checkable with a command, artifact, diff, or explicit observation.
- The definition of done maps to goal analysis and trace IDs.
- It includes documentation/work record completion when auditability is required.
- It does not use vague criteria like "properly", "as needed", or "確認する" without expected result.

Finding triggers:

- Blocker: No objective completion criteria.
- Major: Criteria exist but do not cover the stated goal.
- Minor: Criteria are good but not fully mapped to trace IDs.

## 9. Review Verdict Guidance

Use the strictest applicable verdict:

- `PASS`: No Blocker/Major findings; at most small Minor notes.
- `PASS_WITH_NOTES`: No Blocker findings; one or more Minor findings, or a low-risk Major with a clear workaround already in the doc.
- `REVISE`: Any Major finding that could cause wrong work, audit gaps, or repeated clarification.
- `FAIL`: Any Blocker finding, or multiple Major findings that make the workdoc unreliable.
