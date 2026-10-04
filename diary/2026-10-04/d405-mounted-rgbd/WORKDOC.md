# 作業計画書 兼 記録書：実機24姿勢の撮影

**日付：** 2026年10月04日
**作業ディレクトリ・リポジトリ：** /home/inaho-omen/Project/my_dynamixel_arm_sandbox
**作業者：** Codex単独

## 1. 作業目的

### 1.1 ゴール要求分析

ユーザーが視点変更したUSBカメラで、実機を休止・スタンバイ・ID1±30°・ID1中立の20候補へ動かし、2〜3秒止めて画像/画面PNGを撮る。撮影表を先に作り迅速に進める。合計24姿勢。電源ON/全トルクOFFを新READで確認済み。カメラはpipewireで使用中のため解放依頼中。

非ゴール：IK/PnP/精密校正、一般制御framework、全域ROM認証。0°はユーザー採用の現物中立。候補の自然さ/干渉は実画像で都度確認し、疑わしい姿勢へ進まない。状態記録を残し、最後は元の安定した畳み姿勢へ戻す。

### 1.2 サブゴール・トレース

| ID | 要求 | 証拠 |
| --- | --- | --- |
| TR-1 | 撮影表24姿勢 | reports/pose-capture-20261004/SHOT_TABLE.md、config/pose_capture_20261004.json |
| TR-2 | 限定実動作・停止/復帰 | temp/pose_capture_motion.py、tests/test_pose_capture_motion.py、events.jsonl |
| TR-3 | 実画像と画面PNG | photos/、screenshots/、manifest、HTML一覧 |
| TR-4 | 迅速な逐次撮影 | camera review→次のcommand、2.5秒静止、PV5→6、原本/既存guard不変 |

## 2. 作業内容

計画/調査：AGENTS/既存standby controller/read-only guard、最新READ、カメラ所有者を確認。実装：既存guard/read/health検査を使う別controllerと撮影用の小スクリプト。検証：本物SDKの模擬通信でalias/範囲外/停止/復帰/復元を確認してから実機へ。

入力は24delta表、実goalは新baseline+round(delta*4096/360)。候補は肩±3°、肘66〜78°開き、手首24〜36°下向き、未装着ID5ホーン±10°。5台全てmodel1060/mode3/drive0/offset0/SecondaryID255を確認。RAM書込みだけでPV6/PA1/PWM350を使う。1段最大30°、逆方向/overshoot/停止/temperature/voltageを既存閾値で監視。欠測は埋めない。中断は現在位置保持。

カメラを占有するpipewireを勝手に終了しない。V4L0 busy、V4L2は同時stream USB帯域不足。15:46にCheeseの映像ウィンドウから現在のカメラ映像を取得できた。アプリを閉じず、映像領域652×367だけを保存する（V4L2原解像度ではなくプレビューのスクリーンショット）。毎回新規取得し、アームと配線を確認してから次へ進む。休止画像を保存済み。まず既存route elbow30→60→72→wrist10→30でスタンバイへ。新候補は前画像確認後のみ。終了はID1/2/5中立→wrist0→elbow60→30→0→全OFF/復元。

## 3. 作業チェックリスト

### フェーズ1：計画と準備
### 手順 1: 接続と撮影表（TR-1）
- [x] 🖐 **操作**: 最新READと24pose撮影表を保存する。
- [x] 🔎 **確認**: 5ID/電源/全OFFと候補範囲を確認する。
- [x] 🧪 **テスト**: 24行・20中立候補・ID1±30・差分値が計画範囲内であることを検査する。
- [x] 🛠 **エラー時対処**: camera busyの所有者を報告し解放を待つ。使用中processを終了しない。

### フェーズ2：実装と通信検証
### 手順 2: 限定撮影controller（TR-2/4）
- [x] 🖐 **操作**: 新controller/SDK模擬テストを追加する。
- [x] 🔎 **確認**: 観測guard/ID3 guardは変更せず5台RAM envelope/段階target/保持停止を実装する。
- [x] 🧪 **テスト**: pytest模擬SDKをRED→GREEN、既存standby/全testsとruffで確認する。
- [x] 🛠 **エラー時対処**: 実機前に修正。閾値を緩めず、カメラ/通信異常では保持する。

