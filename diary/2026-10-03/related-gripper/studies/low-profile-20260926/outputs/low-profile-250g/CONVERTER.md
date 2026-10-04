# STEP→URDF変換器 — Pixi / OCCT 8.0.1

**継続作業注記:** 以降のbuild/convert記録は引き継ぎ前の実行である。
今回の [独立再検証](../../revalidation/README.md) は旧D6/D7の証跡監査と検証器改善を行い、
Pixi/OCCT8の再ビルド・再変換は実施していない。新しい検証器は--modelで別出力先を指定できる。

## 入力と実装計画（2026-09-26）

ユーザー所有の [yuki-inaho/urdf_from_step](https://github.com/yuki-inaho/urdf_from_step) を新規cloneした。開始commitは `ebe40d9e9d95c9b170d4ac1cee5ee47db625f10f`、既存差分なし、専用指示ファイルなし。変更は `work/urdf_from_step` の `codex/pixi-occt8` ブランチで行い、既存ROS経路を保持する。

[公式OCCT latest](https://github.com/Open-Cascade-SAS/OCCT/releases/tag/V8.0.1) は **8.0.1**、tag `V8.0.1`、commit `b8f597c677811d1f9f4d8a97f5ae2825c0353a42`。conda-forgeのlinux-64にはOCCT/pythonocc-core 8.0.1が存在する。Pixi 0.79.0は既存 `pixi` を利用する。古い検索キャッシュではpythonocc 7.9がlatestと表示されたが、実パッケージ検索結果で8.0.1を確認した。

1. `pixi.toml` / `pixi.lock` にPython、pythonocc-core、OCCT、数値/試験/ビルド依存を固定する。OCCTは配布済みバイナリを使い、変換器のPython wheelを実際にビルド・実行する。OCCT自体を今回ソースコンパイルしたとは表現しない。
2. ROS不要のCLIを追加し、STEP読取・XCAF階層/配置・STL生成をOCCT 8.0.1で実行する。旧readerの不要な旧API importとrospy依存を整理し、従来の関数契約も保つ。旧ROS起動経路を削除しない。
3. 名前に関節を符号化する既存形式に加え、通常CAD用の明示JSON設定を受け付ける。曖昧な部品所属、未所属、重複所属、不正な関節木、未定義の軸/単位はエラーにする。
4. 小STEPで名前・入れ子/反復配置・mm/inch単位・複数solidを検査し、不正入力も拒否する。今回のV2 STEPから12剛体メッシュとURDFを新規生成する。
5. 閉路はURDF木と別の制約・受動関節計算で扱い、既存基準の441姿勢（閉路1e-6m）、11 native姿勢（2e-5m/2e-5rad）を新出力で検証する。標準UI URDFの値や古いメッシュを最終出力へ流用しない。

## 今回の入力契約

- STEP: `CAD/final-version.step`、Onshape V2 `f6162b4adc88af9d07f1194a`、SHA256 `9f58c947753e9229b30939da23ce4c87c1cc85eeb39372518de4ffb98991b93f`。
- 262 occurrence / 207 solids / 55 sheets。全occurrenceを一度ずつ所属させ、同名の複数実体も数で検査する。面部品を勝手にsolidと扱わない。
- 12剛体は `reports/expected-groups.json` の部品名・数、関節位置/軸/リミットは `robot/joint-definitions.json` を根拠に設定する。STEPだけから関節意味を推測しない。
- CAD座標はZ上、OCCT読取長さはmmに正規化し、URDF/STLはm。各linkの原点とmeshの局所変換を明示する。
- カメラ本体固定原点は(-0.2,165,235)mm、手首URDFリミットは[-102,124]°。
- 質量/材料未確定のため動力学対応を偽装しない。effort/velocityやinertialが未校正であることを出力に記す。

実装・ビルド・回帰の結果は以下へ追記する。現時点は計画であり、動作確認済みとは扱わない。

## ビルドと実行環境

Pixi install成功。Python 3.12.14、pythonocc-core 8.0.1、OCCT 8.0.1（conda build `all_hbfeb9d6_201`）を実行した。`/proc/self/maps` で実ロード先が `libTKernel.so.8.0.1` と確認できた。`pixi run build` は `urdf_from_step-0.2.0-py3-none-any.whl` を生成し、`pip install --no-deps` 後にPYTHONPATHを空にした実行でもsite-packagesから読み込めた。`reports/converter-runtime.json` と `reports/converter-build.log` に保存。

実装はROS不要CLI、mmへ明示正規化するXCAF reader、全occurrenceの一意所属/数/木構造検査、m単位の新STLとURDF生成、従来命名からの設定下書きを追加した。旧ROS reader関数名を互換入口として維持し、反復部品の同名統合を防止する。従来のROS起動/RViz自体は未検証。新CLIの形状回帰・今回モデル変換は次の検証項目で行う。

## 途中保存時点の回帰結果

小STEPの13試験がPASS（`reports/converter-tests.xml`）。mm/inch、同名・同位置の反復、入れ子配置、複数solid、メッシュのm単位、不正な関節木/軸/リミット/部品所属の拒否を含む。最初はOCCT 8の色取得bindingで11件失敗した。`XCAFDoc_ColorTool.GetColor` をクラス経由で呼ぶ修正後に通過し、失敗ログも `converter-tests-red-color.xml` に保持した。

実モデルのV2 STEPも262 occurrenceをOCCT 8.0.1で読めた（`reports/converter-v2-intake.json`）。ruffとwheel再ビルドも成功。**今回モデルのURDF生成、441閉路、11姿勢のFK照合は、このcommit/push時点では未完了**。最終マニュアル・スキル更新も後続項目であり、途中保存をDoD完了とは扱わない。

## 実モデル変換・照合の完了結果

上記途中保存後に、V2 STEPを指定変換器で実変換した。16 links / 15 joints / 12新STL、262 occurrenceを全て所属させた。5能動・4受動・6固定関節。`robot/model` が今回の出力であり、旧版のメッシュや標準UI URDFを転用していない。

441閉路サンプルの最大残差は **3.46945e-17 m**（基準1e-6 m）。11 native姿勢の最大差は **8.78488e-9 m / 5.33710e-8 rad**（各2e-5）。ゼロ姿勢行列誤差2.78e-17。`robot/validation.json` が今回データ。これは数値的な運動学の一致であり、CAD/実機の寸法精度をnmで保証する意味ではない。

4件の照合試験は、正常V2の受理、実V1のパッド逆所属の拒否、yaw軸反転の拒否、並進単位1000倍の拒否を検証した。最後の負対照は初回に並進0のyawを選んで無効となり、並進がある肩姿勢に直した。失敗XMLも保持した。

## 再実行

変換器は [codex/pixi-occt8](https://github.com/yuki-inaho/urdf_from_step/tree/codex/pixi-occt8)、checkpoint commit `1b2cea3`。作業場では以下を変換器ディレクトリから実行した。`pixi` がPATHになければ `pixi` を使う。

```sh
cd temp/intake_d405_20260926/converter
pixi install --locked
pixi run versions
pixi run test
pixi run build
pixi run convert ../../outputs/low-profile-250g/CAD/final-version.step \
  --config ../../outputs/low-profile-250g/robot/converter-config.json \
  --output temp/low-profile-robot-recheck
pixi run python ../../outputs/low-profile-250g/robot/validate_robot.py \
  --model temp/low-profile-robot-recheck --output temp/low-profile-robot-recheck-validation.json
pixi run pytest -q ../../outputs/low-profile-250g/robot/test_validation.py
```

出力先は新規/空ディレクトリを指定する。既存結果の暗黙削除はしない。継続作業で更新した最後のvalidateは `--model` の新規出力を直接検証し、`--output` は未作成ファイルだけを受け付ける。上記は元PCの配置を前提とした例で、この継続環境ではPixi再実行していない。移設可能なコマンドは継続作業READMEを参照。`converter-config.json`、`joint-definitions.json`、`reports/expected-groups.json` が関節/所属の根拠。STLはm単位のCAD世界座標、visual/collision originに逆link座標、joint originに親子相対座標を使う。

## 残る制約

`pg3_states.py` の非線形従属計算が必要で、通常の線形mimicでは閉路を表現できない。質量/慣性は推測していない。effort/velocityの0は未設定の運動学用placeholderであり、実機コマンドの定格ではない。55面部品があるためcollision STLのwatertight/convex性や物理エンジン互換も保証しない。元ROS launch/RViz経路、非Linux環境、造形強度、疲労、実機校正は未検証。カメラ固定linkの原点は校正済みoptical frameではない。
