# 関連作業の確認記録（2026-10-03）

対象期間は2026-09-03〜2026-10-03（JST）。確認対象は本リポジトリと
`/home/inaho-omen/Project/low_cost_robot` の `docs/`、`temp/`、`diary/`、
`studies/`、`skills/`、`.codex/skills/`、入口文書、および関連する保存会話ログ。

最新の実作業は **2026-09-26**。本リポジトリの最後のコミットは同日21:44 JSTの
`47b52a5`（低配置D405研究の取り込み、PR #4）。Onshape会話の9月30日12:41 JSTの
追記は、9月26日に起動したマニュアル配信用HTTPサーバーの終了記録であり、
その日に新しい設計を実施した証拠ではない。

## 直近の作業と到達点

| 日付（JST） | 作業 | 到達点・残件 |
|---|---|---|
| 9/18 | low_cost_robotのCAD生成器をレビュー | 凸外周を穴と誤認、Y方向加工の符号、CLIの誤正常終了を是正。63試験成功の記録。XL430置換形状自体は原形非同等で未承認。 |
| 9/19 | 混在サーボ幾何改訂と全XL430版を分離 | 混在版7部品の再生成・印刷パッケージを確認。全XL430版は外部干渉54組を再現し、未承認隔離と印刷停止ゲートを追加。別のR3印刷案件では7部品・0.16 mm G-codeの媒体保存記録がある。 |
| 9/22 | 全XL430の組立・締結・配線と応急アイドラを調査 | J4配置のみの補正で外部干渉54→46組。旧一体つば案は挿入工程不成立。金属筒＋PLA案内筒の外側支持案を別候補で検証。P05カメラジグ、MuJoCo/AprilGridの合成校正も整備。全体の実機成立は未達。 |
| 9/23 | PG2/PG3取込・全腕組付け・自己監査 | ラック概念案の全DoD達成宣言を撤回。PG2は単体診断、PG3 C9は全腕へ統合。旧P06支持部との干渉、クランクB-rep、締結・工具・挿入工程、遮蔽を個別検査。旧r5は後続要求の完成形ではない。 |
| 9/24 | ID5単独開閉へ変更、上方D405 R5を作成 | ロール不要・追加モーターなし。P05局所配線窓r2、全腕STEP/headless可視化。D405 R5は俯角65°、M3穴を追加。ユーザー指示による試作用G-codeとSD保存の記録あり。実機装着・強度・実撮像の合格ではない。 |
| 9/25 | テスト高速化・締結BOM・リポジトリ整理 | 719件の記録、逐次14分06秒→約5分28秒。締結BOM草稿を追加。low_cost_robotではOrcaプリセット展開、SDK依存、temp除外を保存。 |
| 9/26 | Onshape可動モデル・URDF・カメラ低配置研究 | 75°短縮案を比較基準に、俯角30°・爪+20 mmの低配置V2を作成。パッド誤所属のV1を修復。441閉路状態と11姿勢を照合。カメラ高さは比較元より12.40 mm低いが、比較部分の250 gモーメントは9.45%増。製作承認false。 |
| 9/26 | 低配置案の検証器改善・取り込み・OCCT8追試 | 不正行列/NaN/重複姿勢/欠落所属等の誤受理を修正。固定Pixi/OCCT8.0.1環境でwheel再ビルド・再変換。対象13＋52＋20＝85試験、受領URDF/config/12 STLとのSHA一致の記録。PR #4をmainへmerge。全suiteはVTK abortで未完了。 |
| 9/26 | HN11代替M2インサート版・クーポン・6組G-code | 回転掃引と4穴集約バグを修正し22試験成功の記録。M486なし互換版、ピップで穴径識別、SD保存まで。途中の「6関節すべて装着保証」は撤回・部分達成へ訂正。クーポン結果と本体1組の確認が残る。 |

## 再開時に区別すべき記録

- 本体の指定はID5-only PG3とD405 R5。俯角30°・爪+20 mmのV2は保存された研究候補であり、
  本体の製作版へ自動採用したという記録ではない。
- `docs/HANDOFF.md`、`INSTALLATION_READINESS.md`、Sep23/24の作業書には古い構成が残る。
  更新日の後先と「旧案」「撤回」「継承FAIL/UNKNOWN」の注記を読む。
- 低配置案の別エージェントによるD7は当初、保存証跡の監査だった。その後、本リポジトリへの
  取り込み時にPixi/OCCT8の実再ビルド・再変換を行った。
  最新の入口は [取り込み記録](../../docs/D405_LOW_PROFILE_INTAKE.md) と
  [integration/verification.json](../../studies/low-profile-20260926/integration/verification.json)。
- 低配置案には既存8接触/小隙間FAIL、完成状態の台座4本の工具アクセスFAIL、720p距離基準FAIL、
  材料/公差/締結保持/配線/連続トルク/実カメラ校正のUNKNOWNが残る。
- HN11の最新状態は
  [Sep26作業書](../../related-low_cost_robot/temp/workdoc_Sep26-2026_hn11_idler_m2.md) の§7.6〜7.7。
  M02/M03/M04の締結をCADで評価した。M01/M05/M06のアイドラ側4穴は未確認。
  クーポン実測→採用径→本体1組の熱圧入・締結・無通電回転→6組再生成の順。

