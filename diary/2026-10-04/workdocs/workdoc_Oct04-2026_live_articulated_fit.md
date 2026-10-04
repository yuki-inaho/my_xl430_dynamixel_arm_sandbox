# 作業計画書兼記録書：画像・CADによるリアルタイム関節姿勢認識

日付: 2026-10-04。開始20:04:36 JST+0900。担当: Codex単独。
作業場所: /home/inaho-omen/Project/my_dynamixel_arm_sandbox（PRIVATE、main、開始HEAD2b3185b）。
使用スキル: write-workdoc-uv / review-written-workdoc / start-work-with-docs。

## 1. 作業目的

### 1.1 ゴール要求分析

ユーザーの目的は、添付の画像・CAD位置合わせをこのリポジトリで再現でき、
実カメラ画像から背景を除去して、動くアームの関節姿勢とCAD重畳を継続表示できること。
入力はDownloadsのrobot_fit_20261004.zipとChatGPT-FilterRegフィッティング実装.md。
GPU使用可。元資料の未達を引き継いで完了扱いにはしない。

明示要求: 同等の尺度付きarticulated FilterReg、画像/CAD認識、リアルタイム、
背景分離、uv/Python/nanobind、SOLID/KISS/DRY、作業書とレビュー、DoDまで継続。
当初の制約: 観測・描画のみ。後述D15では初期認識用の限定姿勢変更を追加した。
既存の保持guardを変更しない。姿勢推定値をモーター目標値へ直結しない。
人手の静止画注釈をライブ自動背景分離と扱わない。ICPだけをFilterRegと呼ばない。
静止画の任意深度単位と、RealSenseのm単位を区別する。RGB-Dライブでは尺度は1に固定。
推定関節はCAD参照姿勢との差分で、encoder校正値や制御指令とは別。
可視形状を持たないJ5はnull、末端搭載物の版はモデル選択として明示する。

| ID | サブゴール・要求 | 対象 | 証拠 |
|---|---|---|---|
| TR-1 / SG-1 | 添付内容・出典・静止画機能の取り込み | packages/articulated-filterreg、docs/ARTICULATED_POSE_RECOGNITION.md | archive hash、入出力一覧、元結果再現 |
| TR-2 / SG-1 | 未達nanobindのビルド/import | uv path dependency、CMake | native binding実値と元14試験 |
| TR-3 / SG-2 | FilterReg E/M段階とFK維持 | perception/filterreg.py、vendor数値核 | GPU/direct Gaussian対照、関節Jacobian・回復試験 |
| TR-4 / SG-2 | 自動背景分離 | perception/segmentation.py | 自動推論マスクと実画像重畳、使用重みrevision |
| TR-5 / SG-3 | ライブRGB-D/保存データの入力 | perception/source.py | 同一frame RGB/depth/K、serial・timestamp、SDK尺度 |
| TR-6 / SG-3 | CAD可視面描画・連続推定 | perception/renderer.py、tracker.py | 実レンダリング、動画/保存frame追跡、失敗時状態 |
| TR-7 / SG-3 | viewerと性能 | perception/server.py、CLI | 専用Playwright、実fps/遅延、非同期最新frame処理 |
| TR-8 / SG-4 | 品質・再現・技能 | tests、docs、skills、diary | 最小限の意味のある試験、ruff/ty/複雑度、記録 |

成功条件: 元静止画32初期値の最良状態を再計算/重畳可能。nanobind実動作。
ライブでは自動領域抽出からmetric深度の関節推定が動き、CADを画像へ重畳し、
更新率とframe ageを画面に表示。対話的表示の目標は10 pose/s、p95 age<0.5秒。
実性能不足なら最適化し、数値を隠さない。認識が失われた場合はlost/reacquiringとして
古い結果を現在の推定と表示せず、再初期化する。実姿勢の精度は真値なしに断定しない。

非ゴール: 推定値による自動ロボット駆動、IK、encoder自動校正、CAD形状の改造、印刷。
既存20姿勢データやDownloads原本を上書きしない。今回のcommit/pushは新たに依頼されていない。

### 1.2 確認済み前提と設計

