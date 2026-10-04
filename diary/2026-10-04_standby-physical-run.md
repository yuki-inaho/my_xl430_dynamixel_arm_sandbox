# 2026-10-04 実機スタンバイと記録時点

ユーザーは精密角度の追込みより「動いたことの確認」とスタンバイ移行を優先した。
サブエージェントは使用していない。既存ID3単軸guardを広げず、
`src/arm_observer/standby_motion.py`に別のID2/3/4限定RAM経路を追加した。

- 12:55:48：2064/3128/1156/2058/2059を開始基準に、肩・肘・手首を保持。
- 12:56：elbow30到達。次のelbow60は36countの下がりでdeadline停止。OFFせず保持した。
- 12:59：元基準・復元設定を残したまま再開。1回最大30count補正で到達、閾値緩和なし。
- 13:01：前腕は概ね前方・手先は下向きの実スタンバイ。画像確認、読値2064/3115/1969/1721/2059。
- 13:02:28：段階復帰で元姿勢付近へ戻った。
- 13:02:44：ID4→3→2を脱力。全OFF確認、RAM3項目を全3台READ照合して復元、exit0／port閉鎖。
- 13:03：独立10秒200frame、約20Hz、欠測0、全OFF、最大span1count。最終2064/3118/1159/2050/2059。
- 13:06：ユーザーが「電源きりました」と報告。報告後カメラ3frameで畳み姿勢を保存した。

実機作業はユーザー指示で一時停止（goal paused）。その後は記録・スキル・HTMLのみ。
電源OFF後のモーターREAD／WRITEは行っていない。電源の実電圧測定、荷重支持の
確認、精密CAD校正、全経路自己干渉、校正済み実機live描画は未完了として残す。
今回の実動作・画像確認をもってこれらの未完了項目を全て完了とはしない。

[画像入りレポート](../reports/robot-completion-20261004/standby-record-html/REPORT.html)、
[実機結果](../reports/robot-completion-20261004/standby-stage-resumed/STANDBY_ja.md)、
[5回自己レビュー](../reports/robot-completion-20261004/standby-stage-resumed/SELF_REVIEW_5.md)。
最終offline品質はPython291件、ruff／ty／最大複雑度10、スキル形式検査成功。
signal/logging停止の追加修正は実機終了後のoffline検証で、実機再試験済とはしない。
commit／pushは今回行っていない。
