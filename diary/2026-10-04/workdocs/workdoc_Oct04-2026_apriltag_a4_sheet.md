# AprilTag 36h11 A4グリッドシートPDF生成とOpenCV高精度認識器の実装 作業計画書 兼 記録書

---

**日付：** `2026年10月04日`
**作業ディレクトリ・リポジトリ:** `/home/inaho-omen/Project/my_dynamixel_arm_sandbox`（git リポジトリ、distribution名 `my-dynamixel-arm-sandbox`、Pythonパッケージ `arm_observer`）
**作業者：** `実装担当エージェント（OpenCode / deepseek-v4.1-flash）`
**配置先の指示：** ユーザー指示により本作業書は `temp/` ではなく `diary/2026-10-04/workdocs/` に置く。これはリポジトリの日付別保存規約（`diary/<date>/workdocs/`）に一致する。

---

## 1. 作業目的

本日の作業は、以下の目標を達成するために実施します。

*   **目標1:** AprilTag 36h11 のA4グリッドシートPDFを2枚（Sheet 1: ID 0–11、Sheet 2: ID 12–23、各枚3列×4行・タグ40 mm）生成する、再利用性・可搬性の高いコードを `arm_observer` に統合する。
*   **目標2:** テスト用の人工データ（合成画像）を生成し、OpenCVベースで corner refine 等の高精度設定を有効にしたAprilTag認識器を実装して、認識精度を定量検証する。
*   **目標3:** 上記をuv環境で完結させ、TDD・品質ゲート・作業記録により第三者監査可能な証跡を残す。

### 1.1 ゴール要求分析

*   **ユーザーの直観的・直截的な目的:** ロボットアームのワークスペース作業で使える「実寸が正しいAprilTagマーカーA4シート」を手元で何度でも生成・印刷でき、さらにそのマーカーをOpenCVで高精度に認識できる状態にする。生成コードと認識コードは他プロジェクトへも持ち出せる形にする。
*   **明示要求:**
    1. `my_dynamixel_arm_sandbox` 以下にA4グリッドシートPDFを**2枚**生成するスクリプトを作る。
    2. self-consistent / self-contained / well-defined であること。
    3. ディレクトリ構造がわかりやすく、uv環境上で動作すること。
    4. 再利用性・可搬性があり、SOLID / KISS / DRY であること（本体 `arm_observer` に統合しつつ、独立して切り出せる構成）。
    5. テスト用の人工データを使った認識器（OpenCVベース）も作る。
    6. AprilTagの corner refine など、精度が良くなる設定を有効にする。
    7. 作業書を write / review スキルで作成・レビューし、start-work-with-docs スキルでDoDを満たすまで継続する。
*   **暗黙制約:**
    *   uv プロジェクト（`uv.lock` 管理）で完結し、コマンドは `rtk proxy` を前置する（`AGENTS.md`）。justfile は存在しないため（確認済み）、`just` は使わず `uv` を直接使う。Python は `requires-python = ">=3.11"` であり、必ず `uv run` 経由でプロジェクトの `.venv` を使う（システムPython 3.10のcv2は使わない）。
    *   ドメインデータは immutable な型付きレコード。辞書はJSON/TOML境界のみ（`AGENTS.md`）。
    *   TDD（Red→Green）と atomic なチェックリスト。暗黙のfallback禁止。
    *   品質ゲート: `uv run pytest` / `uv run ruff check src tests scripts` / `uv run ty check` / `uv run scripts/check_quality.py`（循環的複雑度上限10）。
    *   実機（DYNAMIXEL）へのアクセスは本作業では行わない。カメラ実機も使わない（合成画像のみ）。
    *   既存の未commit変更（`git status` の M 群）には触れない。新規ファイルの追加のみ行う。
*   **非ゴール:**
    *   実機カメラ画像の取得・キャリブレーション本体（eye-in-hand等）の実装。
    *   36h11 以外のファミリ（16h5/25h9）対応、587 ID全件の埋め込み（必要になった時のための拡張点は残す）。
    *   印刷プリンタの制御、PDFの自動ラスタライズ検証。
    *   GUI表示（headless環境前提。PNG書き出しのみ）。
    *   `git commit` / `git push`（ユーザーの明示指示があるまで実施しない。作業ツリーへの追加のみ）。
*   **成功条件（客観）:**
    1. `arm-tag-sheet generate` が A4（210×297 mm）のPDFを2ファイル出力し、各PDFのMediaBoxがA4で、タグ16進パターンがOpenCV辞書と一致する。
    2. `arm-tag-sheet verify` が合成画像に対して全12 IDを検出し、コーナーRMS誤差 ≤ 0.5 px をJSONで記録し終了コード0を返す。
    3. 追加テストを含む `uv run pytest` が全green、`ruff` / `ty` / `check_quality.py` が成功する。
    4. 生成物（PDF 2枚、合成画像PNG、検証JSON、マニフェスト）が `reports/` に残り、本作業記録から参照できる。
*   **リスクと前提:**
    *   公式 `tag36h11.c` のコード表とOpenCV `DICT_APRILTAG_36h11` は**180°回転**の関係で一致する（本作業書作成時にID 0–3で実測確認済み。全IDでテスト化する）。この対応を誤るとPDFも認識テストも崩れるため、最初にテストで固定する。
    *   `opencv-contrib-python-headless` と `reportlab` の導入にネットワークが必要。失敗時はブロッカーとして記録する（暗黙fallbackしない）。
    *   既存 `.venv` に `cv2` / `reportlab` は未導入（確認済み）。

### 1.2 サブゴール構造