### フェーズ3：撮影
### 手順 3: 24枚の実撮影（TR-3/4）
- [x] 🖐 **操作**: 休止原画像を確認してcontrollerをdry-run→executeし、各poseへ移動/静止/撮影/画面保存する。
- [x] 🔎 **確認**: 原画像で自然さ・干渉・配線を確認してから次のposeを指示する。
- [x] 🧪 **テスト**: 写真24枚/画面PNG/READ counts/時刻/SHAが対応し撮影表の全行が埋まる。
- [x] 🛠 **エラー時対処**: 疑わしい接触・drift・欠測連続なら現在位置保持し原因/最後の画像を保存する。

### 手順 4: 復帰と記録（TR-2/3）
- [ ] 🖐 **操作**: 元姿勢へ段階復帰し全OFF/設定復元を照合、HTML一覧と日誌を保存する。
- [ ] 🔎 **確認**: シリアル閉鎖、全OFF、元姿勢画像、写真/画面リンクを確認する。
- [ ] 🧪 **テスト**: manifest画像数/hashとHTML decodeを検証する。
- [ ] 🛠 **エラー時対処**: OFF/復元未確認を成功にしない。未撮影行は未完了とする。

## 4. コマンド

uv/rtk使用。justfileなし。動作は `uv run --no-sync python temp/pose_capture_motion.py --plan config/pose_capture_20261004.json --output reports/pose-capture-20261004/run`、既定dry run。実行には `--execute`。カメラと撮影用HTTPは隣のgripper uv環境（cv2導入済み）。

## 6. 完了の定義

- [ ] TR-1/3: 実24姿勢の撮影表・写真・画面PNG・時刻/count/SHAが揃う。
- [ ] TR-2: 元姿勢復帰、全TorqueOFF、RAM復元とserial閉鎖の証拠がある。
- [ ] TR-4: 2.5秒停止・実画像レビューと例外/変更/未確定の記録がある。

## 7. 作業記録

**重要な注意事項：**

* 作業開始前に必ず `date "+%Y-%m-%d %H:%M:%S %Z%z"` コマンドで現在時刻を確認し、正確な日時を記録します。
* 各作業項目の開始/完了を記録すること。
* コマンド/ファイルと成功・失敗・エラー・修正・フェーズ進行を具体的に記録すること。
* 未撮影や不明値を成功/ゼロとみなさない。

