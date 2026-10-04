# D405 手本姿勢・脱力・保持・撮影GUI 作業計画書兼記録書

日付: 2026-10-05 / 作業者: Codex（単独）
作業場所: `/home/inaho-omen/Project/my_dynamixel_arm_sandbox`

## 1. 作業目的
手本姿勢を見ながら腕を手で合わせ、トルクON/OFF、D405 RGB-D保存を一つのGUIで行う。

### 1.1 ゴール要求分析
ユーザー要求はcvui等のGUIとxdotoolによる実操作確認。既存OpenCVはheadless、Tkinter/Pillowは利用可能なのでTkinterを明示採用する。撮影は既存D405 owner HTTP（18109）を再利用し、SDK pipelineを増やさない。
手本は写真と生countの記録であり、校正済み世界角や安全な自動移動目標ではない。手本の読み込みと現在の撮影を手本にする操作を設ける。起動・終了時の自動トルク切替はしない。
現在の物理支持が未確認であるため実機切替は人のGUI操作で行う。検証ではREADと実D405撮影のみ、ON/OFFはSDK通信エミュレータで検証する。キャップ把持DoDは別作業書の未達のまま。

### 1.2 サブゴール構造
| ID | 成果物 | 確認 |
|---|---|---|
| SG1/TR1 | `pose_gui_control.py` 手動切替境界 | 実SDKエミュレータのON/OFF・拒否テスト |
| SG2/TR2 | `pose_gui.py` ネイティブGUI | xdotoolで表示・撮影・手本設定・終了 |
| SG3/TR3 | docs/技能/diary/画像 | 実D405 RGB-D、count bracket、画面証跡、commit/push |

### 1.3 設計・判断 D20（新規GUI専用）
今回のユーザー指示でGUIの手動トルク切替を実装する。既存READ-only observerの許可範囲は変更しない。新規専用Portは通常READ、操作中だけ64の0/1、116の**新鮮な現在countと完全一致する値**、ON準備中の上限以下PWM/PA1/PV6を一送信毎のtokenで許す。EEPROM、手本への自動移動、PWM増加は許さない。
ONは全5台のモデル1060、ID、secondary255、mode3、drive0、offset0、position limit、healthを直前確認。停止した3標本(span<=3count/velocity0)、各ON対象のGoalPWMが1..885であることを確認してから、その台がOFFであることと現在countを再読取。PWMは現在値と350(ID5は310)の小さい方に制限、PA1/PV6へRAMのみ設定し、goalを書きreadbackしてON。既にONの台は触らない。ON後15count超のjumpを異常として表示し後続を止める。異常時自動OFFや盲目的再試行はしない。
06:33の見直し: 電源断でRAM profileが初期値に戻る場合にもこのGUIだけで現在位置保持ONを実行できるよう、上記の下方PWM制限/PA1/PV6を明示採用。OFF/終了では高いPWMへ自動復帰しない。機構への自動移動は依然許さない。SDKエミュレータで初期profileからの制限とゼロPWM拒否を追加確認する。
OFFは重量を支えたとユーザーがGUIでチェックした操作のみ。各台逆順OFF/readback、失敗は不明として表示。ONも手で重量を支えた状態で操作。チェックは操作毎に解除する。制御はCLI `--control` が明示された場合のみ可能。標準起動はREAD-only。
serialは一つのworkerが排他的所有し、UIスレッドはTk描画だけ。新鮮でない状態はUNKNOWN。カメラ/通信失敗は表示して切替を無効化し、暗黙再接続はしない。
撮影は新鮮な5台の前標本、HTTP not_before要求、後標本を保存。velocity0、前後drift<=3count/torque一致ならaccepted。それ以外はrejectedとして保存し手本指定を拒否する。カメラowner serial230322272284とage<=2sを検証。単なる画像デコードを把持成功としない。
出力は`~/data/xl430-arm/YYYY-MM-DD/pose-gui/<session>/`へRGB/深度/IR/paramsを実体コピーする。referenceも実体コピーし可搬化する。
06:25の実機READ検査は全台No PING response。電源/通信状態は未確定。標準の関節付撮影/ON/OFFはUNKNOWNで無効化し、追加の明示ボタン「D405のみ撮影（関節値なし）」でcamera_only=true/counts=null/accepted=falseを保存する。暗黙fallbackをせず、撮影結果を正解関節姿勢とは扱わない。GUI切替境界と関節付き撮影は実SDKエミュレータで検証し、実D405撮影は明示camera-onlyモードで検証する。

