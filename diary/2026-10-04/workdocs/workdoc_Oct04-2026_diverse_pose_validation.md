# 作業計画書 兼 記録書：多姿勢の認識検証と処理時間改善

**日付:** 2026年10月04日 21:32 JST
**作業ディレクトリ:** /home/inaho-omen/Project/my_dynamixel_arm_sandbox
**作業者:** Codex、単独実行・自己レビュー。サブエージェントなし。

## 1. 作業目的

### 1.1 ゴール要求分析
ユーザー要求は「より多様かつ自己干渉しない関節角でRealSenseと照合してポーズ認識を確認し、実行時間も最適化」。前回は主に台座・肘のみで、IoUの合格を関節認識の正しさと同一視できない。
今回は実機の相対encoder変化と、encoderを入力しないRGB-D推定の変化を比較する。肩・手首を含む候補を作り、支持・配線・実画像を確認して段階的に進める。画像から得た角度を実機目標へ流さない。
絶対校正と全可動域の衝突保証は未達のまま隠さない。失敗姿勢・未観測軸を含む結果を成果とする。ID5には爪がなく画像上可観測な自由度でないので保持する。
既存MuJoCo表示モデルは接触を無効化している。干渉検査の合格証拠に流用しない。旧手首−5°停止例を調べ、同じ経路を再実行しない。
成功条件は、可能な範囲の約20姿勢と各軸の実変化・推定変化・実RGB-D・成否・時間を対応付け、失敗を解析すること。性能は同一設定・同一入力で前後比較し、live全時間に対する成功Hz、frame/mask age p50/p95、追跡率、処理段階を記録する。静止の短い好成績を全姿勢性能と呼ばない。
ユーザーは自律的な観察・動作を許可済み。新しい制御経路を作らず既存ガードを再利用。uv --no-sync、rtk proxy、手編集apply_patch、最小限のテスト。無関係な差分・他のカメラ所有processは保持する。

### 1.2 サブゴール構造
| ID | 内容 | 成果物・検証 |
|---|---|---|
| SG1/TR1 | 多様な候補と制約 | 撮影表、実画像、全5台READ、停止/復帰記録 |
| SG2/TR2 | 認識の独立評価 | 画像推定とencoder相対変化、深度残差、IoU、可観測性 |
| SG3/TR3 | 性能改善 | 段階profile、同条件前後比較、全経過時間のlive統計 |
| SG4/TR4 | 再現性 | scripts/、skills/、docs/、日付別diaryとHTML |

### 1.3 トレーサビリティ方針
データ正本は ~/data/xl430-arm/2026-10-04/diverse-recognition/、検証・報告は diary/2026-10-04/diverse-recognition/。RGB-Dと推定を同じframeで保存し、encoderを時刻で前後観測する。ハードウェア同期ではない。推定の関節角は絶対真値としない。相対差5°超は診断対象として明示し、低残差だけで合格にしない。

## 2. 作業内容
フェーズ1：既存干渉/動作停止記録と実装の調査、撮影範囲・測定方法を決定。
フェーズ2：現行性能を記録し、測定された律速だけを改善。撮影保存/評価は既存SDK ownerと制御を再利用。
フェーズ3：最小検査後に段階動作・撮影・レビュー。候補間の遷移も実画像で評価。失敗時は既存hold/return/release規則を守る。
フェーズ4：姿勢評価・性能・失敗をレポートにまとめ、スキルへ汎用知見を反映。

## 3. 作業チェックリスト

### 手順 1: 制約と撮影計画の調査（TR1/TR2）
- [x] 🖐 **操作**: 既存停止記録・モデル・現物を調べ、撮影候補と動作範囲を本書へ記録。
- [x] 🔎 **確認**: CAD角とcountを分離し、肩/手首候補の採用・不採用理由がある。
- [x] 🧪 **テスト**: 調査の自動テストは追加せず、現物画像と元ログを照合。
- [x] 🛠 **エラー時対処**: 干渉や配線が不明な候補は実行せず、根拠のある縮小候補と未検証範囲を記録。

