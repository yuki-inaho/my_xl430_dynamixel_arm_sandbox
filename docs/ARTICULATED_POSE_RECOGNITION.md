# RGB-D画像とCADからの関節姿勢認識

`packages/articulated-filterreg/` はユーザー提供のrobot_fit_20261004.zipを
取り込んだ数値パッケージです。元のモデル、注釈、32試行の記録は保存しています。
ライブ実装は `src/arm_observer/perception/` にあり、実機の指令・encoder取得を行いません。

## セットアップ

リポジトリのルートで実行します。Python環境とGPU依存を一緒に固定します。

```bash
rtk proxy uv sync --locked --extra perception-gpu
```

nanobind/CMakeの構築にはC++コンパイラが必要です。RTX2070でCUDA11.8版torch2.7.1と
EGL/NVIDIA描画を確認しています。初回の背景分離にはHuggingFaceから重みを取得します。
公式 `ZhengPeng7/BiRefNet_lite` のrevision
`aa62cd87eafb9cc43056d08ef3615a14628b831d` を固定し、safetensorsを使用します。
そのrevisionのモデルコードを `trust_remote_code=True` で実行します。
重みはHF cacheに保存され、リポジトリには含めません。

## 元静止画の再現

```bash
rtk proxy uv run --no-sync python scripts/replay_articulated_fit.py \
  --output diary/2026-10-04/articulated-fit/static-replay
```

元32試行の選択済み最良初期値を再最適化します。元の手動訓練5点と画像maskを使用する
再現経路です。元結果との差はstate最大1.64e-14、選択score1.11e-16でした。
これを注釈なしの自動認識の成功とは扱いません。元の全初期値探索・評価・出力コードも
パッケージに含み、`articulated-filterreg --help` から利用できます。
元CLIのfitは指定rootのresultsへ出力するため、保存済みresultsを上書きしない作業用rootで使います。
元のvalidate_reproduction.pyはC ABI前提の記述と原本書換えがあるため、上記replayを使います。

## 外部D435によるライブ認識

```bash
rtk proxy uv run --no-sync arm-pose-fit \
  --camera-serial 922612070196 \
  --model models/current_arm_r3_d405_r5_65.npz \
  --backend native --port 18111 --width 480 --segmentation-size 768 \
  --output diary/2026-10-04/articulated-fit/live-run
```

ブラウザで `http://127.0.0.1:18111` を開きます。RGB/CAD重畳、登録用マスク、
CAD基準の関節角、状態、更新率、frame/mask ageを表示します。現在はD435全体視点が対象です。
手先D405は別の撮影・観測用途で、全アームの外形を観測できるカメラと混同しません。
他プロセスがカメラを所有している場合は、そのプロセスを勝手に終了しません。
終了は起動ターミナルでCtrl+C。カメラ子processと自分のHTTP serverだけを閉じます。

初期化には広い候補探索があり、定常追跡と別に時間がかかります。姿勢がまだ求まらないときは
reacquiring、入力欠損やCAD不一致ではlostを表示し、古い角度を現在の推定として出しません。
肩・肘・手首が画像上で離れ、リンクの輪郭が見える構図を初期化に使うと対応付けが容易です。
その後に畳む姿勢を追跡します。台座と外部カメラを固定し、アーム全体と足元をなるべく写します。
現在の初期探索は、台座が直立し画像で上方向、足元がforegroundの下側にある卓上構図を仮定します。
これはカメラの厳密な外部校正ではありません。台座やカメラを動かした場合は再取得が必要です。

一度、開いた姿勢で正しく位置合わせできたら、同じ三脚・台座のまま折り畳み姿勢を追跡します。
成功した画像/CAD推定は`last-good-pose.json`へ保存します。再起動時には
`--initial-pose <以前のrun>/last-good-pose.json`で初期値として再利用できます。
モデルSHA256・camera serial・metric scaleを検査し、新しい画像への品質判定も行います。
受理できなければlostのまま台座の位置を保持します。カメラ・台座を移動した場合は以前の初期値を使わず、
開いた姿勢で取り直してください。これは画像由来の初期値で、encoderやモーター校正値ではありません。
再取得時も直前の成功姿勢を試し、失敗後に背景へ根元を合わせ直しません。
初期値のない初回だけ広い探索を行います。この初回探索は物体の同一性を保証せず、
特に畳まれた腕では誤対応が残ります。実際のmask・重畳を確認してから初期値を再利用してください。
台座の可視面に100点以上の有効深度が必要で、CADとの深度差中央値15 mm以下を要求します。
黒い台座がRGB maskから欠落することがあるため、台座判定にはmask外も含むaligned depthを使います。
台座が遮蔽された場合もlostです。自動で別の背景へ追従することは許しません。

