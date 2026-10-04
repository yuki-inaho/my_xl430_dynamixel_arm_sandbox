# 継続作業の自己レビュー5回（2026-10-04）

担当Codexのみ。別エージェントを使用せず、各回で異なる実出力／契約を照合した。これは全軸校正・姿勢移行の完了報告ではない。

| 回 | 観点・独立入力 | 発見と改善 | 結果／残件 |
|---|---|---|---|
| 1 | 実送信の宛先と方向。SDK serial emulator、実全5台routing READ、固定R3原資料 | Secondary IDによる別モーター宛てRAM WRITE、自己申告のCAD sign/hashを拒否。固定資料から再導出しsource/session付き原本READを検査 | R1/R2回帰PASS、実全台alias255。未検出の別motorを不在とは断定しない |
| 2 | 実機open/hold/returnログ、事後metadata、独立18条件 | 各phaseのTorqueON、復帰±5、RAM復元READと終了codeを拘束。1154→1264→1154、他ID delta0、復元一致 | 実encoder検証PASS。現物の視覚観測／全軸の角度校正とは区別 |
| 3 | sourceのみを変更した専用browser/UI、校正apply payload | backend拒否後に4現物checkboxが残る問題を発見。source/session/invalidationで解除しpayloadにもsourceを明記 | source-confirmation-reset.txt、source-browser-check.json。合成fixtureの確認を現物確認として流用していない |
| 4 | branch会話raw prefix／API user、Claude queueのcompact正規化、繰返しuser | both/no-dedupとchannel別網羅性検査。fork branchを先祖会話全部と誤認する表現を修正 | API user31/31、export回帰5PASS。10:47以後とfork先祖は今回snapshotの外、後で別cutoffを出力 |
| 5 | 電源OFFの実READ100frames／写真SHA、CAD基準側面／公式仕様／元robot実装 | 全OFFの安定参照と支持荷重・移行指令を分離。自動基準合わせを仮zeroへの移動で代用しない。現在neutral2軸の確認は他軸zeroへ昇格させない | anchor独立検証PASS、全span0。支持点・全軸校正・連続経路は未解決 |

使用証拠はこのディレクトリのrepair-gates.json、id3-actual-validation.json、actual-live-browser-check.json、power-off-reference-validation.json、source-confirmation-reset.txtと原本logs。5skillの更新は一般条件に限定し、今回の2062等を汎用既定にしていない。

自動校正に関して、R3 joints.jsonのzeroはCAD保存姿勢であることをdonor READMEが明記する。元low_cost_robot/robot.pyはcountを直接読み書きし、URDF/CADへのoffsetを提供しない。Homing Offsetはservoの位置表示へ加算する設定で、組立リンクの角度を観測する機能ではない（[ROBOTIS公式](https://emanual.robotis.com/docs/en/dxl/x/xl430-w250/#homing-offset20)）。この証拠から、未記録の機械組立offsetをREADだけで確定することはできないと判断した。写真推定を実校正済みとして送信しない。

ユーザーD7: ID1/ID5現在位置neutral、爪/D405未装着を確定。基準合わせは自動を希望。全軸自動移行を実行するには残るoffsetの独立観測／既知組立基準が必要であり、この前提を手作業依頼へ黙って置き換えない。