### 手順 2: 現行性能の測定（TR3）
- [x] 🖐 **操作**: 現行ライブ全期間統計と同じ保存frameの処理profileを保存。
- [x] 🔎 **確認**: 初期化、推定、描画、mask、保存I/Oを区別し律速を特定。
- [x] 🧪 **テスト**: 計測のための追加単体テストは不要。実frame・入力hash・設定を保存。
- [x] 🛠 **エラー時対処**: GPU競合や鮮度切れは除外せず記録。無関係processを止めない。

### 手順 3: 測定に基づく実装改善（TR2/TR3）
- [x] 🖐 **操作**: perceptionと再利用する撮影/評価scriptを最小変更し、変更理由を記録。
- [x] 🔎 **確認**: 質・鮮度ゲートを緩和せず、同一入力で結果/時間を比較。
- [x] 🧪 **テスト**: tests/test_perception.pyと変更した制御境界の既存テストを実行。新しい不具合には代表回帰ケースのみ追加。
- [x] 🛠 **エラー時対処**: 性能退行は条件差を確認し、悪化した変更を採用しない。motor安全判定を緩めない。

### 手順 4: 多姿勢撮影（TR1/TR2）
- [x] 🖐 **操作**: fresh all-OFF/read/画像から開始し、1姿勢ずつ保持・RGB-D保存・目視レビューして復帰。
- [x] 🔎 **確認**: 各画像、推定、前後READ、timestamp、失敗も保存。最終全台OFFとRAM復元を確認。
- [x] 🧪 **テスト**: 実行前に既存packet/envelopeチェックを1回。繰り返す模擬動作試験は作らない。
- [x] 🛠 **エラー時対処**: 逆動作・停滞・支持移動・接触・張った配線は次姿勢へ進めずhold。支持姿勢への復帰が無理なら支援を求める。

### 手順 5: 独立比較と実時間検証（TR2/TR3）
- [x] 🖐 **操作**: 軸別相対変化、深度/輪郭、追跡率・時間を全撮影行で集計。
- [x] 🔎 **確認**: 成功/失敗/観測不能/未実行を区別。追跡失敗の時間を速度計算から消さない。
- [x] 🧪 **テスト**: 1回の対象suite・ruff・ty・complexityと専用headless Playwrightで実画像を確認。
- [x] 🛠 **エラー時対処**: 精度不良は画像の対応とモデル・mask・局所解を調べ、改善できない範囲を制約として明記。

### 手順 6: 成果物とスキルの更新（TR4）
- [x] 🖐 **操作**: docs/・skills/・画像付きHTML・日付別作業書を更新。
- [x] 🔎 **確認**: 保存RGB-D・表・失敗例・実機終了状態へ到達できる。
- [x] 🧪 **テスト**: git diff --check、HTML画像decodeと横overflow、技能形式検査。
- [x] 🛠 **エラー時対処**: 欠損リンクは実ファイルへ修正。未実行を完了に書き換えない。

## 4. 作業に使用するコマンド参考情報
本repoにjustfileなし。uv.lockを使い既存GPU extraを保持。
`rtk proxy uv run --no-sync arm-pose-fit --help`
`rtk proxy uv run --no-sync python -m arm_observer.camera_pose_capture --help`
`rtk proxy uv run --no-sync pytest tests/test_perception.py -q`
`rtk proxy uv run --no-sync pytest tests/test_id3_motion.py -k 'packet or guard or write or envelope' -q`
`rtk proxy uv run --no-sync ruff check src tests scripts`
`rtk proxy uv run --no-sync ty check`
`rtk proxy uv run --no-sync python scripts/check_quality.py`
既存viewer18111、D405 capture18109、report18112を区別する。

## 6. 完了の定義
- [x] TR1：多様な候補の採否・実移動・支持/終了状態が記録されている。
- [x] TR2：RGB-Dによる関節認識をencoder相対変化で検証し、失敗/制限も数値と画像で示す。
- [x] TR3：同条件の改善前後とlive全時間の速度/鮮度/成功率を報告。
- [x] TR4：成果物が存在し、必要検査とスキル・作業記録が整合。

