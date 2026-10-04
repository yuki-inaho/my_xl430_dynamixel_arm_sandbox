"""Write the Japanese evidence report from the actual recorded numerical outputs."""
from pathlib import Path
from datetime import datetime, timezone
import json

ROOT = Path(__file__).resolve().parents[1]


def read(name):
    return json.loads((ROOT / 'results' / name).read_text())


def main():
    params = read('parameters.json')['components']
    calibration = read('calibration.json')
    camera = read('photo_camera.json')
    residuals = read('surface_residuals.json')['components']
    checks = read('validation.json')
    coin = read('coin_check.json')
    names = {'cot_L': '指サック・写真左', 'cot_R': '指サック・写真右',
             'foam_L': '黒いゴム・写真左', 'foam_R': '黒いゴム・写真右',
             'band_L': '輪ゴム・写真左', 'band_R': '輪ゴム・写真右'}
    dimensions = []
    distances = []
    for key, label in names.items():
        a, b, c = params[key]['export_bbox_mm']['size']
        dimensions.append(f'| {label} | {a:.1f} | {b:.1f} | {c:.1f} |')
        m = residuals[key]
        distances.append(f"| {label} | {m['evaluation_points']} | {m['distance_median_mm']:.3f} | {m['distance_p95_mm']:.3f} | {m['distance_max_mm']:.3f} |")
    note = f'''# GLBスキャンによる左右軟質指先の再推定・結果報告

作成日: 2026年10月4日。対象: 今回提供されたグリッパ写真とScaniverse GLB。

## 1. 結論と今回の修正

提供GLBの三角形・テクスチャを実際に読み込み、既存フレームCADを尺度基準にして、指サック・黒いゴム・輪ゴムを左右別の6ソリッドとして再構成しました。前回の写真のみから置いたモデルは寸法と配置が未検証だったため、今回のモデルで置き換えてください。とくに前回の指サック基部径約11mm台という設定は引き継いでいません。

出力は観察された形状に合わせた**外形占有モデル**です。指サックも中実に近似しており、肉厚、中空部、内部コア、弾性、圧縮時の変形は測定していません。小さな白い突起は元の樹脂部材として扱い、新規接触パッドとして重複追加していません。

## 2. 入力と尺度基準

入力GLBは83,525頂点・147,506三角形、8192×4096のテクスチャを持つメッシュです。入力写真は2048×1536画素です。入力そのものとSHA-256は `inputs/` および `results/input_manifest.json` に収録しています。

尺度は元CAD `PG3_C92_J28/CAD/parts/01_frame.step` と `02_cap.step` を参照しました。フレーム幅92mm、四隅のねじ中心の間隔75×49mmを基準に、俯瞰スキャン上で4点を選択し、相似変換を求めました。Z方向の基準は上部キャップ面の中央値27.1mmとしています。ねじ頭の高さだけには依存していません。

* 元GLBの1座標単位 = **{calibration['scale_mm_per_source_unit']:.6f} mm**。
* 元の座標単位をmとみなした場合の補正倍率 = **{calibration['scale_relative_to_meters']:.8f}**（約1.06%縮小）。
* 基準に使用した4ねじのXY残差RMS = **{calibration['datum_xy_rms_mm']:.3f} mm**。
* Z基準面426点の10/50/90百分位 = 26.773 / 27.100 / 27.528mm。

4ねじ残差は**校正に用いた点の整合度**であり、独立した実寸精度ではありません。キャップ面でZを合わせた後、スキャンのねじ頭は仮定したCADねじ頭高さより約0.70〜0.77mm低く残ります。これを隠して3D残差0.12mmと称していません。手動中心選択、プリント寸法、スキャンの平滑化・ひずみの影響が残ります。

### 100円硬貨による補助確認

硬貨は尺度の最適化には使っていません。CAD尺度補正後の俯瞰テクスチャに円を当てた参考確認では、採用した明度しきい値130で直径 **{coin['measured_diameter_mm']:.3f} mm**、公称22.6mmに対して **{coin['diameter_difference_mm']:.3f} mm** でした。しきい値110〜150では20.476〜22.440mmに変わります。テクスチャの輪郭と影の選び方に感度があるため、硬貨だけを根拠に尺度を追い込んでいません。この幅は信頼区間ではありません。

公称寸法の参照先: 造幣局「貨幣に関するよくある質問」 https://www.mint.go.jp/faq-list/faq_coin 。画像上の単一の画素/mm倍率を高さの異なる指先にそのまま適用する方法は採用していません。

## 3. 分割・近似形状

分割はスキャンの空間範囲、頂点に移したテクスチャ色、および手動確認によるものです。今回SAM、EdgeTAM、BiRefNetの推論は実行していません。全自動の汎用認識器ではなく、この入力用に確認した領域を再現できる構成です。

指サックは、傾けた楕円断面のテーパ部分と滑らかな楕円体の上半分を組み合わせています。左右独立に各12初期値の頑健最小二乗を実行しました。黒いゴムはスキャン断面の分位点を基にした段付き・面取りした丸角柱と楕円断面の上部で近似し、手動で面や切欠きを調整しました。輪ゴムは傾斜した楕円帯です。輪ゴムの半径方向の厚さ1.2mmは**可視化用の仮定値**であり、材質の実測厚さではありません。

左右は提供写真の左／右を意味します。機構側のメーカー定義のL/Rではありません。左右の大きさ、断面比、傾き、中心位置を同一に固定していません。

## 4. 出力外形寸法

以下は輸出したSTEPを囲む、CADのX/Y/Z軸に平行な外接箱の寸法です。楕円断面の主軸径や材料厚さとは異なります。単位mm。Xは左右、Yは奥行、Zは上向きです。

| 部材 | X幅 | Y奥行 | Z高さ |
|---|---:|---:|---:|
{chr(10).join(dimensions)}

「指サック＋黒いゴム」の高さは各部の高さを単純加算した値ではありません。接合部にはわずかな重なりがあります。内部界面の適合や異材接触を保証するモデルではありません。

## 5. スキャンに対する表面残差

注釈したスキャン頂点を約1mm格子で間引き、出力三角形への最短ユークリッド距離をVTKで求めました。暗黙関数の近似残差ではなく、出力メッシュ表面への距離です。**当てはめ領域の片方向残差であり、未使用点による精度検証でも、実物の計測誤差や信頼区間でもありません。** 見えていない面は評価できません。モデルからスキャンへの逆方向の距離を含む完全な対称評価ではありません。

| 部材 | 評価点数 | 中央値 mm | 95百分位 mm | 最大 mm |
|---|---:|---:|---:|---:|
{chr(10).join(distances)}

指サックの細かな粒状突起や裾の薄い縁は平滑なモデルに含めていません。右の黒いゴムには最大約4.38mmのずれが残ります。表面の手切り凹凸を再現することより、少数の単純形状で扱いやすい形にすることを優先した部分です。形状のずれをマスクで隠していません。

## 6. 写真へのカメラ合わせと重畳

提供GLBと提供写真は別撮影です。スキャン中のねじ、白い印、指サックの縁など10点を写真の10点と手動対応させ、焦点距離とカメラの位置・姿勢を推定しました。主点は画像中心に固定し、レンズ歪みゼロを仮定しています。以前のロボットアーム画像の水平51°・垂直30°は今回の写真に流用していません。

1408×1056画素での推定焦点距離は{camera['focal_px']:.3f}画素です。校正点の再投影誤差は中央値{camera['median_error_px']:.3f}画素、RMS {camera['rms_error_px']:.3f}画素、最大{max(camera['residual_pixels']):.3f}画素でした。10点とも校正に使用しています。これを独立検証誤差と呼んでいません。元の2048×1536画素換算では中央値{camera['median_error_px']*2048/1408:.3f}画素、RMS {camera['rms_error_px']*2048/1408:.3f}画素です。

重畳画像は出力した3Dモデルの三角形を透視投影し、深度バッファと透視補正付き補間で実際に描画しています。生成画像ではありません。写真の輪郭に合うように2D変形したり、分割マスクでモデルのはみ出しを削ったりしていません。重畳ではモデル同士の遮蔽を考慮しますが、写真中の任意の前景物による隠れを推定して除去してはいません。

* `photo_overlay.png`: 2048×1536の原寸重畳、凡例なし。
* `photo_overlay_labeled.png`: 原寸重畳、下部に凡例。
* `photo_overlay_preview.png`: 1408×1056の表示用。
* `photo_comparison.png`: 同一切出しで元写真と重畳を比較。
* `scan_overlay_front/top/oblique/side.png`: スキャンの4方向への重畳。
* `annotations/photo_scan_check.png`: CADではなくスキャン自体を写真へ投影した補助確認。

水色=指サック、橙=黒いゴム、紫=輪ゴム。色は識別用で実材質を表しません。

## 7. モデル形式と座標変換

`models/soft_addons_scanfit.step` は新規部材だけの6ソリッドです。左右を分離したSTEPと、部材ごとのSTEP/STLもあります。`soft_addons_scanfit.glb` は同じ部材の閲覧用メッシュです。

`models/scan_with_fitted_addons.glb` は**実際のテクスチャ付きスキャンと、独立選択可能な6追加部材**を重ねた比較シーンです。スキャンの背景机を大幅に切り落としています。`soft_addons_with_reference_frame.step/.glb` は固定フレームと2枚のキャップを参考追加したものです。可動機構全部を再構成した「完成グリッパCAD」ではありません。

STEPとSTLはmm、元C92構築座標系のZ上向きです。STL自体には単位欄がないため、読込み側でもmmを指定してください。GLBはm、Y上向きとし、変換は次のとおりです。

`GLB = (CAD_x, CAD_z, -CAD_y) / 1000`

`CAD_mm = (GLB_x, -GLB_z, GLB_y) * 1000`

CAD原点は机面やグリッパ底面ではありません。元の構築座標系を保持しており、キャップ上面のZ=27.1mmです。スキャン元座標→CADの一様尺度・回転・並進は `results/calibration.json`、CAD→写真カメラは `results/photo_camera.json` に保存しました。

## 8. 出力検査と再現性

6部品それぞれのSTEP再読込みで形状有効、ソリッド数1、正体積を確認しました。6メッシュも全て閉じています。GLB再読込み後、m・Y上向きからmm・Z上向きへ戻した外接箱の最大差は{checks['glb_roundtrip_bounds_max_error_mm']:.8f}mmです。これはファイル形式の往復検査であって、物理寸法の精度ではありません。

STEPと三角形化メッシュの体積差は最大{100*checks['max_mesh_vs_step_volume_relative_error']:.3f}%でした。閾値2.5%の範囲内です。滑らかなSTEPと有限分割のメッシュは完全に同一ではありません。

出力に対する事後回帰テスト `tests/test_exports.py` は19件です。実行ログは `results/pytest.log` に保存しています。これはテスト先行開発を後付けで称したものではありません。別ディレクトリ再実行の成否・数値比較は `results/reproducibility.json`、ステージごとの開始・終了と終了コードは `results/reproduction_execution_journal.jsonl` を参照してください。

## 9. 再実行と依存環境

この配布物は提供入力向けの再現手順です。別のスキャンへ無変更で対応する汎用復元ソフトではありません。手動対応点・分割範囲はソースとJSON、選択頂点は `annotations/selected_vertex_ids.npz` に残しています。

既存環境では `uv run --no-project --python /opt/pyvenv/bin/python src/run_all.py` で実行しました。処理対象のルートはソースの相対位置から解決するため、作業パスを変えて再実行できます。途中から再開する場合は `--start-at build_models` などを指定できます。各段階のログは `results/rerun_*.log` に出力します。

新規環境向けには、Python3.13用の実使用バージョンを `pyproject.toml` に固定しています。フォルダ内で `uv sync`、続いて `uv run python src/run_all.py`、`uv run pytest -q` の順です。ただし、今回検査したのは既設環境での実行と再実行であり、**空の環境からの依存ダウンロードは未検証**です。日本語凡例の描画にはNoto Sans CJKが必要で、標準参照先は `/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc` です。フォントファイルは配布物に含めません。

## 10. 残る限界

外形の近似モデルであり、製造用の型、精密寸法検査、材料定数、把持力の評価にはなりません。柔らかい部材の撮影間の変形、透明部のスキャン誤差、輪郭の粗さが残ります。左右を対称化していない一方、細かな破れ、粒状突起、輪ゴムの重なりや裏側の回り込みは簡略化しています。参考フレーム以外の全可動部CADの姿勢同定は今回の完了条件に含めていません。
'''
    (ROOT / 'results/report_ja.md').write_text(note)
    readme = '''# グリッパ軟質部材 — GLBに基づく再推定版

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
'''
    (ROOT / 'README.md').write_text(readme)
    provenance = '''# 参照CADの出所

元添付: `3d-printed-dynamixel-gripper-main.zip`

取り出したファイル:
- `3d-printed-dynamixel-gripper-main/references/pg3-c9/PG3_C92_J28/CAD/parts/01_frame.step`
- `3d-printed-dynamixel-gripper-main/references/pg3-c9/PG3_C92_J28/CAD/parts/02_cap.step`

B-rep形状はそのまま使用しました。前側キャップは後側キャップをZ軸まわりに180度回転して参照表示しています。これらは固定枠の基準用で、可動部全体の完全モデルを意味しません。入力ハッシュは `results/input_manifest.json` を参照してください。
'''
    (ROOT / 'inputs/reference_cad/PROVENANCE.md').write_text(provenance)
    print('Japanese report, README and CAD provenance written.')


if __name__ == '__main__':
    main()
