# 次エージェントへの引き継ぎ — Onshape低配置D405

> 継続作業後の入口はリポジトリ直下の START_HERE_ja.md と diary/handoff_Sep26-2026_low_profile_continuation.md。
> 以下は20:20 JST時点の保存記録。旧D6/D7はその後に証跡監査し、別環境で検証器を改善した。

**引き継ぎ日時: 2026-09-26 20:20 JST。ユーザー指示により実作業をここで止め、保存と引き継ぎへ切り替えた。**

## 最初に読むもの

1. [作業書](WORKDOC.md) が正本の写し。通常36/36項目完了、DoDはD1〜D5完了、**D6とD7が未チェック**。完成済みと誤認しない。
2. [人向け20ページマニュアル](MANUAL.pdf) / [HTML](MANUAL.html)、[比較REPORT](REPORT.md)。19画像、実メニュー・失敗・修復を記載。
3. [最終レビュー](final-review.md)、[API-USAGE](API-USAGE.md)、[CONVERTER](CONVERTER.md)、[URDF検証](robot/validation.json)。
4. [スキル案内](skills/ONSHAPE-WORKFLOW.md)。設計repo直下 `skills/` に4スキル13ソースを参照/agents込みで保存済み。

直近のユーザー追加指示は「skillsをリポジトリskills/へcommit漏れなく」「作業書をdiary/へcommit/push」「続きは別エージェントへ。引き継ぎ文書もcommit/push」。新しい設計や試験を勝手に進めず、現在点を残した。引き継ぎ先へメッセージ送信や新規チャット作成は行っていない。

## 作業場所とGit

|用途|場所 / ブランチ|
|---|---|
|元の作業場|`studies/onshape-20260926`（親自体はGit外）|
|正本workdoc|`work/temp/workdoc_Sep26-2026_low_profile_d405.md`|
|ユーザー成果物|`outputs/low-profile-250g/`|
|今回コード|`work/low-profile/`|
|設計Git checkout|`work/gripper-low-profile`、`codex/onshape-low-profile-d405`|
|設計保存コピー|repo内 `studies/low-profile-20260926/`|
|変換器Git checkout|`work/urdf_from_step`、`codex/pixi-occt8`|
|作業書/レビュー/引き継ぎ|設計repo内 `diary/*Sep26-2026_low_profile_d405.md`|

設計originは `https://github.com/yuki-inaho/3d-printed-dynamixel-gripper.git`。途中保存 `6117edb`、**最終実体成果物 `00bd70c4e995788298d98e9de78f0e5e6d70ca35`** をpush済み。引き継ぎ記録はその後続commitへ保存する。変換器originは `https://github.com/yuki-inaho/urdf_from_step.git`、**`1b2cea31c56b875bf98c1d65084781322f5fc835`** をpush済み。両remote SHAをls-remoteで確認した。PR作成・mainへのmergeはしていない。

元repo `.` は変更していない。`../low_cost_robot` には本作業と無関係な未追跡4ファイルがある。HN11アイドラのintent/parts/validate/testで、削除・commit・修正していない。今後も他作業として保持する。

全shellコマンドは `rtk` を先頭に付ける（`RTK.md (local instruction)`）。ユーザーはFree/public、headless、直接Onshape API最小化、250g payloadを指定。材料・造形方向は未指定。印刷、通電、購入は行っていない。

## 再開順序

1. `start-work-with-docs` に従い正本と現在の未チェック項目を確認し、`date "+%Y-%m-%d %H:%M:%S %Z%z"` で開始を記録する。引き継ぎ時点でactive-itemはなし。残りをまとめてチェックしない。
2. **D6**: `API-USAGE.md` の操作一覧・例外なし・直接API0・旧ローカルcounter526不変・キャッシュ利用を証跡と照合する。本文と証拠は既に揃うが、最終DoDチェックは未実施。
3. **D7**: Pixi lock、公式OCCT8.0.1根拠、実ロードkernel、wheel、13小STEP試験、V2実変換、441/11照合、保存commitを照合する。実装/実行は完了し、最後のDoD照合だけ未実施。
4. 各チェック直後にlog_work.pyで記録し、必要なレビュー追記を行う。成果物・`skills/`・`diary/` の内容を同期し、限定pathspecでcommit/pushする。今回の引き継ぎ保存を全DoD達成とは扱わない。
5. その後に新しい設計改善をするなら、材料・実物荷重/トルク/摩擦等の前提を新作業書へ分離する。既存のUNKNOWN/FAILを理由なくPASSへ変えない。

