# 成果物とGit保存先

- CAD: [public Onshape V2](https://cad.onshape.com/documents/29e8557c76e89bcf64f50566/v/f6162b4adc88af9d07f1194a/e/d5415bf725ba822741b01703)、[固定版STEP](../../../../../../../../3d-printed-dynamixel-gripper/studies/low-profile-20260926/outputs/low-profile-250g/CAD/final-version.step)。
- 人向け: [MANUAL.pdf](MANUAL.pdf) / [HTML](MANUAL.html) / [REPORT](REPORT.md)。
- ロボット: [URDF](../../../../../../../../3d-printed-dynamixel-gripper/studies/low-profile-20260926/outputs/low-profile-250g/robot/model/robot.urdf)、[設定と検証](robot/README.md)。メッシュ12個を含むmodelディレクトリを保ったまま使用する。
- スキル: [4スキルと出典](skills/ONSHAPE-WORKFLOW.md)。リポジトリ直下skills/にも参照ファイルを含め保存。
- 設計保存先: [3d-printed-dynamixel-gripper / codex/onshape-low-profile-d405](https://github.com/yuki-inaho/3d-printed-dynamixel-gripper/tree/codex/onshape-low-profile-d405)、`studies/low-profile-20260926`。
- 変換器保存先: [urdf_from_step / codex/pixi-occt8](https://github.com/yuki-inaho/urdf_from_step/tree/codex/pixi-occt8)、commit `1b2cea3`。

今回の途中保存は設計 `6117edb` と変換器 `1b2cea3`。最終成果物のcommitとremote照合は以下に追記する。commit保存時点と完了後の作業記録を区別し、記録の自己参照SHAは作らない。

最終成果物とOnshapeスキルは [00bd70c4e995788298d98e9de78f0e5e6d70ca35](https://github.com/yuki-inaho/3d-printed-dynamixel-gripper/commit/00bd70c4e995788298d98e9de78f0e5e6d70ca35) としてpush済み。変換器は [1b2cea31c56b875bf98c1d65084781322f5fc835](https://github.com/yuki-inaho/urdf_from_step/commit/1b2cea31c56b875bf98c1d65084781322f5fc835)。DoD照合後の作業記録は設計ブランチの後続commitで追記する。4スキル13ソースと参照ファイル全件の追跡、index内容とSHA、push成功を確認した。

35回帰試験、441閉路、11native姿勢、20ページ/19画像、直接Onshape API 0件。動力学、造形強度、実機耐久性・校正は未確認。今回と無関係なlow_cost_robot内のHN11未追跡4ファイルは変更・commitしていない。

ユーザー指示で別エージェントへの引き継ぎへ切り替えた。通常36/36、DoD D1〜D5済、D6/D7は未チェックで保持。[HANDOFF.md](HANDOFF.md) を参照。作業書・レビュー・引き継ぎの写しはリポジトリ直下diary/にも保存する。全DoD完了を宣言する保存点ではない。