## 処理と座標

1. カメラ専用spawn processで1280×720/30fpsのRGB/depthを取得し、SDKでcolorへalign。
   1枠queueと親の最新frameスロットを使い、推論待ちのFIFOを作りません。
2. RGBとdepthを同時resize（既定640×360、`--width 480`では480×270）。実SDK Kをpixel centerまで補正し、depth countに
   実センサーのm/countを掛けます。非ゼロBrown歪みは共通remap、未対応歪みは明示拒否。
3. 別workerでBiRefNet CUDA/float16、768入力による自動maskを継続更新します。最新のmask frameから
   現在のRGBへ逆向きoptical flowでmaskを伝播します。現在時刻から0.5秒を超えるmaskは使いません。
   raw maskとopeningを施した登録用maskは別のものです（640幅では7px、480幅では5px）。
   成功追跡時の面積に対して極端に崩れた新maskは拒否します。拒否中に古いtimestampを
   更新せず、0.5秒で失効するため、入力崩壊を成功した追跡として隠しません。
   細いUSBケーブルの除外は形態処理であり、手描き注釈ではありません。
4. PCAとarea-weighted CAD面サンプルから初期姿勢候補を作り、可視面で選択します。
   候補順位のnearest距離は初期候補の採点だけで、ICPによる更新ではありません。
5. 観測点を固定したGaussian E段階から質量・一次/二次momentを求め、共有C++ coreで
   リンクごとのtwistを関節Jacobianへ集約してM段階を解きます。
   自動maskの輪郭距離は明示した画像補助項で、更新時と採否判定時の双方に含めます。
6. ModernGL/EGLで可視面の色、camera-space XYZ、bodyを同じ描画から取得します。

Gaussian backendは `native`（nanobindの格子Gaussian）または `cuda`（exact Gaussian）。
GPUが使えないときの暗黙fallbackはありません。nativeが既定で、背景分離とCAD描画はGPUです。
metricライブではscale=1を固定します。静止画の自由尺度・任意深度単位とは区別してください。
Camera座標はx右、y下、z前、長さm。qはSTEP参照姿勢との差分rad/degです。
J5は観測可能な下流形状がないためnullであり、ゼロ角と推定しません。
qとモーターID・neutral count・回転方向を、この認識だけで実機校正値に変換してはいけません。
RGB-Dは同じSDK framesetをalignしています。RGBとdepthのセンサーtimestampを別々に残し、
露光が完全に同時とは断定しません。表示するageはhost受領からの経過時間です。

## モデルと記録

bare_arm.npzは元資料の裸R3。`models/current_arm_r3_d405_r5_65.npz` は裸R3に
長尺D405ホルダー・カメラ・締結部品21 meshをwristへ加えた別モデルです。
現物の65°/75°区別は未確定で、65°は候補版です。爪は未装着、実ケーブル全体は未モデル化です。
生成スクリプトと隣接JSONに出典・座標原点・input/output SHA256を保存しています。

出力は `poses.jsonl`、間引いたRGB/mask/metric depth/K、frame metadata、モデル名、
backend、重みrevision、重畳画像です。保存RGB-DはそのframeのKと組にして扱ってください。
raw neural maskは`segmentation-*.raw-mask.png`と対応するRGBへ別保存し、登録用maskと区別します。
深度残差やmask IoUは対応の診断値であり、真の関節角誤差ではありません。

保存neutral+20姿勢の再処理は全21画像がtracking、IoU0.702–0.868でした。
これは画像間ジャンプごとに8回整定するoffline処理で、動画性能や真の角度精度ではありません。
512入力の初期runは領域抽出の崩壊と誤対応があり、成功45姿勢/56秒（0.80Hz）でした。
その後、肘10/20/30°の実機観察でリンクを見分けやすい初期姿勢を取得し、
768入力・CPU thread1・画像由来初期値・短い欠損からの再取得を改善しました。
修正後は60秒で成功987姿勢（16.46Hz）、publication age p95=0.116秒。
さらに20°の実機指令でencoder変化約18.9°、画像推定変化約18°の追従を確認。
復帰・全トルクOFF・RAM復元も確認済みです。HTTPを約10秒99回観測した結果は全99回tracking、
frame age p95=0.157秒、mask age p95=0.387秒でした。
最終コードでの別60秒も1012/1012成功、16.87Hz、publication age p95=0.114秒を確認しました。
対象条件は外部カメラ/台座固定・nominal R5_65・開いた姿勢の画像由来初期値です。
完全に畳まれた画像からの初回探索は誤解が残るため、同じ性能や角度精度を保証しません。
最新証拠は[日付別レポート](../diary/2026-10-04/articulated-fit/REPORT.html)にまとめています。

