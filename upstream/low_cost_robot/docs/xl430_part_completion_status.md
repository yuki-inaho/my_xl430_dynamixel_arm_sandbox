# XL430 CAD部品の完成・未完成メモ

更新日: 2026-09-19  
対象: `skills/cad-reverse-parametric/studies/xl430_lowcost/`

## 判定基準

このメモでの「完成」は、**現時点で3Dプリンタ向けSTLとして扱えること**を意味します。具体的には、watertight、volume、winding、boundary edge、non-manifold edgeのメッシュ検査を通過した成果物です。

ただし、印刷可能であることは、実機への取付、ねじ締結、可動域、干渉、強度、耐久性、Dynamixel XL430との機能適合を保証しません。これらは実機検証が別途必要です。

`outputs/print/print_readiness_report.json` はメッシュ検査の根拠として参照しますが、`elbow_to_wrist_xl430` の形状解釈誤りが判明する前に生成されたものです。そのため、同部品については最新レビュー結果を優先します。

2026-09-19に別途、XL430 2台とXL330系4台を維持するフォロワー幾何改訂が追加されました。これは全関節XL430化ではなく、XL430専用の本表とは別の印刷パッケージです。詳細は [follower_geometry_revision_20260919.md](follower_geometry_revision_20260919.md) を参照してください。

同日受領した全6関節XL430静止組立は再生成できましたが、置換後に54件の外部部品間体積干渉が確認されたため未承認です。詳細は [all_xl430_revision_20260919.md](all_xl430_revision_20260919.md) を参照してください。流用された7部品は、全XL430向け適合済み部品として本表の完成欄へ追加しません。

## 完成した印刷可能パーツ

| パーツ | 印刷に使用するSTL | 判定根拠 | 残る制約 |
|---|---|---|---|
| shoulder rotation（元形状） | `skills/cad-reverse-parametric/outputs/print/shoulder_rotation_orig.stl` | メッシュ検査を通過 | 元形状の印刷物であり、XL430向け再設計品ではない |
| shoulder to elbow（XL430） | `skills/cad-reverse-parametric/outputs/print/shoulder_to_elbow_xl430.stl` | メッシュ検査と主要インターフェース検査を通過 | 有機形状全体の元STEP同等性、実機組付け、荷重下の強度は未確認 |
| elbow to wrist extension（現行形状） | `skills/cad-reverse-parametric/outputs/print/elbow_to_wrist_extension_xl430.stl` | メッシュ検査を通過 | 現行実装は元形状を保存するno-opであり、XL430固有の局所再設計ではない |
| gripper static part（XL430） | `skills/cad-reverse-parametric/outputs/print/gripper_static_part_xl430.stl` | メッシュ検査を通過 | 現状ではXL430置換による形状変更が不要という扱い。実機干渉と締結は未確認 |
| gripper moving part（印刷修復版） | `skills/cad-reverse-parametric/outputs/print/gripper_moving_part_xl430_print.stl` | 0.2 mmの外周リリーフを加えた修復版がメッシュ検査を通過 | 正規生成物ではなく印刷専用派生物。機能穴を保持しているが、実機動作は未確認 |

## 未完成または印刷成果物として未承認のパーツ

| パーツ・成果物 | 現在の状態 | 未完成とする理由 | 完成に必要な作業 |
|---|---|---|---|
| elbow to wrist（XL430） | `outputs/parts/` と `outputs/print/` に旧STLが残る場合がある | 元STEPの凸状外形をホーン穴として誤解した形状で、体積も元形状から大きく乖離している。通常のXL430出力は現在ブロック済み | 元STEPの外形を保持した再構成、変更範囲の限定、形状・インターフェース検証、print-readinessの再実行 |
| elbow to wrist（明示的prototype出力） | `*_prototype.step` / `*_prototype.stl` を明示指定時のみ生成可能 | 調査・比較用であり、印刷承認品ではない。コマンドも失敗終了して誤採用を防ぐ | 上記の正式な形状修正後、通常名での生成を再開する |
| gripper moving part（正規XL430 STL） | `skills/cad-reverse-parametric/outputs/parts/gripper_moving_part_xl430.stl` | watertightおよびvolume判定に失敗し、異常edgeが残る | 正規モデル自体をmanifold化するか、印刷用途では上表の`*_print.stl`を正式採用する方針を決める |
| XL430 motor mount単体 | `mount_XL430_W250_T.*` などの生成物がある | 現行のprint-readiness対象と印刷パッケージに含まれず、印刷用成果物としての検証記録がない | メッシュ検査、取付穴、ねじ頭・ナット逃げ、サーボ外形との干渉を検証して印刷候補へ追加する |
| XL430アーム全体の組立成果物 | 6台をXL430形状へ置換した診断用静止STEPあり | 217要素の再読込には成功したが、置換後に54件、最大約9,608.8 mm³の外部部品間体積干渉がある。穴軸と連続経路も未検証 | ブラケット・リンク・グリッパーの取付基準を再設計し、置換後の穴軸、静止干渉0件、連続掃引干渉を検証する |

## 取扱上の注意

- `elbow_to_wrist_xl430.stl` は、ファイルが存在しても印刷しません。最新のレビューでは未完成です。
- `gripper_moving_part` は、現時点では末尾が `_print.stl` の修復版だけを印刷候補とします。
- `elbow_to_wrist_extension_xl430.stl` は印刷可能ですが、XL430対応形状が完成したという意味ではなく、現状の元形状維持版です。
- 物理印刷の実施結果は [3d_print_checklist.md](3d_print_checklist.md) に記録します。チェックリストの完了は、CAD設計や実機適合の完了とは別に扱います。