ZIPは550ファイル、展開サイズ56,690,120 bytes。R3裸アームの4可観測関節と尺度、
手動訓練5点/検証14点、CPU格子Gaussian、C++twist集約、元14試験を含む。
nanobindは元環境で取得できず未達、C ABI14試験のみ成功と明記されている。
旧画像にはD405/爪がない。現在のD405搭載モデルは別モデル版として扱う。
W Python3.13.9、justfileなし、rootはuv_build、既存pytest340件。
D435(serial922612070196)とD405(serial230322272284)を検出。
RTX2070/8GiB、既存EdgeTAM環境のtorch2.7.1+cu118がCUDA/sm75で実動作。
外部D435を全体認識に使用。D405は手先視点として区別する。

新規native packageはuvのeditable path dependencyとして統合し、observerのbuild backendは維持。
元ZIPを不変の入力証拠として残し、展開先packagesを修正可能な実装正本とする。
アーカイブ結果と新しい検証出力の場所は分ける。
ライブ側は入力、領域抽出、FilterReg、レンダリング、状態管理、HTTP表示を分離する。
GPU exact Gaussianと元native latticeを選択可能にし、暗黙に切り替えない。
自動背景分離はBiRefNet liteをcommit固定で推論。既存EdgeTAMの再利用可否も調査済みだが、
prompt依存マスクを初期自動抽出と混同しない。重みはcacheに置き、必要依存はuv固定。
GPU描画はEGL/ModernGLでCAD可視面とcamera-space XYZを同時取得し、不要なCPU全mesh反復を避ける。
レビュー補足: Python3.13用CUDA wheelを実際に確認してからGPU依存を固定する。
RGBの歪みモデルとcoefficientsを確認し、pinhole描画へ渡す前にRGBとaligned depthを
同一remapで補正する。未対応歪みは明示拒否。カメラKを画角推測で置換しない。
cad model/version、mask age、raw depth scale、processed resolutionも各runで保存する。
ライブ初期化は別時間として計測し、定常frameの性能値と混ぜない。

## 2. 作業概要

調査/設計（SG-1）→入力取り込み/native構築（SG-1）→ライブ認識実装（SG-2/3）→
実データとUI/性能検証（SG-3/4）→資料・技能・日付別証拠保存（SG-4）。
既存コードをコピーして別の撮影システムを作らず、RealSenseのframe/metadata仕様を再利用。
SDK所有者を確認し、既存D405サーバーや他ユーザープロセスを閉じない。

## 3. 作業チェックリスト

### フェーズ1：調査と設計

### 手順1: 入力・モデル・依存の照合（TR-1/2/5）
- [x] 🖐 **操作**: 添付文書/ZIPの主要実装、元DoD、公式FilterReg論文、GPUとカメラを調査する。
- [x] 🔎 **確認**: 本書1.2と入力manifestに可視関節数、尺度、元未達、接続機器を記載。
- [x] 🧪 **テスト**: 調査のため新規unit試験不要。元test_native/geometry/recovery等14試験を特定。
- [x] 🛠 **エラー時対処**: ZIPの危険なpathやsymlinkは展開拒否。資料不足を黙って別モデルへ置換しない。

### フェーズ2：実装

### 手順2: 可搬なuv/nanobindパッケージ取り込み（TR-1/2）
- [x] 🖐 **操作**: ZIPをpackages/articulated-filterregへ安全に展開し、rootのpath依存として構築する。
- [x] 🔎 **確認**: source hashを残し、標準AF_BINDING=nanobindで_nativeがimportできる。
- [x] 🧪 **テスト**: 未導入import失敗→uv sync後成功、元14試験を実行。C ABI合格で代替しない。
- [x] 🛠 **エラー時対処**: CMake/Eigen/ABIエラーは最小境界で修正し、元ソース差分とlogを保存。

### 手順3: 静止画再現経路を接続（TR-1/3）
- [x] 🖐 **操作**: 元のfit/renderと保存最良初期値の再実行を、新パッケージ経由で実行する。
- [x] 🔎 **確認**: 尺度・角度・画像誤差を元結果と比較し、使用注釈とbackendを記録。
- [x] 🧪 **テスト**: 元回復試験と原本を上書きしない独立replayで対照。数値誤差をバイト一致と混同しない。
- [x] 🛠 **エラー時対処**: 新出力へ書き、results原本を守る。元32試行の未実行を実行済みと扱わない。

