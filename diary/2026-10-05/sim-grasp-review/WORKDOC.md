# 作業計画書兼記録書：蓋把持成果物の厳格レビュー・改善・公開

日付: 2026-10-05。担当: Codex単独。開始: 2026-10-05 19:08:59 JST+0900。
作業場所: .。作業書正本は本書、公開用記録はdiary/2026-10-05/sim-grasp-review/WORKDOC.md。

## 1. 作業目的
元のIK蓋把持作業書と18分割成果物の実態を照合し、不足を改善してコード・再現入力・合成証拠・レビュー記録をcommit/pushする。

### 1.1 ゴール要求分析
ユーザーが求めるのは画像だけの成功宣言ではなく、通常重力の自由蓋を左右の指で持ち上げ、判定と証拠を他PCで再現できる成果物。原契約は20mm/2sec、両指80%、grip漂移5mm、接近2mm、禁止接触/境界/数値異常なし。元条件を緩めない。今回の完成成果物は箱50mm・蓋中心[0,180,57.5]mm・摩擦0.7の名目条件。別実装の40mm箱条件と混ぜない。

明示要求: 詳細な辛口レビュー、改善、skills改善、commit/push。実機操作なし。元archive/partsはtempに保持してcommitしない。root remoteは現在PUBLIC（gh repo viewで確認）、実写/会話ログ/私的原記録はlocalに保存し、公開技術記録と合成画像のみをstageする。元のprivate記録を無条件に公開しない。共有observer環境を変更せずpackage専用uv環境を使用。

### 1.2 サブゴール構造
|SG/Trace|要求|成果物|判定|
|---|---|---|---|
|SG1/TR1|作業書と実態の照合|REVIEW.md・完了照合章|全元TR1..5に根拠、未確認と対象外を分離|
|SG2/TR2|不具合を改善し統合|packages/sim-cap-grasp/|原条件維持、外部path fallback/古いcache/不正modelを拒否|
|SG3/TR3|実行と証拠|新nominal/no-close/replayログ・HTML|mj_step再実行成功、負例失敗、原結果との差を記録|
|SG4/TR4|スキルと再現記録|skills/sim-grasp-review/、diary|同じ失敗を繰り返さない具体手順、元実写はlocal保持|
|SG5/TR5|公開を完了|限定commit・remote HEAD検証|stage監査PASS、archive/私的入力を除外、nonforce push|

### 1.3 トレーサビリティ方針
各項目完了直後に日時・実施・結果・証拠を記録する。CHECKEDは主張であり、元実体・実行結果に照合する。変更前のimport archiveはimmutableな監査原本。判定、model、plan、metadata、state、contactのhashを別管理。

## 2. 作業内容
調査: 元作業書、全主要source、判定契約、collision分類、source/cache、保存試行を照合する。設計: 軽量standalone packageを採用し、原成果物の意味を保ったままinput validation、model integrity、可搬性、公開内容を修正する。実装: packageと少数の独立不良対照を追加する。検証: 専用uv lockでnominal/negative/repeatを実行し、変わったコードだけlint/format/test。元未変更摩擦/質量試行は再計算し履歴を残す。observer/Rust契約は未変更なので全suite/Cargoの再実行対象外。justfileは新packageのtargetを提供しない。

## 3. 作業チェックリスト

### 手順1: 辛口レビューを確定する（TR1）
- [x] 🖐 **操作**: 原作業書・source・実体を読んでREVIEW.mdにseverity/根拠/改善方針を保存。
- [x] 🔎 **確認**: 名目成功、再実行未確認、cacheとinput/model制約、公開先、collision除外の限界が分類される。
- [x] 🧪 **テスト**: 調査のため自動テスト追加なし。修正の独立対照を次手順で先に確認する。
- [x] 🛠 **エラー時対処**: 元内容の不足は未確認と記録、archive/hash原本を上書きしない。

### 手順2: 再現packageと必要な修正を実装する（TR2）
- [x] 🖐 **操作**: packages/sim-cap-graspにcode/model/source meshを明示選択で統合し、監査で判明した不具合を修正。
- [x] 🔎 **確認**: 共有src/config/hardware transport未変更、閾値/scene/制御値を変更しない。元cache/source hashと不足入力を検査。
- [x] 🧪 **テスト**: 少数の独立対照で隠れた物体支持、不正CLI、古いcacheを修正前後に確認。
- [x] 🛠 **エラー時対処**: 依存はpackage .venvだけでuv sync --frozen。staleは明示停止、元履歴を削除しない。

