# STEPからスライサー投入データまで

STEPはCAD交換形式であり、Creality K1CなどのFDMプリンタへ直接渡す印刷データではない。印刷工程では、CAD検査済みのSTEPからSTLを用意し、メッシュ検査を通したうえでOrcaSlicerへ渡す。

## 成果物の分離

次の4種類を同じディレクトリで混ぜない。

| 区分 | 用途 | 完成扱い |
|---|---|---|
| `STEP/` | CAD形状の保存・再編集・出典確認 | CAD保存用。印刷可否は別判定 |
| `STL/` | スライサー入力 | watertight、volume、winding、異常edgeゼロが必要 |
| `GCODE/` | プリンタに渡す最終データ | スライサー成功、部品数、開始/終了マクロ、危険な温度命令を検査 |
| `validation/` | 入力ハッシュ、寸法、判定、生成ログ | 再現性の証跡 |

旧生成物のファイルが存在することは、承認の根拠にしない。設計レビューでブロックされた部品は、メッシュが閉じていても印刷パッケージへコピーしてはならない。

## 推奨コマンド

XL430 studyの印刷パッケージは次で作る。通常のCAD・メッシュ検査を先に実行し、印刷許可リストを確認してから使う。

```bash
cd skills/cad-reverse-parametric
rtk uv run python studies/xl430_lowcost/validate_print_readiness.py --repair
rtk uv run python studies/xl430_lowcost/prepare_print_package.py \
  --source-dir outputs/print \
  --output-dir outputs/xl430_print_package \
  --slice \
  --enable-support \
  --orca ~/Applications/OrcaSlicer.AppImage
```

`prepare_print_package.py` は、承認済み部品を明示的なallow-listで選び、元のSTEP/STLを上書きせずにパッケージへコピーする。`elbow_to_wrist_xl430` のように設計レビューで未承認のものは、ファイルが残っていても除外する。

## OrcaSlicerの実行

GUIを開かずにAppImageを一時展開し、`xvfb-run`でヘッドレス実行できる。プロファイルはインストール済みファイルを直接編集せず、パッケージ配下へコピーして局所変更する。

- プリンタ: Creality K1C / 0.4 mm nozzle
- プロセス: 0.20 mm Standard
- フィラメント: CR-PLA @K1C
- 自動配置: `--arrange 1`
- スライス: `--slice 0`
- 壁: 初期試作では3周を基準にする
- サポート: 形状に浮き領域警告が出る場合は有効化し、警告が消えたことを確認する
- `M191`（チャンバー温度待ち）は、プリンタ側マクロの対応を確認できない限り出力しない。プロファイルの`chamber_temperature`を0にして、生成G-codeにも`M191`がないことを検査する

`--export-3mf`は環境によって出力パスを二重連結して失敗してもG-codeを残すことがある。印刷パッケージの自動化では、3MF出力の成功を前提にせず、G-codeと`result.json`を個別に検証する。

## 2026-09-19フォロワー幾何改訂

混在サーボ構成の改訂CADは、まず次で元STEPのハッシュ、保存後STEP、7部品のB-rep/STL、基準姿勢の干渉を検証する。

```bash
cd skills/cad-reverse-parametric/studies/follower_geometry_revision
rtk uv run python source/rebuild.py --render
rtk env CAD_RELEASE_DIR=../../outputs/follower_geometry_revision \
  uv run python -m pytest -q source/test_revision.py
rtk uv run python prepare_print_package.py
```

7部品はK1Cの造形範囲のため、通常は複数プレートになる。`prepare_print_package.py`は`plate_N.gcode`をすべて保存し、各プレートの部品定義、スライサー警告、`START_PRINT`/`END_PRINT`、`M191`を検査してから`passed: true`を出す。1プレートだけを確認して残りを無視してはならない。

## 全XL430置換後の再検査ゲート

別構成で検証済みのSTLを流用できても、モーターや購入部品を置換した新しい組立に、その検証結果をそのまま継承してはならない。印刷パッケージ作成前に、置換後の組立STEPを再読込し、少なくとも次を新しい構成に対して再実行する。

- モーターoccurrence数と置換manifest
- 取付穴軸、基準面、ねじ・スペーサーのスタック
- 静止基準姿勢の外部部品間体積干渉
- 必要な関節範囲の離散姿勢と連続掃引干渉

`studies/all_xl430_revision/`はこのゲートの例である。6台のXL430と217末端要素は再現できたが、置換後の静止干渉が54件あり、全XL430版の穴軸レポートもないため、`prepare_print_package.py`は失敗終了する。基準モデルの干渉0件、閉じた7個のSTL、スライサー成功のいずれも、この不合格を上書きしない。

## 超音波カッターケース作業から引き継いだ運用

2026-09-18の超音波カッターケース作業では、入力アーカイブを展開してREADMEと形状を確認し、OrcaSlicerのAppImageを`xvfb-run`でヘッドレス実行した。今回のXL430パッケージも、次の運用上の判断を引き継いでいる。

- GUI操作の成否ではなく、`result.json`、G-code、部品名、警告の有無を機械的に検査する。
- プロファイルはインストール先を直接変更せず、出力パッケージへコピーしてスライス時の変更値を保存する。
- プロファイル由来のチャンバー待ちなど、対象プリンタのマクロ契約が不明な命令は生成物から除外して検査する。
- OrcaSlicerが「浮いている領域」などの警告を出した場合、警告を無視せず、向きまたはサポートを見直してから再スライスする。
- USBやプリンタへ渡すのは、検証レポートの`passed: true`を確認したG-codeだけにする。

## G-codeの最低限の検査

次を満たさなければ、プリンタへコピーしない。

- OrcaSlicerの`result.json`が`return_code=0`かつ`error_string=Success.`
- 全プレートの`EXCLUDE_OBJECT_DEFINE`を合算して期待した部品数と一致する
- 各部品名が全プレートのG-codeに1回ずつ現れる
- `START_PRINT`と`END_PRINT`がある
- `M191`がない
- レイヤー数、推定時間、フィラメント量を検証レポートへ残す

## 実機確認の順序

メッシュ検査とG-code検査は、組付けや強度を証明しない。初回は本番部品を一度に刷らず、次の順で確認する。

1. 実機の取付穴・軸・ねじを確認するための小型試験片を用意する
2. 薄い試験片を印刷し、実機部品で嵌合を確認する
3. 問題がなければ本番部品を印刷する
4. 組立、可動域、干渉、配線、発熱、強度を別記録に残す

試験片の寸法や変更量を根拠なく作らない。インターフェースの実測値または設計仕様がない場合は、印刷可能な本体と実機適合未確認を明確に分ける。
