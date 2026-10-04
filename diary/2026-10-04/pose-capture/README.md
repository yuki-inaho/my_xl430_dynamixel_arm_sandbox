# 実機24姿勢の撮影・復帰中断記録

休止・スタンバイ・ID1±30°・ID1中立20候補、計24姿勢を撮影し、写真24枚とPlaywright画面PNG24枚を保存。台座傾斜で一度止め、ユーザーが工具で支持した後に候補1を再撮影して再開した。失敗原画像はrejected/に保持。肩の0°戻しは追従条件を満たさず、候補10〜20を安定保持できた−2°へ変更し、元の案を.initial.jsonに保存。今回の角度は現物中立からのencoder指令差分であり、CADの絶対角ではない。

終了後の畳み復帰は16:28:25 JSTに肘の18秒deadlineで停止し、5台現在位置保持。腕の重量を外部支持して進めるというユーザー回答後、16:51:57 JSTに保持姿勢のまま全5台TorqueOFFと元のRAM設定復元を読戻し確認し、シリアルを閉じた。元の畳み姿勢への自動復帰は未達として残す。電源装置は未操作で、物理的な電源OFFは未確認。写真の完了と各終了条件を分けて記録している。

[撮影HTML](../../../reports/pose-capture-20261004/index.html) / [manifest](../../../reports/pose-capture-20261004/manifest.json) / [作業書](WORKDOC.md)

[撮影表](SHOT_TABLE.md) / [最新の終了状態](../../../reports/pose-capture-20261004/final_state.json) / [復帰停止時の実画像](../../../reports/pose-capture-20261004/photos/return_stop_1628.jpg)
