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
