# RealSense RGB-D撮影と3D表示

2026-10-04 17:12の実確認: Intel RealSense D435、serial 922612070196、FW 5.16.0.1、USB 2.1。
RGB/深度/左右IRは640×480、15fps。SDKの実depth_scaleは0.0010000000474974513 m/count。
新しい依存追加やロボット接続は不要。カメラ取得は既存 realsense_capture_tool、点群計算は既存 rgbd_data_utility_tools の実装を呼ぶ。

## 使い方

下記のSCRIPT_ROOTはこのリポジトリ、CAPTURE_PROJECTとRGBD_PROJECTは再利用元checkout。
各checkoutの既存uv環境を使う。PC固有パスは引数で渡す。

```bash
SCRIPT_ROOT=/path/to/my_dynamixel_arm_sandbox
CAPTURE_PROJECT=/path/to/realsense_capture_tool
RGBD_PROJECT=/path/to/rgbd_data_utility_tools
CAPTURE_DIR=/path/to/data/capture-01

# 単発取得。出力先は新規ディレクトリに限定して原画像の上書きを防ぐ。
rtk proxy uv run --directory "$CAPTURE_PROJECT" --no-sync python "$SCRIPT_ROOT/scripts/capture_realsense.py" \
  --capture-project "$CAPTURE_PROJECT" --serial CAMERA_SERIAL --output "$CAPTURE_DIR"

# 色付きPLYと自己完結HTML。SDKから保存した深度単位とRGB内部パラメータを読む。
rtk proxy uv run --directory "$RGBD_PROJECT" --no-sync python "$SCRIPT_ROOT/scripts/export_rgbd_point_cloud.py" \
  "$CAPTURE_DIR" --rgbd-project "$RGBD_PROJECT"

# ライブプレビュー。単一ストリームを保持し、ブラウザのボタンで同一frame bundleの画像を保存。
rtk proxy uv run --directory "$CAPTURE_PROJECT" --no-sync python "$SCRIPT_ROOT/scripts/capture_realsense.py" \
  --capture-project "$CAPTURE_PROJECT" --serial CAMERA_SERIAL --output /path/to/data --serve-port 18107
```

ライブは http://127.0.0.1:18107/ 。現在のデモの3Dリンクは出力親以下のcapture-01/point-cloud.htmlを開く。
任意の保存フォルダにもexport後のHTMLを直接開ける。3Dは保存済みフレームの表示で、点群のライブ更新は実装していない。
RGB/深度表示はMJPEG連続配信。状態表示は1秒ごとに更新。取得モードはwidth/height/fps引数で指定する。実取得処理の速度はstatus.jsonのacquisition_rate_hzに示し、設定fpsとは区別する。終了はCtrl+C、SDK camera.close(hardware_reset=False)で解放。
ほかの撮影アプリが同じカメラを使用中なら終了させず、そのアプリでの使用が終わってから開始する。

## 保存と確認

- color.png、depth.png（生uint16）、aligned_depth.png（RGB基準のuint16）、ir_left/right.png。
- metadata.json: device/serial/FW/USB、実深度単位、stream内部パラメータ・歪みモデル、SDK外部パラメータ、frame bundle番号と時刻、保存時刻、形状、深度有効率。
- per_stream_timestampsとrobot_observationはnull。取得していない情報を確定値として扱わない。
- calibration.tomlは元のcapture tool書式を併記。metadata.jsonのSDK外部回転値はcolumn-majorのflat配列と明記しており、TOMLとは別に保持する。
- depth_preview.pngは0〜2mの表示用画像。測定・点群化には16bit深度を使う。
- point-cloud.plyは全有効深度点。point-cloud.htmlの表示だけ既定2.5mで切り、最大約3万点へ間引く。単位m、RGBカメラ座標の右X/下Y/前Z。軸入替なし。
- 非ゼロ歪み係数は既存のピンホール点群処理へ無条件に渡さず拒否する。D435今回取得した係数はゼロ。
- 写真の採用は実画像のピント・構図・遮蔽確認で決める。ファイル生成、深度有効率、HTML描画だけを写真品質やロボットの安全姿勢の合格としない。

## 今回の証拠

データ正本: ~/data/xl430-arm/2026-10-04/realsense-camera-check/
- capture-01: 17:12:10の壁・モニターを撮影した実RGB-D。深度有効率73.16%。
- capture-20261004-171424-154928: ライブ保存操作で取得したRGB-D。関節観測なし。
- capture-01/point-cloud.ply: 224,761点。HTMLの表示は27,563点。
- live-preview.png / point-cloud-preview.png: 専用headless Playwrightの実画面。
- ライブ保存前後でSDKframe番号680→682と新しい受信時刻を確認。保存ボタンも実行済み。
- 元リポジトリの未コミット変更を保持。テストスイート、SDK再インストール、機器リセット、ロボット書込みは実施していない。

## 1280×720・30fps（18:20追加）

ユーザー指定で --width 1280 --height 720 --fps 30 を追加し、同じ18107のビューアを起動。
SDK profileでRGB/Depth/左右IRそれぞれ1280×720・30fpsを確認。USB3.2、同一serial、観測FWは5.17.3.10（この作業でFW書込みはしていない）。
capture-20261004-182023-913145はD405取付済みアームを含む実RGB-D、capture-20261004-182230-537606はstreams一覧を含むメタ付き保存。
SDK設定30fpsと整列/JPEG/配信の実速度は異なる。18:22の処理実測は19.43Hz。画像の暗部にノイズがあり、全姿勢写真の採用を確定したものではない。
D405は実機に取付済みだがUSB未接続というユーザー申告。撮影入力は外部D435。
# D405付きニュートラルと20姿勢（2026-10-04 18:27〜18:38）

データ正本：`~/data/xl430-arm/2026-10-04/d405-mounted-rgbd-1827/`。
開始neutral＋台座5方向/肘4段階の20unique＋終了neutralの計22組。
各組に原RGB、生uint16深度、RGB整列深度、左右IR、深度プレビュー、
metadata.json、calibration.toml、pose.jsonを保存。20動作姿勢には撮影前後の
live telemetryと画像SHA256を添付した。RGB-D/encoderはhardware同期ではない。
D405はアーム取付済み・USB未接続で、撮影は外部D435。

固定焦点でリンク/ボルト輪郭を確認したが低照度ノイズがある。原PNGにノイズ除去はしない。
手首-5°候補は未達停止して不採用、手首を保持する表へ変更した。台座±30°/肘10〜30°
は実画像を一枚ずつ確認して撮影。終了時は新ニュートラル復帰・全OFF・RAM復元を読戻し済み。

`scripts/save_pose_rgbd.py --dataset DATASET --pose pose_01`は既存camera serverへPOSTする。
`scripts/export_rgbd_pose_gallery.py DATASET`は画像を再取得せず、既存記録から一覧を生成する。
実撮影controllerは`python -m arm_observer.camera_pose_capture --help`。
`--execute`なしでは書込みせず、基準/健康状態のみを確認する。
再実行には新しい基準観測と取り付け/支持の確認が必要で、今回の固定count表を
別の組立・別の机へそのまま流用しない。
PRIVATE Git保存コピー：`diary/2026-10-04/d405-mounted-rgbd/`。
