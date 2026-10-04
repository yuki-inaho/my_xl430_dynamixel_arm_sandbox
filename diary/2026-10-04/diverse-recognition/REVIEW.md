# 多姿勢認識・実機撮影・性能のレビュー

2026-10-04、Codex単独。画像認識から実機への指令は接続していない。
ユーザーの電源OFF報告後はserialへアクセスせず、保存データとカメラのみでレビューした。

## 結果と範囲

20姿勢を2.5秒保持し、RGB-D・K・mask・CAD重畳・推定・前後encoderを対応保存。
元データは `~/data/xl430-arm/2026-10-04/diverse-recognition/`。
このレポートの `captures/` はportableなコピーで、元の中断区間は保持している。
アームR3系、長尺D405ホルダーR5 nominal65°、爪なし。65°/75°の実物区別と絶対角校正は未確定。
モデルhashは `cc15059b6256b1cf88452d3c85a5a0f8861b08ce00978c9e498f86208ce9dcf0`。
出典・作成入力・変換は [モデルJSON](../../../models/current_arm_r3_d405_r5_65.json) にある。
外部D435 serial922612070196、RGB8/Z16 native1280×720/30、処理480×270。
手先D405 serial230322272284は搭載済みだが、全体認識の入力には使っていない。

| 評価 | 結果 | 制限 |
|---|---|---|
| 台座 | 16 holdout MAE1.15°、最大2.97° | 実相対幅58.54°、根元位置固定 |
| 肩 | MAE0.43°、最大1.41° | 実相対幅4.39°に限定 |
| 肘 | MAE0.37°、最大0.88° | baselineから実開き約9〜29° |
| 手首 | 未検証 | 実+1.85°に対する画像変化は約0.06°、+6°候補は停滞 |
| ID5 | 未検証 | 爪なしで動く下流形状がない |
| 自己干渉 | 全域UNKNOWN | 受理経路は実画像で接触・支持移動・配線の張りを認めず。MuJoCoは接触無効 |

画像推定にencoderは入力していない。相対符号は独立の一軸変化から `[+1,-1,+1]` とした。
符号に用いたpose01/05/06/07を精度の評価集合から除外している。
絶対ゼロ点や世界座標の校正ではない。前後READの最大差は1count、画像host時刻を挟む。
ハードウェア同期や厳密な同時露光とは呼ばない。
全行・符号根拠・実時刻は [evaluation.json](evaluation.json)。

## 停止と終了状態

21:49:51、手首+6°候補でID4が3413countのままno progress。target3460、有限補正3490でも進まず、
既存guardが全台present goal保持で終了コード2にした。原因は未確定。出力や判定を緩めていない。
元のpose04（+3°、実21count=1.846°）は保持し、追加手首候補を取り除いたcontinuation表を保存。
肘30°のまま手首を基準3392へ戻し、3398countの確認後、肩・台座・肘の撮影を継続した。
21:53:42、pose09到着後のID1単発MissedSampleでも停止し、そのrunから画像を受理しなかった。
fresh状態/設定を確認した別continuation-2でpose09を撮り直して20まで完了した。
これらの2区間は元のイベントと撮影表を残している。

21:58:35.842、支持姿勢へ復帰、全5台Torque OFF、変更したRAMの復元とreadbackを確認。
最終counts `[2103,3482,1163,3398,1951]`。
21:59:42の独立READ3回も同値、全OFF、error0、最高43°C、9V、port closureを確認。
その後ユーザーが電源OFFを報告した。以後のレビューはオフラインとカメラだけである。

## 性能改善

同じframe/K/初期state/model/backendで60更新を比較。全60の推定は前後一致。
中央値40.76→29.23ms（28.3%短縮）、p95 49.30→33.23ms。
State/Kの値による描画cache、mask距離場の再利用、上限1件の背景保存を採用した。
StateやK変更時はcacheを無効化し、遅い保存をFIFOに溜めない。実測profileを保存している。
IoU.60、surface15mm、frame/mask age.5秒およびmotor guardは緩めていない。

撮影21:46:54〜21:58:36の701.97秒全体（停止・再開を含む）で13897成功/13916記録、
19.80成功Hz、frame age p95 .101秒、mask age p95 .355秒。
処理中央値：mask preparation12.49ms、registration26.65ms、JPEG3.76ms。
baseline静止180秒は15.76成功Hzだが撮影状態が同一ではないため、これだけで改善倍率を決めない。
99.86%のtracking比率は真の正解率ではない。全域精度・長時間運転性能とも別の測定である。
この性能測定は次の不在修正追加前。追加後に実機をもう一度動かして再測定してはいない。
[performance.json](performance.json) と圧縮済みjournalに測定根拠がある。

## レビューで見つかった背景誤追跡と修正

22:14:37、腕が写っていない画像の箱・ケーブルへ台座を動かしてtrackingになる例を発見。
実画像を視認して不在と判断した。元の誤推定は
[失敗画像](captures/arm-absent-negative/color.png) と [元記録](captures/arm-absent-negative/pose.json) に保持。
従来はseedを一度使って消費し、失敗後のglobal探索が別の背景へ根元を移していた。
最後に受理したseedを保持し、既知の固定sceneではglobal根元探索へ戻らないよう修正した。
台座の可視body0とaligned depthを比較し、有効100点以上・深度差中央値15mm以下を追加要求。
黒い台座がRGB maskから漏れるため、maskの台座包含率は使っていない。

保存20姿勢の台座深度差は1.85〜2.42mm。不在の実画像では元anchorで34.72mm。
20姿勢の保存推定はすべて新gateを通過し、不在画像は4回続けてもlost、seed/rootを維持。
これはgate互換性・不在回帰試験で、新しい角度fit精度試験ではない。
[presence-regression.json](presence-regression.json) にhashと各判定を保存した。
別途、カメラに戻ったアームも位置が変わり台座誤差約23〜24mmでlostとなった。
10秒のHTTP97観測はtracking0、fresh frame age p95 .088秒、mask .293秒。
[Playwright画面](moved-scene-after-fix-viewer.png) は「アームは見えるが元sceneが無効」の例。
これを「腕がない画像」と混同しない。カメラ・台座移動時は古いseedを使わず明示的に再取得する。
初回のseedなし探索や同じ奥行きの別物体など、全種類の誤対応を除去した保証はない。

## 実装と検証のレビュー

取り込み元数値packageと現行camera/segmentation/renderer/trackerを分離。
観測APIは同じframeのRGB-D/K/mask/overlay/metadataをatomic snapshotで返し、古い観測は503。
D16は別撮影controllerと計画windowを使い、旧D14/ID3・READ observerの許可範囲を変えていない。
撮影表1つから動作/保存/評価へ渡し、20行分の重複した模擬テストは増やしていない。
元packageの14数値試験と元最良解replayを確認。保守側full suiteは346passed（26.61秒）を1回。
不在修正後は影響するperception5件だけ再実行して5passed（3.48秒）。
Ruff・ty・最大complexity10・保守対象のdiff whitespace・skill形式・HTML画像/overflowを最終確認した。
全staged diffには元のEigen/source results/STEPの空白警告が残る。入力hashを守るため
原本を正規化していない。新規/保守コードのチェックはPASS、全diffをPASSとはしていない。
既存全32探索を不要に繰り返さず、同じ保存frameと実失敗例で検証した。

元の連続camera記録はローカルに保持する。Gitは20姿勢・失敗例・参照画像・計測・圧縮journalを
選んで格納し、無関係の未追跡reports/、build/cache、連続全frameは含めない。
作業書とreviewを `diary/2026-10-04/workdocs/` に保存。
