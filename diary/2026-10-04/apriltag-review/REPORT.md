# OpenCode AprilTag作業のレビューと引継ぎ改善

2026-10-04、Codex単独。元会話 `ses_ef9acce07ffeYULSB0x04SUqHN` を読取専用SQLiteで照合。
ユーザー指定は36h11・別々のA4 PDF 2枚・各3×4タグ・黒枠40 mm・ID 0–11/12–23。
配置先arm_observer、OpenCV corner refine、人工画像認識、diary作業書、会話出力も確認。
元エージェントは手順18まで実行し、最終完了回答・手順19–21の証拠が未記録だった。

## 発見・改善

| 指摘 | 修正と証拠 |
|---|---|
| 印刷指示が「100%・実寸も無効」で誤り | 実寸を選び、自動拡縮のみ無効に修正。 |
| NaN/Infinityの寸法、負のID・ぼけ指定等 | 成果物を生成する前に明示拒否。CLIの異常入力試験を追加。 |
| 非整数px/mmで黒セルの継ぎ目が白くなる | 始点と終点を同じ物理座標から丸める。5.3px/mmの外枠連続性と全ID検出を確認。 |
| cv2.imwrite失敗を無視 | 保存失敗は終了コード1、成功JSONを作らない。失敗注入で検証。 |
| コード表の出典・配布条件が未収録 | 公式commitとSHA256を固定、24コードと36座標を実ソースに照合。families.pyに配布条件を保持。 |
| CLIの採点・入出力混在 | 採点を小さな関数に分離、複雑度15→10。 |
| 重複する生成/hash・全ID/RMSテスト | それぞれ一回の処理で両方を確認。全24 IDとOpenCVの独立比較は維持。 |
| 人工描画だけではPDF実体を検査していない | Popplerで実PDFを画像化し、MediaBox、全24 ID、40 mm外枠、100 mmバーを検査。 |
| OpenCodeの会話JSONが未出力 | 130メッセージ・ユーザー8件・質問の選択回答を保持。reasoning81件は明示除外。共通秘密伏字を使用、今回伏字0件。 |

## 成果物と検証

- [A4 Sheet 1 / ID 0–11](apriltag_36h11_a4_sheet_1_ids_000-011.pdf)
- [A4 Sheet 2 / ID 12–23](apriltag_36h11_a4_sheet_2_ids_012-023.pdf)
- [SHA256 manifest](sheets.json)、[PDF実体検査](pdf_validation.json)、[画像付きHTML](index.html)
- [人工検証1](verify-sheet-1/synthetic_verify.json)、[人工検証2](verify-sheet-2/synthetic_verify.json)
- [公式ソース照合](upstream_validation.json)、[コード複雑度](code_quality.json)
- [会話clean JSON](../conversations/opencode-apriltag-20261004_clean.json)
- [元作業書](../workdocs/workdoc_Oct04-2026_apriltag_a4_sheet.md)、[追補作業書](../workdocs/workdoc_Oct04-2026_apriltag_followup.md)

両人工画像は透視変換・ぼけσ0.8・ノイズσ2.0・seed3、各12/12 ID、最大RMS **0.3881 px**。
閾値0.5 pxを変更していない。回転0/90/180/270°、追加ぼけ条件の試験も通過。
PDF MediaBox **595.2756×841.8898 pt**、150 dpiラスタ上のタグ辺39.963–40.132 mm、
100 mmバー100.245 mm（ラスタの2px量子化幅0.339 mm内）。印刷物の測定ではない。

全体pytest **340 passed / 21.11秒**。ruff、ty、最大複雑度**10以下**、技能形式検査は成功。
型検査が指摘したCLIのheterogeneous dictからの添字処理は、型の明らかなSheetPlanを参照して修正。
修正後の型検査と対象CLI試験を実施し、全suiteを重複実行しない。

```bash
rtk proxy uv run --no-sync arm-tag-sheet generate --output-dir diary/2026-10-04/apriltag-review
rtk proxy uv run --no-sync arm-tag-sheet verify --sheet-index 1 --output-dir diary/2026-10-04/apriltag-review/verify-sheet-1 --rms-limit 0.5
rtk proxy uv run --no-sync arm-tag-sheet verify --sheet-index 2 --output-dir diary/2026-10-04/apriltag-review/verify-sheet-2 --rms-limit 0.5
rtk proxy uv run --no-sync python diary/2026-10-04/apriltag-review/verify_pdf_artifacts.py
rtk proxy uv run --no-sync pytest -q
rtk proxy uv run --no-sync ruff check src tests scripts
rtk proxy uv run --no-sync ty check
rtk proxy uv run --no-sync scripts/check_quality.py
```

PDFの再生成ではReportLabの作成時刻によりhashが変わる。新manifestと再生成PDFを対にして照合する。
検証画像2枚は別フォルダに置き、固定名の上書きを防ぐ。Popplerはシステム依存、Python版はuv.lock固定。
OpenCode SQLiteはagent-jsonl-compactの入力形式に対応しないため、正直に専用adapterを使用。
transactionのcutoff以後の会話は含まない。選択snapshot hashはDB全体のhashとは異なる。

今回のcommit対象には先行する撮影リファクタリング・D405実データ・技能も含む。
ロボット通信・動作・印刷は行っていない。人工精度を実カメラ精度とは扱わない。
GのCAD/viewerや隣接RealSenseリポジトリのユーザー差分、既に保存した旧reports原本は対象外。
