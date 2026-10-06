> これは当初の実行作業書の履歴。後続の公開範囲・GitHub統合はpackageのPUBLICATION.mdを参照。全rawに関する検証はローカル成果物で実施し、公開snapshotには全rawを含めない。

# ランダム把持差分の受入・再実行 作業計画書兼記録書

日付: 2026-10-05 / 作業者: Codex / repository: my_dynamixel_arm_sandbox
対象: packages/sim-cap-grasp、skills/sim-grasp-review、diary/2026-10-05/random-grasp-review。

## 1. 作業目的
### 1.1 ゴール要求分析
ユーザーの目的は提出済みランダム把持を現在の名目シミュレーションへ取り込み、資料と実態を照合して改善すること。4受領ファイルを読み、既存保護を維持して実行可能な状態へする。ZIP2本は同一なので一方だけ検査する。
制約: uv固定環境、単独実行、実機接続なし、入力不変、閾値/物性を成功合わせで緩めない。実写・会話・元archive・絶対パスを公開成果へ含めない。既存別作業の差分は保全する。新framework/複製モデル/広範囲テストは作らない。
成功条件: 適用元を照合、ランダム入口が既存input/mesh/evaluator保護を維持、実dynamic positive/repeat/no-close、凍結した新100配置を全母数で実行、HTMLと証跡を確認。元100rawが未納品である点は未確認として区別する。
非ゴール: ハードウェア、未校正実機安全範囲、下降連続把持の新要件化、元100rawの捏造。公開pushは今回資料の非ゴールであり本作業では実行しない。
前提: 旧C7/R3モデル、固定pitch−50度、perfect simulated-state feedback、有限経路screen。原qualificationは記録上100/100、下降中91件接触喪失、84件支持箱接触前。これを穏やかな下置き成功と呼ばない。
### 1.2 サブゴール構造
|ID|成果物|検証|
|---|---|---|
|SG1/TR1 入力調査|tempの原本コピー・inventory・review|SHA/ZIP/patch適用元・差分|
|SG2/TR2 実装受入|packages/sim-cap-graspの拡張|既存保護維持、狭い検査|
|SG3/TR3 動的確認|results/review-random-*、freeze/index/raw|repeat、negative、新100集計|
|SG4/TR4 証跡|技術記録、合成HTML/画像、skill改善|ブラウザ、privacy、diff|
### 1.3 トレーサビリティ
上記IDを各手順に併記。元結果と新結果、静的filterと動的試行、完全rawと報告のみを区別。

## 2. 作業内容
調査10–20分: 元zip安全展開、22ファイルpatch比較、既存保護との差分を記録。
実装15–30分: 新モジュールを受入、evaluate変更を手動merge、CLI/hash/中断・trace読取を補修。
確認25–40分: 代表/repeat/no-close後、固定条件で新100候補4並列、1800秒上限。以後rendererと技術記録。失敗を隠さず、未達なら原因を記録して修正/別batch。

## 3. 作業チェックリスト
### 手順1: 入力・コードレビュー (TR1)
- [x] 🖐 **操作**: 元コピーをtempへ保存し安全ZIP展開、patchと報告の内容を読む。
- [x] 🔎 **確認**: 22対象と元archiveSHA一致、元100raw不足・適用方針を記録。
- [x] 🧪 **テスト**: 適用checkのみ。調査にunit追加不要。
- [x] 🛠 **エラー時対処**: 任意HEADへの強制適用をせず元snapshotコピーへcheck。
### 手順2: 拡張・保護を統合 (TR2)
- [x] 🖐 **操作**: 新ファイル追加とevaluate/QA手動merge。再利用モデルは複製しない。
- [x] 🔎 **確認**: input/mesh hash、引数検証、中断raw保持、gzip/zstd互換が維持。
- [x] 🧪 **テスト**: 提出8testsと既存integrity4tests、変更対象ruff。実欠陥には最小反例。
- [x] 🛠 **エラー時対処**: 旧改善の逆戻りを先に修正、判定/物性は維持。
### 手順3: 実物理の最小確認 (TR3)
- [x] 🖐 **操作**: 新規代表trialを実mj_step実行。
- [x] 🔎 **確認**: freecap・actuator移動・return・判定rawと独立audit一致。
- [x] 🧪 **テスト**: 同環境repeatとmatched no-close。全state一致/negative失敗。
- [x] 🛠 **エラー時対処**: 失敗raw保存、必要な制御修正後別名で再試行。
### 手順4: 新100配置を凍結・実行 (TR3)
- [x] 🖐 **操作**: 新seedでfreeze、qualificationを4並列/BLAS1・1800秒上限で実行。
- [x] 🔎 **確認**: 最初100accepted、全proposal/reject/失敗、95以上成功unsafe0とCI。
- [x] 🧪 **テスト**: batch hash/母数/全raw監査・下降補足診断。
- [x] 🛠 **エラー時対処**: 失敗の置換禁止。未達を記録しcontrollerのみ改善し別seed全batch。
### 手順5: 可視確認と記録 (TR4)
- [x] 🖐 **操作**: 新trace二視点media/HTML・technical review・再実行README・skill教訓を作成。
- [x] 🔎 **確認**: headless Playwrightでreport動作と画像を確認。
- [x] 🧪 **テスト**: 対象diff/check/privacy、結果依存の誇張なし。
- [x] 🛠 **エラー時対処**: raw不足/旧結果との違いを明示し未確認と成功を混同しない。