| ID | サブゴール | 目的との対応 | 成果物 | 検証方法 |
| :--- | :--- | :--- | :--- | :--- |
| SG-1 | 依存と環境の確定（reportlab / OpenCV導入、ベースラインgreen確認） | 目標3・明示要求3 | `pyproject.toml` / `uv.lock` 更新 | `uv run python -c "import reportlab, cv2"`、既存pytest green |
| SG-2 | 36h11タグパターンの純Python実装とOpenCV整合 | 目標1・2 | `src/arm_observer/apriltag/families.py` | `test_tag_modules_match_opencv`（全24 ID） |
| SG-3 | シートレイアウト・描画プリミティブ・PDF出力 | 目標1・明示要求1,4 | `layout.py` / `drawing.py` / `pdf.py` | レイアウト幾何テスト、PDF MediaBoxテスト、黒モジュール被覆テスト |
| SG-4 | OpenCV高精度認識器と合成データ生成 | 目標2・明示要求5,6 | `detector.py` / `synthetic.py` | corner refine設定テスト、合成12 ID検出RMSテスト、回転不変テスト |
| SG-5 | CLI統合・成果物生成 | 目標1・明示要求1,3 | `cli.py`、`arm-tag-sheet` エントリ、PDF 2枚、マニフェスト | CLI e2eテスト、`reports/` 実物生成 |
| SG-6 | ドキュメント・品質ゲート・作業記録 | 目標3・監査性 | `docs/tag_sheet.md`、README追記、作業記録 | 全品質ゲート実行ログ、DoD監査 |

### 1.3 トレーサビリティ方針

| Trace ID | 要求・制約 | 対応する作業要素 | 証跡 |
| :--- | :--- | :--- | :--- |
| TR-1 | A4グリッドシートPDFを2枚生成 | 手順9–10（PDF）、手順15–16（CLI）、手順18（実生成） | `reports/tag-sheet-*/apriltag_36h11_a4_sheet_*.pdf`、`sheets.json` |
| TR-2 | 36h11パターンの正確性 | 手順3–4（family + OpenCV照合テスト） | `tests/test_apriltag_family.py` 実行ログ |
| TR-3 | 実寸（mm）レイアウトと100 mm参照バー | 手順5–8（layout/drawing）、手順18 | レイアウト幾何テスト、PDF内REFバー |
| TR-4 | OpenCV高精度認識（corner refine有効） | 手順11–12（detector） | `test_detector_settings`、`detector.py` |
| TR-5 | 人工データでの認識定量検証 | 手順13–14（synthetic）、手順19（verify実行） | `synthetic_scene.png`、`synthetic_verify.json` |
| TR-6 | uv環境・再利用性・可搬性 | 手順2、手順17、手順20 | `pyproject.toml`、`docs/tag_sheet.md`、品質ゲートログ |
| TR-7 | 監査可能な記録とatomic手順 | 全手順 | 本作業書§7、チェックリストのチェック状態 |
| TR-8 | 既存機能への非破壊 | 手順1、手順20 | 既存テストgreen、`git status` 比較 |

---

## 2. 作業内容

### フェーズ 1: 調査・設計フェーズ (見積: 0.5h)

このフェーズでは、実装に着手する前の準備作業を行います。

1.  **現状のアーキテクチャ分析：**
    *   **タスク内容：** `src/arm_observer/` の型規約（frozen/slots dataclass、beartype、NamedTuple、Protocol）、CLI規約（argparse、`build_parser`+`main`）、テスト配置 `tests/`、品質ゲート `scripts/check_quality.py`（循環的複雑度≤10）を確認する。
    *   **目的：** 新規サブパッケージを既存流儀に一致させ、手戻りを防ぐ。
    *   **対応サブゴール/Trace ID：** `SG-1 / TR-6`
2.  **依存コンポーネントの確認：**
    *   **タスク内容：** 公式コード表 `~/Project/apriltags/apriltags-source/tag36h11.c`（`codes[0..23]`、`bit_x`/`bit_y` 36点、`width_at_border=8`、`total_width=10`）と、OpenCV `cv2.aruco.DICT_APRILTAG_36h11` の `generateImageMarker` 出力の対応（180°回転一致）を確認する。`reportlab` の `canvas` によるmm指定描画、`opencv-contrib-python-headless` の `ArucoDetector` / `CORNER_REFINE_APRILTAG` のAPIを確認する。
    *   **目的：** パターン生成の正しさを最初に固定し、認識器設定の前提を確定する。
    *   **対応サブゴール/Trace ID：** `SG-2 / SG-4 / TR-2 / TR-4`
3.  **設計方針の文書化：**
    *   **タスク内容：** 下記「設計方針」のとおり、モジュール分割・データ型・ファイル命名・レイアウト数値を確定する。
    *   **目的：** 実装のロードマップと検証点を明確にする。
    *   **対応サブゴール/Trace ID：** `SG-3 / SG-5 / TR-1 / TR-3`

#### 設計方針（確定事項）

*   **パッケージ構成（新規追加のみ、既存ファイルは編集しない）:**

```text
src/arm_observer/apriltag/
├── __init__.py      # 公開APIの再export（generate_sheets, SheetSpec, Detection など）
├── families.py      # TagFamily + 36h11 ID0-23 のコード表 + 8x8モジュール行列（純Python）
├── layout.py        # A4寸法・SheetSpec・TagSlot・SheetPlan・plan_sheets()（純Python）
├── drawing.py       # RectOp/LineOp/TextOp + build_sheet_drawing()（mm座標、純Python）
├── pdf.py           # reportlabでDrawingをPDF化（write_sheet_pdf）
├── detector.py      # OpenCV ArucoDetector高精度設定 + detect_tags()
├── synthetic.py     # 合成シーン生成（render_sheet_scene）+ 正解コーナー
└── cli.py           # arm-tag-sheet {generate, verify, detect}
tests/
├── test_apriltag_family.py
├── test_apriltag_layout.py
├── test_apriltag_drawing.py
├── test_apriltag_pdf.py
├── test_apriltag_detector.py
├── test_apriltag_synthetic.py
└── test_apriltag_cli.py
docs/tag_sheet.md    # 使い方・印刷手順・精度設定・制約
```

