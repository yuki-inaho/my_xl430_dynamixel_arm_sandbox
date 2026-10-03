# 3D Printed DYNAMIXEL Gripper

**2026-09-26取り込み:** [低配置D405のレビュー・OCCT 8再実行](docs/D405_LOW_PROFILE_INTAKE.md)。
俯角30°・爪20 mm延長のV2候補と改善検証器を取り込み、固定Pixi環境でwheel再ビルド・再変換した。
新規URDFと12 STLは受領モデルと全バイト一致。製作承認はfalse。

現行候補: **ID5だけでPG3を開閉、下流の追加モーターなし**。
`outputs/pg3-id5-only-r1/`へ全腕3開度STEP/三面図を生成。原本保持、実機装着DoDは未達。
仕様は[ID5単独開閉](docs/PG3_ID5_ONLY_DESIGN.md)、実行記録は
[Sep24作業書](temp/workdoc_Sep24-2026_pg3_id5_only.md)。

旧r5履歴: **P06局所改修・側方カメラホルダ・取付ねじ候補の6台構成**。
P06/frame干渉240.5625→0 mm3、 nominal離隔0.5 mm。側面4穴だけφ2.8へ変更し、
実相手M06 CADの穴軸・ねじ深さを照合。実機装着・印刷DoDはまだ未達です。
r4ではPG3フレーム端部4箇所だけに0.3 mmの逃げを追加。元部品を再構成せず、
取付穴・主レール・mask外の材料を保持しています。r5では寸法を変えずにクランクの
B-rep生成手順を修正し、simulationも改修済み実組立の形状を使用します。統合CAD/画像/
運動学は`outputs/pg3-installable-candidate-r5/`。r4補足検査は履歴でありr5へ自動継承しません。
[実機装着の受入状況と未確定条件](docs/INSTALLATION_READINESS.md)を参照してください。
[旧r5の設計契約・締結・組立順・再現方法](docs/PG3_INSTALLATION_CANDIDATE.md)は履歴です。
[以前の無改修取込結果](docs/PG3_C9_INTEGRATION.md)は比較用の履歴です。

2026-09-23再監査: **全DoD達成の宣言は撤回**。ラック案は歯・案内・固定が未実装の概念図。
PG2 R5 (縦置きXL430、クランク+2リンク、印刷ガイド) を別候補として追加しました。
[辛口レビュー・2方式の現状と改善順](docs/REVIEW_PG2_AND_SELF_AUDIT.md)を先に参照してください。

2026-09-24の要求は、**全XL430・ロール不要・平行グリッパ**です。
ID5だけで開閉・追加モーターなしに確定。旧r5は最新要求の完成形ではありません。
[新設計仕様](docs/PG3_ID5_ONLY_DESIGN.md)と
[作業書](temp/workdoc_Sep24-2026_pg3_id5_only.md)に沿って検証中です。
カメラ未購入、28x28 mm四穴を維持。最新希望はID5モーターケース角ねじ付近を使い、
モーター上方から把持域を斜め下向きに見る構成です。旧P05側方案は受入候補ではありません。
詳細は[新カメラ取付要求](docs/CAMERA_MOUNT_ID5_CORNER.md)と
`specs/camera_mount_id5_corner.yaml`を参照。把持物は寸法未定のキューブ。
P05局所配線逃げ候補の検討は許可済みですが、CADは製作承認ではありません。
コード位置と再現用CAD入力は[カメラ設計コード索引](docs/CAMERA_MOUNT_CODE_INDEX.md)にまとめています。

- [カメラジグの設計・検証・組立順序](docs/CAMERA_JIG.md)
- [全XL430末端の現状と検証結果](docs/ALL_XL430_TERMINAL_STATUS.md)
- [BOM草稿](docs/BOM_DRAFT.md)
- [組立・合成校正・実機校正の手順](docs/ASSEMBLY_AND_CALIBRATION.md)
- [未解決事項と再開条件](docs/OPEN_ISSUES.md)
- [他エージェントの横開きグリッパ・カメラ案のレビューと改善方針](docs/REVIEW_LATERAL_20260922.md)
- カメラCAD: `outputs/camera-jig-20260922-r11/`。
- 全XL430末端CAD: `outputs/terminal-all-xl430-20260922-r3/`。
- MuJoCo/AprilTag E2E: `outputs/calibration-demo-20260923-r4/`。
- いずれも **UNVALIDATED/診断候補。印刷・実カメラ校正・運用承認ではない。**