## 現在のOnshape

推薦する比較版は [V2 Low profile D405 - corrected jaw pads](https://cad.onshape.com/documents/29e8557c76e89bcf64f50566/v/f6162b4adc88af9d07f1194a/e/d5415bf725ba822741b01703)。

- Document `29e8557c76e89bcf64f50566`、workspace `6bce790334ee57d808213530`。
- Part Studio `2195f3c400eb079287ae06af`、Motion Assembly `d5415bf725ba822741b01703`。
- V2 `f6162b4adc88af9d07f1194a`。12 composites、12 instances、13 mates、baseだけ固定。
- V1 `4577cc931e9bc290e2b31032` は左右pad誤所属の失敗版。最終として使わない。
- 以前の75°compact文書は `7b85d8922959cbe564b6e0cb`、別文書として保持。

今回のV2は旧compactのCopy workspace＋Import Updateで作った改善版。今回ゼロから再構築したと主張しない。以前の独立再構築と区別する。

## ブラウザとキャッシュ

Playwright CLI session `onshape-headless`、1600×1000、persistent profile。APIキーでの作業はしていない。ambient in-appのsignin画面と専用Chromeのログイン状態は別である。

```sh
cd studies/onshape-20260926/work
rtk proxy npx --yes @playwright/cli -s=onshape-headless tab-list
```

引き継ぎ時、tab0はV2 read-only Assembly、tab1は旧マニュアル、tab2は今回のマニュアル。CAD上で編集中ダイアログや実行中のAnimateはない。tab2が選択中。Onshape操作前にtab0を選び、DOMと実表示を再確認する。URL/タイトルだけでWebGL描画完了としない。

ローカルpreviewは `http://127.0.0.1:8767/low-profile-250g/MANUAL.html`。serverはoutputsをrootにして起動中だが、セッション継続は保証されない。停止していたら作業場で `rtk proxy python3 -m http.server 8767 --bind 127.0.0.1 --directory outputs` を使う。既存serverがある場合は二重起動しない。

configは `work/cache/onshape/headless.config.json`。profileと `work/cache/onshape/private/` の認証stateは700/600で保護され、Git/成果物へ含めていない。秘密値を表示・commitしない。旧APIクライアントのcounter `work/api-count.txt` は526で、この研究の増分0。年次残量ではない。内部fetchをAPI節約の代用にしない。

## 設計結果と交換条件

採用は `E20_P30_Y165_Z235`。D405俯角30°（+Yから下向き）、ガラス中心(-0.2,165,235)mm、爪+20mm。旧75°に対しカメラ高さ-12.40mm。比較部分の250gモーメントは0.350412→0.383540N·m、**+9.45%**。変わらないアーム/グリッパ重量は比較部分に含めない。

5,040候補、光学356通過、実マウント33候補/31通過。30°で成立する最小延長20mm、その群で最低高さを採用した。より低い25/30mm延長案は負荷増が大きい。大域最適/全体負荷改善/強度改善は主張しない。

爪根元Y<203.6mmを保持し先端だけ延長。非CAM5 236部品中232保持、4爪/pad変更。2爪+2マウントは有効な単一solid、水密STL。両眼3対象で最小可視率0.932768、最短78.685mm。848×480の75mm基準PASS、720p100mmはFAIL。実カメラ校正・反射・深度性能は未検証。

開閉23姿勢×6,100対象ペアの旧新比較で新規/悪化干渉なし。既存8接触/小隙間FAILは保持。手首physical[-124,102]°、native/URDF[-102,124]°で以前より合計18°狭い。サンプル確認であり連続全関節の証明ではない。

12本の段階別工具包絡はPASS。完成状態の台座4本は工具アクセスFAILなので台座→カメラ付きcarrierの順。締結保持、実物公差、ケーブル、材料、疲労/クリープ、連続トルクは不明。製作承認false。

## URDFと実検証

- 最終入力 `CAD/final-version.step`、SHA256 `9f58c947753e9229b30939da23ce4c87c1cc85eeb39372518de4ffb98991b93f`。
- 262 occurrences / 207 solids / 55 sheets。12新STL、16links、15joints（5能動/4受動/6固定）。`robot/model/robot.urdf` が最終。
- `robot/converter-config.json` はUIの軸/位置/limitsと所属を明示。STEPから関節意味を自動推定したものではない。
- `pg3_states.py` で非線形閉路を解く。441状態の最大残差3.46945e-17m、11native姿勢の最大並進8.78488e-9m、回転5.33710e-8rad。基準は閉路1e-6m、pose各2e-5m/rad。
- 小STEP13＋FK負対照4＋CAD18＝**35試験PASS**。実V1 pad誤所属、逆軸、1000倍単位などを拒否。13品質項目PASS、20p/19画像のPDF/HTMLを確認済み。
- inertialなし、effort/velocity=0は未設定。camera_bodyは校正済みoptical frameではない。55 sheetsを含むSTLは物理エンジン用convex/watertight collision保証なし。ROS launch/RVizは未検証。

### 再現コマンド

変換器環境はPixi0.79.0、Python3.12.14、pythonocc/OCCT8.0.1 linux-64。公式V8.0.1 commit `b8f597c677811d1f9f4d8a97f5ae2825c0353a42`。OCCTはconda-forge binaryで、ソースコンパイルしたとは主張しない。

```sh
cd temp/intake_d405_20260926/converter
rtk proxy pixi install --locked
rtk proxy pixi run versions
rtk proxy pixi run test
rtk proxy pixi run lint
rtk proxy pixi run build
rtk proxy pixi run python ../../outputs/low-profile-250g/robot/validate_robot.py
```

再変換はCONVERTER.mdのコマンドで空の出力先を指定する。既存modelを削除して上書きしない。PYTHONPATH空でinstall済みwheelからV2の262部品を読めた証拠も `reports/converter-wheel-intake.json` にある。

CAD側は元gripper repoのuv/CadQuery2.7環境を使う。変換器のOCCT8とは分離している。

```sh
cd studies/onshape-20260926
rtk proxy uv run --project . --no-sync pytest -q work/low-profile/test_design.py work/low-profile/test_validation.py
rtk proxy python3 work/low-profile/log_work.py start '対象項目と完了条件'
# 対象項目だけを検証した後に done を実行する。
rtk proxy python3 work/low-profile/log_work.py done '実結果と証跡'
```

## 再実行してはいけないもの・失敗の教訓

- `archive_v1_poses.py` は実行済み移動操作。現在の正常poseを旧失敗フォルダへ移すので無条件再実行しない。
- `create-repaired-version.js`、全pose exportなどのUI変更スクリプトは記録用。必要な理由と現在stateなしで再実行しない。
- 旧 `work/optimization/motion_pipeline.py` / `work/export_robot.py` はAPI経路。今回の標準経路では使わない。
- V1では同形padの所属が左右逆だった。代表部品だけの行列では検出できない。全memberを照合し、修復後11姿勢全件を再出力済み。
- read-only Versionで一時姿勢をApplyしてもSTEPが中立になる場合がある。MainでApplyしてpose STEPを出す。最終固定版の中立STEPは別に保存する。
- Animateの終点は閉じると戻った。Apply limitでも他軸が動き得る。全5軸を再捕捉して確認する。
- UI更新は逐次実行。非同期処理が終わる前の次操作で別Compositeへ選択が混入したことがある。
- OCCT8色bindingはクラス経由GetColorが必要だった。初回11失敗のXMLを保持。単位負対照も並進0のyawでは無効だったため肩poseへ直した。
- 元repo全体のclean要求は、無関係な未追跡HN11作業を誤ってFAILにした。削除せず範囲外として記録した。

## 保存の注意

`checkpoint.py` は新研究だけを `studies/low-profile-20260926` へコピーしmanifestを作る。認証/profileは対象外。`sync_skills.py` は4スキルだけを同期。`sync_diary.py` は作業書・レビュー・引き継ぎをdiaryへ同期する。通常は限定pathspecを使い、outputsはignoreされるため今回の出力範囲だけ明示して追加する。

設計コードは元repoとworkspace配置に依存する。保存コピーだけで全工程が自動実行できるという意味ではない。別マシンでは配置と依存を明示して準備し、古い文書IDへ書き込まない。

引き継ぎ時点の「未完了」はD6/D7の最終監査と、その後の完了記録。デジタルモデルの実生成・35試験・441/11照合は済んでいる。物理的未知は検証済みへ繰り上げない。
