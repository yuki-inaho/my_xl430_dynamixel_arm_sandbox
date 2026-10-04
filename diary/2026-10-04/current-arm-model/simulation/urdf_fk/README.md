# R3のURDF変換とFKビューア

裸アームの4関節角からM05軸中心と方向を計算し、実URDFを読み込んだMuJoCoで描画する。IKなし、SDK/シリアルなし、実機count入力なし。既存uv.lock/MuJoCo3.13.0を使用。

```bash
rtk proxy env MUJOCO_GL=egl uv run --no-sync python -m simulation.urdf_fk.demo --output outputs/urdf-fk-r3-new-run
rtk proxy env MUJOCO_GL=egl uv run --no-sync python -m simulation.urdf_fk.server --output outputs/urdf-fk-r3-20261004-r2 --port 18104
```

生成時は存在しないrun名を指定。確認済み実出力は[r2](../../outputs/urdf-fk-r3-20261004-r2/)、ビューアは <http://127.0.0.1:18104/>。4角度を指定して「ゆっくり反映」、または3例を選択。停止は古い目標を消費する。斜め/側面/正面/上面を切り替える。

角度はCAD保存姿勢からdegree、内部rad/m、位置表示mm。緑の線はM05中心から+Yへ45 mmの方向表示。端の点はTCPではない。ID5ケースはID4下の固定表示で、爪/カメラは未装着構成。色は元表示モデルの設定。

## 入出力と検証

[仕様JSON](../../specs/urdf_fk_r3.json)が原本SHA、期待10mesh/180要素/55surface要素、4軸/表示範囲、3例/5検証姿勢を固定。`model.py`は元MJCF chain/CAD軸を照合しOBJを無変更コピー。URDF→imported.xml→scene.xmlは実MuJoCo compilerの出力。

生成：robot.urdf、meshes/、imported.xml、scene.xml、model-manifest.json、fk-results.json、verification.json、3姿勢×2視点PNG。元MJCF/独立XML・NumPy FK/変換後MuJoCoの位置・姿勢と全10meshのcompiled世界外接箱を比較。

```bash
rtk proxy env MUJOCO_GL=egl uv run --no-sync pytest -q tests/test_urdf_fk.py tests/test_current_arm_viewer.py
rtk proxy uv run --no-sync ruff check simulation/urdf_fk tests/test_urdf_fk.py
```

## 対応範囲

現変換器はspec固定の、無回転body/geom frame、各body原点に1hingeの4軸直列モデル専用。異なるframeは拒否する。別ロボットは軸・親子変換の対応と独立試験を追加し、推測で向きを補正しない。

limits/mass/inertia/effort/velocityは仮値。collision/動力学積分なし。0.5°/frame・目標20Hzは表示更新でモーター制限ではない。現物の絶対校正結果ではない。[写真仕様](../../docs/CURRENT_ARM_SPEC.md)、[スキル](../../skills/urdf-mujoco-fk/SKILL.md)