| 日付 | 時刻 | 作業者 | 作業内容 | 結果・備考 |
| --- | --- | --- | --- | --- |
| 2026-10-04 | 15:36:09 JST | Codex | 作業開始、接続確認 | 15:36:35 READ:2063/3123/1147/2049/2059、5台全OFF、9.0〜9.2V、30〜31℃、error0、port closed。 |
| 2026-10-04 | 15:39:06 JST | Codex | 撮影表・候補範囲の保存 | 24姿勢。PV5→6。V4L0=busy、V4L2=No space left on device。同時stream帯域不足。ユーザーへプレビュー解放を依頼、移動は未開始。 |
| 2026-10-04 | 15:40:53 JST | Codex | 最新READと24pose | 最新5台READ保存、config delta24行と撮影表を作成。既存dirty差分保持。ユーザーD11の限定書込許可をAGENTSへ記録。 |
| 2026-10-04 | 15:40:54 JST | Codex | 5ID/電源/全OFF | 5ID/model1060、給電9.0〜9.2V/全TorqueOFF/停止状態を確認。0°はユーザー中立、goalは新baseline差分。camera解放待ち。 |
| 2026-10-04 | 15:42:11 JST | Codex | 24行・20中立候補 | configは休止/standby/±30と20中立を厳密検査し、delta bounds/PV6/PA1/PWM350/2.5秒を固定。test_pose_capture_motion.pyに実SDK guard/復帰/停止/aliasのテストを追加、未実装RED後GREEN実行中。 |
| 2026-10-04 | 15:42:11 JST | Codex | camera busyの所有者 | pipewireのカメラ使用を終了せず、ユーザーへプレビュー閉鎖を依頼済み。camera原画像が存在するまでexecuteがトルクONを拒否する。 |
| 2026-10-04 | 15:42:12 JST | Codex | 新controller/SDK模擬 | temp/pose_capture_motion.pyを追加。旧read-only/ID3/standby controllerファイルは変更しない。5台RAM envelope、段階移動、2.5秒hold、command/readyの逐次進行と元姿勢復帰を実装。 |
| 2026-10-04 | 15:44:46 JST | Codex | 観測guard/ID3 guard | 元の観測/ID3/standbyソースを変更せず、別controllerの5台RAM envelope、最大30°分割、fresh alias/mode/全OFF検査、保持停止と元姿勢復帰を確認。 |
| 2026-10-04 | 15:44:47 JST | Codex | pytest模擬SDKをRED | 未実装RED後、撮影controllerの実SDK通信層テスト11件PASS、既存を含む302件PASS（15.31秒）、対象ruff PASS。実機書込みは未実行。 |
| 2026-10-04 | 15:44:47 JST | Codex | 実機前に修正 | 対象ruff/302件でエラーなし。camera未取得なのでトルクONを保留。通信停止/欠測時は現在位置保持、元姿勢を確認するまでOFFにしない。 |
| 2026-10-04 | 15:46:49 JST | Codex | カメラ取得を復旧 | Cheeseのカメラ領域652×367をウィンドウから新規取得。休止画像をVLM確認。アプリを閉じず、プレビュー画面の取得として解像度/sourceを明記。 |
| 2026-10-04 | 15:47:16 JST | Codex | 限定撮影を開始 | fresh baseline2063/3123/1147/2049/2059、5台alias/modeをREAD再確認。全5台RAM PV6/PA1/PWM350、現在count目標でトルクON。30→60→72→wrist10→30の各画像を確認。 |
| 2026-10-04 | 15:51:46 JST | Codex | 台座傾斜で中断 | 休止/standby/ID1±30の4正常撮影、neutral_01撮影で台座が傾き先端が椅子側に乗るように見えた。次の候補を動かさずOperator stop、5台へ現count保持goal、controller終了2/serial閉鎖。台座支持のユーザー確認待ち。 |
| 2026-10-04 | 15:52:26 JST | Codex | 中断後の独立READ | 全5TorqueON・rpm0・error0・35〜39℃。2074/3096/1904〜1905/1770/1953。現在保持、元姿勢復帰/全OFF/設定復元は未実施。残り19未撮影。単眼画像と関節countだけで台座安定を認証しない。 |
| 2026-10-04 | 15:55:30 JST | Codex | 中断記録/HTML/スキル | 写真5枚+画面5枚のSHA検証、正常4/拒否1/未撮影19をHTMLとmanifestへ保存。Playwrightで5画像decode/中断表記を確認。15:54:06〜20の独立READ15回でも全ON/静止/error0/35〜38℃。bounded-servo-motion lessonsに実例を追記。台座支持確認待ち、24枚完了扱いにしない。 |
| 2026-10-04 | 16:01:43 JST | Codex | 台座支持確認と再開準備 | ユーザーが工具で台座を押さえ安定させたと確認。15:57 READは全ON/静止/error0/35〜42℃、新規USB原画像で台座は机上・先端は椅子から離れた。保持の再enableは行わず、元baseline/RAMと停止後5保持goalを新READ照合する再開経路を追加。SDK再開/復元テストRED→13件GREEN。rejected原画像を残して候補1を再撮影する。 |
| 2026-10-04 | 16:08:44 JST | Codex | 微小戻りの補正順序を修正 | 16:05:33 ID2は3080countのまま3123目標へ進まず、既存補正に到達する前にno progress停止。台座は立ったまま。別撮影controllerで方向/overshoot/保持を先に検査し、既存±30count・1回補正後の1秒をその新Goal書込みから計測。18秒総deadline/数値閾値/範囲は維持。実SDKの負荷deadband正制御と永久拘束の停止負制御をRED→GREEN検証。物理的な不動原因は未断定。 |
| 2026-10-04 | 16:13:56 JST | Codex | 撮影候補の記録付き変更 | ID2の段階−1°は3101countへ動いたが、0°は1回補正後もno progressで再停止。固定後の台座は立ったまま。元configを.initial.jsonへ保存し、未撮影10〜20の肩deltaを−2°へ改めた。20種類の要求は維持、ID2の0°追従失敗は未解決として残し、ROM合格にしない。ID3/4/5値と全guard/上限は変更なし。 |
| 2026-10-04 | 16:18:05 JST | Codex | 静的偏差と保持時の変位を分離 | neutral10はreached時ID3=2014/目標2034で既存20count内、直後2013へ1count変化しただけでPhoto holding drift停止。撮影の静止監視は到達時の実測countから20count以内の変位と定義し、移動完了時の目標誤差20/overshoot15/逆方向/1秒進捗/18秒期限は維持。sampleで実測の元envelope逸脱も新たに拒否。1count jitter正制御/21count実移動停止とenvelope逸脱負制御をRED検証後修正。目標偏差と保持変位をreadyへ別々に記録する。 |
| 2026-10-04 | 16:27:38 JST | Codex | 休止原画像を確認してcontrollerをdry-run→execute | 休止・standby・ID1±30・中立20の24姿勢を取得。候補1は台座支持確認後の再撮影を採用し旧失敗画像はrejected/に保存。各画像の後に次の指令を送り、24個のPlaywright PNGも保存。撮影後の畳み復帰を開始。 |
| 2026-10-04 | 16:27:38 JST | Codex | 原画像で自然さ・干渉・配線 | 全24採用原画像をCodexが順に見てから次へ進めた。再開後の台座は工具で安定、目立つ接触/張った配線なし。USB映像はややピンぼけのため細かな接触や隠れた箇所は未認証。 |
| 2026-10-04 | 16:29:05 JST | Codex | 写真24枚/画面PNG/READ counts | 24 unique JPEG/PNG/review/姿勢表一致/count5個/時刻/原画像SHA256を検証PASS。再開後20枚はUSB1280×720、最初4枚はプレビュー652×367。HTML一覧の反映は終了状態を確認してから行う。 |
| 2026-10-04 | 16:29:05 JST | Codex | 疑わしい接触・drift・欠測連続 | 台座傾斜とID2のno progress、保持1count jitter、最後の畳み復帰でdeadline停止を保存。各停止で5台現在count保持しport閉鎖。最後の停止位置[2062,3108,1343,2053,2062]の新原画像/READ確認を開始。写真24枚は揃ったが全OFF/元休止復帰はまだ未完了。 |
| 2026-10-04 | 16:31:07 JST | Codex | 撮影24姿勢完了・復帰停止・一覧検証 | SDK対象18件、全309件PASS、ruff PASS後に再開。neutral10〜20まで取得し、全24 JPEG/PNG/count/時刻/SHA整合PASS、Playwright24画像decode/24画面リンクPASS。16:28:25畳み復帰でID3が1343count付近から進まず18秒deadline停止、全5現在位置保持/port閉鎖。16:29独立READ全ON/速度0/error0/[2062,3112,1351,2052,2062]、38〜49℃。腕の支持をユーザーへ確認中で全OFF/元休止/RAM復元は未完了。HTMLに実状態を明記、スキルlessonsを更新。 |

