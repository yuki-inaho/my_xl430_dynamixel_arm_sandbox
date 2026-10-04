# グリッパ軟質部材 — GLBに基づく再推定版

前回の写真のみの近似モデルを置き換える版です。提供GLBをCAD尺度で校正し、左右非対称の指サック・黒いゴム・輪ゴムを6部品に分けました。

## すぐ開くファイル

| 用途 | ファイル |
|---|---|
| 追加部材だけのSTEP | `models/soft_addons_scanfit.step` |
| 追加部材だけのGLB | `models/soft_addons_scanfit.glb` |
| 実スキャン＋近似形状を重ねたGLB | `models/scan_with_fitted_addons.glb` |
| 元写真との比較 | `results/photo_comparison.png` |
| 元写真への原寸重畳 | `results/photo_overlay.png` |
| スキャンへの斜視重畳 | `results/scan_overlay_oblique.png` |
| 寸法・尺度・残差・注意点 | `results/report_ja.md` |
| 作業レビュー | `docs/review.md` |

STEP/STLはmm・Z上向き、GLBはm・Y上向きです。座標変換は `GLB=(CAD_x,CAD_z,-CAD_y)/1000`。左右は提供写真基準です。指サックは肉厚不明のため**中実の外形占有モデル**です。内部構造や表面の粒状突起、弾性は再現していません。`with_reference_frame` は固定枠を加えた参考版であり、全可動機構の完成CADではありません。

## 再現

Python3.13の実使用依存バージョンを `pyproject.toml` に記載しています。既設環境での動作と別ディレクトリ再実行を検査しました。空の環境での依存取得は未検証です。

1. 依存取得: `uv sync`
2. 入力から再実行: `uv run python src/run_all.py`
3. 出力検査: `uv run pytest -q`

日本語注釈画像の生成にはNoto Sans CJKフォントが必要です。フォントは同梱していません。途中再開例: `uv run python src/run_all.py --start-at build_models`。

入力GLB・写真・尺度用STEPを収録しています。大きな描画用中間配列は配布物から除外しましたが、ソースから再生成されます。`results/model_meshes.npz` と選択頂点IDは含めています。スキャンのみの重複GLBは省略し、スキャン＋近似形状の比較GLBを収録しています。比較GLBでは各ノードの表示を切り替えられます。

入力の同一性は `results/input_manifest.json`、配布ファイルの同一性は `MANIFEST.sha256`、再実行の比較結果は `results/reproducibility.json` で確認できます。