## 2. 作業内容
調査/設計→制御・GUI実装→最小検証→利用資料/保存の4段階。ユーザーの重複工程削減指示を優先し、確認・テスト・エラー指針は各操作に添え、同じ成果の重複チェックを作らない。

## 3. 作業チェックリスト
### 手順1: 調査・作業書レビュー（TR1..3）
- [x] 🖐 **操作**: AGENTS、既存SDK guard/camera API、Tk/xdotool、手本資料を確認し本書をreview rubricでレビューする。
- 🔎 **確認**: D20が既存cap制御の拡大ではなく専用GUIの境界として明記されている。
- 🧪 **テスト**: 調査は自動テスト不要。次の手順でSDK実送信境界2ケースを追加する。
- 🛠 **エラー時対処**: owner競合時は起動しない。camera停止時は明示エラーとし勝手にpipelineを作らない。
### 手順2: GUIと専用制御を実装（TR1/2）
- [x] 🖐 **操作**: `src/arm_observer/pose_gui{,_control}.py` と最小テストを作成する。
- 🔎 **確認**: 手本/ライブ/各ID/ON/OFF/撮影が一画面。UIのI/O待ちで描画が止まらない。
- 🧪 **テスト**: `tests/test_pose_gui.py`でsupportなし拒否、現在値park、既ON不変、全OFF、未許可write拒否。
- 🛠 **エラー時対処**: 部分失敗で成功表示しない。UNKNOWNを表示してONをロックする。
### 手順3: 実カメラとGUI操作確認（TR1..3）
- [x] 🖐 **操作**: `uv run --no-sync pytest -q tests/test_pose_gui.py`、変更箇所ruff/ty、GUIを起動しxdotoolで撮影/手本/終了し画面を保存する。制御許可モードの起動も、手動操作がなければWRITE無し。
- 🔎 **確認**: 実RGB-D/paramsとcount不明の明示記録が出力先に存在し、実機WRITEなし。関節付きbracketはエミュレータで検証。serial終了時close。
- 🧪 **テスト**: 通信エミュレータのみでON/OFF。GUIの実機切替は未検証と記録する。
- 🛠 **エラー時対処**: 対象の失敗だけ修正・再検証。実機支持未確認で切替検証しない。
### 手順4: 再現手順・技能・保存（TR3）
- [x] 🖐 **操作**: `docs/D405_POSE_GUI.md`、技能の再利用手順、diary作業書/証跡を保存し明示pathsだけcommit/pushする。
- 🔎 **確認**: PRIVATE mainとHEAD一致、git diff --check成功。
- 🧪 **テスト**: 過剰な全suite再実行はしない。
- 🛠 **エラー時対処**: 関係ない差分を取り込まない。push失敗は実状態を記載する。

共有serial openは `standby_motion.open_standby_bus` に任意port_factoryだけ追加し、既存呼び出しは同じPortのまま。初期手本は記録済みの折り畳み観測基準（D435俯瞰、前後counts一致2021/3537/1144/3386/2091）。安全認定ではないとJSONに明記する。
最終レビューで撮影キーをF8へ変更。SpaceのTkボタン通常activationとグローバル撮影bindingが二重発火しうるため専用キーにする。preview decode失敗はUNKNOWN表示し、Tk更新ループを維持する。

## 4. 完了の定義
- [x] TR1: 手動ON/OFF境界のSDKエミュレータ検証が成功し実機未検証範囲が明記されている。
- [x] TR2: 表示・手本・実D405撮影をxdotoolで操作しスクリーンショットが保存されている。
- [x] TR3: 再起動手順/技能/diaryと実体RGB-Dの保存先が記録され、commit/push済み。

