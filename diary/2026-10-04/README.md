# 2026-10-04 作業記録・作業書の保存版

稼働中の原本を残して日付別に保存した。Markdown/HTMLの相対リンクは保存先へ調整。
会話JSON・画像・生ログは原本とSHA256を照合。詳細は[ARCHIVE.json](ARCHIVE.json)。

制御コード・テストの未commit変更は今回の保存commitに含めていない。
仕様やスキルの保存版は作業時点の記録で、現在のHEADの実装済み機能とは区別する。

## 最後の実機状態

スタンバイへ段階移行後、元姿勢へ戻し全TorqueOFFとRAM復元を確認。
13:06にユーザーが電源OFFを報告。以後モーター通信なし、実機作業は一時停止。
精密校正・支持荷重経路・全域自己干渉・校正済live描画は未完了。

[画像入りHTMLレポート](reports/robot-completion-20261004/standby-record-html/REPORT.html)

181MB/212MBの元動画2件はサイズ制限によりローカルに残した。
写真frame・画像入りHTML・元動画の場所とSHA256は保存している。

## conversations

- [2026-10-04_claude_session_c1ea256b_clean.json](conversations/2026-10-04_claude_session_c1ea256b_clean.json)
- [diary-archive-20261004_codex_clean.json](conversations/diary-archive-20261004_codex_clean.json)
- [robot-completion-20261004_codex_clean.json](conversations/robot-completion-20261004_codex_clean.json)
- [standby-record-20261004_codex_clean.json](conversations/standby-record-20261004_codex_clean.json)

会話JSONは書き出し時点のスナップショット。今回の保存依頼を含む最新exportにも、その後のcommit/push結果は含まれない。
日誌にある実装行番号のリンクは作業時点のコードを参照するため、記録のdiff証拠も併読すること。

## records

- [2026-10-04_delivery-review.md](records/2026-10-04_delivery-review.md)
- [2026-10-04_id3-open-10deg.md](records/2026-10-04_id3-open-10deg.md)
- [2026-10-04_standby-physical-run.md](records/2026-10-04_standby-physical-run.md)

## reference-docs

- [STANDBY_POWER_OFF_POSITIONS.md](reference-docs/STANDBY_POWER_OFF_POSITIONS.md)
- [id3_motion_spec.md](reference-docs/id3_motion_spec.md)
- [readonly-architecture.md](reference-docs/readonly-architecture.md)

## reports

601件の写真・生ログ・検証結果。個別ファイルはARCHIVE.jsonに列挙。

## reproduction

- [build_standby_record_report_20261004.py](reproduction/build_standby_record_report_20261004.py)
- [validate_camera_id3_run.py](reproduction/validate_camera_id3_run.py)
- [measure_elbow_image_phase.py](reproduction/measure_elbow_image_phase.py)

## skill-notes

- [SKILL.md](skill-notes/robot-park-pose-definition/SKILL.md)
- [r3-lessons.md](skill-notes/robot-park-pose-definition/references/r3-lessons.md)
- [SKILL.md](skill-notes/robot-live-calibration/SKILL.md)
- [verification-matrix.md](skill-notes/robot-live-calibration/references/verification-matrix.md)
- [SKILL.md](skill-notes/bounded-servo-motion/SKILL.md)
- [lessons.md](skill-notes/bounded-servo-motion/references/lessons.md)
- [SKILL.md](skill-notes/dynamixel-readonly-status/SKILL.md)
- [SKILL.md](skill-notes/session-clean-export/SKILL.md)
- [SKILL.md](skill-notes/git-commit-push/SKILL.md)

## workdocs

- [workdoc_Oct04-2026_delivery_review.md](workdocs/workdoc_Oct04-2026_delivery_review.md)
- [workdoc_Oct04-2026_delivery_review.review.md](workdocs/workdoc_Oct04-2026_delivery_review.review.md)
- [workdoc_Oct04-2026_robot_completion.md](workdocs/workdoc_Oct04-2026_robot_completion.md)
- [workdoc_Oct04-2026_robot_completion.review.md](workdocs/workdoc_Oct04-2026_robot_completion.review.md)
- [workdoc_Oct04-2026_standby_power_off.md](workdocs/workdoc_Oct04-2026_standby_power_off.md)
- [workdoc_Oct04-2026_standby_power_off.review.md](workdocs/workdoc_Oct04-2026_standby_power_off.review.md)