*   **依存追加:** `reportlab>=4.4,<5`、`opencv-contrib-python-headless>=4.10,<5`（numpy 2系対応のため4.10以上）。
*   **データ型（immutable）:** `TagFamily` / `SheetSpec` / `TagSlot` / `SheetPlan` / `RectOp` / `LineOp` / `TextOp` / `Detection` / `SceneTruth` / `SyntheticScene` は `@beartype @dataclass(frozen=True, slots=True)`。`TagFamily` は `code` のtupleを持つ。
*   **タグ行列の定義:** `TagFamily.tag_modules(tag_id) -> tuple[tuple[bool, ...], ...]`、形状8×8、`True`=黒（インク）。外周1セルは黒。内側6×6はコードビット（MSBが先頭、`bit=1`→白、`bit=0`→黒）を、公式 `bit_x/bit_y` を180°回転した位置へ配置する（OpenCV `generateImageMarker` と一致）。この対応はテスト `test_tag_modules_match_opencv`（全24 ID）で固定する。
*   **レイアウト（既定値）:** A4縦210×297 mm、外周マージン12 mm、3列×4行、タグ40 mm（黒枠外寸）、タグ間ギャップ10 mm、各タグ下にIDラベル（Helvetica 6.5 pt、ASCII）。上部ヘッダ2行、下部に100 mm参照バー（10 mmごとの目盛り、両端に0/100表記）。座標はPDF左下原点、layout計算は左上原点mmで行い、`drawing.py` で変換する。
*   **シート割当:** Sheet 1 = ID 0–11、Sheet 2 = ID 12–23。出力ファイル名 `apriltag_36h11_a4_sheet_{n}_ids_{first:03d}-{last:03d}.pdf`。
*   **マニフェスト:** `sheets.json`（パラメータ、各PDFのファイル名・ID範囲・SHA256）。
*   **認識器設定（精度優先）:** `cornerRefinementMethod=CORNER_REFINE_APRILTAG`、`cornerRefinementWinSize=5`、`cornerRefinementMaxIterations=50`、`cornerRefinementMinAccuracy=0.01`、`aprilTagQuadDecimate=1.0`、`aprilTagQuadSigma=0.0`、`polygonalApproxAccuracyRate=0.01`、`adaptiveThreshWinSizeMin/Max/Step=3/53/4`、`minMarkerPerimeterRate=0.01`、`useAruco3Detection=False`。
*   **合成データ:** シート平面画像（px/mm指定）を作り、`cv2.getPerspectiveTransform` + `warpPerspective` で透視変換、ガウスぼけσ・ガウスノイズσ・乱数seedを指定。正解コーナーはタグ黒枠四隅の変換結果。検出コーナーとは巡回シフト最小距離で対応付け、RMSを算出する。
*   **CLI:** `arm-tag-sheet generate --output-dir DIR [オプション]`、`arm-tag-sheet verify --output-dir DIR [--rms-limit 0.5 など]`、`arm-tag-sheet detect --image PATH [--output-json PATH]`。`verify` は失敗（未検出IDまたはRMS超過）で終了コード2。
*   **ドキュメント:** `docs/tag_sheet.md` に印刷時の実寸確認手順（100 mmバーを定規で測る、100%印刷）を明記。READMEに短い節を追加。

### フェーズ 2: メイン機能の実装 (見積: 2.0h)

このフェーズでは、設計方針に基づいてTDDで機能を実装します。各モジュールは Red（テスト追加→失敗確認）→ Green（実装→成功）の順で進めます。

1.  **family実装：** `families.py` に36h11 ID0–23のコード表と `tag_modules()` を実装する。
    *   **対応サブゴール/Trace ID：** `SG-2 / TR-2`
2.  **layout実装：** `layout.py` に `SheetSpec`/`TagSlot`/`SheetPlan` と `plan_sheets()`（A4フィット検証、マージン・ギャップ・ラベル・参照バー位置の算出）を実装する。
    *   **対応サブゴール/Trace ID：** `SG-3 / TR-3`
3.  **drawing実装：** `drawing.py` に描画プリミティブと `build_sheet_drawing()`（タグ黒セルの矩形列、ラベル、ヘッダ、参照バー）を実装する。
    *   **対応サブゴール/Trace ID：** `SG-3 / TR-1 / TR-3`
4.  **pdf実装：** `pdf.py` に `write_sheet_pdf()` を実装する（reportlab、A4固定、ベクター矩形、ヘッダに「PRINT AT 100% (ACTUAL SIZE)」表記）。
    *   **対応サブゴール/Trace ID：** `SG-3 / TR-1`
5.  **detector実装：** `detector.py` に高精度設定の `build_detector()` と `detect_tags()` を実装する。
    *   **対応サブゴール/Trace ID：** `SG-4 / TR-4`
6.  **synthetic実装：** `synthetic.py` に `render_tag_image()` と `render_sheet_scene()` を実装する。
    *   **対応サブゴール/Trace ID：** `SG-4 / TR-5`
7.  **CLI・公開API実装：** `cli.py`、`__init__.py`、`pyproject.toml` の `arm-tag-sheet` エントリを追加する。
    *   **対応サブゴール/Trace ID：** `SG-5 / TR-1 / TR-6`

### フェーズ 3: テストと動作検証 (見積: 1.0h)

最終フェーズでは、実装した機能が意図通りに動作するかを総合的にテストします。

1.  **実成果物の生成：** `arm-tag-sheet generate` でPDF 2枚と `sheets.json` を `reports/tag-sheet-20261004/` に生成する。
    *   **対応サブゴール/Trace ID：** `SG-5 / TR-1`
2.  **合成データ認識の定量検証：** `arm-tag-sheet verify` を実行し、全12 ID検出とRMS ≤ 0.5 px、corner refine有効を `synthetic_verify.json` に記録する。
    *   **対応サブゴール/Trace ID：** `SG-4 / TR-5`
3.  **品質ゲート：** `uv run pytest` / `uv run ruff check src tests scripts` / `uv run ty check` / `uv run scripts/check_quality.py` を実行する。
    *   **対応サブゴール/Trace ID：** `SG-6 / TR-6 / TR-8`
4.  **DoD監査：** §6の完了の定義を1項目ずつ証跡と照合し、本作業書§7に記録する。
    *   **対応サブゴール/Trace ID：** `SG-6 / TR-7`

---

## 3. 作業チェックリスト

*作業が完了したら `[ ]` を `[x]` に変更します。*

### フェーズ 1: 調査・設計フェーズ

*（注: 手順2の依存追加は環境準備であり、ランタイムコードの変更ではない。これ以外にフェーズ1ではリポジトリの実装コードを変更しない。）*

