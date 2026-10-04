# AprilTag A4グリッドシート生成と高精度認識

`arm-tag-sheet` は AprilTag 36h11 のA4グリッドシートPDFを実寸（mm単位のベクター）で生成し、
合成カメラ画像に対する検出精度をOpenCVで定量検証するためのコマンドです。

- 生成コード: `src/arm_observer/apriltag/`
- 既定シート: A4縦210×297 mm、3列×4行、タグ40 mm（黒枠外寸）、ギャップ10 mm、外周マージン12 mm
- 既定ID: Sheet 1 = ID 0–11、Sheet 2 = ID 12–23（36h11のコード表はID 0–23を固定収録）
- 用紙下部に100 mm参照バーと「PRINT AT 100% (ACTUAL SIZE)」表記を印刷

## 生成

```bash
rtk proxy uv run arm-tag-sheet generate --output-dir reports/tag-sheet-20261004
```

出力（`sheets.json` に各PDFのSHA256を記録）:

- `apriltag_36h11_a4_sheet_1_ids_000-011.pdf`
- `apriltag_36h11_a4_sheet_2_ids_012-023.pdf`
- `sheets.json`

オプション: `--columns` / `--rows` / `--tag-size-mm` / `--gap-mm` / `--margin-mm` /
`--sheet-count` / `--first-id`。ページに収まらない指定は `ValueError`（終了コード1）で拒否し、
自動縮小などの暗黙fallbackはしません。

## 印刷（実寸の担保）

1. プリンタ設定で「100%」または「実際のサイズ」を選び、「用紙に合わせる」などの自動拡大・縮小を**無効**にする。
2. 印刷後、シート下部の100 mm参照バーを定規で測る。
3. 100 mmから外れる場合はプリンタのスケーリング設定を修正して再印刷する。
4. タグサイズは白い余白ではなく黒枠の外寸（40 mm）である。

PDFはベクター図形なので、正しい倍率で印刷されれば解像度劣化はありません。
ヘッダ等の文字はASCII（Helvetica）のみで、CJKフォント埋め込みに依存しません。

## 認識（openCV・精度優先設定）

`src/arm_observer/apriltag/detector.py` の `build_detector()` は速度より精度を優先します。

- `cornerRefinementMethod = CORNER_REFINE_APRILTAG`（AprilTag専用コーナー再精細化）
- `cornerRefinementWinSize = 5` / `cornerRefinementMaxIterations = 50` /
  `cornerRefinementMinAccuracy = 0.01`
- `aprilTagQuadDecimate = 1.0`（間引きなし）/ `aprilTagQuadSigma = 0.0`（前段ぼかしなし）
- `polygonalApproxAccuracyRate = 0.01`、`minMarkerPerimeterRate = 0.01`、
  `adaptiveThreshWinSizeMin/Max/Step = 3/53/4`、`useAruco3Detection = False`

## 合成データでの定量検証

```bash
rtk proxy uv run arm-tag-sheet verify --sheet-index 1 --output-dir reports/tag-sheet-20261004/verify-sheet-1 --rms-limit 0.5
rtk proxy uv run arm-tag-sheet verify --sheet-index 2 --output-dir reports/tag-sheet-20261004/verify-sheet-2 --rms-limit 0.5
```

`src/arm_observer/apriltag/synthetic.py` がシート平面を透視変換し、ぼけ（σ0.8）と
ガウスノイズ（σ2.0）を加えた合成画像と正解コーナーを生成します。

- `synthetic_scene.png`: 合成入力画像（Sheet 1、既定）
- `synthetic_verify.json`: 期待ID・検出ID・ID別RMS・最大RMS・corner refine設定・合否
- ファイル名は共通なので、2枚を検証するときは上記のように別フォルダへ保存する。
- 終了コード: `0` 全ID検出かつ最大RMS ≤ `--rms-limit`、`2` 検証失敗、`1` 引数・I/Oエラー

主要オプション: `--sheet-index`（既定1）、`--px-per-mm`（既定6.0）、`--blur-sigma`、
`--noise-sigma`、`--seed`、`--rms-limit`、`--flat`（透視変換なし）。

## 実画像の検出

```bash
rtk proxy uv run arm-tag-sheet detect --image /path/to/photo.png --output-json /path/to/detections.json
```

グレースケール画像から36h11を検出し、IDと4コーナーを出力します。
コーナー順はタグの基準方向で左上・右上・右下・左下です。画像上での最小座標順ではありません。

## 制約

- 収録IDは0–23（`families.py`）。これより大きいIDを要求すると明示的に拒否する。
- ページサイズはA4固定（`SheetSpec.page` を変えれば他サイズも計算可能）。
- 検出辞書は `DICT_APRILTAG_36h11` 固定（他ファミリは未収録）。
- 実機カメラやプリンタの制御は行わない。合成画像とPDF生成のみ。
- 合成画像のRMSはこの人工条件での結果であり、実カメラの精度を示すものではない。
  印刷倍率は100 mmバーを実測し、実画像の精度は別途評価する。

## 出典と再現

コード表・ビット座標は[AprilRobotics公式tag36h11.c](https://github.com/AprilRobotics/apriltag/blob/b7c0ebe9aa20f82ec7a828579004f9e706bfecd9/tag36h11.c)の
commit `b7c0ebe9aa20f82ec7a828579004f9e706bfecd9` を固定参照しています。
ファイルSHA256: `38ff6e308067eb32ccf624e9cc5e7a75b45ad82b3cf9f80980cb86ebaa88512b`。
その著作権・配布条件は `families.py` に保持しています。実行時のネット取得は不要です。
認識設定は[OpenCV公式ArUcoドキュメント](https://docs.opencv.org/4.x/d5/dae/tutorial_aruco_detection.html)を参照。
依存版は `uv.lock` が正本で、`uv sync --locked` で再現できます。

レビュー済み成果物・元会話・検証結果は [日付別記録](../diary/2026-10-04/apriltag-review/REPORT.md)にあります。
