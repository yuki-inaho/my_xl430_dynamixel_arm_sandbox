# 今回の取り込み・Pixi/OCCT 8追試

[取り込みレビュー](../../../docs/D405_LOW_PROFILE_INTAKE.md) と [verification.json](verification.json) が
今回の記録。隣の `revalidation/` は受領した別エージェントの記録であり、別実行として保持する。

## 元環境の追試

repo rootから実行する。Linux用の固定lockを使い、既存の出力を上書きしない。
以下の変換はCADファイルを読み、ローカルファイルを作る。Onshapeへのアクセスは不要。
Git取得と依存パッケージの取得にはネットワークが必要。

```bash
RUN=$(mktemp -d temp/d405-occt8-XXXXXX)
CONVERTER="$RUN/converter"
BASE=studies/low-profile-20260926/outputs/low-profile-250g
rtk proxy git clone --single-branch --branch codex/pixi-occt8 https://github.com/yuki-inaho/urdf_from_step.git "$CONVERTER"
rtk proxy git -C "$CONVERTER" checkout --detach 1b2cea31c56b875bf98c1d65084781322f5fc835
rtk proxy pixi install --manifest-path "$CONVERTER/pixi.toml" --locked
rtk proxy pixi run --manifest-path "$CONVERTER/pixi.toml" --locked versions
rtk proxy pixi run --manifest-path "$CONVERTER/pixi.toml" --locked test
rtk proxy pixi run --manifest-path "$CONVERTER/pixi.toml" --locked build
PY="$CONVERTER/.pixi/envs/default/bin/python"
rtk proxy "$PY" -I -m pip install --no-deps "$CONVERTER/dist/urdf_from_step-0.2.0-py3-none-any.whl"
rtk proxy "$PY" -I -m urdf_from_step "$BASE/CAD/final-version.step" --config "$BASE/robot/converter-config.json" --output "$RUN/model"
rtk proxy uv run --no-sync python "$BASE/robot/replay_step.py" --output "$RUN/replay"
rtk proxy "$PY" "$BASE/robot/validate_robot.py" --model "$RUN/model" --native "$RUN/replay/native-pose-transforms.json" --output "$RUN/verification.json"
```

`python -I` でソースツリーのPYTHONPATHを除外し、インストールしたwheelを用いて変換する。
kernelはPixiのOCCT 8.0.1配布バイナリであり、OCCTソース自体の再コンパイルではない。
CadQuery/OCPで行うSTEPの独立読込はrepoのuv環境を使う。
CLIの生ログには環境のパスが出るため、`RUN` はGit対象外に置く。

## 証跡の読み方

- `verification.json`: D6保存監査・D7実行の区別、archive SHA、kernel/wheel情報、結果、未確認項目。
- `kinematics.json`: 新規OCCT 8変換と今回の独立STEP再読込の照合。
- `native-pose-transforms.json`: 今回の11姿勢の独立読込から作った入力。
- `converter-tests.xml`: 今回の変換器13試験。
- `robot-tests.xml`: 取り込み・修正後の改善版52試験。
- `cad-tests.xml`: 保存検査補強後の20試験。変更前の18件に2件追加。
- `geometry-preservation.json`: 保存された実V2の爪/パッドとR5原本の照合。
- `artifact-equality.json`: 新規URDF/config/12 STLと受領した最終V2の全バイト一致。
- `quality.json`: lint・プライバシー照合と、既存19ファイルの整形不一致。
- `manifest.json`: 共有可能な取り込みファイルの最終SHA。元manifestの代わりに検査する。

取り込み時にテキストの個人パスを除去したため、元の `SNAPSHOT-MANIFEST.json`、
`INPUT-SNAPSHOT-MANIFEST.json`、旧XML/JSON内のSHAは原本に対する履歴である。
元bundleは取り込み前に1599件の全ファイル照合がPASSした。原本はGit対象外で保管する。
このディレクトリのログも個人パスを除いた写しであり、バイト同一の生ログとは呼ばない。

生成モデルは受領モデルと全バイト一致したため、同じ大きなSTLを二重にGitへ追加しない。
新規生成モデル・wheel・生ログ・各姿勢の完全inventoryはローカルの
`temp/intake_d405_20260926/occt8-original/` に残す。