### 手順 1: ベースラインの確認と非破壊の記録
- [x] 🖐 **操作**: `rtk proxy git status --short` と `rtk proxy uv run pytest -q` を実行する。
- [x] 🔎 **確認**: 既存テストが全green（または既知の結果）で、未commit変更一覧（既存M群）を変更しない方針を記録した。
- [x] 🧪 **テスト**: 既存テストスイートの結果が録れる。今回追加予定テスト名（`test_apriltag_family/layout/drawing/pdf/detector/synthetic/cli`）を作業記録に列挙する。
- [x] 🛠 **エラー時対処**: pytestが既存要因で失敗する場合は失敗テスト名と原因を記録し、今回の変更範囲外であることを明示する。`uv` 自体が失敗する場合は `rtk proxy uv sync --locked` を試し、それでも失敗すればブロッカーとして停止する。

### 手順 2: 依存の追加（Red→Green）
- [x] 🖐 **操作**: 先に `rtk proxy uv run python -c "import reportlab"` と `rtk proxy uv run python -c "import cv2.aruco"` の失敗を確認してから、`rtk proxy uv add "reportlab>=4.4,<5" "opencv-contrib-python-headless>=4.10,<5"` を実行する。
- [x] 🔎 **確認**: `pyproject.toml` の `[project.dependencies]` に2件追加され、`uv.lock` が更新され、両importが成功する。
- [x] 🧪 **テスト**: `rtk proxy uv run python -c "import reportlab, cv2, cv2.aruco; print(reportlab.Version, cv2.__version__)"` が成功する（Red→Green）。
- [x] 🛠 **エラー時対処**: ネットワーク不可時はエラーを保存しブロッカー記録。バージョン競合時は `uv add` の解決メッセージを記録し、numpy 2系と互換のバージョンに調整する。

### 手順 3: 36h11パターン照合テストの追加（Red）
- [x] 🖐 **操作**: `tests/test_apriltag_family.py` を新規作成し、(a) 全24 IDで `tag_modules` が `cv2.aruco.generateImageMarker(DICT_APRILTAG_36h11, id, 8) == 0` と一致、(b) 形状8×8、(c) 外周1セルが全て黒、(d) 範囲外IDで `ValueError` のテストを書く。
- [x] 🔎 **確認**: `rtk proxy uv run pytest tests/test_apriltag_family.py -q` が `ModuleNotFoundError: arm_observer.apriltag`（または import error）で失敗する。
- [x] 🧪 **テスト**: `test_tag_modules_match_opencv`（parametrize 24 ID）、`test_outer_border_is_black`、`test_tag_id_out_of_range_rejected` がRedであることをログに残す。
- [x] 🛠 **エラー時対処**: テストがcollection error以外で落ちる場合はテストコード自体を修正。OpenCVの `generateImageMarker` 仕様差異時は `cv2.__version__` と引数仕様を確認し、テストを公式APIに合わせる。

### 手順 4: families実装（Green）
- [x] 🖐 **操作**: `src/arm_observer/apriltag/__init__.py` と `families.py` を作成し、公式 `tag36h11.c` の `codes[0..23]`、`bit_x`/`bit_y`（36点）、`width_at_border=8`、`total_width=10` を反映して `TagFamily` と `tag_modules()` を実装する。
- [x] 🔎 **確認**: `rtk proxy uv run pytest tests/test_apriltag_family.py -q` が全green。
- [x] 🧪 **テスト**: 手順3のテストがRed→Greenに変化する。
- [x] 🛠 **エラー時対処**: 一致しないIDがある場合は、ビット順（MSBが先頭）・回転（180°）・1=白の対応を1つずつ切り分け、`/tmp/opencode/check2.py` と同様の比較スクリプトで差分セルを特定する。

### 手順 5: レイアウトテストの追加（Red）
- [x] 🖐 **操作**: `tests/test_apriltag_layout.py` を新規作成し、(a) `plan_sheets(SheetSpec())` が2枚を返しID範囲が0–11/12–23、(b) 各タグは40.0 mm、ギャップ10 mm、全タグがマージン内、(c) タグ矩形同士が重ならない、(d) 参照バーが100.0 mm、(e) A4に収まらないサイズ指定で `ValueError` のテストを書く。
- [x] 🔎 **確認**: `rtk proxy uv run pytest tests/test_apriltag_layout.py -q` が import error で失敗する（Red）。
- [x] 🧪 **テスト**: `test_sheet_pair_ids`、`test_tag_geometry_exact_mm`、`test_no_overlap`、`test_reference_bar_length`、`test_oversize_rejected`。
- [x] 🛠 **エラー時対処**: 期待値は浮動小数のため `pytest.approx(abs=1e-9)` を使う。定義の曖昧さが出た場合は本作業書§2の設計方針（マージン12、ギャップ10）に立ち返る。

### 手順 6: layout実装（Green）
- [x] 🖐 **操作**: `layout.py` に `PageSize`、`SheetSpec`、`TagSlot`、`SheetPlan`、`plan_sheet()`、`plan_sheets()` を実装する（左上原点mm、IDは行優先）。
- [x] 🔎 **確認**: `rtk proxy uv run pytest tests/test_apriltag_layout.py -q` が全green。
- [x] 🧪 **テスト**: 手順5のテストがRed→Greenに変化する。
- [x] 🛠 **エラー時対処**: フィット検証の式（`margin*2 + cols*tag + (cols-1)*gap <= 210` 等）を再計算する。ページ高さのヘッダ/参照バー分も検証に含める。

### 手順 7: 描画プリミティブテストの追加（Red）
- [x] 🖐 **操作**: `tests/test_apriltag_drawing.py` を新規作成し、(a) 各タグの黒矩形集合が `tag_modules` の黒セルと一致、(b) 参照バーの矩形長が100.0 mm、(c) ヘッダにシート番号とID範囲と "100%" 文言が含まれる、(d) 同一planから同一Drawing（決定的）のテストを書く。
- [x] 🔎 **確認**: `rtk proxy uv run pytest tests/test_apriltag_drawing.py -q` が import error で失敗する（Red）。
- [x] 🧪 **テスト**: `test_black_rects_match_modules`、`test_reference_bar_rect`、`test_header_text_contains_actual_size`、`test_drawing_is_deterministic`。
- [x] 🛠 **エラー時対処**: 座標系（左上原点→PDF左下原点）の変換で符号を誤りやすい。1タグ分の期待矩形を手計算し、最初の不一致で座標変換を疑う。