## 7. 作業記録
**重要な注意事項：**
* 作業開始前に必ず `date "+%Y-%m-%d %H:%M:%S %Z%z"` コマンドで現在時刻を確認し、正確な日時を記録します。
* 各作業項目を開始する際と完了する際の両方で記録を行うこと。
* 作業内容は具体的なコマンドや操作手順を詳細に記載すること。
* 結果・備考欄には成功／失敗、エラー内容、解決方法、重要な気づきを必ず記入すること。
* 複数のフェーズがある場合は、フェーズごとに開始・完了の記録を取ること。
* コード変更を行った場合は、変更したファイル名と変更内容の概要を記録すること。
* エラーが発生した場合は、エラーメッセージと解決策を詳細に記録すること。

| 日時JST | 項目 | 内容・結果・証拠 |
|---|---|---|
| 2026-10-04 21:32:56 | 手順1開始 | AGENTS、skills、camera_pose_capture、tracker、server、MuJoCo表示仕様を調査。現在画像はアームと長尺D405・青USBループを含む。前回手首−5°停止、CAD衝突UNKNOWNを確認。 |

| 2026-10-04 21:38:52 | 手順1確認 | D16にfresh count基準、±3°肩/正6°手首候補と−5°停止ログの区別を記載。 |

| 2026-10-04 21:38:52 | 手順1検証 | camera.jpg、attempt1-events.jsonlの末尾READと18:32:58停止を確認。 |

| 2026-10-04 21:38:52 | 手順1完了 | 負手首を除外し小変化から段階観察。全可動域証明とはしない。 |

| 2026-10-04 21:38:52 | 手順2開始/操作完了 | baseline-live-180s.json、profile-before/results.json/profile.txtを生成。初回CLI必須output漏れとStateキー誤記を修正して再計測。 |

| 2026-10-04 21:38:52 | 手順2確認 | 静止追跡の40.76ms中、2描画17.6ms。maskは別worker、full初期化は測定に混ぜない。保存I/Oは追跡後に同期実行していた。 |

| 2026-10-04 21:38:52 | 手順2検証 | frame-032321を固定、SHA256と全60推定を保存。新しいテストなし。 |

| 2026-10-04 21:38:52 | 手順2完了 | 同じGPU上で既存live稼働中。温度87°C/VRAM3095MiB、180秒内18reacquiringも含む。 |

| 2026-10-04 21:47 | 手順3実装 | rendererの値cache/readonly view、silhouette距離場再利用、1件背景保存、matched observation API、保存script、D16の別windowを実装。 |

| 2026-10-04 21:47 | 手順3確認 | 固定frameの60推定が前後完全一致、40.76→29.23ms/p95 49.30→33.23ms。threshold不変。neutralのNPZ/PNGと実API応答を確認。 |

| 2026-10-04 21:47 | 手順3検証 | cacheテストRED→GREEN、perception+protocol41passed。camera既存2件+D16 SDK guard/復帰1件=3passed。complexity最大10。 |

| 2026-10-04 21:47 | 手順3完了 | 型チェックの画像None境界を明示修正。live速度は実撮影中にも測り静止microbenchmarkと分離。全5台fresh READ21:45:38はOFF、全値安定、error0。 |