## 8. 16:33時点の完了範囲と引継ぎ状態

- 撮影TR-1/3：採用24姿勢のJPEG/Playwright PNG/指令差分/READ count/撮影時刻/SHAが揃った。全24画像とPNGをブラウザdecode検証済み。再撮影前の台座傾斜写真と途中の停止ログは削除していない。
- 撮影の20候補は肩−3°/−2°に変更。元の0°/+3°案とID2の追従失敗は未解決として残す。細かな隙間・隠れた接触・精密CAD角・全可動域は未認証。
- 終了処理TR-2：畳み復帰で肘が進まず停止したため未完了。16:32:50の独立READは全TorqueON/速度0/error0、37〜49℃、[2062,3111,1351,2052,2062]、port closed。作業controllerは終了2で停止し、他のserial ownerもない。電源装置は操作していない。
- 全OFF/元休止復帰/RAM復元のチェック項目は未チェックのまま。急な脱力を避けるため、腕の重量をクッションや手で支持できるかユーザーへ質問中。支持の回答なしでOFFを実行しない。
- HTML一覧：reports/pose-capture-20261004/index.html。最新状態：final_state.json。日誌：diary/2026-10-04/pose-capture/。bounded-servo-motion/references/lessons.mdを今回の実例で更新済み。
- 検証：動作controller SDKテスト18件、全309件PASS。最終の撮影/HTML出力補助を含む対象ruffはHTML長行11件を修正後PASS。追加の実機動作・温度上限/PWM上限/停止閾値の拡大は行っていない。

