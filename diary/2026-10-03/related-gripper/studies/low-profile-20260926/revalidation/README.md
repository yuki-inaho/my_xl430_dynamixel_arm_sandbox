# 継続作業 — 検証器の誤合格防止と実STEP再検証

## 結果と証跡

入力コミット: `bba1f4e0762b35f84ebe8d3cfaaf41180e453831`。
入力ZIPのcommentとGitHub対象ブランチの先頭を照合し、元snapshot 327ファイルのSHA256が全件一致した。
詳細は [input-integrity.json](input-integrity.json)。

|検査|今回の結果|証跡|
|---|---|---|
|旧D6/D7|保存証跡の監査完了。新しいOCCT8実行ではない|[handoff-audit.json](handoff-audit.json)|
|修正前の12負対照|11件が誤受理されテスト失敗、1件は元から拒否|[hardening-red.xml](../../../../../../../3d-printed-dynamixel-gripper/studies/low-profile-20260926/revalidation/hardening-red.xml)、[log](../../../../../../../3d-printed-dynamixel-gripper/studies/low-profile-20260926/revalidation/hardening-red.log)|
|修正後の全試験|既存4件＋追加48件、52 PASS|[full-tests.xml](../../../../../../../3d-printed-dynamixel-gripper/studies/low-profile-20260926/revalidation/full-tests.xml)、[log](../../../../../../../3d-printed-dynamixel-gripper/studies/low-profile-20260926/revalidation/full-tests.log)|
|STEP本体の再読込|11×262＝2,882部品姿勢、baseline込み3,144件|[再抽出JSON](step-replay/native-pose-transforms.json)、[log](../../../../../../../3d-printed-dynamixel-gripper/studies/low-profile-20260926/revalidation/step-replay.log)|
|閉路441状態|最大3.469446951953614e-17 m、基準1e-6 m|[再読込後の検証](kinematics-step-replayed.json)|
|11姿勢FK|最大8.784880096336909e-9 m / 5.3371044601806986e-8 rad、基準各2e-5|同上|
|実V1不良対照|爪のmemberに5.16416212733822 mmの相対移動、正しく拒否|[failure.json](v1-step-negative/failure.json)、[log](../../../../../../../3d-printed-dynamixel-gripper/studies/low-profile-20260926/revalidation/v1-step-negative.log)|

CAD寸法、STEP/STL、URDF、関節設定、元の許容値は変更していない。
小さい数値誤差は同じCAD由来の座標計算が一致したという意味で、実物のナノメートル精度ではない。

## 修正内容

`robot/validate_robot.py` は11件という数だけでなく、定義済みの11姿勢を重複・欠落なく含むことを検査する。
有限値、正しい4×4剛体変換、全12グループの部品数・所属、固定V2と入力SHAを検査する。
URDFのリンク/関節/軸/制限/原点を設定JSONと照合し、visualとcollisionのメッシュ・原点・scaleも検査する。
外部パス、親ディレクトリへの参照、モデル外へのsymlink、不一致ハッシュを拒否する。
`assert` に依存せず、不正データは非ゼロ終了する。

`--model` は検証したい出力ディレクトリ、`--native` はSTEPを独立再読込した姿勢情報。
デフォルトは標準出力のみ。`--output` は未作成ファイルだけに書き、過去の `robot/validation.json` を更新しない。
本検証器は**この固定V2用**であり、任意の新設計を受け入れる汎用ロボット検証器ではない。

`robot/replay_step.py` は付属 `scripts/assembly_io.py` のXCAF readerを使い、STEPを直接再読込する。
全構成部品の名前・数・solid/sheet・面数・局所boundsを照合し、同名部品の繰返しも保持する。
代表部品だけでなく全memberの剛体運動、5能動関節の角度とpivotを確認する。
各姿勢の全262件を新しいJSONへ保存し、途中失敗は成功として扱わない。
局所bounds/面数の一致は形状同値性や強度の証明ではない。

## 実行環境

今回実測: Python 3.13.5、NumPy 2.3.5、SciPy 1.17.0、trimesh 4.11.1、pytest 9.0.2。
STEP再読込だけに CadQuery 2.8.0、cadquery-ocp 7.9.3.1.1 を使用。
元PCのrtk、Pixi、pythonocc-coreと元R5 STEPは本環境にない。外部シェルDNS取得も失敗した。
固定converter commitとlockはGitHub connectorで読んだが、新しいlocked install/build/convertは未実施。
元の13 converter＋18 CAD試験は過去XMLの監査であり、この52件に合算しない。