### 手順3: 改善版を新しい環境で検証する（TR3）
- [x] 🖐 **操作**: packageからnominal/同seedrepeat/no-closeを新規outputへ実行し、独立判定・原state差・最小品質ゲートを保存。
- [x] 🔎 **確認**: 実mj_step成功、同条件比較、negative失敗、支持/外力なし。原摩擦/質量感度の成功/失敗も保持。
- [x] 🧪 **テスト**: 新package限定pytest、ruff check/format、compiled modelとraw監査。元observer suiteは変更なしのため対象外。
- [x] 🛠 **エラー時対処**: 失敗はsource/plan/model/controller hashesを確認して診断、契約を緩めない。

### 手順4: レポート・スキル・記録を完成する（TR4）
- [x] 🖐 **操作**: 改善後の二視点証拠と公開HTML、完了照合章、再利用skill、local会話書き出しを作る。
- [x] 🔎 **確認**: headless Playwrightで実表示確認。原履歴と改善版を混ぜない。技術記録がcloneから実行可能。
- [x] 🧪 **テスト**: 画像/動画/リンク検査、skill形式検査、成果物実体とhash照合。
- [x] 🛠 **エラー時対処**: file protocol拒否時はloopback HTTPのpreviewを使用。別sessionを閉じない。

### 手順5: 限定commitとpushを実行する（TR5）
- [ ] 🖐 **操作**: 新package/公開技術記録/skillだけをstage、precommit監査、commit、nonforce push。
- [ ] 🔎 **確認**: remote mainとHEAD一致、元archive/実写/会話raw/既存他作業をstageしていない。
- [ ] 🧪 **テスト**: git diff --cached --check、staged audit、git ls-remote。公開データを追加する場合は明示回答を待つ。
- [ ] 🛠 **エラー時対処**: remote先行ならfetchし今回の限定commitだけ通常rebaseして再検証、force pushしない。

## 4. コマンド参考
`cd packages/sim-cap-grasp && uv sync --frozen && MUJOCO_GL=egl uv run --no-sync python run.py --seed 0 --output results/review-nominal`
`uv run --no-sync pytest -q tests` / `uv run --no-sync ruff check .` / `uv run --no-sync ruff format --check .`
source/cacheの修正はbuild_scene.py、IKはik.py、実行はrun.py、判定はevaluate.py、証拠はreport.py。依存仕様はpackage pyproject/uv.lockを固定。

## 6. 完了の定義
- [ ] TR1: 元全要求との初期/改善後判定を根拠付きで保存。
- [ ] TR2/3: repoの実体から新環境mj_stepがSUCCESS、negativeがFAIL、repeat比較が存在。
- [ ] TR3/4: 全失敗履歴はarchiveに保持、公開する選択rawと再現コード、二視点証拠、限界が存在。
- [ ] TR4/5: 更新skillと作業記録、公開stage監査、commit/push/HEAD一致確認が存在。

## 7. 作業記録
2026-10-05 19:52 JST: 手順4対処完了: supported loopback previewを使用、任意favicon404のみ。専用headless sessionと自分のHTTP serverのみ終了、他session不変。次は手順5操作。
2026-10-05 19:52 JST: 手順4テスト完了: browser-qa.json PASS、2skills形式PASS、変更python lint/format PASS、gzip roundtripとfresh modelasset hash guardを確認。
2026-10-05 19:52 JST: 手順4確認完了: 13画像/4動画/24links PASS、current hold画像目視。元と新trialを名前/比較JSONで分離。source/lock/model/inputs/rawの実体とstandalone CLIを確認。
2026-10-05 19:52 JST: 手順4操作完了: REPORT.html/全fresh二視点、8章照合、skills/sim-grasp-reviewとgit skill改善、local predecessor clean export実体を保存。現API rawは未保存の限界を明記。
2026-10-05 19:52:17 JST: 手順4成果物確認。HTML13画像/4動画(readyState4)/24links200、desktop/mobile overflowなし、専用headless session確認。browser-hold.pngを目視、二視点で持上げ/両指内capを確認。専用sessionとloopbackだけ終了。実SIGINT対照は12sample保存、FAILURE/KeyboardInterrupt/normal_completion=false/result生成。元環境bit-exactではない点をレビューとHTMLに明記。公開監査のgzip秘密/絶対path拒否、numeric/phase NPZ受理を実確認。2skill形式と変更code lint/format PASS。

## 8. 完了照合・調査分析サマリ

### 8.1 調査メタ情報

|項目|内容|
|---|---|
|調査日時|2026-10-05 19:52:17 JST+0900（date実出力）|
|調査者|Codex単独、サブエージェントなし|
|対象作業書|本書と元WORKDOC_SIM_GRASP.original.md / 完成WORKDOC_SIM_GRASP.md（archive原本）|
|対象repository|my_dynamixel_arm_sandbox、packages/sim-cap-grasp|
|参照証跡|REVIEW.md、review-verification.json、raw-audit-review-repeat.json、tests/test_integrity.py、evidence/browser-qa.json|

### 8.2 現況サマリ

