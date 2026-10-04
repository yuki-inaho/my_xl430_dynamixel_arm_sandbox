# 作業計画書 兼 記録書：スタンバイ・電源OFF姿勢
**日付：** 2026年10月04日
**開始時刻：** 2026-10-04 09:19:49 JST+0900
**作業ディレクトリ・リポジトリ：** /home/inaho-omen/Project/my_dynamixel_arm_sandbox（6e1c16b、uv）
**描画/幾何：** /home/inaho-omen/Project/3d-printed-dynamixel-gripper（main、MuJoCo3.13.0）
**作業者：** Codex root単独。ユーザー指示によりsubagent禁止。

## 1. 作業目的
スタンバイ姿勢と現状を基準にした電源OFF姿勢を定義し、MuJoCoとPlaywrightで候補の向きを検証する。
### 1.1 ゴール要求分析
ユーザーはID1/ID5中立、ID2は今程度に肘を引き、ID3の下流リンクを世界前方へ水平、ID4でID5を約30°下向きにしたい。無通電で急落することを避けたい。
追加回答：台座前の約5 mmクッションがあり、現在姿勢は安定しているので電源OFFはそれを基本にする。
制約：現物の全軸ゼロ/符号/中立・支持点が未校正。最新保存logは現在のfresh READではない。既存の限定ID3commandをmulti-jointへ拡張しない。今回の試行はsimulationのみで、serialなし。
成功条件：保存logのraw countsを出典付きで残す。CAD候補は世界軸ベクトルで水平/−30°をassertし、現状へ無理に適用しない。電源OFFの基準・支持手順・未確認を明示。元CADとproduction codeは不変。
非ゴール：機械設計変更、無校正の実機指令、gravity=0 viewerによる無通電安定性の認定。
### 1.2 サブゴール構造
| ID | サブゴール | 成果物 | 検証 |
|---|---|---|---|
| SG-P1 | 世界向きとmotor/CAD基準を区別 | docs/STANDBY_POWER_OFF_POSITIONS.md | 保存log/軸/向き照合 |
| SG-P2 | 候補の運動学を再現 | reports/standby-position-20261004、offline script | MuJoCo姿勢・角度assert |
| SG-P3 | 電源OFF手順と汎用技能 | skills/robot-park-pose-definition/SKILL.md | schema/形式/支持条件 |

### 1.3 トレーサビリティ
TR-P1 = ID1中立・ID2現状・ID3水平・ID4−30°・ID5中立。手順1/2/3。
TR-P2 = 現状安定・前側5 mmクッション。手順1/2/4。
TR-P3 = root単独・uv/rtk・原本不変・実機なし・再現技能。全手順。

## 2. 作業内容
フェーズ1調査：最新保存frameのcounts、R3 joints/scene、既存Boolean対照ERROR、校正状況を照合。
フェーズ2定義：肩をパラメータにし、世界前方+Y・上+Z、neutral yawを定義。ID3/ID4は世界向きから求める。電源OFFはcurrent-supportedというnamed状態にする。
フェーズ3検証：MuJoCo compile/qpos・リンクベクトル・planeクリアランスを確認、Playwrightで正面/側面表示。collision/重力・クッション支持はUNKNOWNのまま。
フェーズ4記録：仕様JSON/Markdown、専用汎用skill、再現コマンドと残件を書く。