### 手順 8: drawing実装（Green）
- [x] 🖐 **操作**: `drawing.py` に `RectOp`/`LineOp`/`TextOp` と `build_sheet_drawing()` を実装する（タグ黒セル矩形、IDラベル、ヘッダ2行、100 mm参照バーと目盛り）。
- [x] 🔎 **確認**: `rtk proxy uv run pytest tests/test_apriltag_drawing.py -q` が全green。
- [x] 🧪 **テスト**: 手順7のテストがRed→Greenに変化する。
- [x] 🛠 **エラー時対処**: 矩形数不一致の場合は黒セル数え上げ（外周28 + 内側の黒ビット数）とラベル・バーの矩形が混入していないかを切り分ける。

### 手順 9: PDF出力テストの追加（Red）
- [x] 🖐 **操作**: `tests/test_apriltag_pdf.py` を新規作成し、(a) `write_sheet_pdf` が `%PDF-` で始まるファイルを生成、(b) バイト列中にA4相当のMediaBox（595.28×841.89 pt、±1 pt）が1つある、(c) CLIのファイル名規則 `apriltag_36h11_a4_sheet_1_ids_000-011.pdf` が得られるテストを書く。
- [x] 🔎 **確認**: `rtk proxy uv run pytest tests/test_apriltag_pdf.py -q` が import error で失敗する（Red）。
- [x] 🧪 **テスト**: `test_pdf_header_and_mediabox`、`test_sheet_filename`。
- [x] 🛠 **エラー時対処**: reportlabのMediaBox表記揺れに備え正規表現 `MediaBox\s*\[\s*0(\.0+)?\s+0(\.0+)?\s+595\.\d+\s+841\.\d+\s*\]` を使う。圧縮設定は `pageCompression=1`。

### 手順 10: pdf実装（Green）
- [x] 🖐 **操作**: `pdf.py` に `write_sheet_pdf(plan, family, path)` とファイル名生成 `sheet_filename(plan, family)` を実装する（reportlab `canvas.Canvas`、`reportlab.lib.units.mm`、Helvetica）。
- [x] 🔎 **確認**: `rtk proxy uv run pytest tests/test_apriltag_pdf.py -q` が全green。
- [x] 🧪 **テスト**: 手順9のテストがRed→Greenに変化する。
- [x] 🛠 **エラー時対処**: フォント未指定や単位誤りで例外が出た場合は、`canvas.setFont("Helvetica", size)` と `mm()` 変換を確認する。

### 手順 11: 認識器設定テストの追加（Red）
- [x] 🖐 **操作**: `tests/test_apriltag_detector.py` を新規作成し、(a) `build_detector()` のパラメータで `cornerRefinementMethod == cv2.aruco.CORNER_REFINE_APRILTAG`、(b) `aprilTagQuadDecimate == 1.0`、(c) 単一のOpenCV生成マーカー画像からIDと4コーナーが得られる、のテストを書く。
- [x] 🔎 **確認**: `rtk proxy uv run pytest tests/test_apriltag_detector.py -q` が import error で失敗する（Red）。
- [x] 🧪 **テスト**: `test_corner_refine_enabled`、`test_detect_single_opencv_marker`。
- [x] 🛠 **エラー時対処**: `getDetectorParameters` が無いOpenCV版では `DetectorParameters` の属性を直接保持する設計に切り替え、バージョンを記録する。属性名差異（`useAruco3Detection` 等）は `cv2.__version__` と突き合わせる。

### 手順 12: detector実装（Green）
- [x] 🖐 **操作**: `detector.py` に `DetectorSettings`（frozen）、`build_detector()`（設計方針の高精度パラメータ）、`Detection`（frozen）、`detect_tags()` を実装する。
- [x] 🔎 **確認**: `rtk proxy uv run pytest tests/test_apriltag_detector.py -q` が全green。
- [x] 🧪 **テスト**: 手順11のテストがRed→Greenに変化する。
- [x] 🛠 **エラー時対処**: `ArucoDetector.detectMarkers` の戻り値順序（corners, ids, rejected）を確認。`ids is None` は空tupleへ明示変換する（fallbackではなく定義）。

### 手順 13: 合成データテストの追加（Red）
- [x] 🖐 **操作**: `tests/test_apriltag_synthetic.py` を新規作成し、(a) Sheet 1の12 IDを透視変換した合成画像で全ID検出、(b) コーナーRMS ≤ 0.5 px、(c) 単一タグを90/180/270°回転しても同一ID検出、(d) ぼけσ1.0+ノイズσ2.0でも検出、のテストを書く。
- [x] 🔎 **確認**: `rtk proxy uv run pytest tests/test_apriltag_synthetic.py -q` が import error で失敗する（Red）。
- [x] 🧪 **テスト**: `test_detect_all_sheet_ids`、`test_corner_rms_within_limit`、`test_rotation_invariance`、`test_blur_and_noise_robustness`。
- [x] 🛠 **エラー時対処**: 検出漏れ時は正解コーナー順序の対応付け（巡回シフト）を疑い、デバッグ画像を `/tmp/opencode/` に書き出して目視確認する（GUIは使わない）。

### 手順 14: synthetic実装（Green）
- [x] 🖐 **操作**: `synthetic.py` に `SceneTruth`/`SyntheticScene`（frozen）、`render_tag_image()`、`render_sheet_scene()`（`cv2.getPerspectiveTransform` + `warpPerspective` + ぼけ/ノイズ、seed固定）、`corner_rms_px()` を実装する。
- [x] 🔎 **確認**: `rtk proxy uv run pytest tests/test_apriltag_synthetic.py -q` が全green。
- [x] 🧪 **テスト**: 手順13のテストがRed→Greenに変化する。
- [x] 🛠 **エラー時対処**: RMSが閾値を超える場合は、(1) タグ行列、(2) 透視変換の正解座標、(3) 検出器設定 の順に切り分ける。循環的複雑度が10を超えそうな関数はヘルパーへ分割する（品質ゲート対策）。