```bash
rtk proxy uv sync --locked
rtk proxy env MUJOCO_GL=egl uv run pytest -q -n auto --dist loadgroup   # 並列（推奨）
rtk proxy env MUJOCO_GL=egl uv run pytest -q                              # 逐次（同じテスト集合）
rtk proxy env MUJOCO_GL=egl uv run python -m scripts.review_pg3_installation \
  --out outputs/pg3-install-next
rtk proxy uv run python -m scripts.review_pg3_guide_relief outputs/pg3-install-next \
  --out outputs/pg3-install-next-audit/guide_relief
```

並列実行の振り分けは `tests/conftest.py` が決める（モジュール単位、重いモジュールは分割、合成キャリブレーションは1回生成）。
繰り返し解析するSTEPは `.pytest_cache` の内容アドレス型キャッシュから読む（`CAD_STEP_CACHE_DIR=` で無効化）。
i7-9750H（6コア/12スレッド）で719件: 12並列約1分50秒、6並列約2分15秒、逐次約5分30秒（変更前14分06秒）。12並列の最小空きメモリ約9 GB。
内訳と判断は [テスト実行時間の記録](docs/TEST_PERFORMANCE.md)。検証対象・閾値は逐次実行と同一。

現在の生成・監査は未達項目を残すためexit 2。正常終了や描画だけを印刷承認にしません。
原本01_frame/07_crankのコピーは参照用で、r5の部品選択は`review.json`のreplacement mapに従います。

以前のカメラ単体・校正デモを再現する場合 (現PG3統合版とは別):

```bash
rtk proxy uv run python -m camera_jig.build --out outputs/camera-jig-next
rtk proxy uv run python -m camera_jig.serviceability outputs/camera-jig-next
rtk proxy env MUJOCO_GL=egl uv run python scripts/run_calibration_demo.py \
  --config specs/simulation_calibration.yaml \
  --out outputs/calibration-demo-next
```

出力先は未使用のrun名にする。`camera_jig.serviceability`は、装着状態でカメラねじへ工具が
入らないことを検出してexit 2になる。先付け工程の結果は同JSON内で別に記録する。
静的合格を可動域・強度・配線・印刷承認へ読み替えない。

PG2の入力検証・独立STEP検査 (元ソースは実行しない):

```bash
rtk proxy uv run python -m scripts.review_pg2 import \
  outputs/PG2_XL430_upright_printed_guide_R5.zip --out references/pg2-r5
rtk proxy uv run python -m scripts.review_pg2 review \
  --source references/pg2-r5/PG2_XL430 --out outputs/pg2-next --render
```

この環境では取込済み。importは既存ディレクトリを上書きしません。
reviewは全腕未適合・未解決を理由にexit 2。JSONと画像は残し、成功扱いで印刷へ進めません。
方式台帳: `specs/gripper_variants.yaml`。最新診断: `outputs/pg2-independent-20260923-r2/`。
旧E2E r4は履歴であり、コード変更後のSHA再検証で不一致になることは正常です。

## 構成

- `camera_jig/`: P05固定カメラジグの生成/検証コード。
- `gripper_design/`: 全XL430 interface、平行ジョー概念、末端assembly、締結/工具契約。
- `simulation/`: 座標変換、AprilGrid、MuJoCo EGL描画、検出、校正、CAD連携。
- `tests/`: 正常・不良対照の回帰検査。
- `references/arm-r3/`: 写真のリンクに対応するR3入力。変更禁止。
- `references/robonine/`: SO101参考カメラ取付とライセンス。
- `skills/`: プロジェクト内のコピー。PlaywrightはCADスキルと独立。
- `references/arm-baseline/`, `references/prior-checkpoint/`: 別形状・旧調査。今回の取付元と混同しない。
- `docs/HANDOFF.md`, `REQUIREMENTS.md`, `DESIGN_BASIS.md`, `INTERFACES.md`,
  `CAD_PDCA.md`: 初期引継ぎ資料。PG3最新状態は`PG3_INSTALLATION_CANDIDATE.md`を優先する。
- `outputs/`, `temp/`: Git対象外。検証結論はdocsにも記録。

Python 3.12 + uv。GitHubリポジトリは`yuki-inaho/3d-printed-dynamixel-gripper`。
CAD作業中の実機通電・通信・モーター制御は行わない。

## Onshape取り込み・検証・URDFの保存点

[2026-09-26の成果と手順](studies/onshape-20260926/README.md)。短縮D405候補の公開V2、URDF、スクリーンショット付きマニュアル、作業記録を保存。次の低位置カメラ・爪延長設計の比較基準です。
