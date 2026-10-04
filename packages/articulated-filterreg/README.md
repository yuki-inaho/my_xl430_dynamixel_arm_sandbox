# 裸XL430アームの尺度付き関節位置合わせ

**主結果は画像整合基準を満たしていますが、DoD全完了ではありません。nanobindのビルド・読込み確認が未達です。** 実計算は同じC++数値核を明示C ABI経由で呼び出したものです。`AF_BINDING=ctypes`を指定しない場合、nanobindが無くても黙って切り替えることはありません。

最初に `results/comparison.png`、`results/overlay.png`、`results/report_ja.md` をご確認ください。主結果は `results/best.json` と `results/transforms.json` です。注釈改訂前の結果は `results/archive_annotation_v1/` に分離しています。

## 実施範囲
R3 STEPから5モーター・5プリント部品を抽出し、4つの可観測関節、全体姿勢、一様尺度を推定しました。D405・爪・6個目のモーターは含めません。J5は今回のモデルと画像では観測できないためnullです。関節値はR3 CAD参照姿勢からの角度であり、実機エンコーダ値や指令値ではありません。

原論文の固定観測Gaussian E段階と、リンク内twist正規方程式を関節空間に写像するM段階を実装しました。尺度列と、手動の訓練特徴点5点・輪郭補助を追加しています。画像補助を外した自由尺度の別試験では縮退が生じたため、主結果を「無補助の純粋なFilterRegが成功した」とは解釈できません。

## 標準のnanobind構成（この環境では未検証）
通信と依存を利用できる環境で、作業ルートから実行します。

```sh
uv sync --group dev
uv run python -m pytest tests -q
uv run articulated-filterreg fit --root . --starts 32 --seed 20261004
uv run articulated-filterreg render --root .
```

`pyproject.toml`、CMake、`cpp/bindings.cpp` がnanobindの構成です。nanobind==2.12.0を指定しています。今回 `No module named nanobind` で構成が失敗し、fresh uv lockも依存キャッシュ不足で失敗しました。成功したlockファイルを装ったものは添付していません。上記4コマンドが成功したとは主張していません。

## 実際に動作を確認したC ABI構成
CMake・Ninja・C++17コンパイラ・uvと、`requirements-tested.txt`に記録した数値依存のあるPythonを用います。元環境ではPython 3.13.5、GCC 14.2、uv 0.10.0でした。

```sh
AF_PYTHON=/path/to/python scripts/run_capi.sh test
AF_PYTHON=/path/to/python scripts/run_capi.sh fit --starts 32 --seed 20261004 --iterations 14
AF_PYTHON=/path/to/python scripts/run_capi.sh render
```

`/path/to/python`は数値依存を導入したPythonに置換します。会話内の実行では `/opt/pyvenv/bin/python` を使用しました。C ABIの数値核はその場でコンパイルするため、特定glibc用の既成バイナリを互換品と誤認して使う必要はありません。新規環境に依存を入れる場合は、利用可能な環境で `uv pip install --python /path/to/python -r requirements-tested.txt` を実行します。この依存導入自体は今回の通信制限下では再検証できていません。

再開は `--resume` を追加します。seed、設定、注釈・モデルのSHA256が一致しない再開は拒否します。出力は `results/` に書き込むため、既存結果を残す場合はルートをコピーしてから実行してください。

## 主要ファイル
- `src/articulated_filterreg/`：状態・FK、観測、最適化進行、評価、描画、入出力。
- `cpp/`：Gaussianモーメント、リンク別正規方程式、nanobindと明示C ABIの別境界。
- `model/`：元R3 STEP、出所、派生URDF/STL、観測配列。コア再実行はCadQueryを要しません。
- `annotations/`：手動領域と訓練/未使用検証点。SAM/BiRefNet推論ではありません。
- `results/trials/`：32初期値の初期/最終/全反復。`all_trials.csv`は一覧です。
- `tests/`、`logs/`、`temp/`：テスト、実行証跡、作業書とレビュー。

原資料からCADを再抽出する場合のみCadQuery/OCPが必要です。`python scripts/build_model.py --source /path/to/3d-printed-dynamixel-gripper-main` を使用します。元STEP内の参照姿勢に回転を二重適用しません。旧URDFは比較資料として残し、R3の寸法と混用していません。

## 座標と評価の注意
写真は652×367、主試行の画角は51°×30°です。`s`は「CAD 1mあたりの単眼深度単位」で、カメラ並進のm換算は `translation_depth_units / s` です。PLYの `*_camera` は画像系x右/y下/z前、`*_opengl` とglbは元MoGE書出しと同じx右/y上/z後です。各形式の単位は任意深度単位です。

IoUは手動領域と予測可視面の一致で、実世界精度ではありません。布・テープのみ外部遮蔽として扱います。`raw_geometry_overlay.png`はその遮蔽も除いた実CAD全体の重畳です。5訓練点と14未使用検証点は同一画像からの注釈であり、別の実測データセットではありません。3Dの90%残差だけでなく未除外残差も `metrics.json` に残しています。

`docs/final_review.md` と `temp/workdoc_Oct04-2026_articulated_filterreg.md` に、未達DoD・修正履歴・再実行証跡を記載しています。出所条件は `THIRD_PARTY_NOTICES.md` を参照してください。実機通信・駆動は実施していません。