### 手順4: Gaussian/FKとGPU描画のライブ境界を実装（TR-3/6）
- [x] 🖐 **操作**: perception/filterreg.pyとrenderer.pyを追加し、観測Gaussianとリンクtwistを接続する。
- [x] 🔎 **確認**: FKを再実装せず、CUDA exact/nativeを明示選択。CAD XYZと画像投影が一致。
- [x] 🧪 **テスト**: Gaussian/native direct比較、合成関節回復、GPU投影の独立チェックを先に記述。
- [x] 🛠 **エラー時対処**: CUDA/EGL不可は明示失敗。GPU利用をログだけで成功と判断しない。

### 手順5: 自動背景分離を実装（TR-4）
- [x] 🖐 **操作**: commit固定のBiRefNet liteをCUDA推論するsegmentation境界を追加する。
- [x] 🔎 **確認**: 元手動maskを入力せず、RGBから実マスクを生成。revision/hashを記録。
- [x] 🧪 **テスト**: 注釈付き画像との比較は未学習評価として実推論一回を保存。単なるmockで代替しない。
- [x] 🛠 **エラー時対処**: 重み/remote code/VRAM不足は記録し、精度と速度を測って設定を改善。

### 手順6: RGB-D sourceと追跡状態を実装（TR-5/6）
- [x] 🖐 **操作**: source.py/tracker.pyへD435と保存dataset入力、初期化・連続EM・lost再取得を追加。
- [x] 🔎 **確認**: K/尺度/時刻は同じSDK frameset、最新frameのみ消費。metric入力でscale1、推定/校正IDを区別。
- [x] 🧪 **テスト**: 保存20姿勢の変化追跡、空mask/欠損depth/遅いframeの無効表示、再取得を確認。
- [x] 🛠 **エラー時対処**: camera占有やフレーム欠損でserial操作しない。構図変更は別のユーザー指示D15として実行。

### 手順7: ライブviewer/CLIを実装（TR-7）
- [x] 🖐 **操作**: HTTP viewerとarm-pose-fit CLIを追加し、RGB/マスク/CAD重畳/角度/状態/実速度を表示。
- [x] 🔎 **確認**: latency・更新時刻・lostが読み取れ、frame配信が推論を待って蓄積しない。
- [x] 🧪 **テスト**: 実サーバーを専用headless Playwrightで開き画像/動的stateを確認。
- [x] 🛠 **エラー時対処**: 未推定結果を現在姿勢と表示しない。cameraFPSとposeFPSを分ける。

### フェーズ3：検証と保存

### 手順8: 実RGB-D認識・性能を検証（TR-4/5/6/7）
- [x] 🖐 **操作**: D435ライブと保存系列で推論し、実画像/状態/速度/遅延を保存する。
- [x] 🔎 **確認**: 自動mask→深度→関節付きCAD重畳が動作、動的系列で姿勢変化、10pose/s/age目標を計測。
- [x] 🧪 **テスト**: 実運用計測と合成真値回復を区別し、自己申告の性能で合格させない。
- [x] 🛠 **エラー時対処**: 速度不足は主要処理を計測して改善、形状不一致や不可観測は状態へ明示。

### 手順9: 品質ゲートを実行（TR-8）
- [x] 🖐 **操作**: root pytest、ruff/ty、複雑度、新規package試験を必要範囲で実行する。
- [x] 🔎 **確認**: observer既存機能を保持、Python制御部の複雑度≤10。数値vendorは別scopeで記録。
- [x] 🧪 **テスト**: フルsuiteは依存変更後一回、後続修正は影響範囲だけ。定数写しの試験を増やさない。
- [x] 🛠 **エラー時対処**: 第三者依存を無根拠にignoreしない。品質予算の拡大で通さない。