### 手順 15: CLIテストの追加（Red）
- [x] 🖐 **操作**: `tests/test_apriltag_cli.py` を新規作成し、`generate --output-dir tmp_path` で2 PDF + `sheets.json` が生成される、(b) `verify --output-dir tmp_path` が終了コード0で `synthetic_verify.json` と `synthetic_scene.png` を生成する、(c) manifestのSHA256が実ファイルと一致する、のテストを書く。
- [x] 🔎 **確認**: `rtk proxy uv run pytest tests/test_apriltag_cli.py -q` が import error で失敗する（Red）。
- [x] 🧪 **テスト**: `test_generate_writes_two_pdfs_and_manifest`、`test_verify_synthetic_exit_zero`、`test_manifest_sha256_matches`。
- [x] 🛠 **エラー時対処**: argparseの終了コード（`SystemExit`）は `pytest.raises(SystemExit)` ではなく `main(argv)` の戻り値整数で検証する設計にする。

### 手順 16: CLI・公開API・エントリポイント実装（Green）
- [x] 🖐 **操作**: `cli.py`（`build_parser`/`main`、`generate`/`verify`/`detect`）、`__init__.py`（公開API再export）、`pyproject.toml` の `[project.scripts]` に `arm-tag-sheet = "arm_observer.apriltag.cli:main"` を追加する。
- [x] 🔎 **確認**: `rtk proxy uv run pytest tests/test_apriltag_cli.py -q` が全green。`rtk proxy uv run arm-tag-sheet --help` が表示される。
- [x] 🧪 **テスト**: 手順15のテストがRed→Greenに変化する。
- [x] 🛠 **エラー時対処**: エントリポイントが反映されない場合は `rtk proxy uv sync` を実行してから再確認する。`main` の戻り値intを `raise SystemExit(main())` で返す。

### 手順 17: ドキュメント追加
- [x] 🖐 **操作**: `docs/tag_sheet.md`（生成・印刷・実寸確認・認識設定・制約）を作成し、READMEの適切な位置に短い節（コマンド例と参照）を追記する。
- [x] 🔎 **確認**: 記載コマンドが実在のCLI引数と一致し、印刷時「100%（実寸）・100 mm参照バーで確認」が明記されている。
- [x] 🧪 **テスト**: ドキュメント記載の `rtk proxy uv run arm-tag-sheet generate --output-dir reports/tag-sheet-20261004` が手順18で実際に成功することをもって検証とする。
- [x] 🛠 **エラー時対処**: CLI引数とドキュメントの齟齬が出た場合はCLI実装を正とし、ドキュメントを修正する。

### フェーズ 3: テストと動作検証

### 手順 18: 実成果物（PDF 2枚）の生成
- [x] 🖐 **操作**: `rtk proxy uv run arm-tag-sheet generate --output-dir reports/tag-sheet-20261004` を実行する。
- [x] 🔎 **確認**: `apriltag_36h11_a4_sheet_1_ids_000-011.pdf`、`apriltag_36h11_a4_sheet_2_ids_012-023.pdf`、`sheets.json` が存在し、PDFサイズが各数KB以上。
- [x] 🧪 **テスト**: `test_apriltag_cli.py` のe2eテストに加え、実ファイルのSHA256と `sheets.json` の記載が一致することを `sha256sum` で確認する。
- [x] 🛠 **エラー時対処**: 出力先ディレクトリが無い場合はCLIが `mkdir(parents=True, exist_ok=True)` する設計を確認する。権限エラー時は出力先を `/tmp/opencode/` に変え、理由を記録する。

### 手順 19: 合成データ認識の定量検証
- [x] 🖐 **操作**: Codex引継ぎで両sheetのverifyを実行。保存先を `diary/2026-10-04/apriltag-review/verify-sheet-{1,2}` に分けた。コマンドは後述の引継ぎ記録参照。
- [x] 🔎 **確認**: 両方終了コード0、各12 ID、`max_rms_px` = 0.3881 ≤ 0.5、`corner_refinement` = `CORNER_REFINE_APRILTAG`。
- [x] 🧪 **テスト**: `test_verify_synthetic_exit_zero` を含む全体suiteと対象CLI試験で確認、実画像入力とJSONを保存。
- [x] 🛠 **エラー時対処**: 検出漏れ・RMS超過なし。元閾値は変更しなかった。

### 手順 20: 品質ゲートの実行
- [x] 🖐 **操作**: pytest、ruff、ty、check_qualityを実行。結果の保存先は `diary/2026-10-04/apriltag-review/`。
- [x] 🔎 **確認**: 全ゲート成功、最大循環的複雑度10。§7の引継ぎ記録を参照。
- [x] 🧪 **テスト**: 全体340 passed / 21.11秒。最後の型修正後は対象CLI8 passed / 2.26秒。
- [x] 🛠 **エラー時対処**: ruffの未使用import等3件、tyのdict添字型2件を修正。複雑度15は採点とI/Oの分割で10へ改善。gateや型の無視設定は追加していない。

### 手順 21: 完了の定義（DoD）監査と作業記録の完成
- [x] 🖐 **操作**: §6を成果物、実PDF検査、テスト、出典と照合。元OpenCode記録は残し、Codex引継ぎ結果を追記。
- [x] 🔎 **確認**: 全DoDとTR-1〜TR-8の対応を§7に記載。
- [x] 🧪 **テスト**: 再実行コマンドとPDF実体検証スクリプトを保存。ブラウザでも4画像読込み・7リンクHTTP200・横はみ出しなしを確認。
- [x] 🛠 **エラー時対処**: 印刷済み紙と実カメラ精度は対象DoDに含まれず、未検証と明記。合成精度を実撮影精度と誤記しない。

---

## 4. 作業に使用するコマンド参考情報

### 基本的な開発ワークフロー

```bash
# 依存同期（lock厳守）
rtk proxy uv sync --locked

# 依存追加（今回の作業）
rtk proxy uv add "reportlab>=4.4,<5" "opencv-contrib-python-headless>=4.10,<5"

# CLI確認
rtk proxy uv run arm-tag-sheet --help
```

### テストと品質管理

