# CAD再構成ツールのレビューと改善記録

対象: `skills/cad-reverse-parametric`、特に `studies/xl430_lowcost/parts/elbow_to_wrist.py`。
開始時のコミット: `ecdc3e6`。作業ブランチ: `fix/cadre-geometry-review-20260918`。

依頼は、DynamixelアームのPython CAD処理をレビューして改善し、Playwrightで確認しながらスキルも改善すること。
リポジトリ内の `cad-reverse-parametric`、`playwright-cli`、`skill-creator` の手順を使用した。

## レビュー結果

### P1: 元STEPの外周を穴と誤認していた

元の `hardware/follower/step/elbow_to_wrist.step` のφ18.124円筒面は、二枚の板の丸い外周である。
面の向きはconvex、軸方向の範囲はY[6.5,9.5]とY[39,42]だった。
旧実装とintent YAMLは、これを「Y=42から深さ4mmのホーン座ぐり穴」と扱っていた。

また、φ2の8面はY[8.3,9.5]とY[39,40.2]に分かれる。
「4軸・8面だから4本の深さ6mmの止まりタップ穴」という旧説明は成立しない。
径から付けた `M2-tap` というラベルだけでも、ねじの用途は確定できない。

原因は `hole_families` が凸面と凹面を混在させ、穴の中心を軸に垂直な面へ投影して奥行きを捨てていたこと。
この一覧が一致しても、外周と穴の取り違えや、一方の板の欠落を検出できなかった。
修正前のXL330条件の生成モデルは、元STLに対して体積が約279.499%増加していた。

改善: `inspect` に `surface_sense`、`axial_range_mm`、`angular_span_deg` を追加。
`bore_families` と `outer_cylinder_families` を分けた。既存の `hole_families` は互換性のため残し、
未分類の円筒面一覧であることを `hole_families_semantics` とドキュメントに明記した。
面の内外の判定は、外向きに向き付けられたsolidを前提とする。

### P1: 穴の加工方向と位置が誤っていた

CadQueryの `XZ` 面の法線は-Y方向。
旧 `_blind_seat_y()` は押し出しを+Yと解釈していたため、狙いのY[38,42]ではなくY[34,38]を切っていた。
その結果、入口のY=41.9には材料が残り、外から入れない空洞ができていた。
共通の `blind_seat()` もY軸だけ符号が逆だった。

改善: 世界座標で指定する加工方向をワークプレーンの法線に変換し、elbowも共通関数を利用するようにした。
X/Y/Zと正負の6条件で、入口の空隙、指定深さ、底の材料を確認するテストを追加した。
elbow試作モデルでは、ポケットのY=41.9と38.1が空隙、37.9が材料であることを検査する。
小径穴についてもY=36.1が空隙、35.9が材料であることを確認する。

旧 `measure_section.py` は円筒面の長さが4mmであるだけで止まり穴と判定していた。
これも入口・底・位置を確認する方式に修正した。円筒面の長さや個数だけでは止まり穴の証拠にならない。
公式根拠: [CadQueryのPlane定義](https://cadquery.readthedocs.io/en/latest/_modules/cadquery/occ_impl/geom.html)。

### P1: 同等性に失敗してもXL430版を正常終了で生成していた

旧CLIは `C_A1_gap_to_real.equivalent=false` を表示しながら、XL430版を出力して終了コード0を返した。
参照STEP/STLが欠けても検査を省略したまま進めていた。

改善: 同等性不合格は `blocked_non_equivalent`、参照欠落は `blocked_missing_reference` とし、終了コード2を返す。
通常のXL430版は出力しない。ブラウザ診断用の `--export-prototype` を明示した場合だけ
`*_xl430_prototype.step/stl` を出力するが、検証結果も終了コードも不合格のままにする。
結果は標準出力と `elbow_to_wrist_review.json` に保存される。

**今回、XL430置換設計そのものを完成させたわけではない。**
穴加工の実装を直しても、試作モデルの体積差は約279.127%であり、元形状とは異なる。
原形状に沿った局所変更の設計、実際の取付面・ねじ・軸の確認、隣接部品との組立確認は残っている。
旧 `outputs/parts` / `outputs/print` の生成物は今回の合格品ではない。
形状の読み込み成功やwatertightだけを根拠に、これらを組立可能とは扱わない。

### P2: 記載どおりの単体実行が失敗していた

`uv run python studies/xl430_lowcost/parts/elbow_to_wrist.py ...` は、
`ModuleNotFoundError: No module named 'domain'` で停止した。
既存テストが `sys.path` を補っていたため、通常のCLI実行の問題を隠していた。

改善: スクリプト自身がstudyのimportパスを解決するようにした。
`PYTHONPATH` を外した新しいPythonプロセスでCLIを起動する回帰テストを追加した。

## 検証

修正前の既存テストは **48 passed**。新しい回帰テストは修正前に **9 failed / 4 passed** となり、
Y方向の加工、閉じた入口、円筒面の誤分類、CLIの起動と不合格処理を検出した。
実装修正後、最初の対象テストは **15 passed**。断面検査の回帰も追加した最終の全体テストは
**63 passed in 343.17s**。追加した回帰テストは計15件。
`git diff --check` も通過し、`hardware/` の差分はない。

Playwrightの専用セッション `cadre-review-20260918` でローカルChili3Dを操作し、
元STEP・修正前・修正後の3モデルを読み込んだ。DOMで読込を確認したうえで、
各タブを1440x1000に揃え、X/Y/Zの3方向、計9画面を記録した。
ジズモの現在位置からクリック座標を求め、カメラが指定軸に向いたことも確認した。
画面に表示された形状をB-repの実測と照合した。+Y方向では旧モデルの入口が閉じ、
修正後の試作モデルではポケットが開いている。一方、元STEPは丸い板と4穴であり、
修正後のモデルとも異なることを確認した。レビュー出力は次の場所に分離している。

```text
skills/cad-reverse-parametric/outputs/review-20260918/
  before/       修正前の生成STEP/STL
  after/        修正後の診断用STEP/STLとJSON
  original-*.png / before-*.png / after-*.png
```

+Y方向の比較画像:
[元STEP](../skills/cad-reverse-parametric/outputs/review-20260918/original-y.png)、
[修正前](../skills/cad-reverse-parametric/outputs/review-20260918/before-y.png)、
[修正後の診断用モデル](../skills/cad-reverse-parametric/outputs/review-20260918/after-y.png)。
これらの生成物はローカルのgit管理対象外であり、画像がない環境では上記手順で再生成する。

再現コマンドはskillディレクトリから実行する。

```bash
uv run pytest -q
uv run python studies/xl430_lowcost/parts/elbow_to_wrist.py \
  --out outputs/review/elbow --samples 1000
# 現状の正しい結果: blocked_non_equivalent / exit 2 / XL430版は未出力
```

## スキルへの反映

`SKILL.md` と `references/workflow.md` の「円筒面＝穴」「面数から貫通性が分かる」という説明を是正した。
`references/geometry-review.md` に、内外の識別、入口・底の実測、単体CLI検証、失敗時の出力制御をまとめた。
`references/chili3d_viewing.md` に今回のブラウザ確認で得た注意点を追加した。
skill-creatorの `quick_validate.py` は **Skill is valid!**。

この変更はリポジトリ内のCADスキルが対象で、元の `hardware/` のSTEP/STLを置き換えていない。
