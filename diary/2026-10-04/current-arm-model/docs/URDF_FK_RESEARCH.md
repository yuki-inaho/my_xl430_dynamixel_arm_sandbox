# URDF・MuJoCo・FKの公式資料調査

2026-10-04。13:56にユーザーがIKを取り下げ、FKのみを指定。先行IK調査は履歴、現在の経路は `simulation/urdf_fk`。

| 公式出所 | 今回の判断 |
| --- | --- |
| [MuJoCo3.13 URDF拡張](https://mujoco.readthedocs.io/en/3.13.0/modeling.html#urdf-extensions) | 実URDFをimport→MJCF保存→site/照明追加。拡張の誤記を検出できない場合があるので、出力モデルで検査 |
| [compiler](https://mujoco.readthedocs.io/en/3.13.0/XMLreference.html#compiler) | discardvisual/fusestaticの初期値に依存せず明示。mesh数/固定tool frameを確認 |
| [ROS2 Jazzy公式教材](https://github.com/ros2/ros2_documentation/blob/jazzy/source/Tutorials/Intermediate/URDF/Building-a-Movable-Robot-Model-with-URDF.rst) | parent/child origin、joint-frame axis、revolute limitをm/radで保存。world配置を二度適用しない |
| [ROS urdfdom](https://github.com/ros/urdfdom) | 標準link/visual/inertial/jointを出力。ROS runtime導入なし |
| [ROBOTIS XL430](https://emanual.robotis.com/docs/en/dxl/x/xl430-w250/) | 保存registerのモード/単位と旧wrapperのaddress/byte幅を照合。FKに実機設定を暗黙に持ち込まない |

docs.ros.orgはbot challengeを返したため同じ公式教材のGitHubソースを参照。[現行仕様](CURRENT_ARM_SPEC.md)と[README](../simulation/urdf_fk/README.md)にローカル適用と結果を記録。公式文書が現物校正や可動域を保証する意味ではない。
