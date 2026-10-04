# R3 bare例（2026-10-04）

repo rootで実行。入口 `simulation.urdf_fk.model/demo/server`、入力 `specs/urdf_fk_r3.json`、試験 `tests/test_urdf_fk.py`。[README](../../../simulation/urdf_fk/README.md)を参照。

```bash
rtk proxy env MUJOCO_GL=egl uv run --no-sync python -m simulation.urdf_fk.demo --output outputs/urdf-fk-r3-new-run
rtk proxy env MUJOCO_GL=egl uv run --no-sync python -m simulation.urdf_fk.server --output outputs/urdf-fk-r3-20261004-r2 --port 18104
```

新run名、MuJoCo3.13.0/uv.lock、原本SHAを使用。現変換器は無回転body/geom、origin-centered hinge1個/body、4軸直列のみ対応し他frameを拒否。

5XL430ケース/5印刷部品=180末端/55surfaceを10meshに保持。4軸＋M05中心tool_fixed。M06/P06/P07、爪、D405未選択。ID5にrollを追加しない。

ゼロ0/0/0/0、前方0/−20/−20/−30、旋回20/−10/15/−20 degree。デモ範囲±40/40/60/60degree、0.5degree/frame、目標20Hz。ローカル表示条件で実機設定ではない。

原本/独立FK/import結果を5姿勢/10meshで比較。初期19FK testsには2degree負例・非有限/範囲外・hash/上書き拒否を含む。最終回帰はrunのSELF_REVIEW.md参照。r1で中心markerが隠れたためr2に45mm方向線を追加。tool評価点は変更なし。

現物と版の確度・写真・保存encoder観測は[仕様書](../../../docs/CURRENT_ARM_SPEC.md)。countは過去の実記録でデモ入力/motor goalではない。