## 4. コマンド
packages/sim-cap-graspをcwdに uv run --no-sync python random_plan.py / random_run.py / random_study.py。uv.lock固定、既存package環境。作業のファイル変更はapply_patch。lintは変更対象のみ。

## 5. リビュー
PASS_WITH_NOTES: 元完成書はこの受領ZIPのraw納品範囲を明示。元100の独立検証は未納品で再実行と分離。Herdr/cloud専用queueは移植しない。新100は提出条件に従い一度凍結後に実行。ノンゴールにpushを明記。技術公開用文書は相対パスのみ。

## 6. 完了の定義
- [x] TR1/2: 入力来歴、コード統合、既存保護・対象品質チェック完了。
- [x] TR3: fresh positive/repeat/negative、100配置と全raw結果を保存・監査。
- [x] TR4: 二視点証跡/HTML/記録/skill、制限・不足を明記しprivate情報除外。

## 7. 作業記録
完了: 2026-10-06 00:19:25 JST+0900。全チェックリストとDoDを充足。実機接続・公開・commit/pushは行っていない。
開始・完了の時刻をdateで取得。各checkbox完了直後に記録し次へ進む。具体的command/結果/失敗/証跡を残す。開始前、フェーズ境界、行動40毎に時刻と状況を記録。各行動後k/40を表示。既存差分を上書きしない。
|日時|項目|内容・結果|
|---|---|---|
|2026-10-06 00:18:53 JST+0900|TR4 DoD|二視点5case、HTML/CSV/Playwright証跡、技術REVIEW/README/skillとportable hash inventory完了。原100未納品/下降接触喪失/実機未検証/公開なしを明記。|
|2026-10-06 00:18:53 JST+0900|TR3 DoD|代表/repeat/no-closeと標準mj_step differential/重複SIGINT control、002全100 raw独立audit PASS。001失敗/中断は固定母数で残す。|
|2026-10-06 00:18:52 JST+0900|TR1/2 DoD|4受領ファイル来歴と22差分照合、20新規統合、旧mesh/CLI/evaluator保護維持。対象ruff/skill/diff/技術privacy完了。|
|2026-10-06 00:18:16 JST+0900|手順5 制限|受領原100rawは未確認。旧001は96成功+1実失敗+3不備のINCOMPLETE、壊れたNPZを作り直さず保全。新002の成功のみ全rawで確認。97件の下降中両指接触消失/着地前89件を成功の説明から分離。公開pushなし、元archive不変。|
|2026-10-06 00:17:43 JST+0900|手順5 品質・自主review5/5|変更Python23対象ruff PASS、skill形式PASS、tracked diff check PASS。CSV100/335・全proposal順・凍結producer/model不変確認。技術inventory3872件を検査: text2136、compressed125、NPZ125、private-path/secret所見0。RANDOM_DELIVERY_SHA256SUMS照合PASS。元archive/実写/会話/例外log/破損rawはlocalのみ。下降限界/条件付きCI/旧未納品/未完了の記述をブラウザで再確認。|
|2026-10-06 00:10:54 JST+0900|手順5 ブラウザ|専用headless Chrome/Playwright。169リンク、62画像、10動画の読取正常。100行/search1件、1440px/390pxでpage overflowなし。desktop/mobile証跡保存、視認。専用browser/serverのみ終了。|
|2026-10-06 00:07:22 JST+0900|手順5 作成|代表/最大半径/最大着地前速度/負対照/旧実失敗の5case・二視点動画10本、phase画像、raw SHA/sample対応を作成。actual index/auditによるHTML/CSV、技術REVIEW、RANDOM_README、skill追記。保持の俯瞰/手先と旧失敗close画像を視認。|
|2026-10-06 00:00:46 JST+0900|40行動記録|新100全raw監査完了。二視点映像と実測集計HTMLを作成中。旧001未完了を保全し、新002のみを合格とする。下降接触消失97件、箱接触前89件を記録。counter40→0。|
|2026-10-05 22:41:55 JST+0900|手順2 解決|旧evaluate置換を回避。入力SHA/protocol7d71afd/model e3e32bb不変。複数contact形式黙認とHTML歴史claimの誤表示を修正。|
|2026-10-05 22:41:55 JST+0900|手順2 検査|14pytest PASS/21.90s（元8+既存4+狭い2）。対象ruff PASS。代表plan373sample ACCEPTED。Formatter後数値/物性/判定は不変。|
|2026-10-05 22:41:55 JST+0900|手順2 保護|schema3 mesh検証、事前finite/seed/stale検証、KeyboardInterrupt保存、空trace失敗、reader3形式排他。batch名/seed検証、FAIL CLI非0。自主review1/5:保護;2/5:古い固定数値HTMLをactual indexへ変更。|
|2026-10-05 22:41:55 JST+0900|手順2 実装|20新規モジュール、evaluateはcontact readerだけmerge。既存QA/名目HTML/モデルは保全。新HTMLはRANDOM_REPORT_name.html、media専用subdir。|
|2026-10-05 22:29:32 JST+0900|計画開始|4入力と完成記録全文を読了。ZIP同一。patch22ファイル、正確な元archiveは既に検証済。別作業cameraログ2件保全。新カウンター開始。|
|2026-10-05 22:33:58 JST+0900|手順1 入力読了|inventory.json、CRC88entries、path/symlink検査PASS。報告原本はtempのみ。|
|2026-10-05 22:33:58 JST+0900|手順1 差分レビュー|Major: random runnerは既存mesh hash検証/引数事前検証/KeyboardInterrupt保護を欠く。trace readerはgzip未対応、複数形式黙認。提出audit出力に絶対パス。原100raw未納品。20新規を受入、evaluateは読取1箇所だけmerge。|
|2026-10-05 22:33:58 JST+0900|手順1 適用検査|git applyのexit0だけでは適用確認不可: repository下temp実行は全22skip。GIT_CEILING_DIRECTORIESで親repo探索を止め、新規コピーへ全22適用・実体確認PASS。|
|2026-10-05 22:33:58 JST+0900|手順1 適用方針|元snapshot2既存ファイル+新規20を隔離適用。既存改善済evaluateを置換しない。|
|2026-10-05 23:22:29 JST+0900|手順4 未完了・自主review3/5|30分上限exit124。97結果=96SUCCESS+1NO_GRIP、残3は中断保存に再SIGINTが入りmetadata未確定。qualification-001はINCOMPLETEとして保全、合格扱いしない。物理profileの三重forwardを公開APIの1forward+同じimplicitfast積分へ整理し、中断保護を修正後、別seed91021261008/name qualification-002で新100全数。物性/判定/domain/1800sは維持。見積追加35–45分。40行動記録・counter reset。|
|2026-10-05 23:55:09 JST+0900|手順4 母数確認|335提案/235端点IK棄却/最初100accepted、100SUCCESS unsafe0 invalid0、Wilson[0.9630065,1]。固定prefixはselection/indexと全draw順を照合。|
|2026-10-05 23:55:09 JST+0900|手順4 全raw監査|independent-qualification-002.json: audit PASS/errors0、100独立再判定一致、1386凍結input/source snapshot照合、全step/contact lossless。下降接触消失97/100、最長2.169s（着地後を含む）、着地前速度最大0.69846m/s。|
|2026-10-05 23:55:09 JST+0900|手順4 完了|旧001 INCOMPLETE 96SUCCESS+1NO_GRIP+3 evidence不足保全。新002全100を別seedで完了、物性/判定/domain/1800s不変。2連SIGINT defectと3重forwardを修正、状態byte同等性確認。|
|2026-10-05 23:51:57 JST+0900|手順4 実行完了|qualification-002全100/100SUCCESS、1186.24s、exit0、seed91021261008、freeze f973d28f…、旧001 INCOMPLETEも全100母数で保全。これから全raw独立再判定。|
|2026-10-05 23:30:05 JST+0900|手順4 改善・自主review4/5|1forward+同じimplicitfastによる新loop20.47s/24.77s。旧90sとの代表全20state・contacts byte完全一致、新repeatも完全一致。no-close期待FAIL。標準mj_stepとの接触モデル200step bit-exact unit PASS。2連SIGINT実試行で1sample NPZ有効/metadata確定/FAIL/codec保存確認。parentもpending futures取消とINCOMPLETE記録へ修正。新seed全数へ。|
|2026-10-05 22:48:31 JST+0900|手順3完了・手順4開始|物理失敗修正は不要。負対照FAIL rawも保存。新qualification seed91020261005（元81020261005未再利用）、固定±300mm/filter/物性/contract。4並列、外側timeout1800s/INT+20s killで段階上限を実装。見積25–30分、閾値を緩めない。|
|2026-10-05 22:48:31 JST+0900|手順3 repeat/negative・40行動記録|最適化前後全20state配列・contacts32MBのSHAが完全一致。repeat SUCCESS、no-close NO_GRIP/INSUFFICIENT_LIFTでFAIL。cache単体3tests PASS。profile総69.39s、3MuJoCo処理41.2sが主時間。積分方式/solver warmstartは変えない。行動40→0リセット。|
|2026-10-05 22:46:56 JST+0900|手順3 raw監査|positive audit PASS、validation/acceptance failures0、自由蓋/隠れ支持なし/外力なし/return一致。下降時接触喪失14.268s、箱初接触14.287s、着地前0.445m/sを確認。継続下降保持を主張しない。公式MuJoCo simulation/XML仕様も参照。|
|2026-10-05 22:45:16 JST+0900|手順3 代表実行|SUCCESS 23001samples、保持min36.615mm/99.7%/drift1.317mm、unsafe0、cycle復帰PASS。物理loop89.97s。既存補間配列を毎step構築する重複をcacheへ変更し、bit-exact比較を追加。|
