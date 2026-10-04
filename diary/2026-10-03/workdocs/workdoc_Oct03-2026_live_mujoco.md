# 実機READ live → MuJoCoと校正画面：作業計画書兼記録書

作業者: Codex。開始日時: 2026-10-03 21:00:27 JST。
正本: /home/inaho-omen/Project/my_dynamixel_arm_sandbox/temp/workdoc_Oct03-2026_live_mujoco.md
主作業先: /home/inaho-omen/Project/my_dynamixel_arm_sandbox
描画先: /home/inaho-omen/Project/3d-printed-dynamixel-gripper/simulation/current_arm_viewer
レビュー: [live_mujoco.review.md](workdoc_Oct03-2026_live_mujoco.review.md)

## 1. 作業の目的

### ゴール要求分析
TR-1: 接続した現物の現在角を継続READし、MuJoCoモデルへ反映するモードを実装する。
TR-2: 2026-10-03のユーザー回答「未校正：校正画面も実装する」に対応し、ID→CAD関節、基準カウント、回転方向、PG3基準角を確認・入力できる画面を用意する。
TR-3: 読み取りのみ。モーターのTorque/Goal/ID/Mode/EEPROM等の変更、旧Robotのimport、ポート所有者の停止を行わない。
TR-4: 未校正・古い入力・欠損・異常・メタデータ変更では実機姿勢と表示しない。手動MuJoCo操作と実機READ表示を切り替えられる。
TR-5: 根拠のある試験・実測・ブラウザ確認を保存し、diaryに実装結果と物理確認の残件を記録する。

既存モデルのR3/C7/長尺R5候補を維持する。自己干渉しない範囲の承認、実物の正しい校正、機構取付承認はこの実装の完了とは別。表示のリミットは安全保証ではない。ユーザーの確認なしに任意の実機姿勢をCAD中立として校正しない。

## 2. フェーズとサブゴール
SG-1: 型付きread-only bridge。src/arm_observerに追加し、既存open_bus/Reader/observeとJSONL v2を使う（手順1〜2）。
SG-2: 校正とlive表示。隣repoの既存viewerにlocalhost bridge受け口、校正画面、開始/停止を追加（手順3〜4）。
SG-3: 正負対照、品質、有限実測、独立headless browser、diary（手順5〜8）。

## 3. 作業手順チェックリスト

### 手順1: bridgeの失敗試験を先に追加（SG-1/TR-1,3,4）
- [x] 🖐 **操作**: tests/test_live.pyを追加し、constructor無通信、取消、二重開始、bus占有/例外時の終了、typed statusとJSONL終了をoffline fake Reader/portで試験する。
- [x] 🔎 **確認**: テストはSDK実機を開かず、未実装機能によるREDである。既存送信guardの試験は維持する。
- [x] 🧪 **テスト**: uv run pytest -q tests/test_live.pyを実行し、失敗の原因とexit codeをreports/live_red_bridge.txtへ保存する。
- [x] 🛠 **エラー時対処**: import/fixture設計の誤りなら試験側を修正。モーターアクセスやguard変更でREDを解消しない。

### 手順2: bridgeを実装（SG-1/TR-1,3,4）
- [x] 🖐 **操作**: observerの任意取消を追加し、immutable LiveSnapshot、worker、localhost HTTP開始/停止/status、arm-live CLIを実装する。ポートは明示したstartでのみ開く。
- [x] 🔎 **確認**: 20Hz sync、metadata30秒、JSONL v2、finally閉鎖、停止中は閉鎖済みと偽らない。停止はread取消だけでTorque変更しない。
- [x] 🧪 **テスト**: 手順1の試験と既存offline pytestをGREENにし、busy/error/取消後のport_closedとlog endを確認する。
- [x] 🛠 **エラー時対処**: 不完全frame/SDK例外はfault/errorとして保存。警告閾値、命令guard、既存契約を緩めない。

### 手順3: viewer校正とlive入力の失敗試験（SG-2/TR-2,4）
- [x] 🖐 **操作**: tests/test_current_arm_live.pyにID重複/順序、数値/符号、未確認、stale/終了/異常、metadataとtorque変更、session再接続、4095跨ぎ、既知の角度反映の対照を追加する。
- [x] 🔎 **確認**: 実物校正の代わりに明示したsynthetic fixtureを使い、fixtureを実機校正値として保存しない。既存14件と共存する。
- [x] 🧪 **テスト**: root gripperのuvで新試験REDを保存。fresh正常fixtureとfault/stale等の負の対照の期待結果を確認する。
- [x] 🛠 **エラー時対処**: CADファイルや形状を変更せず、入力変換・校正検証側の問題だけを切り分ける。

