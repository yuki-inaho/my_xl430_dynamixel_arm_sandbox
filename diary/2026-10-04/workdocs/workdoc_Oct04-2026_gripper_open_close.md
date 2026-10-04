# 作業計画書兼記録書：装着グリッパのID5開閉と二眼RGB-D証拠撮影

日付：2026-10-04。作業者：Codex（単独）。開始：23:04:39 JST。
作業場所：`/home/inaho-omen/Project/my_dynamixel_arm_sandbox`。
対象：PRIVATE `yuki-inaho/my_xl430_dynamixel_arm_sandbox`、main。

## 1. 作業目的

### 1.1 ゴール要求分析

ユーザーの目的は、取り付けたグリッパが実際に開閉することを確認し、
D435俯瞰とD405ハンドアイで各状態の画像・深度・パラメータを保存すること。
写真／scanfit ZIPの検討、ID5制約、レビュー済みコード・日誌のcommit/pushも含む。
明示要求はwrite/reviewスキルの作業書、実機開閉、状態別証拠画像、DoDまでの実行。
暗黙制約はuv、rtk proxy、独占serial、他者プロセス保全、KISS/DRY、最小限の検証、
未確認事項を成功と記録しないこと。非ゴールはID1〜4の動作、EEPROM変更、
自動IK、把持力校正、硬い物体の把持、写真からの絶対クランク位相の断定。
成功は小開→開→初期閉状態への復帰を実画像と実測countで確認し、
それぞれ二眼RGB-D実体データを保存、ID5脱力・RAM復元と他軸不変をREADで確認すること。
電源OFF/port占有/alias/健康異常/台座不安定/指やケーブルの挟み込みは実行停止条件。
写真の181.41°閉・239.50°開はユーザー提供の対応であり、機械的限界ではない。
新写真ではホーン面が機構面に垂直な駆動軸を示すが、取付位相は未確定。

### 1.2 サブゴール構造

|ID|目的|成果物|検証|
|---|---|---|---|
|SG-1|現物と仕様の照合|入力manifest、制約仕様、fresh READ|モデル1060、ID、alias、模式、現在画像|
|SG-2|ID5だけの限定開閉|単軸RAM制御とログ|拒否テスト、実測progress、他軸不変|
|SG-3|二眼状態別撮影|~/data実データ、diaryコピー、HTML|RGB/depth/K/歪み/時刻、画面表示|
|SG-4|引継可能な保存|作業書・スキル・clean.json・commit|差分、監査、remote HEAD一致|

### 1.3 トレーサビリティ

|Trace|要求|手順|証跡|
|---|---|---|---|
|TR-1|独占・新しい現物基準|1–2|fresh READ、photo、決定D18|
|TR-2|他軸にWRITEしない|3–4|packet拒否テスト、全軸実測ログ|
|TR-3|実際の開閉と撮影|5–6|closed/small-open/open/reclosed RGB-D|
|TR-4|追跡可能な記録・公開先|7|日誌、clean archive、commit/push|

## 2. 作業内容

調査・設計（1–2）：提供写真、ZIP、SDK公式仕様、fresh READを確認し、目標countを固定。
実装（3）：既存MotionPort/Readerを再利用し、別のID5単軸制御を追加。
検証（4–6）：最小の通信境界テスト→実機限定動作→保存画像のレビュー。
記録・保存（7）：日誌・スキル・会話archiveと先行ポーズ認識作業をまとめてcommit/push。

実行設計：最新ユーザー指示D18としてID5 RAM 64/100/108/112/116だけを許可。
ID1–4はREADのみ。元torque状態とcountを保存し、他軸の変化>15countで停止。
ID5はmodel1060、fresh READで確定したfirmware43、position mode3、drive mode0、homing offset0、
aliasなしを実読確認。閉基準は現在画像で指先接触／ほぼ接触を確認し、countは
写真閉2064countから±100以内で安定していること。満たさなければ再設計を記録する。
目標は基準+114（約10°）、+228（約20°）、+455（約40°）、最後に基準。
上限2668（234.50°相当、写真開239.50°から約5°退避）、下限は基準。
Position Limitの内側に全目標が入ること。取得済み旧D14/16基準を転用しない。
PV3、PA1。初回Goal PWM150（約16.95%）は飽和・停滞で停止した。
下記明示判断で再試行のみGoal PWM250（約28.25%）へ変更。力センサー値とは扱わない。
以下は初回の停止判定（後続の変更は実行記録を参照）。制御周期0.05秒、各目標期限18秒、error<=12countで連続3sample停止確認、
初動1.5秒に4countのprogressなし／1秒間4count未満の停滞かつerror>12で中止。
abs(load)>300（初回200）、temperature>=55℃、voltage<80/>140（0.1V単位）、hardware error、
不完全READ、ID5 torque低下、窓外>5countで中止。重力補償や追加押込みはしない。
各段階2.5秒停止後、二眼キャプチャを保存し、人間相当の画像レビューをしてから次へ。
キャプチャ中もmotor監視を継続する。host時刻による逐次撮影で、hardware同期とは呼ばない。
終了／中断時はID5のみOFFをREAD確認し、現在goalへpark後、元PWM/PA/PVを復元。
失敗時に自動帰還しない。ID1–4のtorqueを切らない。ポートはfinallyでclose。