原作業書の名目成功は生状態とforceの独立監査で支持された。一方、入力fallback、stale cache、受動支持検査、中断記録、公開内容に改善が必要だった。改善版の新しい固定依存環境から実mj_stepを実行し、nominal/repeat SUCCESSとno-close FAILUREを確認した。元XML/閾値/meshはbytes一致だが、再IK丸め差と接触後の軌跡差があるためcross環境bit-exactは主張しない。歴史的感度失敗も残した。実機、外部校正、真の材料物性、全可動域の安全性は未確認のまま。解析・改善・合成証憑は完成、公開commit/pushは次手順。

### 8.3 ゴール要求分析との照合

|Trace|要求|判定|実態・根拠|不足・次アクション|
|---|---|---|---|---|
|TR1|辛口照合|達成|REVIEW.mdの原TR1..5、8指摘と元historyの制約|公開記録をstage|
|TR2|改善と可搬package|達成|source/lock/model/input/rawの実体、検証と4不良対照|原物性・proxy限界は残る|
|TR3|新環境実再実行|達成|review-nominal/repeat SUCCESS、no-close FAILURE、raw audit PASS|cross環境軌跡は未一致として保存|
|TR4|記録/証憑/skill|達成|REPORT.html、13画像/4動画、browser QA、2skills形式検証|available predecessor cleanのみlocal、現API raw会話はPCに未保存|
|TR5|commit/push|未達|まだstage/commit/pushしていない|次手順で限定公開・HEAD確認|

### 8.4 完了の定義との照合

|DoD|判定|確認方法|根拠|備考|
|---|---|---|---|---|
|元要求と改善判定|達成|原作業書/source/rawを読取り照合|REVIEW.md|unchecked課題を隠さない|
|repo実体のfresh dynamics|達成|uv sync --frozen / run.py / audit_raw_trial.py|review-verification.json|同PCrepeat bit-exact、元別環境は不一致|
|失敗保全と二視点証拠|達成|gzip roundtrip/HTML/Playwright|全results実体・browser-qa.json|実写/会話/元archiveはローカル|
|skills/記録/監査/公開|一部達成|skill validate、変更scope lint/format|2skills PASS、公開前stage未実施|commit/push/HEAD確認が残る|

### 8.5 実行した調査コマンドと結果

|コマンド|目的|結果|判断|
|---|---|---|---|
|uv sync --frozen|独立package環境|Python3.12.12/MuJoCo3.13.0、19依存を固定|可搬依存|
|build_scene.py / verify_model.py / ik.py（READMEの最終args）|geometryと4軸path|原XMLbytes同一、5FK/rank PASS、93waypoint|TR2/3|
|run.py --seed 0（nominal/repeat/no-close）|実物理再実行|36.580984mm/2秒/99.65%/1.385053mm、negative FAIL|TR3|
|audit_raw_trial.py results/review-repeat|独立生監査|全sample FK/force/支持/境界PASS、gzip直接読取|TR3|
|pytest -q tests / ruff check . / ruff format --check .|変更scope品質|4PASS、9code lint/format PASS|TR2/3|
|SIGINT対照・public audit不良対照|例外/公開漏れ|部分証拠とFAILURE生成、gzip秘密/絶対path拒否、NPZ技術配列受理|R5/R7|
|playwright-cli 専用headless session|HTML実表示|13画像/4動画/24links正常、mobile overflowなし|TR4|
|quick_validate.py（2skills）|形式|2PASS|TR4|
|git status --short --untracked-files=no / fetch|元差分保全/remote確認|既存camera2logsを残す、stage未実施|TR5準備|

### 8.6 未達・未確認項目とリスク

|区分|項目|現況|リスク|対応|
|---|---|---|---|---|
|未達|公開commit/push|次手順|公開が未完了|明示stage/監査/nonforce push|
|未確認|実機/校正/真のsofttip物性|offlineのみ|simulation成功を現実成功へ外挿できない|別依頼で実測と新しい許可範囲を定義|
|制約|adjacent/mount whole-body collision除外|policy原条件保持|除外面の物理接触を保証しない|collision-exclusions.jsonを公開、全可動域安全を主張しない|
|制約|cross環境数値差|原と新軌跡不一致|seed/versionだけで完全一致を保証できない|差をphase別に記録、同PCrepeatとは区別|
|制約|歴史的producer source|全版同梱ではない|全過去trialを最終CLIだけで再実行はできない|raw/model/plan/control保持、最終run再現と分離|
|未確認|現API turnの全文raw会話|PC sessionsに存在しない|predecessor exportを最新全文と誤認し得る|local exportの範囲を明記、公開しない|

### 8.7 最終判定

**判定:** 条件付き完了（解析・改善・名目再実行・証憑まで）。

**理由:** 固定契約の名目SUCCESS/negative FAILURE、4対照、独立監査、二視点証拠が実体で確認できる。TR5の公開commit/pushは未実施であり完了としない。

