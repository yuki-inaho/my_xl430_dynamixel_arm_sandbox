> 公開範囲: コード・技術記録・CSV・代表合成画像。全raw/元HTML/全freezeはローカルの検証済みbundleに保持し、この公開snapshotには含めない。以下の全raw監査・HTML検査は公開前のローカル成果物に対する記録。

# ランダム把持提出物のレビューと改善

作業: 2026-10-05 22:29:32 → 2026-10-06（JST）。対象はオフラインMuJoCoのみ。
実行入口・結果は [RANDOM_README.md](../../../packages/sim-cap-grasp/RANDOM_README.md)、
可視証拠は [HTML](../../../packages/sim-cap-grasp/PUBLIC_REVIEW.html)。

## 結論

新規qualification-002は100/100成功、unsafe 0、invalid 0。独立実装の監査で全100
試行の判定、2,300,100 sample、接触ログ、実行前選択と凍結入力を照合した。
ただし97試行で下降中の両指接触消失、89試行で箱接触前の消失を観測した。
箱接触前速度の最大は0.69846 m/s。保持と最終配置・復帰の合格を、穏やかな
継続把持下降の成功に言い換えてはならない。

元報告は100成功を主張するが、その100rawはZIPに未納品。元の主張を追認した
結果ではなく、今回の固定条件・別seedによる実行結果である。先行001の失敗と
中断は残し、母数から取り除いていない。当初のレビュー時点では未commit/push。後続のGitHub統合はPUBLICATION.mdに記録する。

## 入力と来歴

受領ZIP2本は同一内容（7,378,710 bytes、88 entries）。一方だけ安全展開し、
CRC、経路逸脱、symlinkを確認。原本・提出資料はtempに不変で保管。

|資料|SHA256|
|---|---|
|report ZIP|7e768f2a6aa659311befc5f54a0846644aa936e8de7401bb4be401ca17a862ea|
|implementation patch|906c8fbc5ba47fc8b71d1251bc3e74db63b1e1dc8e5f955666f24921e88ceb94|
|work record|32571a8dd412cec590c17e57553d659e7f14cabea36cff13e8a4610fb5d69f65|
|patchの元cap archive|4ca0c77a4a992037b559cee7768baa52d2557b23a540a5bc9d5fbf8c5b67b4f4|

patch22対象のうち20新規を受入。改善済みevaluateはcontact readerの統合のみ、
既存QAは置換しない。原CAD・名目モデル・物性・判定閾値を変えていない。

## 辛口レビュー

|重大度|問題と再現条件|対応・証拠|
|---|---|---|
|Major|旧runnerの置換で現行mesh hash・事前CLI検証・KeyboardInterrupt保護が失われる|手動統合、schema3実mesh照合、finite/seed/stale検証を出力作成前に実施|
|Major|git applyが親repo下tempで全ファイルskipでもexit0|親探索を止めた隔離rootで実適用、全22ファイル実体を確認|
|Major|30分timeoutとuvの重複SIGINTで保存途中に再割込み、NPZ3件破損|最初の中断だけ受け、finalize中の再SIGINT無視・handler復帰。2連SIGINT実試行で有効raw/FAIL確定を確認|
|Major|Executorが中断後もpending全件を待つ|pending cancel後にworker回収、INCOMPLETEの固定母数を記録|
|Major|元HTMLの固定数値が新結果にも表示される|actual index/auditからHTML・CSV生成、旧/新batchと未納品rawを明示|
|Major|下降中の接触消失を成功率で覆い隠す|非gate診断も表示。97/100、着地前89/100、最大0.69846 m/sを掲載|
|Moderate|毎step配列再構築と3重forwardがbatch時間を圧迫|補間cacheと1forward+同じimplicitfast。物理・記録byte同等性を検証|
|Moderate|gzip不可、複数contact形式を黙認、独立auditに絶対パス|plain/gzip/zstd排他、lossless hash検証、相対パス出力|

MuJoCoはforwardとintegrationを分けると、観測時点と積分方式の維持が必要。
`mj_step2`はEulerを使うため本変更の代用にできない。
[公式simulation説明](https://mujoco.readthedocs.io/en/3.3.7/programming/simulation.html)、
[公式API](https://mujoco.readthedocs.io/en/stable/APIreference/APIfunctions.html)を参照。
`physics_step.py`は同じimplicitfastを使用し、接触のある別モデル200stepで
標準mj_stepとqpos/qvel完全一致を検証した。

## 実行・監査

|ケース|結果|備考|
|---|---|---|
|代表/変更前|SUCCESS|23s、23,001 samples、物理loop89.97s|
|代表/改善後|SUCCESS|20.47s、旧全20状態配列・contact bytes完全一致|
|改善後repeat|SUCCESS|24.77s、全配列・contact bytes完全一致|
|matched no-close|FAIL|NO_GRIP/INSUFFICIENT_LIFT、全trace保存|
|重複SIGINT|FAIL|1sampleの全20field NPZ有効、metadata確定・lossless contact保存|
|qualification-001|INCOMPLETE|96成功、1実NO_GRIP、3不備、timeout exit124|
|qualification-002|合格|100成功、unsafe0、invalid0、1,186.24s、独立audit PASS|

001: seed91020261005、404提案/304棄却、100選択。元partial indexと破損rawを保全。
002: seed91021261008、335提案/235棄却、100選択。判定・物性・範囲・1800s上限は不変。
002 freeze SHA: f973d28f3aaa110add26b279a3a5a665efccebc736ca1ea6506f4a795539cbda。
002 index SHA: 6d331e01a527806a3347c96c0a43ba0c74af362f41c15b7f90a80f08a94cf7cf。
Wilson95% [0.9630065,1]は選択した新batchの記述値。繰返し開発後の無条件確認的
区間ではない。静的screen棄却範囲、一般pitch、実機へは一般化しない。

代表画像/動画は実rawの再描画。最大半径、最大着地前速度、負対照、旧実失敗も
表示する。再生時qpos設定は描画用であり、物理実験の姿勢書換えではない。
名目D405相当の手先視点は実カメラ校正済み光学を意味しない。

## 残る制限と次の仕事

下置きを改善するなら、下降中の継続把持・着地速度/衝撃を明示gateとして別途
固定し、制御変更後に新seedの全cohortを実行する。今回の成功を守るための
物性や閾値の緩和は行わない。実機移植にはID/zero/sign、実カメラ外部パラメータ、
指材質・ケーブル・collision exemptionの現物検証が別途必要。

headless Playwrightでは169リンク、62画像、10動画の読取、全100行と検索、
PC/スマホ幅を確認。画面証跡はpackageのevidence/report-qualification-002に保存。
技術inventory3,872件（text2,136、compressed text125、NPZ125）を点検し、
private-path/secret所見0。RANDOM_DELIVERY_SHA256SUMS照合PASS。
元archive・実写・会話・破損中断raw・例外logはこの受渡inventoryに含めない。

対象検査のみを実施。初回14tests、補間3、最後のproducer修正6がPASS。
広範囲の別機能testsや実機アクセスは行っていない。スキルにはpatch実体確認、
前段profile/bit同等性、中断保存、固定母数、下降診断の教訓を汎用化して追加した。