```bash
# 全テスト
rtk proxy uv run pytest -q

# 対象テストのみ
rtk proxy uv run pytest tests/test_apriltag_family.py -q

# Lint / 型 / 複雑度
rtk proxy uv run ruff check src tests scripts
rtk proxy uv run ty check
rtk proxy uv run scripts/check_quality.py --output reports/tag-sheet-20261004/code_quality.json
```

### 成果物生成と検証

```bash
# PDF 2枚 + sheets.json
rtk proxy uv run arm-tag-sheet generate --output-dir reports/tag-sheet-20261004

# 合成データでの高精度認識検証（全12 ID、RMS≤0.5px）
rtk proxy uv run arm-tag-sheet verify --output-dir reports/tag-sheet-20261004 --rms-limit 0.5

# 実画像に対する認識（将来用）
rtk proxy uv run arm-tag-sheet detect --image <path> --output-json <path>
```

---

## 6. 完了の定義

*作業が最後まで完了したら `[ ]` を `[x]` にしつつ、作業が本当に完了したかをチェックします*

- [x] 観点1: A4 PDF 2枚、全24 ID、寸法・100 mmバー・SHA一致。`apriltag-review/pdf_validation.json`、`sheets.json`、layout/drawing/pdf試験。(TR-1, TR-3)
- [x] 観点2: 全24 IDがOpenCVと一致。detector試験と両 `synthetic_verify.json` でcorner refineを確認。(TR-2, TR-4)
- [x] 観点3: 両sheet12/12 ID、最大RMS0.3881 px ≤ 0.5。synthetic試験で回転・別ぼけ・ノイズも確認。(TR-5)
- [x] 観点4: pytest340 pass、ruff/ty成功、最大複雑度10。(TR-6, TR-8)
- [x] 観点5: 全Trace IDを後述表で実体証拠へ対応付け、失敗修正も記録。(TR-7)
- [x] 観点6: docs/READMEの実寸印刷と実測手順を修正、証跡別保存のコマンドも記載。(TR-6)

---

## 7. 作業記録

**重要な注意事項：**

*   作業開始前に必ず `date "+%Y-%m-%d %H:%M:%S %Z%z"` コマンドで現在時刻を確認し、正確な日時を記録します。
*   各作業項目を開始する際と完了する際の両方で記録を行うこと。
*   作業内容は具体的なコマンドや操作手順を詳細に記載すること。
*   結果・備考欄には成功／失敗、エラー内容、解決方法、重要な気づきを必ず記入すること。
*   複数のフェーズがある場合は、フェーズごとに開始・完了の記録を取ること。
*   コード変更を行った場合は、変更したファイル名と変更内容の概要を記録すること。
*   エラーが発生した場合は、エラーメッセージと解決策を詳細に記録すること。