今回は既存環境を `uv run --no-project --offline --python python python ...` で明示使用した。
このパスは本環境固有。利用者側では次の `PY` を適切なPythonに設定する。
requirementsは直接依存の版記録で、全推移依存のlockではない。新規環境構築の再現試験も未実施。
既存のroot uv.lock（元CAD環境）は書き換えていない。

## 追試コマンド

展開したリポジトリのルートで実行する。ネットワーク、Onshapeログイン、APIキーは不要。
依存パッケージの事前準備だけは別途必要となる。

新規環境を用意する場合の例は `python3.13 -m venv temp/d405-venv`、
続いて `temp/d405-venv/bin/python -m pip install -r studies/low-profile-20260926/revalidation/requirements-cad.txt`。
これはネットワーク取得を伴う準備例であり、この新規インストール自体は今回未試験。
運動学検査だけならrequirements-kinematics.txtを使用する。

```sh
BASE="$PWD/studies/low-profile-20260926/outputs/low-profile-250g"
PY=python
RUN="$(mktemp -d)"

# 保存モデルを検査。既存validation.jsonは触らない。
"$PY" "$BASE/robot/validate_robot.py" \
  --model "$BASE/robot/model" --output "$RUN/saved-model.json"

# 52件。生成キャッシュは検証成果と区別する。
"$PY" -m pytest -q \
  "$BASE/robot/test_validation.py" \
  "$BASE/robot/test_validation_hardening.py" \
  "$BASE/robot/test_validation_contract.py" \
  "$BASE/robot/test_replay_step.py" \
  --junitxml="$RUN/tests.xml"

# STEP再読込。replayは新規ディレクトリでなければ拒否する。
"$PY" "$BASE/robot/replay_step.py" --output "$RUN/replay"
"$PY" "$BASE/robot/validate_robot.py" \
  --native "$RUN/replay/native-pose-transforms.json" \
  --output "$RUN/fresh-step-model.json"
```

V1不良対照は次のコマンド。**非ゼロ終了が期待値**である。

```sh
"$PY" "$BASE/robot/replay_step.py" \
  --pose-dir "$BASE/CAD/native-poses/diagnostics/v1-pad-misassigned" \
  --output "$RUN/v1-negative"
```

新規再変換先の検査は
`"$PY" "$BASE/robot/validate_robot.py" --model outputs/fresh-robot --output "$RUN/fresh-conversion.json"`。
このコマンド自体は変換ではない。変換器については [CONVERTER.md](../outputs/low-profile-250g/CONVERTER.md)。

## 失敗履歴の読み分け

`hardening-initial-import-error.*` はpytest import modeの選択ミス、
`patch-not-applied-tests.*` はpatch未適用時の失敗、`step-replay-interrupted/` はtool時間制限による途中中断。
いずれも成功回数には含めない。完成した結果は上表のファイルを使う。
`kinematics-hardened.json` は保存JSONを用いた検査、`kinematics-step-replayed.json` はSTEP再抽出後の検査。
元の `robot/validation.json` と過去XMLは履歴として保持する。
物理的FAIL/UNKNOWN、未実施のOCCT8再変換、運用上の注意は [REVIEW.md](REVIEW.md) を参照。

## アーカイブ展開後の追試

[packaging-rehearsal.json](packaging-rehearsal.json) にtar.zstの作成・zstd検査・別配置への展開・
全ファイルSHA256照合を記録した。展開先でも [52試験](../../../../../../../3d-printed-dynamixel-gripper/studies/low-profile-20260926/revalidation/relocation-tests.xml) が通り、
11姿勢のSTEPを再読込して [441/11検証](relocation-kinematics.json) を実行した。
再抽出した姿勢JSONは元の再抽出結果とSHA256まで同一だった。
意図的なファイル改変と未登録ファイルの混入も、整合性検査器がそれぞれ非ゼロ終了で検出した。
これは同じ依存環境での別配置試験であり、新規インストール試験ではない。
リハーサル後に作業記録を封入して最終archiveを再生成するため、上記JSONのarchive SHAは
最終提出物のSHAとは異なる。最終提出物は同梱外の `.tar.zst.sha256` で識別する。