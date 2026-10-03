# Handoff entry point

現在の引き継ぎ書の正本は [../3d-printed-dynamixel-gripper/HANDOFF.md](../3d-printed-dynamixel-gripper/HANDOFF.md) です。まず正本を読み、本directoryのAGENTS.mdとtemp/workdoc_Oct03-2026_id3_open_10deg.mdに従って再開してください。

実機約10°動作は未実施。paired READ helperはoffline/模擬ブラウザ検証までで、手順2aの文書・レビュー整合を残しています。READ bridge 8085は停止・port closed、実機viewer 8084はmanual/未校正です（2026-10-03 22:03 JST時点）。

## 2026-10-04 00:25 更新（Claude）
ID3作業書は完了した。2026-10-04 00:20 の実機2回目で、ID3は約10°開いて収束した（1154→1264、目標1268）。その後もとの位置へ戻し、Torque OFFを確認した。詳細は [diary/2026-10-04_id3-open-10deg.md](diary/2026-10-04_id3-open-10deg.md)、検証は [reports/id3_motion_validation.json](reports/id3_motion_validation.json)。bridge 8085はstopped・port closed、viewer 8084（pid 2897544）は再起動済みで、2a修正版が稼働している。上記の22:03時点の記述は履歴として残す。

