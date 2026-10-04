# P05コネクタ通過窓の局所改善候補

2026-10-03。ユーザーの「コネクタ付きでも通せる寸法」という条件に合わせ、
凍結Onshape V2のP05左右窓を **5.5×10.2 mm、四隅R0.5 mm** に変更した。
Chili3Dで確認したコピーを保存し、元V2、他261部品、モーターケースは保持した。
実物組付けと製作は未承認。**コネクタの窓通過はモーター取り付け前の診断であり、
取り付け後にコネクタを直線で抜き差しできる判定ではない。**

## 成果物

- [統合STEP](../../../../../../3d-printed-dynamixel-gripper/studies/p05-cable-20261003/CAD/V2_P05_CABLE_CLEARANCE_CANDIDATE.step)
- [P05単体STEP](../../../../../../3d-printed-dynamixel-gripper/studies/p05-cable-20261003/CAD/P05_CABLE_CLEARANCE_CANDIDATE.step) / [STL](../../../../../../3d-printed-dynamixel-gripper/studies/p05-cable-20261003/CAD/P05_CABLE_CLEARANCE_CANDIDATE.stl)
- [P05単体の窓](images/view-support.png)、[右側とモーター](images/view-motor-right.png)、[左側とモーター](images/view-motor-left.png)、[支持の斜視](images/view-oblique.png)
- [CAD検査結果](evidence/review.json)、[静的接触走査](evidence/contacts.json)、[装着後コネクタ通過の診断](evidence/plug-with-motor-diagnostic.json)
- [全262部品の保持照合](evidence/unchanged-occurrences.json)、[Chili3D読込・入力SHA](evidence/browser-p05-cable-check-20261003.json)
- [保存後のSHA・文書リンク・ブラウザ検査](evidence/final-verification.json)
- [グリッパ組立マニュアル](../../docs/gripper-assembly-20261003/MANUAL.md) / [PDF](../../docs/gripper-assembly-20261003/MANUAL.pdf)
- [設計判断・検証記録](WORKLOG.md)、[保存ファイルのSHA](MANIFEST.json)

## 寸法と変更範囲

単位mm。窓中心は元V2 world座標Y=151.15、Z=178.7。
左右の既存側壁を貫通し、側壁厚4 mm、内側面X=-14.45/+14.05は移動しない。

| 項目 | 元V2 | 改善候補 |
|---|---:|---:|
| 配線窓の幅Y×高さZ | 3×8 | 5.5×10.2、角R0.5 |
| 仮線φ1.9からP05までの最小距離 | 0.55 | 1.65 |
| 仮線から後カバーまでの最小距離 | 0.25 | 0.25 |
| EHR-3公称筐体の窓通過（モーターなし） | 干渉56.126 mm³/側 | 最小距離0.35 |
| ケースを挟む内側面間隔 | 28.5 | 28.5 |
| 実ケースとの接触面積（各側） | 942.005 mm² | 同じ材料セット、lost/added=0 |
| 元の円筒穴面 | 18 | 18、位置・径・範囲を保持 |
| 窓mask外／保護領域の材料損失 | — | 0 / 0 mm³ |
| 局所除去体積 | — | 270.535 mm³ |

検査に用いたEHR-3筐体断面は9.5×3.8 mm、通過向きは9.5をZ、3.8をYに合わせる。
高さ6.5と別の0.6突出を含む保守的な軸方向包絡を使った。
実ケーブルのロック部・被覆・曲げ制限・造形公差は未確認であり、この公称値を実物保証にしない。
配線診断はPCBから内部で90度曲げ、側方へ直線で出す仮経路である。
PCBヘッダーの軸方向に後カバーを貫く経路は採用していない。

## 組付けの条件と残る問題

モーターが入る前にコネクタをP05窓へ通すことを候補の前提とする。
先配線したモーター全体の挿入軌跡は未検証なので、実行済みの組立手順として扱わない。
モーターを置いた状態でコネクタを側方へ直線移動すると、左右とも後カバーと約29.43 mm³干渉する。
このFAILは窓を広げた結果にも残る。カバーを削る／外したまま使う解決は行っていない。

P05・仮線・全保存相手を除外なしで走査した1848組は **1841 PASS / 1 ERROR / 6 UNKNOWN**。
ERRORは`088:ARM_M04_ref00`の供給B-repのBoolean自己対照不成立、UNKNOWNは仮線6本と
非solidの`152:ARM_M05_ref05`の重なり。これらを組付けPASSへ読み替えない。
装着後プラグ診断524組は **518 PASS / 2 FAIL / 2 ERROR / 2 UNKNOWN**。
FAILは`157:ARM_M05_ref06`後カバー、ERRORは`143:PG3_XL430_fixed`、UNKNOWNは同非solid参照。

接触面保持は締付け荷重・支持強度・印刷嵌合の合格ではない。
実ハーネス、曲げ、ストレインリリーフ、ねじと工具、先配線モーター挿入、全腕可動中の配線は未確認。
CADのM05ラベルと実機ID5の対応観測も未確定のまま。

## 入力と再現

入力は[凍結V2 STEP](../../../../../../3d-printed-dynamixel-gripper/studies/low-profile-20260926/outputs/low-profile-250g/CAD/final-version.step)。
SHA-256: `9f58c947753e9229b30939da23ce4c87c1cc85eeb39372518de4ffb98991b93f`。
[元Onshape V2](https://cad.onshape.com/documents/29e8557c76e89bcf64f50566/v/f6162b4adc88af9d07f1194a/e/d5415bf725ba822741b01703)を変更せず、
XCAFのP05だけをコピー上で置換した。Onshapeクラウド文書、URDF、G-codeは更新していない。
262 occurrenceの名前・階層・配置を保持し、他261部品の形状署名を照合した。
この署名検査を不良B-repの完全な材料集合同等性の証明にはしない。

```bash
rtk proxy uv run --no-sync python -m scripts.review_p05_cable_clearance --out outputs/p05-cable-next
rtk proxy uv run --no-sync pytest -q tests/test_p05_cable_relief.py tests/test_p05_cable_clearance.py
rtk proxy uv run --no-sync ruff check gripper_design/p05_cable_clearance.py scripts/review_p05_cable_clearance.py tests/test_p05_cable_clearance.py
```

変更対象の既存9＋新規14＝23試験PASS。全リポジトリのsuiteは未実行。
STEP再読込のP05材料対照、単体STLの閉じた1成分、実ケースのtrim済み面接触を検査した。
CAD依存版はreview.jsonと既存uv.lockに記録している。
公式経路は[ROBOTIS XL430組立説明](https://emanual.robotis.com/docs/en/dxl/x/xl430-w250/#idler-horn-assembly)、
公称コネクタ寸法は[JST EHデータシート](https://www.jst-mfg.com/product/pdf/eng/eEH.pdf)を参照した。
