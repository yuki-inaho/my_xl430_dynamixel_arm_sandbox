# フォロワーアーム幾何改訂 2026-09-19

## 位置づけ

他エージェントが作成した`follower_cad_revision_20260919.zip`と`CAD_review_ja.html`を確認し、リポジトリ内で再生成できるstudyとして反映した。

この改訂は全関節XL430化ではない。元のXL430 2台とXL330系4台の混在構成を維持し、保存した基準姿勢に対して局所的な形状変更と干渉修正を行う。

元の`hardware/follower/step/arm.step`と`elbow_to_wrist_extension.step`は変更していない。入力SHA-256は`skills/cad-reverse-parametric/studies/follower_geometry_revision/source/input_sha256.json`で固定している。

## 変更部品

| 部品 | 変更内容 | 検証上の注意 |
|---|---|---|
| `elbow_to_wrist_extension_round` | 4穴の左右の耳だけを丸みのある輪郭で補強 | 8か所の皿穴外周余肉2.5 mm以上。外接Y寸法は約93.076 mmへ増加 |
| `base_idler_clearance` | 台座のアイドラ・キャップ周辺に局所逃げを追加 | 台座外形・4穴軸は維持。除去体積は約1,039 mm3 |
| `elbow_to_wrist_standoff` | 4本の一体スペーサーを追加 | 外径5.3 mm、穴径2.3 mm、高さ3.25 mm、壁厚1.5 mm |

そのほかの4部品は、元組立から抽出した形状を維持している。可動爪のSTLだけは、STEPを変更せず、既知の三角形分割欠落に対して0.00001 mmの一時的な円錐リリーフを適用して閉じたメッシュにした。

## 検証結果

生成コマンド:

```bash
cd skills/cad-reverse-parametric/studies/follower_geometry_revision
rtk uv run python source/rebuild.py --render
rtk env CAD_RELEASE_DIR=../../outputs/follower_geometry_revision \
  uv run python -m pytest -q source/test_revision.py
rtk uv run python source/make_report.py
rtk uv run python prepare_print_package.py
```

結果:

| 項目 | 結果 |
|---|---|
| 保存後STEPのソリッド数 | 117。再読込後も117、末端要素161 |
| 7部品のSTEP/STL | 単一ソリッド・閉じたSTL・正体積 |
| 取付穴パターン | 5組、投影軸中心誤差1e-5 mm未満 |
| 部品間干渉 | 元の物理干渉5件を解消し、改訂後0件 |
| 回帰テスト | 46 passed |
| OrcaSlicer | 2プレート、警告なし、各G-code検証`passed: true` |

生成物は次の場所にある。CADレビューHTMLは画像を内包した`CAD_review_ja.html`として生成される。

```text
skills/cad-reverse-parametric/outputs/follower_geometry_revision/
skills/cad-reverse-parametric/outputs/follower_print_package/
```

## 未確認事項

この結果はCAD基準姿勢とスライサー出力の確認であり、次を承認しない。

- 全角度・連続運動中の干渉
- ねじ長さ、ねじかかり、締結力
- 印刷公差と実機部品の嵌合
- 強度、疲労、保持トルク、発熱
- 実物の印刷、組立、運転
- 全関節XL430化

`elbow_to_wrist_xl430`は2026-09-18の設計レビューで未承認のままであり、この改訂パッケージにも含めていない。