## 9. 外部支持後のトルクOFF（D12、16:51:57 JST）

腕の重量をクッション/手で支え、支えたら知らせるという案内に対し、ユーザーが「どうぞ」と回答。畳み再試行は行わず、現保持姿勢から全5台OFFにするD12をAGENTSへ記録した。temp/release_photo_supported.pyは元baseline/RAM/5保持goalを新READと照合し、5→1のTorque=0を個別読戻し、全5OFFを再照合してから現在goalをparkし、PWM885/PV0/PA0を各読戻しした。16:51:57.538 JSTにall_torque_off=true/ram_restored=true、コマンド終了0、with contextでserial閉鎖。証拠はsupported-release/events.jsonl。元の畳み姿勢への自動復帰は未達のまま。電源装置は操作していない。

ユーザーの「いちいちテストしないでいい、最低限」に従い、この後はテスト追加実行なしでトルクOFFと実値読戻しのみ実施。終了状態/HTML/日誌/スキルに反映。支えたまま電源を切ってよいと案内した。元休止復帰を含む旧DoDのTR-2は全達成扱いにしない。

## 10. ピント不良20枚の撮り直し（D13）

ユーザー指摘を受け、再開後20枚のピント不良を採用不可へ訂正。~/data/xl430-arm/2026-10-04/pose-capture/に原データを残し、quality_review.jsonとmanifestで要再撮影を明示。現在の比較画像は0.5秒/1280×720ではぼけ、3秒/1920×1080ではネジ・印字を判別できたため、撮影処理を1920×1080と3秒の焦点待ちに変更。解像度も異なるので単独原因の断定はしない。

ユーザーが電源ONを確認。16:56:59 READは5台全OFF/速度0/error0、現在支持姿勢[2063,3092,1297,2077,2062]。元の1147countまで肘を押し戻さず、元encoder基準と同じ書込範囲を保持し、現在countをparkして再enable。単独の既存controller/撮影処理を再利用し、retake-01/に別世代を保存する。新しいframework・反復unit-test実行は行わない。記録の正本はこの作業書、画像の正本は生成された原画像、一覧は同じmanifestから一度生成する。

- [ ] 撮り直し20姿勢を各原画像の鮮明さ/姿勢/配線確認後に進め、画面PNGとcountを保存する。
- [ ] 終了時の支持姿勢へ戻して脱力/設定復元の実値を確認し、データセット・一覧・スキルを更新する。

## 11. RealSenseへの切替・既存実装調査（17:09 JST）

ユーザーのRealSense撮影への変更で17:03:30に撮影controllerをstop。現在count保持goalを書き、serial閉鎖。USB再撮影neutral_01〜04は鮮明、neutral_05はぼけて不採用。20枚再撮影は未完了。17:04:01のREADは全ON/速度0/error0/[2063,3071,1954,1692,1951]。17:08の有限READはserial機器不在で失敗し、以後の状態は未観測。

ユーザー設置中に~/Project以下のRealSense撮影、RGB-D→PLY、Open3D/Plotlyビューアを確認。既存撮影SDKとRGB-D utilityを使い、実depth_scaleと内部パラメータ・保存名の小さな受渡しを加える経路を整理した。保存済みDS77Cサンプルの色付きPLYを専用headless Playwrightで表示しPNG保存。新RealSenseはまだstream開始せず、機種対応/実画像は未確認。調査の正本は reports/realsense-reuse-20261004/REPORT_ja.md。機器設置後は1枚の実画質を先に確認して撮影へ戻る。テストスイートの再実行、依存追加、別controller複製は行わない。