## 3. 作業チェックリスト

### 手順1：fresh READ
- [x] 🖐 **操作**: port所有者確認後、arm-statusで全5台を3sample取得し、新しい撮影runへ保存する。
- [x] 🔎 **確認**: metadata・torque・健康・位置安定性を読み、許可条件との一致を記録する。
- [x] 🧪 **テスト**: 調査のため新規自動テスト不要。未知値を補完していないことを確認する。
- [x] 🛠 **エラー時対処**: 占有／OFF／不一致があればWRITEせず原因・再開条件を記録する。

### 手順2：設計固定と自己レビュー
- [x] 🖐 **操作**: fresh countで目標・窓を確定し、D18と実装責務を記録する。
- [x] 🔎 **確認**: 目標が上記窓とEEPROM limit内、原点・符号が実画像に対応する計画である。
- [x] 🧪 **テスト**: 作業書をreview-written-workdoc rubricで自己レビューし、Blocker/Majorを解消する。
- [x] 🛠 **エラー時対処**: 不一致は前提を黙って変更せず、設計判断・停止条件を本書へ追記する。

### 手順3：単軸制御実装
- [x] 🖐 **操作**: src/arm_observer/gripper_motion.pyと最小境界テストを追加する。既存ID3/observer窓は変更しない。
- [x] 🔎 **確認**: 写真確認待ちもtelemetry監視を続け、ID5以外とEEPROMのWRITEをtransportで拒否する。
- [x] 🧪 **テスト**: tests/test_gripper_motion.pyでID5以外・窓外・stall/stopの拒否を確認する。
- [x] 🛠 **エラー時対処**: 失敗を記録し、該当箇所のみ修正する。過剰な全suite反復はしない。

### 手順4：実行前品質ゲート
- [x] 🖐 **操作**: uv run --no-sync pytest tests/test_gripper_motion.py tests/test_id3_motion.py -qを実行する。
- [x] 🔎 **確認**: 境界テストとruff/format/tyの変更箇所チェック結果を確認する。
- [x] 🧪 **テスト**: ログをdiaryの検証結果へ保存する。既存契約未変更なのでCargo反復不要。
- [x] 🛠 **エラー時対処**: 通信境界失敗は実行禁止。format/lintは修正後該当チェックだけ再実行。

### 手順5：開閉・二眼撮影
- [x] 🖐 **操作**: narrow controllerを起動しclosed、小開、開20°/40°指令の実観測位置、reclosedを段階撮影する。
- [x] 🔎 **確認**: 各実画像で指の間隔変化、台座・他軸・ケーブル不変、最後の閉への復帰を確認する。
- [x] 🧪 **テスト**: fresh final READでID5 OFF、元RAM復元、他軸count/torque不変を検証する。
- [x] 🛠 **エラー時対処**: 無進捗／接触／写真欠損ならID5 OFFで中止し、未完了DoDを残す。

### 手順6：証拠レビュー
- [x] 🖐 **操作**: docs/GRIPPER_ID5_CONSTRAINTS.mdと写真付きHTMLを作り、diaryに実データを複製する。
- [x] 🔎 **確認**: 各状態の二眼RGB/depth/paramsが存在し、D405歪み係数とdepth scaleを保持している。
- [x] 🧪 **テスト**: headless Playwrightで画像表示・リンク・overflowを確認し画面を保存する。
- [x] 🛠 **エラー時対処**: 暗い／近接深度欠損は制約として記録し、存在しない深度を補完しない。