### 手順10: docs/技能/日付別証拠を保存（TR-1〜8）
- [x] 🖐 **操作**: docs/ARTICULATED_POSE_RECOGNITION.md、技能、diary/2026-10-04/articulated-fitへ記録を保存。
- [x] 🔎 **確認**: 初回setup/再現/起動/モデル版/座標/速度/限界を他ユーザーが再実行できる。
- [x] 🧪 **テスト**: 実CLI例、画像付きHTMLリンク、prompt-to-artifact表を検査する。
- [x] 🛠 **エラー時対処**: 原本にない成功を追記しない。未保証条件を明記し、測定条件でのDoDを照合。

## 4. 作業に使用するコマンド参考情報

全コマンドはWルート、rtk proxy、uvを使用。justfileはない。
`uv sync`で新native packageを構築。GPU依存は明示したperception-gpu extraを使用。
`uv run pytest packages/articulated-filterreg/tests -q`、`uv run pytest tests/test_perception.py -q`。
`uv run --no-sync arm-pose-fit --help`。
ライブ実行例は `uv run --no-sync arm-pose-fit --camera-serial 922612070196 --width 480 --segmentation-size 768 --initial-pose diary/2026-10-04/articulated-fit/recognition-motion/vision-seed.json --output diary/2026-10-04/articulated-fit/live-final --port 18111`。
`uv run ruff check src tests scripts`、`uv run ty check`、`uv run scripts/check_quality.py`。
確定した引数・実行記録は§7へ追記し、未実装CLIの成功は仮定しない。

## 6. 完了の定義

- [x] D1（TR-1/2）入力hash/出典、uv native build/import、元機能と元14試験の実行確認。
- [x] D2（TR-3）Gaussian E段階と関節twist M段階、同等静止画結果、独立数値対照が確認済み。
- [x] D3（TR-4/5）自動背景分離と同一SDK framesetの実RGB-D/カメラ情報で入力が構成される。
- [x] D4（TR-6/7）ライブCAD重畳・姿勢変化認識・lost再取得・実速度/ageが検証済み（条件は最終記録参照）。
- [x] D5（TR-8）最小限の意味のある試験と品質チェックが成功、既存制御契約を変更しない。
- [x] D6（TR-1〜8）作業書レビュー、資料、技能、日付別画像/実測記録と全要求の証拠表を保存。

## 7. 作業記録

**重要な注意事項：**

* 作業開始前に必ず `date "+%Y-%m-%d %H:%M:%S %Z%z"` コマンドで現在時刻を確認し、正確な日時を記録します。
* 各作業項目を開始する際と完了する際の両方で記録を行うこと。
* 作業内容は具体的なコマンドや操作手順を詳細に記載すること。
* 結果・備考欄には成功／失敗、エラー内容、解決方法、重要な気づきを必ず記入すること。
* 複数のフェーズがある場合は、フェーズごとに開始・完了の記録を取ること。
* コード変更を行った場合は、変更したファイル名と変更内容の概要を記録すること。
* エラーが発生した場合は、エラーメッセージと解決策を詳細に記録すること。

| 日付 | 時刻 | 作業者 | 作業内容 | 結果・備考 |
|---|---|---|---|---|
| 2026-10-04 | 20:04:36 JST | Codex | 調査開始・作業書作成 | 入力主要文書・実装を確認。nanobind未達、手動領域、自由尺度縮退を元資料で確認。D435/D405、RTX2070の実在を確認。 |
| 2026-10-04 | 20:10 JST | Codex | 手順1完了・手順2開始 | arXiv1811.10136のE/M/関節twistを確認。ZIP550件のpath/symlink検査後展開、全SHA256をdiary/articulated-fit/input_manifest.jsonへ保存。docsは既存固定マスクを自動と誤記しない。review補足反映。 |
| 2026-10-04 | 20:20:20 JST | Codex | 実行結果確認・手順2/3完了記録 | nanobind extension import成功、元14試験6.49秒で成功。static-replayは5.94秒、最良state最大差1.64e-14、選択score差1.11e-16。元validate scriptはresultsを書き換えbindingもctypes固定のため使用せず、scripts/replay_articulated_fit.pyで同じfitを新出力先へ実行。 |
| 2026-10-04 | 20:20:20 JST | Codex | 手順4/5の結果確認・手順6境界実装開始 | CUDA/direct GaussianとEGL投影の2試験成功。BiRefNetはD435 RGBから実推論、初回0.969秒/定常例0.092秒。最初のCAD重畳は不十分（IoU0.481、中央値8mm）で未合格。GPU重み固定、raw/登録用maskを分離し改善継続。 |