## 12. カメラ単体の実取得・表示（ユーザー指示、17:12〜17:16 JST）

ユーザー「ロボットのかわりにつなげとくからやるだけやっといて」に従い、ロボット動作を再開せずRealSense単体を実行。

- [x] D435の機器情報と対応profileを確認。serial922612070196/FW5.16.0.1/USB2.1、640×480/15fps。
- [x] 既存RealSenseDeviceを再利用したscripts/capture_realsense.pyで17:12:10にRGB、生深度、RGB整列深度、左右IRを保存。実画像は壁・モニターでありアームを含まない。深度有効73.16%、SDK depth_scale=0.0010000000474974513m/count。原画像・単位・内部パラメータ・frame bundle時刻を保存。
- [x] 既存RGBDutilityの点群関数をscripts/export_rgbd_point_cloud.pyから呼び、224,761点の色付きPLYと27,563点表示の自己完結HTMLを出力。Playwrightで3D実描画・PNG確認。
- [x] 単一camera streamのRGB/深度ライブ画面をlocalhost:18107で起動。POST保存実行、frame番号680→682/新時刻を確認し別capture保存。画面PNG保存。
- [x] 使い方・依存環境の引渡し・未取得情報・保存形式・表示制限をdocs/RGBD_CAPTURE.mdに記録。

データ正本は~/data/xl430-arm/2026-10-04/realsense-camera-check/。ライブserverはユーザー調整用に起動継続。3Dは保存済みframeでありライブ点群ではない。新カメラでのアーム20姿勢撮影はまだ未実施。ユーザー最小検証方針によりテストスイートを再実行しない。機器リセット、ロボットportアクセス/書込み、再校正やPnPは行っていない。元RealSense/RGBDリポジトリは変更していない。

## 13. D405付き新ニュートラルとRGB-D 20姿勢（D14）

開始 2026-10-04 18:27:23 JST。ユーザーは現在の折り畳み姿勢をD405付きニュートラル待機として指定し、ID1±30°を含む約20姿勢の生成・実撮影とcommit/pushを依頼した。旧bare基準は今回の基準へ流用しない。18:27:51〜52の実READは[2102,3473,1147,3398,1951]、全OFF、速度0、error0、31〜32℃、9.1〜9.2V。撮影元は外部D435、アームのD405は取付済み・USB未接続。

- [x] 新基準RGB-Dをデータセットへ格納し、実count・画像時刻を区別して記録する。

完了記録：18:27:24のRGB-D原画像5種・深度プレビュー・metadata/calibrationを~/data/xl430-arm/2026-10-04/d405-mounted-rgbd-1827/neutralへコピー。18:27:51〜52の実READ JSONを別添し、画像/READの約28秒差と非同期性をpose.jsonへ記録した。
- [x] 20候補表を保存。ID2/5は現在位置保持、ID1±30°、肘を開く0〜30°、手首±10°。まず肘10°の画像で長尺ホルダーとの隙間を確認する。

完了記録：config/camera_pose_capture_20261004.jsonを正本とし、データセットのplan.json/SHOOTING_TABLE.mdへ保存。20 unique候補。既存PhotoControllerをsrc/へ移して再利用、temp側は互換wrapper。旧Planの範囲は変更せず、新基準のmake_plan/windowのみ専用クラスで選択。apply_patchのmove/add同時指定が失敗したため二段に分けて反映した。
- [x] 同一SDK guard/監視・停止処理を再利用して順次移動、2.5秒静止、RGB-D保存、原画像確認。既定PV6/PA1/PWM350、jump15count、goal誤差20count、18秒deadlineを維持する。

完了記録：18:37:31まで20unique全部の実RGB-D取得、各画像を次指令前にVLM確認。台座実count1766〜2433、ID3実count1248〜1473、肩3473保持、手首3392保持、ID5 1951保持。元記録から小さいP制御誤差が残るので指令度数を精密実角とは記載しない。末尾pose20確認後にニュートラル復帰・OFFへ進む。行動40で進捗記録更新。
- [x] 新ニュートラルへ戻して脱力・設定復元を実READで確認する。停止時は現位置保持であり、無支持の自動OFFは行わない。