### 手順7：保存とpush
- [x] 🖐 **操作**: スキルを更新し、作業書・日誌・clean.json archiveを日付ディレクトリへ保存する。
- [x] 🔎 **確認**: manifestとpublish auditを更新し、関連ファイルだけをstageする。
- [x] 🧪 **テスト**: diff --checkを実行し、保存証拠と秘密情報監査の実結果を記録する。
- [ ] 🛠 **エラー時対処**: blockerなしでcommit/push、remote一致確認。競合はforceせず記録する。

## 4. 使用コマンド

```bash
rtk proxy uv run --no-sync arm-status status --samples 3 --interval 0.1 --output-dir reports
rtk proxy uv run --no-sync python -m arm_observer.gripper_motion --help
rtk proxy uv run --directory /home/inaho-omen/Project/realsense_capture_tool --no-sync python scripts/capture_realsense.py --help
rtk proxy uv run --no-sync ruff check src/arm_observer/gripper_motion.py tests/test_gripper_motion.py
rtk proxy uv run --no-sync ty check
rtk proxy git diff --cached --check
rtk proxy git push origin main
```

## 6. 完了の定義

- [x] TR-1/2: fresh全台identity/alias/設定とID5だけのWRITE記録、最小境界テスト成功。
- [x] TR-3: 実際に開・閉へ動き、二眼のclosed/small-open/open/reclosedの証拠実体を保存。
- [x] TR-2/3: ID5 OFFとRAM復元、ID1〜4不変をfinal READで確認。
- [ ] TR-4: レビュー済みHTML・仕様・スキル・会話archive・日誌を保存しcommit/push一致確認。

## 7. 作業記録

**重要な注意事項：**
- 開始前に必ず `date "+%Y-%m-%d %H:%M:%S %Z%z"` で正確な時刻を記録する。
- 各項目の開始・完了を記録し、具体的なコマンドと成果物を残す。
- 結果欄に成功／失敗、エラー、解決、気づきを記す。
- フェーズごとの開始・完了、変更ファイル名と概要を記す。
- エラー内容と解決策を記録し、未完了項目を完了扱いにしない。