**次アクション:** 手順5の限定stage、私的情報/絶対path/巨大archiveの監査、commit/pushとremote HEAD確認。
2026-10-05 19:43:20 JST: カウント40でリマインダー表示、0へreset。手順4操作中。改善版の全二視点映像生成完了。公開user決定を反映。再利用skill追加、git監査にgzip/NumPy文字列/絶対path拒否を追加。available predecessor sessionをagent-jsonl/bundleでlocal cleanへ出力(149events/56supplement、伏字0)。このreviewのAPI raw logはPC sessionsに存在せず、predecessor exportを現turn全文とは表記しない。
2026-10-05 19:39:36 JST 手順3: 原state完全一致の分析assertが失敗。scene/契約bytes同一とIK丸め差・phase差を調査、同PC再現とcross環境差を分離。成功契約/物性変更なし。手順3完了。
2026-10-05 19:39:36 JST 手順3: 4 integrity tests PASS、ruff check/format PASS(9files)、5pose FK/rank検証PASS、別script raw監査PASS、wrong mesh digest拒否とgzip roundtrip一致。
2026-10-05 19:39:36 JST 手順3: 新trial13秒13001sample、36.580984mm/2秒/99.65%/1.385053mm、支持0/禁止0。原感度を保持。同PC bit-exact、元別環境のstate不一致。再IK差<=1.5e-15rad、因果は未隔離。
2026-10-05 19:39:36 JST 手順3: 新.venvからreview-nominal/repeat SUCCESS、no-close FAILURE。review-verification.jsonと圧縮raw監査を保存。元stateとの不一致も隠さず計測。
2026-10-05 19:32 JST: package固有.venvでuv sync --frozen成功、既存source/model/失敗履歴を保持。manifest不足は停止して修正、古いcacheを拒否。手順2完了、次は手順3操作。
2026-10-05 19:32 JST: 4 tests PASS (2.46s)。cap damping100/stale hash/tampered part/不足source manifest/不正CLIが拒否され、CLI出力未作成を確認。
手順2確認完了 (2026-10-05 19:31 JST): 原scene.xml/evaluation_contract.jsonのbytes一致、全viewer source meshes一致。runにserial/camera SDK importなし。ユーザー公開決定: code/合成画像/技術記録のみ、私的情報/絶対path除外。カウント40リマインダー表示後0へreset。次は手順2テスト。
手順2操作完了 (2026-10-05 19:31 JST): packages/sim-cap-graspへ独立環境/lock、原source/mesh、全trialの可逆gzip rawを選択統合。source/cache/mesh hash、隠れた支持、CLI、中断、公開reportを修正。初回buildは元manifestにdesign_reference未収録のため停止、原内部SHAで確認した3ファイルをmanifestへ追加し再生成成功。元geometry/契約/制御値は変更なし。ruff import1件を修正。共有src/config/既存2log未変更。次は手順2確認。
行動カウント40でリマインダー表示、0へリセット (2026-10-05 19:22 JST)。手順1完了、手順2操作中。独立修正前対照でcap dampingとstale cacheの受理を確認。公開用code/asset/rawの選択コピーを開始。元archiveを上書きせず、私的観測を除外。
手順1-4完了 (2026-10-05 19:20 JST): REVIEW.mdのTR照合と8指摘、cap damping100/stale cache修正前受理を確認。調査のテスト追加なし、archive/共有環境不変。該当項目のみチェック。
手順1-3完了 (2026-10-05 19:20 JST): REVIEW.mdのTR照合と8指摘、cap damping100/stale cache修正前受理を確認。調査のテスト追加なし、archive/共有環境不変。該当項目のみチェック。
手順1-2完了 (2026-10-05 19:20 JST): REVIEW.mdのTR照合と8指摘、cap damping100/stale cache修正前受理を確認。調査のテスト追加なし、archive/共有環境不変。該当項目のみチェック。
手順1-1完了 (2026-10-05 19:20 JST): REVIEW.mdのTR照合と8指摘、cap damping100/stale cache修正前受理を確認。調査のテスト追加なし、archive/共有環境不変。該当項目のみチェック。
**重要な注意事項:** 作業開始前にdateで日時を取得。各項目の開始と完了を記録。操作/変更/成功失敗/原因/修正/未確定を具体記録。フェーズごとに記録し未知/失敗/error/対象外を混同しない。DoD未達は未達のまま保持する。

|日時JST|項目|操作・結果・証拠|
|---|---|---|
|2026-10-05 19:08:59|開始/調査|元18part結合SHA・内部3292SHA一致、生raw監査PASSは前ターン確認。W repo main...origin/main、stage空、既存大量未追跡は別作業。gh repo viewでPUBLICを確認。コード/合成証拠/技術記録のみ公開する方針を提示。|