## ローカルスキル

本リポジトリの `skills/` は7種類。

| スキル | 用途 |
|---|---|
| cad-reverse-parametric | 原形・変更maskを守るCAD検査。汎用cadre本体。旧研究は別証跡。 |
| fdm-plate-layout | STL面の向きとXY回転を分けたプレート比較・G-code可視化。 |
| onshape-robot-workflow | UIでの取り込み、可動リンク/mate、独立再構築、姿勢STEP、URDF追跡。 |
| playwright-cli | 専用sessionのブラウザ操作。無人検査は独立headless session。 |
| write-workdoc-uv | 日本語作業書・要求分析・原子的な手順と記録。 |
| review-written-workdoc | 作業書の自己完結性・実行性・DoD・証跡のレビュー。 |
| start-work-with-docs | 正本を選び、未チェックの1項目ずつ実行・即時記録。 |

low_cost_robotの `skills/` は4種類: cad-reverse-parametric、playwright-cli、
print-cad-validation、claude-tmux-review-bridge。
同名CADスキルでも、low_cost_robot版は既存XL430等のstudyを含み、本リポジトリの汎用版と異なる。
`.codex/skills` は本リポジトリが3入口、low_cost_robotが2入口。
SKILL.mdの実体、SHA、参照文書・リンクは [skill_inventory.json](skill_inventory.json) に保存した。
Playwright文書にある未存在のsnapshotパスはコマンド出力の例で、必須参照欠落ではない。

## 会話JSONと読み方

`agent-jsonl-compact 0.2.0` を使用。ファイルの開始日ではなくイベント時刻で期間を絞った。
Codexは`--channel both`、本文/ツール出力の文字数切詰めなし。
このバイナリが省略する`custom_tool_call/output`と端末CommandExecutionの詳細は追加抽出した。
日付外記録の除外、標準のノイズ除去・連続重複の圧縮はあるため、生ログ完全コピーではない。

| *_clean.json | 内容 |
|---|---|
| codex_019e686d-0cbb-7f52-9c53-33bd5b53573d_clean.json | 5月開始、9/18〜19のCADレビュー・改訂・引継ぎ部分。 |
| codex_019eb98a-eff0-7bb1-ab4b-d49bed4e487a_clean.json | 6月開始、9/21〜24のアーム・グリッパ・校正・ID5変更部分。 |
| claude_code_0b891917-c2aa-4eef-9022-6e2c4183202a_clean.json | アーム・カメラ・BOM・応急アイドラのレビュー。ログ上の日付は9/24〜25。 |
| codex_01a0daf1-5f35-77d3-8bde-8c2083f4a7e2_clean.json | 9/26のHN11作業書・レビュー、D405取り込み・追試・merge。 |
| codex_01a0db03-03f0-7ee2-86eb-190be07bc5a6_clean.json | 9/26のOnshape・カメラ比較・爪延長・Pixi/OCCT8・URDF。9/30のサーバー終了も保存。 |
| opencode_ses_f48290b12fferauv0CBfrZC3SD_clean.json | 9/19のアーム改訂・印刷配置・G-code準備。 |
| opencode_ses_f230d9c31ffeosnKOd9eGp9t4V_clean.json | 9/26のHN11実装・追加レビュー修正・クーポン。後半の別話題も同セッション内で保持。 |
| codex_saved_20260919_cad_activity_clean.json | 以前の可視会話80件の限定snapshot。原本からの新規抽出とは別扱い。 |

OpenCodeの保存元はSQLiteで、スキルのバイナリが対応するrun JSONLとは異なる。
2件はDBを読み取り専用で開き、会話textとtool状態をJSON化した。バイナリで変換したとは表示しない。
関連期間内のCodex/Claudeは今回再抽出。既存の `temp/clean.json` 等は変更していない。

[clean_index.json](clean_index.json) が出所・期間・件数の一覧。
各`extracts/*.summary.json`、`*.transcript.md`、`*.clean.jsonl`も保持する。
currentセッション、statuslineだけの会話、SSD確認、KiCadのみの会話を対象履歴から除外した。
既存session_extractsにある9/18の3ログはtomato_perception_evaluationの柱検出案件だったため、
保存場所だけを根拠にロボットCAD履歴へ混ぜていない。

## 調査範囲と今回の変更

[document_inventory.json](document_inventory.json) にテキスト文書1,117件、SHAが異なる421件を登録。
これはアーカイブ写し、第三者参考資料、スキル文書、古い6月資料も含む件数。
各文書の全文をテキスト走査し、SHAで同一写しを識別し、見出し・項目・作業記録を整理した。
人間向け結論は主要設計書・作業書・後続レビュー・Git履歴・会話の照合に基づく。
全421文書の各行について工学的再検証を実施したという意味ではない。

今回作成したのは本ディレクトリ内の索引、会話抽出、調査用スクリプトと本記録のみ。
CAD生成、印刷/媒体書込み、実機操作、元文書/スキル編集、commit/pushは行っていない。
確認前からあった `.serena/` とlow_cost_robotのHN11関連未追跡4ファイルを保持した。