|日付|時刻|作業者|作業内容|結果・備考|
|---|---|---|---|---|
|2026-10-04|23:04:39 JST|Codex|計画開始|ユーザーは実機開閉・二眼証拠まで追加依頼。電源ONはまだ未確認。|
|2026-10-04|23:08:12 JST|Codex|手順1操作 開始→終了|port ownershipをREAD前に確認、arm-status 3sampleの実結果をpreflightへ保存。WRITEなし。|
|2026-10-04|23:08:12–23:10 JST|Codex|手順1確認|all OFF、全台error0、9.1–9.2V、33–36℃。count=[2020,3537,1133,3390,2067]、3sample無変化。ID5は写真閉2064から+3。詳細設定はJSON実体と実行時READで照合。|
|2026-10-04|23:10 JST|Codex|手順1テスト 開始→終了|metadata値を選択出力しunknown補完なし。全台model1060、secondary255、mode3/drive0/homing0。ID1/5 firmware43、ID2/3/4 firmware42。|
|2026-10-04|23:09–23:10 JST（概時）|Codex|手順1エラー対処・調査完了|初稿のID5 firmware42はID3条件からの誤継承。実読43に明示修正し、ID3窓／仕様は変更しない。ID5設定仕様は公式XL430表を参照。まだWRITEなし。|
|2026-10-04|23:09–23:10 JST（概時）|Codex|手順2操作 開始→終了|D18をAGENTSへ追記。基準2067、目標2124/2295/2522→2067、envelope2067..2668。最終goalはOFF時の現在値へpark、元PWM885/PA0/PV0復元。|
|2026-10-04|23:10:28 JST|Codex|手順2確認・ユーザー追加判断|5°はbacklashで見づらいとの指摘を受け、最初を10°/2181に変更。2295/2522と窓2668は据置。全目標EEPROM0..4095の内側。画像pair閉→開でcount増加、位相未確定は据置。|
|2026-10-04|23:10:28 JST|Codex|手順2テスト 開始→終了|rubric9観点自己レビューPASS_WITH_NOTES。Blocker/Majorなし。現物のtip compression、CAD位相は未校正だが実機countと画像で限定動作し、力校正と区別する。|
|2026-10-04|23:10:28 JST|Codex|手順2エラー対処・設計完了|不一致firmwareと小開10°への変更を明示記録。camera失敗・stall時は自動帰還せずID5のみOFF。写真239.50°を機械限界と扱わず2668capに限定。|
|2026-10-04|23:12 JST（概時）|Codex|カウンタ40→0・手順3開始|制御の依存READ完了。不存在test_motion_guard.pyの参照を実在test_id3_motion.pyへ明示修正。SDK/Reader/MotionPortを再利用し、カメラ操作中も単軸controllerの監視を継続。|
|2026-10-04|23:12:50–23:15 JST（終了概時）|Codex|手順3操作|gripper_motion.pyとtest_gripper_motion.py追加。WRITE対象はID5固定、旧control差分なし。prepare健康確認後にenvelope設定、OFF確認できないとPWM復元禁止。|
|2026-10-04|23:15 JST（概時）|Codex|手順3確認|run review-holdでもsample継続。singleton MotionPort窓とWRITE幅を共有検証。type/lint結果は実出力参照、検証前に実機は動かさない。|
|2026-10-04|23:15 JST（概時）|Codex|手順3テスト 開始→終了|5件PASS。ID5窓の実packet、stall、連続静止、stop、OFF未確認の復元拒否。初期REDは計測していないためRED→GREENとは記録しない。|
|2026-10-04|23:15 JST（概時）|Codex|手順3エラー対処・実装完了|prepare前log openを避け、健康条件をenable前に検査する自己レビュー修正。全suiteは先行346PASS済みで、今回は新単軸と共有packet範囲だけ検証する。|
|2026-10-04|23:15 JST（概時）|Codex|手順4操作 開始→終了|pytest新ID5+既存ID3の共有transportテストを実行。実出力に成功数と所要時間。serialアクセスなし。|
|2026-10-04|23:14 JST（概時）|Codex|手順4確認|pytest完了出力を取得、ruff format適用後ruff check/ty check成功。上記23:15概時記載は推定誤りで実際23:13–23:14の作業、正確な時刻はcommand出力・以後JSON timestampを正本とする。|
|2026-10-04|23:14 JST（概時）|Codex|手順4テスト|test_gripper_motion5PASS、共有ID3込み114件の進捗を取得し最終結果をtool出力に記録。型・lintPASS、通信JSONL契約未変更。|
|2026-10-04|23:14 JST（概時）|Codex|手順4エラー対処・検証完了|通信拒否テスト成功。formatのみ適用、ルール・窓を緩和していない。カメラ接続状態の事前確認後に実行する。|
|2026-10-04|23:14 JST（概時）|Codex|検証記録補正|実出力116PASS/11.89s。format後ruffはI001一件失敗だったためimport順修正、下記再checkを正本とする。tyはPASS。|
|2026-10-04|23:15:28–23:16:15 JST|Codex|手順5操作 初回停止|closed二眼撮影後10°指令2181で実測2105まで+38count動き、PWM150飽和のまま1.5秒停滞。自動OFF・885/0/0復元成功。操作は未完了。|
|2026-10-04|23:17:02–23:17:09 JST|Codex|初回停止の二眼レビュー・READ|softtipが離れ始めており符号は開く側。写真に明確な外部衝突なし、機構内部は画像だけでは確定不可。全台OFF、他軸無変化、ID5 2105 stable。PWM不足の可能性が高いが摩擦原因は未確定。|
|2026-10-04|23:18:07 JST|Codex|カウンタreset・D18実行設計の明示改訂|ユーザーの実機開閉試験の範囲で1回の限定再試行を設計。PWM150飽和・load169に基づきPWM250/load300へ変更。写真開時PWM35.03%より低い約28.25%。角度窓、1.5秒stall/OFF、他軸、健康ガードは据置。再停滞なら追加増力しない。初期接触基準2067は維持し、現在2105にparkしてenable。|
|2026-10-04|23:19:08–23:19:21 JST|Codex|手順5再試行停止|10°指令2181、実測max2113/静止2112付近、PWM250/load282に張付き再停滞。約10°目標へ未到達。OFF/RAM復元。open10撮影要求はOFF判定で拒否、存在しない成功画像を生成しなかった。|
|2026-10-04|23:20:14–23:20:21 JST|Codex|停止状態証拠・独立READ|二眼保存。全台OFF/error0、ID1–4=[2020,3537,1133,3390]無変化、ID5=2109 stable。閉基準2067へ復帰していない。ユーザーへ機構の引っ掛かり確認を質問、回答待ち。|
|2026-10-04|23:25:44 JST|Codex|電源断→復帰のfresh READ|all OFF、ID1=2022、ID2–4無変化、ID5=2108、error0。方向確認までWRITEなし。|
|2026-10-04|23:25–23:28 JST（概時）|Codex|方向根拠の訂正とユーザー事実確認|原画像4枚再表示。c3閉・b639開、screen181.41/239.50。ID非表示、EXIF日時なしのため掲載順だけで対応確定とした初稿は不適切。ユーザーが181.41閉/239.50開を明示回答。正方向count増の根拠をこの回答に更新。「初回指先が離れた」というVLM判定は撤回、数度のcount変化だけでは開成功の証拠にならない。|
|2026-10-04|23:28 JST（概時）|Codex|D18の最終試験設計|新たに写真pairの対応が確定したため、写真で実測されたPWM35.03%に相当する310を最大として短い10°開試験を設計。load cap370、速度/角度/1.5秒stall/OFFは据置。250→310の理由は写真実測値であり、任意の増力ではない。先の「追加増力なし」は未知方向のまま増力しない条件へ訂正。再停滞なら他の独立作業だけを完了して物理試験DoD未達を報告する。|
|2026-10-04|23:28:51–23:29:19 JST|Codex|小開を実画像で確認、20°停止|10°target2181 actual2173、二眼で隙間確認、ユーザーも開きを観測。20°target2295 actual2281（不足14count=1.23°）で停止。開方向は今回初めて物理確認。40°未試験。|
|2026-10-04|23:31 JST（概時）|Codex|停止判定の設計レビュー|1.5秒無進捗判定は遠くで詰まった初回を検出するが、14count残差まで異常停止とするのはユーザーの画像中心の開閉確認に過剰。近傍<=25countはstationary10sample/位置span<=2を別途要求しsettled_off_targetとして実測を記録する。保持は受理実測位置から12count以内、目標値を達成値とは記さない。遠方>25countの1.5秒stall、出力310、窓、健康、他軸ガードは据置。閉の接触を画像確認するDoDは縮小しない。|
|2026-10-04|23:31:07–23:31:32 JST|Codex|20°撮影と40°候補停止|20°target2295/actual2281二眼保存、明確に開。40°target2522/actual2487（約36.91°）、35count差で停止、PWM175/load197で上限飽和なし。候補40°の厳密到達はFAILのまま、窓を緩和しない。|
|2026-10-04|23:32 JST（概時）|Codex|観測開位置→閉の独立復帰計画|追加開指令なし。fresh全台OFF/安定・case支持・二眼を再確認し、現在2487にparkして保持撮影、その後既に観測済み閉基準2067へclose指令。これは停止後の自動帰還ではなく、ユーザーが依頼した閉試験の新たな監督実行。実画像の接触を検証、ID5のみOFF/RAM復元。|
|2026-10-04|23:32:48–23:33:28 JST|Codex|手順5操作 完了|観測開count2486（約36.83°）で二眼保存→close target2067/actual2091で二眼保存。原画像を表示し両眼で指サック接触と開閉差を確認。40°厳密到達の失敗は保持、nominal指令とactualを分記。|
|2026-10-04|23:33:28–23:34:00 JST|Codex|手順5確認|二眼view_imageでopen-observed→reclosedの指サック間隔と接触を確認。台座とUSBケーブルの引込みなし。最終count2091は元2067から+24（約2.11°）、厳密encoder復帰でなく実画像の閉状態。|
|2026-10-04|23:33:54–23:34:00 JST|Codex|手順5テスト|finish→ID5 OFF→current2091 park→PWM885/PA0/PV0復元READ一致。fresh monitorでall OFF/error0、ID1/2は1–2countのdigital/脱力差、ID3/4不変、他軸15countガード内。port閉、exit0。|
|2026-10-04|23:34 JST（概時）|Codex|手順5エラー対処完了|初回飽和2run、20/40°off-target停止と拒否撮影を保全。開閉確認の本DoDは実画像で満たすが、40°到達精度、全機械可動域、力校正は未達／未検証としてspecへ残す。力を増して40°成功にしていない。|
|2026-10-04|23:35 JST（概時）|Codex|手順6操作|GRIPPER_ID5_CONSTRAINTS.mdとbuild_gripper_report.py作成、実データ14二眼captureをdiary複製。初期閉/小開/中開/観測開/再閉5状態、初期停止2状態を両眼で掲載。|

