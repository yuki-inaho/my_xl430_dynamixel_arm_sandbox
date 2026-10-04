# R3 + 長尺R5 + 取付済みD405のFKモデル

2026-10-04の現物写真とユーザーの「D405は取付済み、USB未接続」に合わせた固定visual。
長尺65°版が第一候補で、75°短縮版との最終同定は未完了。
元R3にホルダー16mesh、D405名目外形1meshと取付ねじ2meshを追加した。
29mesh/199occurrences/4DoF。USBケーブル、未装着の爪は含まない。

仕様：`specs/urdf_fk_r3_d405.json`。
実URDF→MuJoCo import、独立FK/全mesh bounds照合を5姿勢で一度実行し、
`verification.json`に記録。最大bounds差2.692e-9m。衝突・荷重の認証ではない。

再生成：`rtk proxy env MUJOCO_GL=egl uv run --no-sync python -m simulation.urdf_fk.demo --spec specs/urdf_fk_r3_d405.json --output outputs/urdf-fk-r3-d405-new-run`

表示：`rtk proxy env MUJOCO_GL=egl uv run --no-sync python -m simulation.urdf_fk.server --output outputs/urdf-fk-r3-d405-20261004-r1 --port 18104`

画面角[0,-20,-20,-30]はCAD例示で実機encoder角ではない。
実機の新ニュートラル参照[2102,3473,1147,3398,1951]との絶対FK校正は未確定。
`browser-d405-side.png`にPlaywright実表示を保存した。