## 5. 注意事項
`rtk proxy` / `uv run --no-sync`。サブエージェント無し。READ監視とwriterを競合させない。D19の失敗ルート/395PWMは再実行しない。ロボットの現在countは写真から世界角に校正されていない。既存dataと参照CADを改変しない。

## 6. 作業記録
| 日時(JST) | 項目 | 結果・証拠 |
|---|---|---|
| 2026-10-05 06:13:18 +0900 | 開始 | date実行。Tk8.6/Pillow12.3、DISPLAY=:1 1920x1080、xdotoolあり。D405 owner serial一致、RGB-D受信age0.18s、serial ownerなし。 |
| 2026-10-05 06:13:18 +0900（開始時刻） | 手順1 | review rubric: PASS。ユーザーの最小工程要求により確認欄の重複checkboxを省略。モデル/alias/profile/goalの境界はD20に固定。公式Python Tk thread model/xdotool docs照合。手本は選択式で認定を捏造しない。 |
| 2026-10-05 06:23:03 +0900 | 手順2 | GUI/専用transaction guard/現在位置parkを実装。SDKエミュレータ2件と既存release3件PASS(0.38s)。ruff PASS、tyのOptional count/PhotoImage保持型を修正してPASS。実機WRITEなし。撮影はreceipt時刻と前後countを照合し実体保存。 |
| 2026-10-05 06:24:08 +0900 | 周期記録 | READ-only画面起動、実D405約18fps表示。nohup起動は環境のchild終了で起動せず、exec継続セッションで再起動。xdotool alt+F4で終了/serial close。独立arm-statusは06:25:54 全5台No PING response。未確定のままON/OFF無効表示。カメラのみ撮影は別の明示操作として追加。 |
| 2026-10-05 06:33:13 +0900 | 手順3 | xdotool clickで実D405 RGB-D保存、RGB/深度切替、UNKNOWN撮影の手本登録拒否、Xボタン終了を確認。証跡gui-final.png/gui-capture-depth.png/gui-unknown-reference-refused.png。実RGB-Dは720x1280 uint16、depth scale約0.0001m/count。session/eventsに実機WRITE0を確認、close記録あり。関節bracket/初期RAM profileからのON/低PWM維持/alias拒否はSDKエミュレータ4件PASS(0.33s)、ruff/ty PASS。 |
| 2026-10-05 06:44:58 +0900 | 手順4/周期記録 | docs/HTML/実RGB-D/技能を保存。技能quick_validate PASS。27明示files、5.41MiB、audit blockers0/warnings14（既知の画像とhome pathsを依頼済PRIVATEへ保存）。commit9cd9d65、push成功、local/remote main同一を確認。diff --cached --check PASS。最後のGUIは専用tmux `d405-pose-gui-20261005` で起動し、F8/手本/D405ライブ画面gui-current.pngを確認。実機の切替・把持は未実施。 |
| 2026-10-05 06:44:58 +0900 | DoD TR1 | tests/test_pose_gui.py 4件PASS。物理ON/OFFは未検証とdocs/HTML/本書に明記。RAM制限と現在値parkを実SDK送信で検証。 |
| 2026-10-05 06:44:58 +0900 | DoD TR2 | 手本実体copy/ライブRGB/深度/カメラのみ撮影/不明姿勢の手本拒否/終了を確認。4枚の画面証跡とRGB-D実体をdiaryへ格納。 |
| 2026-10-05 06:44:58 +0900 | DoD TR3 | docs/D405_POSE_GUI.md、rgbd-arm-pose-capture skill、diary/HTMLを9cd9d65でPRIVATE mainへpush済み。原本~/data/xl430-arm/2026-10-05/pose-gui/を維持。完了記録をportable WORKDOCへ同期して追記commitする。 |

## 7. 未確定事項
現在の実機の重量支持。実機ON/OFFの効果はGUI提供後に利用者が支えた状態で確認する。手本の姿勢が正解かは人が選んだ資料の意味に依存し、保存時に認定を捏造しない。