実装補足: sourceは1280x720/30のD435を640x360へ同一resizeしKのpixel-center補正を行う。
登録用maskには奇数pixel径のopeningを明示適用し、細いケーブルを除く。raw maskは残す。
初期化はarea-weighted CADサンプルとPCA姿勢候補を距離で順位付けし、Gaussian E/Mで最適化。
候補順位のnearest距離をICP更新とは扱わない。三脚固定中のtrackingでは初期化済みrootを保持し
関節のみ更新する。カメラ移動/連続品質低下時はrootも再取得する。metric尺度は常に1。
現物D405ホルダーの65/75度未確定を、models/current_arm_r3_d405_r5_65.jsonへ明記。
工程の境界が一部並行して実装されたが、未完了回復試験/追跡/性能のcheckboxは未達のまま維持。

2026-10-04追記（ライブ実装の根拠）:
- 輪郭項をM段階だけでなくline searchのcostにも含める不整合修正で、保存D435画像のIoUが
  0.648→0.813、深度点距離中央値4.05→2.71 mmとなった。真の関節角精度とは区別する。
- 初期化の卓上構図仮定を明示: reference zが画像の上へ向く、足元がforeground下側。
  root footの下限は最下mask rowから投影した50mm幅分。厳密な校正点とは扱わない。
- CUDA exactだけでなく元nanobind latticeを測定し、停止した単独frameの登録はnative25–36ms、
  CUDA約40–45ms。ライブbackendは明示nativeを既定に変更。暗黙fallbackなし。
- SDK/threadの組合せでmask推論が1.85秒、古いframeを受ける問題を実測。pollへ変更した後も
  目標未達のためcameraをspawn processへ分離。初回SDK起動には15秒の別timeoutを設定。
- cameraとmaskの最新スロットを使い、BiRefNetを独立workerとして追跡から分離した。
  現在の独立画像へoptical flowでmaskを移す。mask/frame age>0.5秒は現在poseとして表示しない。
- scripts/track_recorded_poses.pyはneutral+20種類を全てtrackingとして処理、IoU0.702–0.868。
  JPEGの静止画間ジャンプを8回EMで整定するoffline評価で、動画fpsとしては計上しない。
- root pytest344 passed/32.34秒（新規4試験含む）、ruff成功、複雑度10、対象ty成功。
  非同期実装後のty/UI/性能と保存画像視認の監査は継続中。全体suiteの重複実行はしない。

| 2026-10-04 | 20:43:37 JST | Codex | 手順4/5完了の根拠確認 | root344試験内のCUDA/direct、EGL投影、metric/K、関節回復・欠損depthが成功。元注釈画像の自動mask IoU0.6727（注釈は評価のみ）、512入力のD435実maskを視認。384はmask崩壊のため不採用。 |
| 2026-10-04 | 20:47:15 JST | Codex | ライブ品質/性能の継続確認 | 480幅/512背景分離/小解像度flowでinstant pose更新約8–12Hzを観測するが、missing maskや再初期化が残るためD4は未達。背景分離maskが瞬間的に面積半分未満に崩れたら採用せず、元timestampを維持し0.5秒で失効させる方式を実装。入力欠損をtimestamp更新で隠さない。 |

技能creatorに従いskills/vision-cad-arm-tracking/SKILL.mdを作成、形式検査成功。
技能にはSDK/GIL、正しいE/Mとline search、静止画/ライブ/尺度の区別、maskの実視認、
既存CLI/数値核の再利用、成功pose/sだけを計上する実測方針を記録。運動許可は含まない。

### D15：初期認識用の姿勢変更（ユーザーの追加指示）