完了記録：18:37:58に基準へ到達[2112,3473,1153,3392,1951]、既定20count誤差内。18:38:01全5台OFFを読戻し、脱力後10sample移動20count以内。18:38:02にPWM885/PV0/PA0を各台復元・読戻しし正常終了0、port閉鎖。18:38:41の独立READ3sampleも全OFF/速度0/error0、34〜37℃、[2112〜2113,3473,1153,3392,1951]で安定。neutral-finalへRGB-Dを保存、原画像でも折り畳み・カメラ上部の姿勢を確認した。電源装置OUTPUTは操作していない。
- [x] 写真一覧・スキル・日誌・作業書を更新し、private sandboxへ明示パスをcommit/push、remote一致を確認する。

完了記録：2026-10-04 18:45:15 JST。private mainへ41eb5f8をpush成功、
git ls-remoteとローカルHEADが41eb5f81f8e15b46b33fc8fa9c30b026bc84c92cで一致。
新章13の5項目/今回DoD完了。開始/終了neutralと20uniqueの原画像・parameter・READ・
HTML/PNG、固定D405モデル/ソース、スキル改善を保存した。
既存tempのUSB20枚撮り直しは途中までの過去作業であり、今回のD435 20枚とは別。
旧動画と未追跡reportsはローカル保持、PUBLIC gripperへのpushはしていない。
末尾空行のdiff検査失敗はpush前に修正、git diff HEAD^ --check終了0を再確認した。

push準備記録：HTML22組/44画像をPlaywright decode確認、gallery-browser.png保存。
元画像/params/ログとモデル関連source/仕様/29mesh出力をPRIVATE diaryへコピー。
srcへの移管でtemp依存のテスト入口を修正、対象ruffのimport空行1件を修正後PASS。
新実装SDK20件以外の全suite反復はしない。ステージ365ファイル114.43MiB、
audit秘密/鍵/50MiB超0件。binary/絶対home path/約5MiB OBJはユーザー指定画像/モデル
としてPRIVATE先へ保存する判断。staged diff --checkで過去viewer sourceの末尾空行1件を検出。
commit前に止めず進めたため、push前に原source/保存copyから空行を除き、再照合する。
PUBLIC gripperはpushせず、
関連差分をprivate archiveで保存する。旧大容量動画2本はローカル保持。

新基準は上記実count±3countのみ。専用CameraPhotoControllerの新runに限る。旧Plan/既存D11基準・read-only guardは変更しない。新windowはyaw±371、肩±15、肘-15〜371、手首±144、ID5±15count。機械的衝突全域の認証ではなく、実写真レビューを次動作の条件とする。撮影表20候補完遂・各RGB/uint16 depth/IR/パラメータ/実encoder/時刻が存在し、復帰脱力・push実値が揃うことが今回のDoD。

18:31:02開始：新基準のprepare実READ一致、各motor現在countをparkして全ON。変更SDK経路の必要最小限offline検証20件PASS（2.80秒、既存18+新基準/guard2）。18:31:38 pose_01は[2102,3473,1248,3398,1951]、肘開方向の実移動、ホルダー接触なしを原画像で確認。低照度ノイズは存在するが固定焦点でボルト/リンク輪郭は判読可能。各capture前後の新sampleと時刻・差分、原PNG SHAを保存する。行動40で記録更新、カウントを0へリセット。

18:32:58 手首-5°が18秒deadline未達で停止、全台新現在countをpark、[2102,3473,1473,3383,1951]を保持してport閉鎖。初期表・events・停止RGB-Dは削除せず別添。手首再試行を避け、表を台座[-30,-15,0,15,30]×肘[10,15,20,30]の20uniqueへ変更、ID2/4/5保持をユーザーへ説明。保持goal/元設定を新READ照合する既存resume機構で再enableせず再開した。pose01〜03は同一指令なので再撮影しない。18:35:15までpose09取得、全画像は個別VLM確認後のみ次に進む。台座-30°確認、見える接触/張った配線なし、低照度ノイズは残る。行動40で進捗記録更新。
