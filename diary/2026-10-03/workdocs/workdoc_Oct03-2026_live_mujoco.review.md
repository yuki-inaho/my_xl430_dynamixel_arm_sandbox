# live MuJoCo作業書レビュー
Initial Verdict: REVISE
Final Verdict: PASS
Mode: review-and-fix
Reviewer: Codex自己レビュー（独立subagentではない）。

対象: [workdoc](workdoc_Oct03-2026_live_mujoco.md)
Major修正: 実機未校正とソフトの受け口完了を区別し、DoDに物理校正の残件を明記。校正検証にsession/metadata/torque/staleと符号・wrapを加えた。
Major修正: HTTP起動時無通信、有限実測、所有者保持、停止中の閉鎖状態とfinallyを明文化。
Minor修正: JSONL v2と新HTTP envelopeを区別、既存試験と品質gate、正負synthetic対照の位置を具体化。

rubricのゴール分析・SG/TR対応・四行原子性・TDD・実行コマンド・エラー対処・証跡・DoDを確認。全8手順×4行、DoD4項目。未知の実物値を前提にせず独立作業を進められる。
Residual findings: 実物の校正値はユーザーの現物確認が必要。本実装はその入力画面を含む。動作範囲の安全認定とは別。
Recommended patch scope: なし。指定の順序でRED→実装→検証し、チェックを一つずつ進める。