| 2026-10-04 21:46:54 | 手順4開始 | all-five fresh settings後、guarded controller開始。new baseline=[2113,3474,1160,3392,1951]。データ正本~/data/xl430-arm/2026-10-04/diverse-recognition。 |
| 2026-10-04 21:49:48 | 手順4継続 | pose01〜04保存・overlay目視。肘READ相対8.96/18.90/28.92°、画像8.53/19.64/28.77°。手首+3指令はbaseline3392→3413、実+1.85°、推定+0.06°で追従不足。接触・支持移動・配線の張りは画像で認めず。 |
| 2026-10-04 21:49:51 | 手順4停止・計画修正 | pose05手首+6°でID4 no progress、3413countのまま。既存guardは全台present保持へ移行しexit2。原画像で大きな姿勢/支持変化はなし。追加手首候補を棄却。既存resumeでwrist基準へ戻して確認後、ID2/ID1/ID3だけの候補へ。出力・progress guardは変更しない。 |
| 2026-10-04 21:53:42 | 手順4通信停止 | continuationのpose09到着後ID1 MissedSample、guardでstop/hold。撮影scriptは停止runを拒否。fresh held/settings確認後continuation-2で同じpose09を実行・撮影。 |
| 2026-10-04 21:58:35 | 手順4操作・終了 | continuation-2で20まで目視確認して完了。支持姿勢に復帰、全5台OFF/RAM復元readback、counts=[2103,3482,1163,3398,1951]。 |
| 2026-10-04 21:59:42 | 手順4確認・完了 | 独立READ3回同値、全OFF/error0/max43°C/9V/port closure。ユーザーはその後電源OFF報告。以降serialアクセスなし。実行前41+camera3件を再利用し模擬20行テスト追加なし。 |
| 2026-10-04 22:02〜22:15 | 手順5集計・レビュー | 20姿勢のhost bracketing確認、符号用4姿勢除外・16holdout MAE1.15/.43/.37°。手首/ID5未検証、全域collision UNKNOWN。撮影701.97秒を除外なしで集計し19.80成功Hz/age p95 .101s。 |
| 2026-10-04 22:14:37 | 手順5不具合発見 | 腕不在画像の箱/ケーブルへglobal rootを移してtrackingを出す。生画像を視認し失敗例として保存。既存live停止、元false positiveを消さず保持。 |
| 2026-10-04 22:20〜22:25 | 手順5修正・検証 | seed消費と背景へのroot再探索を禁止、base depth100点/15mm gateを追加。20positive台座1.85〜2.42mm、不在34.72mm。全20 gate通過・不在4連続lost。full346passed後、変更perception5件だけ再実行5passed。移動後の腕が見える新sceneもlost、HTTP97件/10秒tracking0。camera-only server停止。 |
| 2026-10-04 22:25 | 手順6資料・技能更新開始 | 元不在画像と位置変更画像を分け、HTML/REVIEW/docs・vision/rgbd技能へ再取得・評価・runtime知見を反映。連続記録は保持し圧縮journal/選択画像をGitに含める。 |
| 2026-10-04 22:32〜22:39 | 手順5/6最終確認・完了 | Ruff/ty PASS、complexity10。HTML64画像全decode/全リンクOK、1280/390幅overflowなし、screenshot視認。技能vision/rgbd形式PASS。会話snapshot94/94発言coverage、AWS形式1件伏字、114.64MB clean JSONをローカル保存。gzip78.14MBを25MB以下4partsへ分割し復元hash一致。圧縮journal再集計は全数値一致。旧レポートに最終不在修正への案内追加。 |

## 9. 完了分析
全20撮影と相対角検証・測定に基づく処理改善・実不在回帰修正まで完了。
全域collision、絶対校正、手首/ID5角度精度、最終presence修正後の再動作性能は未検証として明記した。
ユーザーの電源OFF後に実機検証を再開していない。追加commit/pushは明示依頼に従い、
PRIVATE main・stage対象・公開前audit・remote一致を別の配布記録で確認する。

## 10. 追加要求：グリッパ装着後の観測とID5制約検討
ユーザーが写真4枚と `gripper_scanfit_20261004 (1).zip` を提供し、装着済みと報告。
D435俯瞰・D405 hand-eyeそれぞれの確認と、ID5の動作角制約案を要求。
撮影時の爪なしモデル/精度と現在の装着状態を分離する。新たなmotor動作・EEPROM書換えは
この観測/検討の作業に含めない。写真の181.41°/239.50°はID表示と現物対応が未確定なので、
確定した実機limitへ直接流用せず参考候補とする（初回記録。後にユーザーが写真pairを確認）。ZIPは入力原本をhash/CRC/manifest確認し、
コードを読まずrun_allを実行して原本を上書きしない。soft-onlyモデルと全可動機構を区別する。