領域抽出は[公式モデル例](https://huggingface.co/ZhengPeng7/BiRefNet_lite)の1024入力を基準に、
同じ保存画像で512/768/1024を比較しました。512はケーブルだけが残る例、768は腕が残る例を視認。
単独GPUで768は約80–84msでした。これをライブ持続速度と混同せず、768を今回の既定としています。
別の画角ではマスクを必ず視認してください。

実測はjournalから独立した成功poseだけを数え、lost/reacquiringの時間も含めます。

```bash
rtk proxy uv run --no-sync python scripts/summarize_pose_journal.py \
  diary/2026-10-04/articulated-fit/live-quality-mask/poses.jsonl \
  --seconds 60 --output diary/2026-10-04/articulated-fit/live-quality-mask/performance.json
```

## 多姿勢検証と最終レビュー（2026-10-04 21:47〜22:25）

最新の[画像付き20姿勢レポート](../diary/2026-10-04/diverse-recognition/REPORT.html)と
[レビュー記録](../diary/2026-10-04/diverse-recognition/REVIEW.md)が今回の結果です。
元データは `~/data/xl430-arm/2026-10-04/diverse-recognition/`。
portableな撮影画像、metric RGB-D・K、encoder前後READはレポートのcaptures/にも保存しています。
認識にはencoderを入力せず、2.5秒保持時の前後READに画像のhost時刻を挟んで比較しました。
同期はhost時刻によるものです。変化の符号を決めた4姿勢を除く16姿勢の相対誤差MAEは、
台座1.15°・肩0.43°・肘0.37°、最大は2.97°・1.41°・0.88°でした。
肩の実変化は約4.4°幅に限られ、絶対校正・全可動域精度ではありません。
手首+6°候補はno progressで停止。+3°の実移動約1.85°も画像で十分分解できず、
手首認識は未検証です。爪なしのID5も未検証です。

実撮影701.97秒（停止・再開を含む）の成功推定は19.80 Hz、frame age p95=0.101秒、
mask age p95=0.355秒でした。静止frame60更新の処理中央値は40.76→29.23 ms（28.3%短縮）、
前後の全60推定は一致。1件の描画cache、輪郭距離場再利用、1件だけの背景保存を使い、
quality/freshnessとmotor guardを緩めていません。撮影期間の追跡率99.86%は正解率ではありません。
この性能測定は下記の最終不在判定追加前です。追加後は保存済み20姿勢の判定互換と
不在・移動の失敗例を検証し、同じ実機撮影を再実行してはいません。

電源OFF後に腕が画角から外れた際、箱・ケーブルへ根元を合わせてtrackingになる不具合を発見しました。
元の失敗画像と推定を残し、seed保持と台座深度判定で修正しました。
20姿勢の台座誤差1.85〜2.42 mmに対し、不在の実画像は34.72 mm。
修正後はこの不在画像を4回連続でlostとし、保存20姿勢はすべて判定を通過。
台座の位置が変わった現在の画像もlostになり、古い角度を出していません。
同じ奥行きの別物体など、全種類の誤認識が除去された証明ではありません。

```bash
# 画像由来の保存姿勢を使ったgate互換性・実不在画像の回帰確認。再fitや角度精度試験ではない。
rtk proxy uv run --no-sync python scripts/check_pose_presence.py \
  ~/data/xl430-arm/2026-10-04/diverse-recognition \
  --model models/current_arm_r3_d405_r5_65.npz --output /tmp/presence-check.json
```

動作はD16の別撮影modeでID1±30°、ID2±3°、ID3開き0..30°、ID4候補0..+6°、ID5保持。
肩・手首は肘20°以上でのみ変更し、ID4停滞後は追加手首候補を棄却しました。
元のD14/ID3限定guardは拡大していません。接触・配線・支持は実画像で都度確認しましたが、
MuJoCo表示モデルは接触無効であり、全域の自己干渉検証はUNKNOWNのままです。
21:58:35に支持姿勢へ復帰・全5台OFF・RAM復元、21:59:42の独立READでも確認。
その後ユーザーが電源OFFを報告。以降はserialアクセス・動作をしていません。