### 手順4: viewer liveと校正画面（SG-2/TR-1,2,4）
- [x] 🖐 **操作**: viewerにlocalhost HTTP受け口、読み取り開始/停止ボタン、raw counts表、校正フォーム、明示確認、校正保存/読込を追加する。旧file入力と手動モードも維持する。
- [x] 🔎 **確認**: ID/基準/方向がユーザー確認済みになるまで姿勢適用を禁止。CAD SHA・metadata・session・Torque変化を校正contextへ結び、切断/古い値では直前姿勢を保留し状態を明示する。
- [x] 🧪 **テスト**: 新旧viewer試験をGREENにし、compile済みモデルのqpos/PG3変換と保持動作を検証する。
- [x] 🛠 **エラー時対処**: 欠損値を0や以前の値で埋めない。再接続時は保存校正を確認して再適用する。実物の未知の対応を推測しない。

### 手順5: 品質と契約（SG-3/TR-3,5）
- [x] 🖐 **操作**: 新workspaceでpytest、ruff、ty、check_quality、Rust test/Clippyを実行。gripperでは対象viewerのruffと新旧pytestを実行しreportsに保存する。
- [x] 🔎 **確認**: JSONL v2フィールド変更なし、最大複雑度10維持、src/config/元CADへの無関係変更なし。
- [x] 🧪 **テスト**: offline命令guard試験合格を実機実行の前提とする。HTTP origin拒否とconstructor無通信、取消を含む。
- [x] 🛠 **エラー時対処**: 品質失敗は実装を分割/修正し再試験。thresholdの増加やtestの削除で完了させない。

### 手順6: 有限live読取り（SG-3/TR-1,3,5）
- [x] 🖐 **操作**: 所有者チェック付きopen_busを通じ、20Hz・10秒の有限bridge読取りを一回実施する。start前はstatusのみ、停止後はport_closedを確認して結果をreportsへ保存する。
- [x] 🔎 **確認**: 実測Hz/欠損/期限超過、motor IDs/値、JSONL終了を確認。実物未校正のため姿勢はまだ反映しない。
- [x] 🧪 **テスト**: outgoing guardがPING/READ/validated SYNC_READ以外を拒否する合格結果と対応する。busyなら所有者を残して停止し、BLOCKED_HARDWAREとして保存する。
- [x] 🛠 **エラー時対処**: busy/未接続/timeoutで他プロセスを止めない。再試行を繰返さずraw errorを記録。有限チェックの未達は隠さない。

### 手順7: Playwright検証（SG-3/TR-1,2,4,5）
- [x] 🖐 **操作**: 独立headless named sessionで8084を開き、live値と校正フォーム、手動切替、画角、フレーム進行を確認する。描画用自分のserverのみ再起動可。ユーザーtabは保持する。
- [x] 🔎 **確認**: 実機の未校正liveと既知syntheticの校正済み姿勢を区別。synthetic対照ではモデルに反映した角度をHTTPと画像で確認する。
- [x] 🧪 **テスト**: 正負入力と切断/staleの表示、画像1060×760、増加frame_seq、ブラウザconsole errorを保存する。必要な実機読取りは有限runとする。
- [x] 🛠 **エラー時対処**: rendererエラーやHTTP停止を代理画像で隠さず記録。実物校正が未完了でも画面と入力対照は完了可能、実物に合う姿勢の検証は未達と明記する。

### 手順8: diaryと使い方（SG-3/TR-5）
- [x] 🖐 **操作**: README/renderer READMEとdiaryに起動・接続・校正・停止、実測/試験/画面の結果と残件を追記。追加ユーザー要求に従いproject-localの汎用robot-live-calibration skillを作成し、検証表・GET-only probe・5観点レビューと検証結果を保存する。
- [x] 🔎 **確認**: 未校正、版候補、安全範囲ERROR/UNKNOWNを維持。実機書込みなし、任意姿勢を実機中立にしたとの誤記なし。
- [x] 🧪 **テスト**: local link、git diff --check、新規ファイル直接検査、元CAD SHAを確認し、JSON証拠と本文の数値を照合する。
- [x] 🛠 **エラー時対処**: 未確認をPASSで埋めない。機能実装完了とユーザーが現物で行う校正の残件を分けて報告する。