ユーザーは肩・肘の間隔がある姿勢を提案し、その変更をエージェント自身が
判断・観察・実行するよう指示した。初期認識に必要な姿勢変更として、既存D14の
CameraPhotoControllerとconfig/camera_pose_capture_20261004.jsonを再利用する。
ID1/2/4/5を保持し、ID3をまず10°、画像でケーブル・台座・リンク間隔を確認して
20°、必要なら30°まで開く。既存PV6/PA1/PWM350・RAM限定・各種guardを変更しない。
取得した画像の推定関節角を制御角に使わず、既存のbaseline相対pose_01/02/03を使う。
実機の新しい現在値・識別・全OFF・支持状態・追加D405 USBケーブルの余裕を確認する。
baseline不一致なら閾値を拡大せず、現物画像とREADから再検討する。

- [x] 接続復帰後のREAD、現在画像、ケーブルと台座の支持を確認。
- [x] 既存10°→20°→必要時30°の段階移動を各画像で観察し、初期認識を評価。
- [x] 実機の最終保持/復帰/脱力状態を実測して記録。

2026-10-04 20:52–20:58 JST: USB一覧にはD435/D405を検出したが、BestTechnology E148はなく、
/dev/serial/by-id・ttyUSB0/1・ttyACM0も存在しなかった。モーターにREAD/WRITEは行っていない。
USB再接続を一度依頼し、その間に保存姿勢画像と現在の重畳を確認した。
保存pose_03（ID3相対30°）はリンクを見分けやすい。一方、現状の折り畳み画像は
別の折れ方にCADが合う場面があり、IoUだけで角度の正しさを断定できない。
直近journal実測をlive-quality-mask/performance.jsonに保存。成功45件/56.02秒＝0.80Hz、
成功publication ageのp95＝0.210秒。lost20件・reacquiring3件を含む。
瞬間9Hzを持続性能とは扱わずD4未達を維持。性能集計CLIをscripts/summarize_pose_journal.pyに追加。
ruff/ty/複雑度（最大10）は更新後も成功。viewer.pngを専用Playwrightで保存。

### D15の実行・最終検証記録

| 日付・時刻（JST） | 内容 | 実測結果・証拠 |
|---|---|---|
| 2026-10-04 20:59:59 | 接続復帰後の実SDK READ3回 | 全5台OFF、エラー0、9.0–9.1V、34–36℃。旧referenceからID1 +11 / ID3 +6 / ID4 -6 countの変化があり、閾値を拡大せず、実画像と新しい安定基準[2113,3474,1153,3392,1951]を記録。 |
| 21:01:20–21:02:50 | 既存CameraPhotoControllerで10/20/30°を段階実行 | 全軸の現在値をparkしてから保持、ID3のみ変更。ID3実測1250/1369/1484 count、約8.5/19.0/29.1°の変化。各画像でケーブル余裕・台座・リンク間隔を観察。recognition-motion/events.jsonlとopen-*.jpg。 |
| 21:06:30 | 元の支持姿勢へ復帰・脱力・RAM復元 | ID3 1157、他軸安定、全5台OFFを各READで確認。21:07:25の別READ3回でもOFF・エラー0・同じ位置。電源装置のOUTPUTは操作していない。 |
| 21:08–21:09 | 同一RGB3枚で入力解像度比較 | 512では腕が消えてケーブルだけ残る例、768/1024では腕が残る。768約80–84ms、1024約137–141ms（単独GPU、ライブfpsとは別）。公式例1024を参照し、今回の既定は768・CPU thread1。segmentation-resolution/results.json。 |
| 21:12–21:13 | 初期認識で求めた視覚状態を再利用して折り畳みを追跡 | モデルhash・camera serial・metric scaleを検査し、fresh画像の品質で再判定。60秒で987成功/16.46Hz、publication age p95 0.116秒。初回探索は別。live-seeded768/performance.json。 |
| 21:14:15–21:15:36 | 修正後の実機20°追従確認、復帰・OFF | 新基準ID3 1157→1372（約18.9°）、CAD推定は約18°変化。ID1/2/4/5保持。open-20-state.json/overlay.jpgを保存。復帰後ID3 1160、全5台OFF・RAM復元完了。recognition-motion-confirmed/events.jsonl。 |
| 21:16 | HTTP viewerの実際のageを約10秒観測 | 99/99 tracking。frame age p95 0.157秒、mask age p95 0.387秒。HTTP polling回数をpose fpsと混同しない。live-seeded768/http-age.json。 |
| 21:19–21:20 | 最終版の独立60秒計測・checkpoint再読込 | 1012/1012 tracking、16.87Hz、publication age p95 0.114秒。last-good-pose.jsonを実CLI loaderでmodel SHA256・camera serial・metric scale・4関節として読込確認。live-final/performance.json。 |

