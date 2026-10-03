# 低配置D405の取り込みレビュー・OCCT 8再実行

2026-09-26。入力はユーザー提供ZIPと、その後続の `gripper-d405-improved-20260926.tar.zst`。
既存mainの `19a9e7e` に対して、研究候補・検証器・記録を取り込んだ。
今回の集約結果は [verification.json](../studies/low-profile-20260926/integration/verification.json)。
元の `references/`、R5設計コード、CAD/STL/URDFのバイト列は保持した。

## レビューの結論

取り込み対象は **俯角30°・左右爪20 mm延長のV2候補**。
以前の75°研究案と比べ、カメラ群の高さは12.40 mm低くなる。
保存された比較では、250 g対象・カメラ・爪変更分の手首モーメントは9.45%増える。
これは変わらない腕全体の重量を含めない部分比較で、許容荷重の認定ではない。

|指摘|取り込み時の処理|
|---|---|
|旧作業場所への絶対パスと、分割された研究間の参照が残っていた|個人パスを除去。CAD試験で使うrepo・前研究の参照はファイル位置から解決するよう修正|
|ブラウザ画像にアカウント表示が含まれる|元画像、それを埋め込むHTML/PDF、旧ZIPをGit対象外にした。ローカル原本を保持|
|爪保存検査が同一オブジェクトの自己演算だけを制御にしていた|独立した幾何コピーで双方向の差分と共通体積を検査。空COMMONを返す故障負例を追加|
|元アーカイブのmanifestは取り込み後のテキストに一致しない|原本用manifestを歴史証跡として保持し、取り込み後専用manifestを別途作成|
|改善版ではPixi/OCCT 8の再変換が未実施だった|固定commit・lockから環境を新設し、wheelビルド・インストール・新規変換・照合を実行|

## 今回新しく実行した検証

- 変換器commit `1b2cea31c56b875bf98c1d65084781322f5fc835` を取得し、`pixi install --locked` を実行。
- Python 3.12.14 / pythonocc-core 8.0.1 / OCCT 8.0.1。ロードされたkernelも8.0.1と確認。
- wheelを再ビルドし、そのwheelを隔離環境へインストール。`python -I` でsite-packagesから実行。
- V2 STEPから16リンク・15関節・12メッシュ・262 occurrenceを新規生成。
- 新規URDF・config・12 STLは、保存された最終V2とSHA-256が全件一致。
- 変換器13試験、改善検証器52試験、元CAD18試験を再実行。保存検査補強後のCAD試験は20件。
  18件と20件は同じ試験群の前後であり、合算しない。
- STEPを別のCadQuery/OCP環境でも11姿勢×262 occurrence再読込し、新規変換モデルとFK照合。
  441閉路状態の最大残差は3.46945e-17 m、11姿勢の最大差は8.78488e-9 m / 5.33710e-8 rad。
- リポジトリ全体の回帰、23姿勢の全干渉再計算、全候補の探索は今回の実行対象に含めていない。
- `ruff check .` はPASS。取り込みコードの整形もPASS。全体のformat確認では既存の未変更19ファイルが不一致であり、
  今回の取り込みとは別の残件として [quality.json](../studies/low-profile-20260926/integration/quality.json) に記録した。

上記の小さい残差は数値的な一致を示す。実物精度を示す値ではない。
詳細ログは `studies/low-profile-20260926/integration/` に個人パスを除いて保存する。

## D6・D7の扱い

**D7の再ビルド・再変換は今回実行済み**。OCCT自体のソースビルドではなく、lockで指定された
配布バイナリを用いた変換器wheelのビルドと実行である。

**D6は保存されたUI・API使用記録の監査**を維持する。原本の1599ファイルをmanifestと照合し、
35 UIログ・保存画像・API記録を確認した。今回のOnshape UI操作と直接API呼出しは0件。
現在のアカウント残量、ライブカウンタ、現行UIを新しく確認したことにはしない。

## 未解消の設計条件

- 既存の8接触・小隙間FAILを維持。今回「全干渉なし」へ書き換えていない。
- 完成状態では台座4本の工具アクセスFAIL。台座→カメラ付きcarrierの組立順が必要。
- 848×480の保存診断は通るが、720pの100 mm距離基準はFAIL。
- 爪延長により手首の保存サンプル範囲は物理角−124〜+102°に狭まる。
- 材料・造形方向・締結保持・公差・配線・連続トルク・疲労/クリープ・実カメラ校正は未確認。

製作承認は `false`。印刷、実機変更、通電、Onshape更新、commit/pushは今回行っていない。

## ファイルとプライバシー

- 研究入口: [低配置案](../studies/low-profile-20260926/README.md)、[比較元の75°案](../studies/onshape-20260926/README.md)。
- 全腕STEP: [final-version.step](../studies/low-profile-20260926/outputs/low-profile-250g/CAD/final-version.step)。
- 単品: 同じCADディレクトリの `CAM5_BASE`、`CAM5_D405_CARRIER`、`PG3_finger_L`、`PG3_finger_R` のSTEP/STL。
- 運動学モデル: [robot.urdf](../studies/low-profile-20260926/outputs/low-profile-250g/robot/model/robot.urdf)。
- 原本アーカイブの展開先と生ログはGit対象外の `temp/intake_d405_20260926/`。

受入テキストは個人パス・アカウント表示を除去した写し。古いXML・JSONのSHAは原本用であり、
原本の主張や失敗履歴を改めて実測した値に置き換えていない。
HTML/PDF/ブラウザ画像へのリンクはローカルでは利用可能だが、それらはGit配布には含まれない。
共有可能な手順はMarkdown、CADレンダー、コード、数値証跡を参照する。
古いUI更新・梱包スクリプトは履歴として取り込み、公開Onshape版へ再実行していない。

```bash
rtk proxy python scripts/verify_d405_intake.py
rtk proxy uv run --no-sync pytest -q studies/low-profile-20260926/outputs/low-profile-250g/robot
rtk proxy uv run --no-sync pytest -q studies/low-profile-20260926/work/low-profile/test_design.py studies/low-profile-20260926/work/low-profile/test_validation.py
```

取り込み後専用manifestはファイル同一性の検査であり、製作安全性の保証ではない。
今回の再ビルド手順は [integration/README.md](../studies/low-profile-20260926/integration/README.md) に記録する。
