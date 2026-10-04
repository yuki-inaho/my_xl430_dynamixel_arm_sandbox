# 2026-10-03 作業記録・作業書の保存版

稼働中の原本を残して日付別に保存した。Markdown/HTMLの相対リンクは保存先へ調整。
会話JSON・画像・生ログはSHA256を照合。過去の会話JSON一件のみAPIキー形式の文字列2か所を伏せた。詳細は[ARCHIVE.json](ARCHIVE.json)。

制御コード・テストの未commit変更は今回の保存commitに含めていない。
仕様やスキルの保存版は作業時点の記録で、現在のHEADの実装済み機能とは区別する。

## 関連するgripper側の記録

- [写真と部品版の照合](related-gripper/temp/photo-version-check_20261003/REPORT_ja.md)
- [組立マニュアル](related-gripper/temp/gripper-assembly-20261003/MANUAL.md)・[PDF](related-gripper/temp/gripper-assembly-20261003/MANUAL.pdf)
- [直近一か月の作業調査と会話JSON一覧](related-gripper/temp/recent-work-review_20261003/README_ja.md)
- [現状アーム調査](related-gripper/outputs/arm-current-audit-20261003/REPORT.md)
- [MuJoCo viewerの調査](related-gripper/outputs/current-arm-mujoco-20261003/VIEWER_REVIEW.md)

過去一か月のJSONは10月3日に行った調査の保存版として格納した。各JSON本文のイベント時刻が作業日時である。
88 MBの会話JSON一件は `*_clean.json.gz` として可逆圧縮した。`gzip -dk <file>` で展開でき、展開後のSHA256はARCHIVE.jsonのsource_sha256と一致する。
`opencode_ses_f48290b12fferauv0CBfrZC3SD_clean.json` は `[REDACTED_API_KEY]` 2か所以外の内容を保持した。原本はローカルに残し、Gitには伏せた保存版を含める。
Webから保存済みのlow_cost_robot READMEには、元から未取得のpictures画像3件へのリンクが残る。
CAD原本や実装ソースへの参照は保存した本文の根拠であり、一部は元のローカル作業場所を参照する。

## records

- [2026-10-03_current-arm-findings.md](records/2026-10-03_current-arm-findings.md)
- [2026-10-03_live-mujoco-calibration.md](records/2026-10-03_live-mujoco-calibration.md)
- [2026-10-03_package-rename.md](records/2026-10-03_package-rename.md)
- [2026-10-03_readonly-arm-setup.md](records/2026-10-03_readonly-arm-setup.md)
- [2026-10-03_typed-readonly-monitoring.md](records/2026-10-03_typed-readonly-monitoring.md)

## reports

66件の写真・生ログ・検証結果。個別ファイルはARCHIVE.jsonに列挙。

## workdocs

- [workdoc_Oct03-2026_current_arm_findings.md](workdocs/workdoc_Oct03-2026_current_arm_findings.md)
- [workdoc_Oct03-2026_current_arm_findings.review.md](workdocs/workdoc_Oct03-2026_current_arm_findings.review.md)
- [workdoc_Oct03-2026_id3_open_10deg.md](workdocs/workdoc_Oct03-2026_id3_open_10deg.md)
- [workdoc_Oct03-2026_id3_open_10deg.review.md](workdocs/workdoc_Oct03-2026_id3_open_10deg.review.md)
- [workdoc_Oct03-2026_live_mujoco.md](workdocs/workdoc_Oct03-2026_live_mujoco.md)
- [workdoc_Oct03-2026_live_mujoco.review.md](workdocs/workdoc_Oct03-2026_live_mujoco.review.md)