## 3. 作業チェックリスト
### 手順 1: 保存状態と基準の調査（SG-P1/TR-P1/P2）
- [x] 🖐 **操作**: 直近完了READ logの末尾valid frameとmetadata、R3軸・sceneとBoolean記録を読み出す。
- [x] 🔎 **確認**: countsをCAD角と混同せず、現在freshではないこととneutral/zero未校正を記録する。
- [x] 🧪 **テスト**: source SHA/5 unique IDs/Torque OFF/closedの保存実体を確認する。
- [x] 🛠 **エラー時対処**: current姿勢のCAD角が求まらなければnullとし、勝手にzero count=現在値へ設定しない。
### 手順 2: 姿勢候補と停止手順の定義（SG-P1/P2/TR-P1/P2）
- [x] 🖐 **操作**: offline scriptでCAD候補と保存countsをJSONへ出力する。
- [x] 🔎 **確認**: 肩q2をパラメータとし肘・手首の相対角を計算、世界方向が一致することを確認する。
- [x] 🧪 **テスト**: MuJoCo compileと複数肩角で前腕pitch0°/ID5方向pitch−30°をassertし、未知calibrationを実機指令へ変換しない。
- [x] 🛠 **エラー時対処**: collision ERROR/未校正を描画成功で置き換えず、現物運転値は未確定のまま記録する。
### 手順 3: Playwrightで候補を見る（SG-P2/TR-P1/P3）
- [x] 🖐 **操作**: 専用mock viewerへ候補CAD角を入れ正面/側面/斜めPNGとstateを保存する。
- [x] 🔎 **確認**: 画像の軸方向と定義を照合し、現在実機姿勢の再現と誤表示しない。
- [x] 🧪 **テスト**: 同一qposの幾何最下点とクッションplaneを検査し、接触/支持安定性を判定しない。
- [x] 🛠 **エラー時対処**: 対象viewerだけを操作、既存実機bridge/start/stopを呼ばず、撮影失敗は再取得する。
### 手順 4: 文書と汎用skillを残す（SG-P3/TR-P2/P3）
- [x] 🖐 **操作**: docs/STANDBY_POWER_OFF_POSITIONS.mdとrobot-park-pose-definition skillを作成する。
- [x] 🔎 **確認**: 支持確認→負荷を預ける→脱力確認→電源OFFの停止手順と再起動条件、未確定事項を読み直す。
- [x] 🧪 **テスト**: skill quick_validate、JSON/link/field整合、git diff --checkを実施する。
- [x] 🛠 **エラー時対処**: 指令変換や停止の実機確認が必要な残件を明示し、今回simulation-onlyを安全確認済みと書かない。

### 手順 5: 追加の現状写真を反映（SG-P1/P2/TR-P1/P2）
- [x] 🖐 **操作**: HTvws4Qa0AALhgC.jpegの原本hashを記録し、裸アームで写真近似とstandbyのMuJoCo画像を作る。
- [x] 🔎 **確認**: 写真近似角は2D投影からの仮定でありcalibration/実機目標でないこと、C7/カメラを含めない状態を明示。
- [x] 🧪 **テスト**: 裸アームmodelをcompileして向き/頂点結果を保存し、PlaywrightでHTML比較画像がdecodeすることを確認する。
- [x] 🛠 **エラー時対処**: 現状を「CAD完全折畳み・全0°」へ変換せず、支持点不明と版・未校正を残す。


## 4. コマンド参考
コマンドはrtk proxy。rootのuv環境で `uv run --no-sync python temp/evaluate_standby_positions_20261004.py`。
ブラウザ `playwright-cli -s=delivery-review-20261004`、18084は専用simulation、18085はmock。
## 5. 留意事項
描画モデルのgravity/contact/inertiaは物理検証用でない。motor IDはユーザーの役割定義、CAD M-number一致は未確定。neutralはencoder factory2048と同義にしない。未確定情報に暗黙fallbackは置かない。
## 6. 完了の定義
- [x] DoD-P1: 世界向き検証済みのstandby候補、raw基準/未校正のPOWER_OFF_SUPPORTED仕様が保存済み。
- [x] DoD-P2: MuJoCo数値・PNG・机/クッションとの関係とcollision/安定性UNKNOWNが保存済み。
- [x] DoD-P3: 文書・skill・再現script・検査結果と残件が保存済み。