## 4. 作業に使用するコマンド参考情報

全shellはrtk proxy、Pythonはuv。write-workdoc-uv/review-written-workdoc/start-work-with-docsを使用。既存両AGENTS/RTK・readonly architecture・SDK/Reader/observer/serverを確認済み。
新workspace: rtk proxy uv run pytest -q、rtk proxy uv run ruff check src tests scripts、rtk proxy uv run ty check、rtk proxy uv run scripts/check_quality.py。
Rust: rust/arm-observer-contractでrtk proxy cargo test、rtk proxy cargo clippy --all-targets -- -D warnings。
renderer: gripper repoでrtk proxy uv run --no-sync pytest -q tests/test_current_arm_viewer.py tests/test_current_arm_live.py。
bridge CLI: rtk proxy uv run arm-live --port 8085（起動自体は未接続、POST startでのみ接続）。
renderer CLI: rtk proxy uv run --no-sync python simulation/current_arm_viewer/server.py --port 8084 --live-url http://127.0.0.1:8085。
headless: rtk proxy playwright-cli -s=current-arm-live-check-20261003 open http://127.0.0.1:8084。
互換性: bridge statusのHTTP envelopeは新規app契約。JSONL metadata/frame/end v2のフィールドは不変。
校正をmetadataから推測しない。確認チェック必須、ID一意、sign±1、finite基準、PG3角25..135、CAD SHA一致。mode3は最短の4096カウント差、mode4は線形。対応外modeを拒否。
bridge停止中はstate=stopping/port_closed=false、worker finally終了後のみclosed=true。startでは新session UUIDとlogを作る。

## 6. 完了の定義
- [x] DoD-1/TR-1,3: actual bridgeとviewer liveが実装済み。constructor無通信、開始/停止、JSONL保存、guard、finally閉鎖が検証されている。
- [x] DoD-2/TR-2,4: 校正画面・保存/読込・確認付き適用が実装済み。未校正/stale/fault/設定変更/session変更/torque変更を姿勢保留する試験が成功。実物の校正はユーザー確認待ちとして記載。
- [x] DoD-3/TR-5: 品質結果、有限実測または具体的hardware阻害証拠、Playwright描画検証、日誌・使い方が実在し、元CADとread-only契約を保つ。
- [x] DoD-4: 全通常チェックを一つずつ完了し、直後の日時/evidence記録がある。未達や残件は明記し、未校正の実機姿勢を確認済みとは表示しない。

## 7. 作業記録

**重要な注意事項：**
* 作業開始前に必ず date "+%Y-%m-%d %H:%M:%S %Z%z" で時刻を確認し記録する。
* 各項目の開始と完了の双方を記録し、完了直後に一つだけチェックする。
* コマンド・結果・エラー・修正ファイルを具体的に記載する。
* フェーズごとの開始・完了を記録する。元ファイルとユーザー変更を保持する。
* Codexが実行。行動カウントN=40。新規作業書の開始時に0へリセット、行動ごとに表示、40でリマインダーと状況記録。

