# Skills

このディレクトリが、このプロジェクトで作成・改善したスキルの正本です。Claude Code は
`.claude/skills/<name>`、Codex は `.codex/skills/<name>` のリンクから発見します（リポジトリ内の
相対リンクで、グローバル登録はしません。`dynamixel-readonly-status` だけは従来どおり
`~/.codex/skills` からもリンクしています）。

| スキル | 用途 |
|---|---|
| `dynamixel-readonly-status/` | 5台の XL430 を PING・READ・検証済み SYNC_READ だけで点検・監視する |
| `robot-live-calibration/` | エンコーダ値を CAD/MuJoCo 姿勢へ反映する viewer・校正 UI と、手で動かした向きの2点記録 |
| `bounded-servo-motion/` | 1関節だけの限定動作（例: ID3 を約10°開く）の設計・検証・実行。知見は `references/lessons.md` |
| `git-commit-push/` | 初回 commit を含む commit & push。公開前の監査スクリプト `scripts/precommit_audit.py` |
| `session-clean-export/` | Claude Code / Codex の会話 JSONL を、確認済みの `*_clean.json` に書き出す |

`imported/low_cost_robot/` と `imported/3d-printed-dynamixel-gripper/` には、各プロジェクトの
スキルを出典別に保存しています。同名スキルも混ぜず、元の説明・コード・参照資料を保持します。
取り込んだスキルを使うときも、このプロジェクトの AGENTS.md（実機は読み取り専用。例外は
ID3 の限定動作だけ）が優先されます。コピーしたスキルはグローバル登録しません。

出典・コピー対象・ハッシュ・除外条件は `../upstream/import_manifest.json` に記録しています。
関連スクリプトと Python モジュールは `../upstream/` にあります。