### 手順7
- [x] 🖐 ZIP・写真を保存/照合し、既存camera専用取得で2台のRGB-D/Kを取得。
- [x] 🔎 実画像の爪・カメラ視野・対象深度、参照座標系・既存PG3角のnamespaceを確認。
- [x] 🧪 ZIP CRC/hash/geometry最小検査と専用headless browser。新制御テストは作らない。
- [x] 🛠 不可視/近距離欠損/未校正はそのまま報告。推測limitや旧モデルを実機設定にしない。

| 日時JST | 内容・結果 |
|---|---|
| 2026-10-04 22:48頃 | 写真4枚を視認。PG3枠/クランクに黒フォーム・橙色band・青い指サックが左右装着。D405は背後。Wizardの角度181.41/239.50°とTorque ON表示は提供写真時点で、ID番号/最新状態は写っていない。 |
| 2026-10-04 22:50頃 | ZIP97entries/45.58MB、SHA76d72f6a7af0d9bfab11a3c1ad6e02c246b6aeb5d0d0eff5a7f4f0761a8d7238。README/review/calibration/validation/残差を読む。6soft部品＋固定枠で、全可動機構は含まれず。 |
| 2026-10-04 23:49以降の記録整理 | 手順7操作完了。二眼接続/取得、写真原本とZIP保存済み。追加の実機開閉は別作業書workdoc_Oct04-2026_gripper_open_close.mdを正本としてD18下で実行。観測だけの本手順とは許可を分離。 |
| 2026-10-04 23:49以降の記録整理 | 手順7確認完了。元写真、二眼実画像、depthscale/歪み、mm Zup対m Yup、physical count対CAD crank角をGRIPPER_ID5_CONSTRAINTSへ明記。 |
| 2026-10-04 23:49以降の記録整理 | 手順7テスト完了。ZIP96manifest一致/CRC、6STEP valid、STL/GLB検査。専用headlessで追加後35画像/リンク/1280・390幅を確認。新制御は別D18作業で境界6件。 |
| 2026-10-04 23:49以降の記録整理 | 手順7対処完了。カメラ移動/消灯後のtip crop、近接欠損を保持。推定limitをEEPROMへ書かず、旧jawなしモデルの今回認識未対応を明記。 |

## 8. 判断・設計記録
### D16：今回の候補範囲と評価
ユーザーの多様な非干渉姿勢の依頼に基づき、独立のdiverse-v1計画でID1±30°、ID2±3°、ID3開き0..30°、ID4 0..+6°、ID5保持を候補とする。基準はfresh全OFF値。肩/手首は肘20°以上でのみ変化させ、最初は一軸3°から実画像・実変化を確認する。旧−5°は18:32:58のPhoto waypoint deadline、実手首3383countで止まったため再実行しない。D405 USBの余裕、台座支持、リンク間隔を毎姿勢観察。新候補が成立しない場合は停止と原因を残し、その軸を確認済みにしない。これは全域安全保証ではない。
### 性能設計
180秒baselineは2836 tracking/2854 records、15.76成功Hz、出版frame age p95 .128s。静止frame60回profileでは中央値40.76ms/p95 49.30ms。2回の描画が計17.6ms/更新、texture read計7.9ms、配列copyも大きい。前フレームの最終描画と次フレームの初期描画は同一State/Kなので、値一致の1件cacheで再利用する。maskの距離場もregisterの各反復で再計算せず1回にする。保存I/Oを1件だけの背景workerへ分離し、frame・mask・推定・表示画像を同じsnapshotとして保存する。観測専用snapshot endpointで既存撮影側からencoder前後READと照合する。鮮度.5s/IoU.60/15mmは変更しない。

### D17：固定sceneでの不在・移動の拒否
一度受理したsceneは最後のvision seedのrootを保持し、3回以上のlossでもseedを消費しない。
global root探索はseedなし初回だけ。RGB maskと独立なbody0 aligned depthを判定し、100点以上・中央値15mm以下を要求する。thresholdの根拠は保存20positiveと実不在negativeにあり、masked base fractionは.09まで落ちるため包含率は使わない。受理画像でgate互換性と実失敗例4連続lostを確認。初回探索や同深度別物体の同一性は未保証。
電源OFF後は実機動作せず、最終presence修正後の動作Hzを再測定済みとは書かない。旧performanceと最終gate検証を別証拠として報告する。