## 7. 作業記録
**重要な注意事項：**
* 開始前に必ずdate "+%Y-%m-%d %H:%M:%S %Z%z"で正確な日時を記録。
* 各項目の開始/完了をその都度記録、同時に未チェック一項目だけ進める。
* コマンド/操作・ファイル・具体的な結果・失敗原因・対処を記録。
* フェーズ開始/完了、コード変更があれば内容、想定外変更を残す。
* Codex、N=40、各行動カウントを明示。未確認を成功にしない。
| 日付 | 時刻 | 作業者 | 作業内容 | 結果・備考 |
| :--- | :--- | :--- | :--- | :--- |
| 2026-10-04 | 09:19:49 JST+0900 | Codex | 計画開始 | ユーザー追加条件・AGENTS・R3 joints・scene・BooleanERROR・skillを確認。レビュー7件は別workdocで完了。 |
| 2026-10-04 | 09:22:11 JST+0900 | Codex | 🖐 **操作**: 直近完了READ logの末尾valid frameとmetadata、R3軸・sceneとBoolean記録を読み出す。 | 最新完了READ live_20261004T002126_286881+0900.jsonlの全5台valid末尾frame/metadata/endとR3軸、既存Boolean gate ERROR_INPUT_BOOLEAN_CONTROLをbaseline-evidence.jsonへ保存。 |
| 2026-10-04 | 09:22:12 JST+0900 | Codex | 🔎 **確認**: countsをCAD角と混同せず、現在freshではないこととneutral/zero未校正を記録する。 | ユーザーneutralは工場2048と同義にしない。ID2の現在程度は未校正のためCAD q2 parameterとして定義し、3例−20/0/+20°は試験例に限定。保存frameはOct4 00:21頃でfreshでない、現在の姿勢全軸CAD角はnullとする。 |
| 2026-10-04 | 09:22:12 JST+0900 | Codex | 🧪 **テスト**: source SHA/5 unique IDs/Torque OFF/closedの保存実体を確認する。 | 保存logのSHAを取得、5 unique IDs・各position/hardware_error/device_alert/fault条件を検査、全台Torque OFF・終了port_closed=true。snapshot自体の取得時刻を保存し再読の現在値と誤認させない。 |
| 2026-10-04 | 09:22:13 JST+0900 | Codex | 🛠 **エラー時対処**: current姿勢のCAD角が求まらなければnullとし、勝手にzero count=現在値へ設定しない。 | 全軸calibrationなしのため電源OFF実機target counts/target CAD anglesは未確定。旧read値はhistory fingerprintのみとし、再現指令に使わない。Boolean対照ERRORは解消せず姿勢候補の干渉/無通電安定はUNKNOWN。 |
| 2026-10-04 09:23:39 JST+0900 | Codex | count reset0 | 保存raw ID1=2054/ID2=3354/ID3=1154/ID4=2058/ID5=2059（00:21:38、全OFF/閉鎖）。世界向きのparameter候補とsupported current named状態を作る。実機targetへの昇格なし。 |
| 2026-10-04 | 09:24:25 JST+0900 | Codex | 🖐 **操作**: offline scriptでCAD候補と保存countsをJSONへ出力する。 | temp/evaluate_standby_positions_20261004.pyを新規作成、実MuJoCoモデルをcompileし、reports/standby-position-20261004/positions.jsonへパラメータ定義・3肩角例・保存raw fingerprint・UNKNOWNゲートを出力。hardware_targets=null。 |
| 2026-10-04 | 09:24:27 JST+0900 | Codex | 🔎 **確認**: 肩q2をパラメータとし肘・手首の相対角を計算、世界方向が一致することを確認する。 | R3軸[Z,−X,+X,+X]をmodelと照合。q1=0、q3=q2、q4=−30で前腕+Y=(0,1,0)、ID5軸=(0,0.8660254,−0.5)。肩−20/0/+20すべて同じ世界向き。ID5中立encoderとθ90 CAD例を区別。 |
| 2026-10-04 | 09:25:13 JST+0900 | Codex | 🧪 **テスト**: MuJoCo compileと複数肩角で前腕pitch0°/ID5方向pitch−30°をassertし、未知calibrationを実機指令へ変換しない。 | compile成功、肩−20/0/+20の世界方向を独立vector assertでPASS。NaN肩角入力はexit2で拒否。ID5実機neutral count/null・全hardware_targets=nullを保持し、mode/countへ自動変換する経路は作っていない。 |
| 2026-10-04 | 09:25:14 JST+0900 | Codex | 🛠 **エラー時対処**: collision ERROR/未校正を描画成功で置き換えず、現物運転値は未確定のまま記録する。 | standby向きPASSとself_collision/連続path/無通電安定UNKNOWNを別field保存。比較用CAD折畳み例は現在再現ではなく、q3約−97.78°で長尺ホルダー等がtableを下回るため停止姿勢として採用しない。現状支持を根拠なくCAD zeroへ置き換えない。 |
| 2026-10-04 | 09:26:40 JST+0900 | Codex | 🖐 **操作**: 専用mock viewerへ候補CAD角を入れ正面/側面/斜めPNGとstateを保存する。 | 専用18084にCAD例[0,−20,−20,−30], θ90を入力し側面・斜めPNGとbrowser-pose-state.jsonを保存。headless Playwrightによる実MuJoCo描画を使用。既存8084不変。 |
| 2026-10-04 | 09:26:41 JST+0900 | Codex | 🔎 **確認**: 画像の軸方向と定義を照合し、現在実機姿勢の再現と誤表示しない。 | 側面PNGを画像で視認。前腕は水平、ID5の支持/ホーン方向は下向き30°。C7の爪の伸びる向きはこの軸と別なので仕様で説明する。q2−20°は仮の描画例、全軸physical neutral/現状肩角は未校正と明記する。 |
| 2026-10-04 | 09:26:42 JST+0900 | Codex | 🧪 **テスト**: 同一qposの幾何最下点とクッションplaneを検査し、接触/支持安定性を判定しない。 | visible mesh実頂点のworld座標でstandby下流最下点43.50 mm、クッション上面5 mmとの差38.50 mm（footprint不明、接触未確認）を保存。standby_power_off_allowed=false。畳みCAD例はtable下へ48.49 mm達するので現状として採用せず不一致を明示。 |
| 2026-10-04 | 09:26:43 JST+0900 | Codex | 🛠 **エラー時対処**: 対象viewerだけを操作、既存実機bridge/start/stopを呼ばず、撮影失敗は再取得する。 | JSONとPNGの同一qposを確認。専用test serverは無serial。実機bridge/start/stopは呼んでいない。photoreal/dynamicsの成功に置換せず、物理支持とfull-path検証をUNKNOWNとして仕様へ渡す。 |
| 2026-10-04 | 09:30:05 JST+0900 | Codex | 🖐 **操作**: docs/STANDBY_POWER_OFF_POSITIONS.mdとrobot-park-pose-definition skillを作成する。 | docs/STANDBY_POWER_OFF_POSITIONS.mdと新規robot-park-pose-definition skill/reference、persistent scripts/evaluate_arm_park_pose.pyを作成。2姿勢/世界ベクトル/現在supported基準/停止startup状態遷移/unknownと実機未実行を記述。root uvから明示simulation-rootで再現PASS。 |
| 2026-10-04 | 09:32:52 JST+0900 | Codex | 🔎 **確認**: 支持確認→負荷を預ける→脱力確認→電源OFFの停止手順と再起動条件、未確定事項を読み直す。 | 支持成立を写真だけで断定せず、ユーザー報告の安定姿勢をnamed baselineとする。支持→脱力確認→OUTPUT OFF、再起動はfresh READと校正確認の順を定義。追加写真は裸アームなので新規手順5でC7/カメラ無し表示を反映する。 |
| 2026-10-04 | 09:32:53 JST+0900 | Codex | 🧪 **テスト**: skill quick_validate、JSON/link/field整合、git diff --checkを実施する。 | 新規skill quick_validate PASS、script ruff PASS（初回import/line長をapply_patchで修正）、両repo差分検査PASS。positions JSONはorientation PASS/hardware_targets=null、code継続検査は手順5後に実施する。project .codexに新skillリンクを登録した。 |
| 2026-10-04 09:33:52 JST+0900 | Codex | count reset0 | 現状写真追加。裸アームに近い折畳み姿勢、C7/カメラ無しを新規手順5で確認。2D写真をencoder校正へ昇格せず、supported currentの基準画像として保存する。 |
| 2026-10-04 | 09:33:53 JST+0900 | Codex | 🛠 **エラー時対処**: 指令変換や停止の実機確認が必要な残件を明示し、今回simulation-onlyを安全確認済みと書かない。 | 実機command値、支持点、load/friction/dynamic stabilityは未確定。ユーザーの写真・現在安定報告を採用してもold countsを再生しない。review P1未修正の実機制御へ進めず、候補定義/数値/表示だけを成果とする。 |
| 2026-10-04 | 09:34:40 JST+0900 | Codex | 🖐 **操作**: HTvws4Qa0AALhgC.jpegの原本hashを記録し、裸アームで写真近似とstandbyのMuJoCo画像を作る。 | 追加写真原本のSHA保存・同一bytesコピーをevidenceに保存。bare geom group0のみで写真近似[0,−30,−75,+25]°とstandby例[0,−30,−30,−30]°を実MuJoCoでside/iso描画し、photo-pose-analysis.jsonと比較HTMLを作成。 |
| 2026-10-04 | 09:37:33 JST+0900 | Codex | 🔎 **確認**: 写真近似角は2D投影からの仮定でありcalibration/実機目標でないこと、C7/カメラを含めない状態を明示。 | 比較PNGを視認。写真近似はq2−30/q3−75/q4+25という仮のside-plane例で、encoder/CAD校正ではない。現状は裸アームに見え、C7/カメラ無しgroup0で表示した。support contactを写真だけで断定しない。 |
| 2026-10-04 | 09:37:35 JST+0900 | Codex | 🧪 **テスト**: 裸アームmodelをcompileして向き/頂点結果を保存し、PlaywrightでHTML比較画像がdecodeすることを確認する。 | 裸アームMuJoCo compile、world0°/−30° assert、source写真コピーSHA一致。Playwright比較HTML4画像がdecode（photo2048×1935、MuJoCo1060×760）、横overflowなし。static file protocol禁止は専用127.0.0.1:18086で代替、favicon404だけを検出した。 |
| 2026-10-04 | 09:40:04 JST+0900 | Codex | 🛠 **エラー時対処**: 現状を「CAD完全折畳み・全0°」へ変換せず、支持点不明と版・未校正を残す。 | 写真近似は現在値へ昇格せず、q3−75表示例もphysical safe rangeとは扱わない。専用mock test rendererを終了し、18084にbridge無しmanual-only standby previewを起動。既存8084/8087や他user browser不変。比較HTMLと再現スキルを保存し、5自己レビューで修正した。 |
| 2026-10-04 09:40:42 JST+0900 | Codex | count reset0 | photo/bare/orientation artifacts保存、5自己レビュー完了。mock18085と旧専用renderer終了、18084 manual-only previewを残す。最後にDoDのJSON/link/source/quality整合を確認する。 |
| 2026-10-04 | 09:42:22 JST+0900 | Codex | DoD-P1: 世界向き検証済みのstandby候補、raw基準/未校正のPOWER_OFF_SUPPORTED仕様が保存済み。 | 姿勢仕様にworld向き、肩parameter/null physical neutral、支持current named状態とlatest保存raw出典を記録。追加写真は基準image、近似角は未校正。positions.json hardware_targets=nullを最終assert。 |
| 2026-10-04 | 09:42:23 JST+0900 | Codex | DoD-P2: MuJoCo数値・PNG・机/クッションとの関係とcollision/安定性UNKNOWNが保存済み。 | MuJoCo方向ベクトルとside/iso/photo比較PNG・model qpos保存、Playwright decoded4画像/overflow確認。机・クッションとの差を幾何で保存し、衝突/連続path/支持動力学はUNKNOWNと記録。 |
| 2026-10-04 | 09:42:23 JST+0900 | Codex | DoD-P3: 文書・skill・再現script・検査結果と残件が保存済み。 | docs/STANDBY_POWER_OFF_POSITIONS.md、portable explicit-root verification3scripts、汎用skill、自己review5回、FINAL_CHECK.json保存。ruff/maintained ty/skill format/JSON/link/diff PASS、元STEP SHA不変。18084 manual-only preview作動（READ未設定/開始無効）、既存session保持。 |