| 日付 | 時刻 | 作業者 | 作業内容 | 結果・備考 |
| :--- | :--- | :--- | :--- | :--- |
| 2026-10-03 | 21:00:27 JST | Codex | 新規live作業計画開始。ユーザー回答未校正を反映 | 前作業書の基礎集約は完了。実機live実装は本書へ分離し、既存viewer/file受け口だけで完了にしない |
| 2026-10-03 | 21:05:00 JST+0900 | Codex | 🖐 **操作**を確認・完了 | SG-1開始。fake open/OfflinePacket/held acquireによる9件のlifecycle試験を追加。実機へ接続するfixtureなし。 |
| 2026-10-03 | 21:05:01 JST+0900 | Codex | 🔎 **確認**を確認・完了 | testは未存在のarm_observer.live APIを要求し、actual busはmonkeypatchで置換する。guard既存試験は不変。 |
| 2026-10-03 | 21:05:03 JST+0900 | Codex | 🧪 **テスト**を確認・完了 | uv pytest exit2、未実装arm_observer.liveのimportエラーによるREDをreports/live_red_bridge.txtに保存。 |
| 2026-10-03 | 21:05:04 JST+0900 | Codex | 🛠 **エラー時対処**を確認・完了 | 未実装APIによる意図したRED。hardware/guard/CADへ変更なし。試験はそのまま実装へ進む。 |
| 2026-10-03 | 21:07:53 JST+0900 | Codex | 🖐 **操作**を確認・完了 | 手順2開始。live.py/live_http.py、arm-live entrypointとobserve optional取消を実装。constructor/status無通信。 |
| 2026-10-03 | 21:07:54 JST+0900 | Codex | 🔎 **確認**を確認・完了 | 20Hz sync・30秒metadata・既存v2を維持。worker終了前はstopping/closed=false、例外の閉鎖はunknown。bus.py/命令guard不変。 |
| 2026-10-03 | 21:07:55 JST+0900 | Codex | 🧪 **テスト**を確認・完了 | offline76 passed (0.59s)。9新試験でfinite/continuous取消/二重開始/例外を検証。fake packet未対応SYNCをfixtureのtelemetry置換で修正しGREEN。ty PASS。 |
| 2026-10-03 | 21:07:56 JST+0900 | Codex | 🛠 **エラー時対処**を確認・完了 | qualityでobserve complexity11を検出。取消predicateをstopped()へ分割し閾値10を保持、最終gateで再確認する。hardware未接続。SG-1完了。 |
| 2026-10-03 | 21:09:22 JST+0900 | Codex | 🖐 **操作**を確認・完了 | SG-2/手順3開始。synthetic five-ID metadata/frameと校正の正負対照を追加。既知角度はactual compiled MuJoCo qposへ反映して検証する。 |
| 2026-10-03 | 21:09:23 JST+0900 | Codex | 🔎 **確認**を確認・完了 | fixtureはsynthetic-sessionと明記し実物校正に保存しない。field確認、context変化、stale/異常、wrap、local URLの負対照を作成。既存14件不変。 |
| 2026-10-03 | 21:09:26 JST+0900 | Codex | 🧪 **テスト**を確認・完了 | uv pytest exit2。未実装live_inputのimport REDをreports/live_red_viewer.txtへ保存。 |
| 2026-10-03 | 21:09:27 JST+0900 | Codex | 🛠 **エラー時対処**を確認・完了 | 意図した未実装RED。CAD/mesh/shapeに変更なし、変換とcontext検証を実装する。 |
| 2026-10-03 | 21:15 JST | Codex | 行動カウント40到達の記録補正・0へリセット | bridge GREEN76件、viewer RED完了。helperの境界判定を修正し、以降40以上でリマインダーを表示。範囲・未校正・read-only制約を維持 |
| 2026-10-03 | 21:18:51 JST+0900 | Codex | 🖐 **操作**を確認・完了 | 手順4開始。viewer passive BridgeClientとlive開始/停止proxy、5関節校正フォーム・確認・保存/読込・raw表を実装。元file/手動入力を保持。 |
| 2026-10-03 | 21:18:52 JST+0900 | Codex | 🔎 **確認**を確認・完了 | 校正前はrawのみ。session/CAD model hash/ID/FW/mode/drive/homing/torqueのcontextとfreshnessを検証。不一致は校正を解除して保留。currentcount取込は基準一致checkboxを要求。 |
| 2026-10-03 | 21:18:52 JST+0900 | Codex | 🧪 **テスト**を確認・完了 | 新38件+既存14件=52 passed in25.39s。正のknown conversionをcompiled MuJoCo qposと照合、負のstale/fault/contextを拒否。対象ruff PASS。 |
| 2026-10-03 | 21:18:53 JST+0900 | Codex | 🛠 **エラー時対処**を確認・完了 | 一度のpatch context不一致は読み直して修正。UI JSON末尾改行とエラー表示の上書きを修正し、未校正値を姿勢へ埋めない。SG-2完了、品質と実ブラウザへ進む。 |
| 2026-10-03 | 21:19:44 JST+0900 | Codex | 🖐 **操作**を確認・完了 | SG-3/手順5開始。observer pytest/ruff/ty/complexity/Cargo test/Clippyを新規6ログへ保存、全exit0。viewer52件とruff合格。 |
| 2026-10-03 | 21:19:44 JST+0900 | Codex | 行動カウント40到達 | チェックと即時記録を更新。リマインダー表示後、カウンター0へリセット |
| 2026-10-03 | 21:19:45 JST+0900 | Codex | 🔎 **確認**を確認・完了 | v2 fixture/schema一致の既存試験が成功。複雑度閾値10のまま検査成功。bus/guard/Reader/v2フィールド/CADに変更なし。 |
| 2026-10-03 | 21:19:46 JST+0900 | Codex | 🧪 **テスト**を確認・完了 | constructor無通信・停止pending・origin外部拒否・不明write API拒否を追加含む。品質全exit0、hardware前のoutgoing opcode guard試験合格。 |
| 2026-10-03 | 21:19:46 JST+0900 | Codex | 🛠 **エラー時対処**を確認・完了 | lint import1件とroot型例外/例外範囲/timezoneを修正してPASS。品質threshold/testを緩めていない。 |
| 2026-10-03 | 21:24:36 JST+0900 | Codex | 🖐 **操作**を確認・完了 | 手順6開始。headless UIから20Hz/10秒のexplicit startを一度実行、open_bus ownership guard経由。終了後GET statusとsaved JSONLを収集。 |
| 2026-10-03 | 21:24:37 JST+0900 | Codex | 🔎 **確認**を確認・完了 | 200frames、19.999775Hz、incomplete0/deadline0、200×5samples fault/alert/errorなし。port_closed=true、全TorqueOFF。ID3は1153count、姿勢はmanual/未校正を維持。 |
| 2026-10-03 | 21:24:38 JST+0900 | Codex | 🧪 **テスト**を確認・完了 | 202 JSONL recordsがv2 schema適合。endのport_closed=trueと200frameを検証。品質77件のguard合格と対応。hardware validation/browser JSON/png保存。 |
| 2026-10-03 | 21:24:39 JST+0900 | Codex | 🛠 **エラー時対処**を確認・完了 | serial busy/timeoutなし、再試行なし。初回browser run-codeのrequire未定義はhardware開始前に失敗し、return値取得方式へ修正。所有者停止・モーター書込みなし。 |
| 2026-10-03 | 21:29:45 JST+0900 | Codex | 🖐 **操作**を確認・完了 | 手順7開始。独立headless current-arm-live-checkでactual READ UI/終了/未校正/1060×760/frame増加を確認。残りsynthetic校正→描画→staleを検証し、試験校正は別folderへ分離する。 |
| 2026-10-03 | 21:29:45 JST+0900 | Codex | 行動カウント40到達 | チェックと即時記録を更新。リマインダー表示後、カウンター0へリセット |
| 2026-10-03 | 21:32 JST | Codex | 手順7操作のチェックを未完了へ訂正 | actual UIは成功したがsynthetic姿勢対照が残るため、全検証の完了後に再チェックする |
| 2026-10-03 | 21:39:42 JST+0900 | Codex | 🖐 **操作**を確認・完了 | 手順7の全操作完了。actual UI finite READとsynthetic校正フォーム/既知角度/期限超過保持をPlaywrightで確認しJSON/画像を保存。両named sessionはheadless、ユーザーtab保持。 |
| 2026-10-03 | 21:39:42 JST+0900 | Codex | 行動カウント40到達 | チェックと即時記録を更新。リマインダー表示後、カウンター0へリセット |
| 2026-10-03 | 21:39:43 JST+0900 | Codex | 🔎 **確認**を確認・完了 | actualはraw/未校正/manual。syntheticは試験入力ラベル・別calibration-test、[11.25,5.625,0,0], θ101.25を描画後、staleで同じ姿勢を保持し校正解除。混同なし。 |
| 2026-10-03 | 21:39:43 JST+0900 | Codex | 🧪 **テスト**を確認・完了 | viewer54件PASS。browser確認拒否、decoded1060×760、frame進行、manual/live切替、stale保持を実証。console取得0件。初回fixture cross-origin fetch errorはpage.requestへ修正し再検証。 |
| 2026-10-03 | 21:39:44 JST+0900 | Codex | 🛠 **エラー時対処**を確認・完了 | script require/windowの実行文脈誤りとfixture import pathを修正。代理画像を使わずactual MuJoCo JPEGで検証。画角レビューで標準斜めを225°に変更し、爪を見やすくした。物理cal/motionは未達。 |
| 2026-10-03 | 21:45:58 JST+0900 | Codex | 🖐 **操作**を確認・完了 | 手順8開始。README2本と新規diaryを保存。project-local汎用skill/検証表/GET-only probe、5観点レビューを作成。skill quick_validate PASS、probeのframe進行PASS。 |
| 2026-10-03 | 21:45:59 JST+0900 | Codex | 🔎 **確認**を確認・完了 | 未校正/版候補/Boolean ERROR/UNKNOWN/実物校正とID3motion未達を明記。actual countsをCAD0にしていない。motor writeなし、syntheticは別証跡/別folder。 |
| 2026-10-03 | 21:46:00 JST+0900 | Codex | 🧪 **テスト**を確認・完了 | document validator PASS、36元入力の許可変更observer.pyのみで35入力SHA不変、リンク欠落0、diff check2repos exit0。77/54試験ログと200実測を照合。 |
| 2026-10-03 | 21:46:01 JST+0900 | Codex | 🛠 **エラー時対処**を確認・完了 | observer環境のvalidatorにPyYAML不足。gripper既存uv環境で実行しPASS、依存追加なし。未知/未達を合格に置換しない。live実装フェーズ完了、motion intakeへ継続。 |
| 2026-10-03 | 21:45 JST | Codex | 手順8テスト/エラー対処の完了記録を取消 | validator exit1を見落としてPASSを先に記録してしまった。実際はphoto REPORTの想定外SHA変更とpyproject/observerの意図した変更。チェックを戻し最新文書と出所を再確認する |
| 2026-10-03 | 21:48:31 JST+0900 | Codex | 🧪 **テスト**を確認・完了 | 再検査exit0。36入力は33SHA不変、pyproject/observerの2許可コード変更、20:59のphoto文書1更新。最新文書全文とmtime（live開始前）/SHAを確認して別分類。リンク0、2repos diff0、77/54/200を照合。 |
| 2026-10-03 | 21:48:31 JST+0900 | Codex | 行動カウント40到達 | チェックと即時記録を更新。リマインダー表示後、カウンター0へリセット |
| 2026-10-03 | 21:48:32 JST+0900 | Codex | 🛠 **エラー時対処**を確認・完了 | 失敗を見落とした早期PASS記録を明示取消してチェックを戻し、再検査の証拠で再チェック。photo REPORT更新はP05配線窓追記で候補版/未承認は変わらず、上書きせず保持。品質閾値/CAD/guard不変。 |
| 2026-10-03 | 21:49:37 JST+0900 | Codex | DoD-1を確認・完了 | read-only bridge/actual200frames、typed state、開始/停止/finally、guard/constructor無通信の試験77件成功、end閉鎖を検証済み。 |
| 2026-10-03 | 21:49:39 JST+0900 | Codex | DoD-2を確認・完了 | 校正画面/保存/import確認、未校正/stale/fault/context/session/torqueで保留と無効化を40試験+synthetic browserで検証。physical未校正は残件。 |
| 2026-10-03 | 21:49:39 JST+0900 | Codex | DoD-3を確認・完了 | 品質6ログ、actual200frame20Hz、Playwright2入力のJSON/PNG、diary/READMEs/skill保存。R3STEPとC7sourceSHAをprovenanceと直接照合PASS。v2guard契約不変。 |
| 2026-10-03 | 21:49:40 JST+0900 | Codex | DoD-4を確認・完了 | 全8×4通常項目を一つずつ閉じ、早期チェックの誤りは取消・理由と再試験を記録。実物未校正とID3motion未達を残し、専用motion作業書へ継続。 |

## 8. 残件と追加の実機動作工程

ユーザー確認: ID3は肘、現在完全に畳んでおり、動かす向きは肘を開く方向。現物情報として記録し、READのみから推定したと表示しない。
追加の約10°低速動作は[専用作業書](workdoc_Oct03-2026_id3_open_10deg.md)へ分離し、write/review済み。ID3対応/完全屈曲/currentcount、開く符号と基準/支持、専用bounded control、offline試験、実機動作、実物/READ/MuJoCo照合の全6手順×4行を定めた。
本書のread-only bridgeにmotor write APIを加えない。実物校正と専用作業書のmotion DoDは未完了。Boolean対照エラー、連続経路安全、ケーブル・取付も未解決。
