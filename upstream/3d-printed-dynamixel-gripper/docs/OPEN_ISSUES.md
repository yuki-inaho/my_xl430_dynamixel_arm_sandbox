# 未解決事項と再開条件

2026-09-24現行: ID5単独開閉・追加なし・ロール不要は確定。
P05局所逃げ候補許可済み、カメラは未購入/28mm四穴、対象は辺長未定のキューブ。
現在の設計は[PG3_ID5_ONLY_DESIGN.md](PG3_ID5_ONLY_DESIGN.md)。旧r5は履歴。

| Gate | 現状 | 再開/解除条件 |
| --- | --- | --- |
| 実機ID対応 | physical ID4/5→CAD joint未確認 | ラベル、配線、個別ping、無通電姿勢から対応表を作る |
| jaw要求 | 対象物、開口、力、速度、duty未定 | 数値要求と安全率をユーザー承認 |
| jaw機構 | PG3クランク/スライダをID5位置へ移設した検証候補。rack案は別の概念候補 | 新配置の締結、backlash、公差、支持、寿命を設計/試験 |
| camera | 型番、光学frame、FOV、質量未定 | 購入品drawing/実測、視野試験、CAD frame更新 |
| fastener | 公称候補のみ、未購入 | ねじ/ナット/washer/tool実寸、深さ、かかり、底付きを測定 |
| cable | connector/径/曲げ半径/route未定 | 実ケーブルを全可動域でsweepしstrain relief確認 |
| PLA | 強度、creep、寸法補正未試験 | couponと実部品で締付/保持/温度/duty試験 |
| upstream arm | R3全体は未承認 | 全関節可動域、自己干渉、荷重、配線を別途再監査 |
| non-solid | assembly内shell 66件 | 意味を分類し、必要な障害物をsolid/保守的包絡で検証 |
| real calibration | 合成のみPASS | 実board実測、実画像dataset、hold-out評価を完了 |

これらが残る限り、`fabrication_approved`、`powered_operation_approved`、
`real_camera_calibration_approved`を`true`にしない。