| 日付 | 時刻 | 作業者 | 作業内容 | 結果・備考 |
| :--- | :--- | :--- | :--- | :--- |
| 2026-10-04 | 19:01:45 JST+0900 | 実装担当エージェント | 作業書作成（write-workdoc-uv準拠、diary配置） | 調査済み事実: 公式tag36h11.c codes[0..23]取得済み、OpenCV DICT_APRILTAG_36h11 とはID0–3で180°回転一致を実測確認済み。既存venvにcv2/reportlab未導入。 |
| 2026-10-04 | 19:04:57 JST+0900 | 実装担当エージェント | 作業開始: start-work-with-docs開始、開始時刻記録 | レビュー（review-written-workdoc）PASS_WITH_NOTES、安全改善4件反映済み。行動カウント開始。 |
| 2026-10-04 | 19:06 JST+0900 | 実装担当エージェント | 手順1完了: ベースライン確認 | ✅ `uv run pytest -q` = 283 passed (18.19s)。既存M群（README.md, docs/RGBD_CAPTURE.md, pyproject.toml, scripts/*, src/arm_observer/{camera_pose_capture,photo_supported_release,pose_capture_motion,standby_motion}.py, tests/*, skills/*）と未追跡群を記録。以後これらは変更しない。追加予定テスト: test_apriltag_{family,layout,drawing,pdf,detector,synthetic,cli}.py。 |
| 2026-10-04 | 19:07 JST+0900 | 実装担当エージェント | 手順2完了: 依存追加 | ✅ Red確認（reportlab/cv2ともModuleNotFoundError）→ `uv add` 成功。reportlab==4.5.1, opencv-contrib-python-headless==4.14.0.94, pillow==12.3.0 追加。`uv run python -c ...` で reportlab 4.5.1 / cv2 4.14.0 / numpy 2.5.3 / CORNER_REFINE_APRILTAG=True を確認。pyproject.tomlへの差分は既存M（ty exclude行）と今回のdependencies 2行のみで、既存変更は保持。 |
| 2026-10-04 | 19:09 JST+0900 | 実装担当エージェント | 手順3完了: family照合テスト追加（Red） | ✅ `tests/test_apriltag_family.py` 新規作成（実関数名: test_tag_modules_match_opencv / test_shape_and_outer_border / test_tag_id_out_of_range_rejected）。`uv run pytest tests/test_apriltag_family.py -q` は `ModuleNotFoundError: No module named 'arm_observer.apriltag'` でRed（1 error in 0.35s）。 |
| 2026-10-04 | 19:10 JST+0900 | 実装担当エージェント | 手順4完了: families実装（Green） | ✅ `src/arm_observer/apriltag/{__init__,families}.py` 作成。公式tag36h11.cのcodes[0..23]とbit_x/bit_yを収録し、OpenCVに合わせた180°回転セル順でtag_modules()を実装。`uv run pytest tests/test_apriltag_family.py -q` = 26 passed (0.25s)、Red→Green確認。 |
| 2026-10-04 | 19:12 JST+0900 | 実装担当エージェント | 手順5完了: layoutテスト追加（Red） | ✅ `tests/test_apriltag_layout.py` 作成。`ModuleNotFoundError: arm_observer.apriltag.layout` でRed確認。 |
| 2026-10-04 | 19:13 JST+0900 | 実装担当エージェント | 手順6完了: layout実装（Green） | ✅ `layout.py` 作成（PageSize/A4/SheetSpec/TagSlot/ReferenceBar/SheetPlan/plan_sheet/plan_sheets、フィット検証つき）。`uv run pytest tests/test_apriltag_layout.py -q` = 6 passed、Red→Green確認。 |
| 2026-10-04 | 19:13 JST+0900 | 実装担当エージェント | 手順7完了: drawingテスト追加（Red） | ✅ `tests/test_apriltag_drawing.py` 作成（test_black_rects_match_modules / test_reference_bar_rect / test_header_and_footer_texts / test_drawing_is_deterministic）。ModuleNotFoundErrorでRed確認。 |
| 2026-10-04 | 19:13 JST+0900 | 実装担当エージェント | 手順8完了: drawing実装（Green） | ✅ `drawing.py` 作成（RectOp/LineOp/TextOp/Drawing、左上原点mm→PDF左下原点のflip一元化、タグ黒セル・IDラベル・ヘッダ・100mmバー＋目盛り）。`uv run pytest tests/test_apriltag_drawing.py -q` = 4 passed。 |
| 2026-10-04 | 19:13 JST+0900 | 実装担当エージェント | 手順9完了: PDFテスト追加（Red） | ✅ `tests/test_apriltag_pdf.py` 作成（test_pdf_header_and_mediabox / test_sheet_filename）。ModuleNotFoundErrorでRed確認。 |
| 2026-10-04 | 19:13 JST+0900 | 実装担当エージェント | 手順10完了: pdf実装（Green） | ✅ `pdf.py` 作成（reportlab Canvas、mm→pt変換、pageCompression=1、sheet_filenameはfamily名から`tag`接頭辞を除去）。`uv run pytest tests/test_apriltag_pdf.py -q` = 2 passed（MediaBox 595.28x841.89）。 |
| 2026-10-04 | 19:13 JST+0900 | 実装担当エージェント | 手順11完了: detectorテスト追加（Red） | ✅ `tests/test_apriltag_detector.py` 作成（test_corner_refine_enabled / test_accuracy_first_settings / test_detect_single_opencv_marker / test_detect_blank_returns_empty）。ModuleNotFoundErrorでRed確認。 |
| 2026-10-04 | 19:13 JST+0900 | 実装担当エージェント | 手順12完了: detector実装（Green） | ✅ `detector.py` 作成（DetectorSettings=frozen、CORNER_REFINE_APRILTAG、quadDecimate=1.0、quadSigma=0.0、useAruco3Detection=False、ids=None→空tuple）。`uv run pytest tests/test_apriltag_detector.py -q` = 4 passed。 |
| 2026-10-04 | 19:13 JST+0900 | 実装担当エージェント | 手順13完了: syntheticテスト追加（Red） | ✅ `tests/test_apriltag_synthetic.py` 作成（全12ID検出 / RMS≤0.5px / 回転0-270° / ぼけσ1.0+ノイズσ2.0）。ModuleNotFoundErrorでRed確認。 |
| 2026-10-04 | 19:13 JST+0900 | 実装担当エージェント | 手順14完了: synthetic実装（Green） | ✅ `synthetic.py` 作成（render_tag_image / render_sheet_scene、px_per_mm=6.0既定、透視warp＋ぼけ＋ノイズseed固定、corner_rms_pxは巡回シフト最小RMS）。`uv run pytest tests/test_apriltag_synthetic.py -q` = 7 passed（2.85s）。 |
| 2026-10-04 | 19:13 JST+0900 | 実装担当エージェント | 手順15完了: CLIテスト追加（Red） | ✅ `tests/test_apriltag_cli.py` 作成（2 PDF+manifest / verify exit0+RMS / SHA256一致）。ModuleNotFoundErrorでRed確認。 |
| 2026-10-04 | 19:13 JST+0900 | 実装担当エージェント | 手順16完了: CLI・公開API・エントリポイント（Green） | ✅ `cli.py`（generate/verify/detect）、`__init__.py` 公開API、pyprojectに `arm-tag-sheet` 追加。`uv run pytest tests/test_apriltag_cli.py -q` = 3 passed。`uv run arm-tag-sheet --help` 表示確認。 |
| 2026-10-04 | 19:15 JST+0900 | 実装担当エージェント | 手順17完了: ドキュメント追加 | ✅ `docs/tag_sheet.md` 作成（生成/印刷100%/100mmバー確認/精度設定/verify/detect/制約）。READMEに「AprilTag A4グリッドシート生成と高精度認識（2026-10-04追加）」節を「Gitに含めないもの」直前に追記。 |
| | | | | |

## 8. Codexによる引継ぎ完了監査

元OpenCode会話は130メッセージ、途中終了。上記手順19–21とDoDの完了は元エージェントの
実績として遡及記録せず、2026-10-04 19:21以降のCodex単独レビューとして記録する。
追補計画と時刻別記録: [workdoc_Oct04-2026_apriltag_followup.md](workdoc_Oct04-2026_apriltag_followup.md)。
詳細: [レビュー記録](../apriltag-review/REPORT.md)。実成果物の正本保存先は `diary/2026-10-04/apriltag-review/`。
旧reports/tag-sheet-20261004の原本は上書きしていない。

| Trace ID | 引継ぎ監査の証拠 |
|---|---|
| TR-1, TR-3 | ../apriltag-review/sheets.json、PDF2枚、pdf_validation.json、verify_pdf_artifacts.py。 |
| TR-2 | tests/test_apriltag_family.pyの全24ケース、../apriltag-review/upstream_validation.json。 |
| TR-4 | tests/test_apriltag_detector.py、../apriltag-review/verify-sheet-{1,2}/synthetic_verify.json。 |
| TR-5 | 両verify JSONとsynthetic_scene.png、test_apriltag_synthetic.py。 |
| TR-6 | docs/tag_sheet.md、README.md、uv.lock、../apriltag-review/REPORT.mdの再実行手順。 |
| TR-7 | 本節、追補作業書、../conversations/opencode-apriltag-20261004_clean.json。 |
| TR-8 | 全体340 pass、対象CLI8 pass、ruff/ty成功、../apriltag-review/code_quality.json。 |

元手順13/15の重複テストは引継ぎで統合し、実名は `test_all_ids_and_corner_rms_within_limit` と
`test_generate_writes_two_pdfs_and_manifest`。新規の入力・保存失敗・小数pixelセル試験を追加。
元観点の要求値を緩和せずに不具合を修正した。