実装修正: publisherはlost/reacquiringのHzをnullにし、mask ageは現在時刻から計算。
実RGB、raw neural mask、propagated/opened maskを区別して保存。画像書込みの失敗を検査。
微小更新が品質閾値へ届かない場合は内部候補だけを進め、合格するまで公開しない。
連続3失敗で候補を破棄、再取得時は最後の成功状態を先に試し、不適合なら広い探索。
保存checkpointはmodel hash付き。camera所有プロセスとHTTPだけを終了し、port bind失敗でも閉じる。

最小限の確認: root344試験を依存変更後1回、元numerical14試験を別途実行。
以後は影響する関節回復（空mask・欠損depth3回→復元再取得を含む）、表示freshnessの試験のみ。
追加表示試験1件があり、現在rootの試験数は345件だが全345件を再実行したとは記載しない。
実機前の通信guard対照は36件成功。最新ruff/ty、複雑度最大10、技能形式検査成功。
Rust/JSONL motor exchange契約とhardware guardは未変更のためCargo再実行なし。

認識の実証条件: camera/base固定、開いた姿勢で取得した画像由来初期値、nominal R5_65。
畳まれた画像だけからの初回探索は誤対応が残る。CAD角はencoder校正角ではなく、
完全な物理ID対応、65/75°区別、絶対角精度・全姿勢の干渉を今回で認証しない。
RGB-Dは同じSDK framesetをalignした入力で、両timestampを保存する。
異なるセンサーの露光が完全同時とは断定しない。ageはhost受領からの処理/HTTP経過時間。

### 要求→成果物の最終照合

| 要求 | 成果物・検証 |
|---|---|
| 添付と同等の処理を取り込む | packages/articulated-filterreg、input_manifest.json、native-build.json、元14試験、static-replay/replay.json |
| articulated FilterReg/FK/GPU | filterreg.py、renderer.py、tracker.py、既存native E/MとFK、CUDA/direct対照・GPU投影・合成関節回復 |
| 画像/CAD自動認識 | segmentation.py、source.py、raw/登録mask、metric深度/K、21保存画像と実機20°追従 |
| リアルタイム | live-finalの1012成功/60秒、HTTPの99回age、専用headless Playwright screenshot |
| 自分で認識姿勢を選び動かす | D15、10/20/30°の実SDK記録・各写真、改善後20°の追従、2回の復帰/OFF/RAM復元 |
| SOLID/KISS/DRY/YAGNI | 既存FKとCameraPhotoControllerを再利用、境界を入力/領域/登録/描画/状態へ分離、CLI1本と意味のある5認識試験 |
| 作業書・レビュー・技能 | 本書/review.md、docs/ARTICULATED_POSE_RECOGNITION.md、skills/vision-cad-arm-tracking、REPORT.html |

REPORT.htmlは専用Playwrightで最終全30画像の読込みと横overflowなしを確認。
file://はブラウザの許可で拒否されたため、localhost:18112から確認。古い46Hz誤表示の写真は
修正前証拠として明記し、現在の成功更新を示す写真を別掲載する。
最終成果はdiaryへ保存。commit/pushはこのゴールでは新たに依頼されていない。

2026-10-04 21:25:13 JST: 完了照合。最終viewerのheadless Playwright画像を保存し、
最新ruff/tyとdiff whitespaceも成功。本書とレビューをdiary/2026-10-04/workdocsへ保存する。
画像・CAD認識はlocalhost:18111で稼働を継続し、電源装置は操作せず、モーターは全5台OFFで終了。
