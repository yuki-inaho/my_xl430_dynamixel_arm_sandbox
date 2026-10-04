# V2 STEPから生成した運動学モデル

**継続作業の改善:** [52試験と独立STEP再読込](../../../revalidation/README.md)。
`validate_robot.py --model outputs/model --output outputs/new/report.json` で対象を明示できる。
引数なしでは保存modelを検査して標準出力へ表示し、下記の過去validation.jsonは上書きしない。
`replay_step.py --output outputs/new/replay-directory` がSTEP本体を再読込する。
元のPixi/OCCT8変換と、今回のCadQuery/OCP独立検査は別の実行記録である。

- 最終URDF: [model/robot.urdf](../../../../../../../../../3d-printed-dynamixel-gripper/studies/low-profile-20260926/outputs/low-profile-250g/robot/model/robot.urdf)、12 STLは [model/assets](../../../../../../../../../3d-printed-dynamixel-gripper/studies/low-profile-20260926/outputs/low-profile-250g/robot/model/assets)。一式を同じ相対配置で扱う。
- 関節設定: [converter-config.json](converter-config.json)、元のUI定義 [joint-definitions.json](joint-definitions.json)。
- 閉路の従属計算: [pg3_states.py](../../../../../../../../../3d-printed-dynamixel-gripper/studies/low-profile-20260926/outputs/low-profile-250g/robot/pg3_states.py)。`python pg3_states.py 25` で開、90で中立、135で閉。
- 照合: [validation.json](validation.json)、[validate_robot.py](../../../../../../../../../3d-printed-dynamixel-gripper/studies/low-profile-20260926/outputs/low-profile-250g/robot/validate_robot.py)、[test_validation.py](../../../../../../../../../3d-printed-dynamixel-gripper/studies/low-profile-20260926/outputs/low-profile-250g/robot/test_validation.py)。
- 再現環境・コマンド: [CONVERTER.md](../CONVERTER.md)。Pixi + OCCT 8.0.1、ROSなしで実行。

16リンク/15関節、5能動+4受動+6固定。閉路は左右それぞれ2つの固定補助frameの位置一致で検証する。441状態と11 native姿勢を照合済み。入力は `../CAD/final-version.step`（V2、SHA256 `9f58c947753e9229b30939da23ce4c87c1cc85eeb39372518de4ffb98991b93f`）。部品262件を12メッシュへ新規変換した。

このモデルは運動学用。effort/velocity=0は未設定であり、コントローラ設定として使わない。質量/慣性、実機ホーム、カメラ外部校正、物理エンジン用collision形状は未確定。`onshape-native/` は修正前V1の比較用出力で、最終モデルではない。