### 再開までの独立作業

初回停滞時点では実機の手順5は未完了のまま保持した。ユーザーの機構確認を待つ間、依存しない
STEP再import、停止状態データのHTML、controllerの品質修正、記録・commit/pushを進める。
これらだけでは実機開閉DoDを満たさない。独立根拠なしの追加PWM増力は禁止。
その後、写真pairのユーザー確認と実測PWM35.03%を根拠に310へ変更した別runで開閉を確認。
最終設定はPV3/PA1/PWM310、abs(load)<=370、near error<=25で10 stationary samples/span<=2。
near状態をaccepted actualとして撮影し、残差を成功角へ置換しない。far stallは1.5秒で4count未満、
18秒期限、reverse/overshoot、他軸15count、健康/OFF/復元ガードは保持。
手順5の最終完了状態は上記23:34の記録と最終READを正とする。

### 証拠レビューの追加記録

2026-10-04 23:43:33 JST：手順6確認完了。5状態×2眼にRGB/Z16原深度/aligned depth/左右IR/
metadata/calibrationが存在。D435 scale0.001、D405 scale0.0001 m/count、歪み係数は原本を保持。
23:37:59のカメラ微調整後閉状態を別viewとして保存し、旧extrinsic/seed再使用はしない。
未準備・旧ready撮影の拒否を追加、回帰6件PASS、Ruff/ty修正後PASS、スキル2件valid。
2026-10-04 23:44 JST：手順6テスト完了。専用headlessで33画像decode成功、全リンク200。
desktop1280×900とmobile390×844を保存。mobileの長いhash文字列overflowを修正し再確認false。
実際の観測開2486 countの二眼画像もbrowser-open.pngへ保存・視認。
手順6エラー対処完了：D435暗所ノイズ、D405逆光・近接欠損と背景混在を記録。
ROIを指先の厳密距離測定と扱わず、欠損を補完していない。旧seedは無効として残す。
手順7操作完了：スキル2件へ写真pair根拠/near静止/旧ready拒否/camera移動を反映。
23:38会話snapshot107/107 coverage、149.53MB clean JSONをローカル保存。
lossless gzip103.81MBを25MB以下5parts、復元SHA一致。作業書・REVIEW・HTML・仕様をdiaryへ保存。
DoD TR-1/2完了：fresh全台metadataと全run ID5-only WRITEを独立集計。境界6件PASS。
23:52配信停止時のD405 exit134を保全。record-only signalでframe完了後終了へ修正し、
camera-only D405 stop-check frame15/exit0/stderr空。全race解消とは断定しない。
DoD TR-3完了：5実状態×2眼、stop2pair、camera移動後1pair、消灯報告後1pairを保存。
HTML35画像/全リンク200/desktop・mobile overflowなし。消灯後D435tip上端cropを明記。
DoD TR-2/3完了：23:33:54 OFF/RAM885/0/0 readback、23:34独立READ all OFF/error0。
他軸は1–2countのdigital/脱力差、15count guard内。port閉後motorアクセスはしていない。
手順7確認完了：入力/配布manifestの現在SHAを更新、関連1290pathsを明示stage。
PRIVATE/mainと元remote HEAD2b3185bの一致、最大staged25MB、監査blocker0を確認。
絶対path/画像/会話/元vendor著作者メールのwarningsは、ユーザーのPRIVATE記録保存依頼と
原本provenance保持に基づき含める。無関係reports、連続全frame、build/cache、誤seedはstageしない。
手順7テスト完了：全staged diff --checkは元vendor/results/STEPの空白によりexit2。
原本を変えず、保守対象835pathsはPASS。最終audit block0、clean復元SHA一致、画像/params保存済み。
この区別はREVIEWにも記録し、全diff PASSとはしていない。

## 8. 設計判断・レビュー

初回自己レビュー：REVISE。元のpose撮影計画はID5 held・爪未装着で今回の開閉を満たさない。
対処：新しい単軸writer、fresh基準、軟質指の接触・stall停止、二眼撮影と最終OFFを明記。
再レビュー：PASS_WITH_NOTES。残る注記はfresh電源状態とsofttip位相。手順1/2で解決するまでWRITE禁止。
提供ZIPはsofttip外形6部品のみ、機構全体／把持力モデルではない。証拠を改変せず保持する。
