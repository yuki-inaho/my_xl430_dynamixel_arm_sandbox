# 蓋把持成果物：辛口レビュー

対象は18分割された外部成果物。結合SHA256は `4ca0c77a4a992037b559cee7768baa52d2557b23a540a5bc9d5fbf8c5b67b4f4`。18部品および展開後3292ファイルのhashが一致した。元成果物は変更せずローカルtempに保管する。

**初期判定: REVISE。名目シミュレーションの成功は支持されるが、保守可能な再現コードとしては未完成。** 作業書の全チェックが済んでいることは、未知の入力や不正モデルに対する健全性を保証しない。

## 要求と実態

|原要求|実態・根拠|判定|
|---|---|---|
|TR1 入力・依存・観測と仮定の分離|内部hash、uv.lock、assumptions.jsonが存在。外部校正は未確認と明記。ただし不足入力処理に展開先依存fallbackあり|改善必要|
|TR2 通常重力・自由蓋・単一jaw・有限駆動|compiled model、5姿勢FK、閉路rank4、raw監査で支持。判定器に受動支持の検査漏れ|改善必要|
|TR3 4軸IK・非干渉経路|位置3+pitch1、93waypoint、全13001stepの指定禁止接触0。衝突除外の適用範囲に限界|宣言したpolicy内で達成|
|TR4 20mm/2秒/両指80%/漂移5mm/接近2mm|生ログ独立監査PASS。37.723014mm、2.000秒、99.8%、0.758806mm、0.007548mm。no-closeはFAIL|名目条件で達成|
|TR4 感度と失敗を保存|低摩擦・低質量失敗を隠さず保存。半刻み成功だが漂移増加|達成、頑健性は限定|
|TR5 二視点証拠・可搬提出|15画像/4動画・リンク正常。従来fresh replayの証拠hashは今回の結合物とは異なる。コードはtempのみ|今回の結合物で実再実行・repo統合が必要|

## 指摘と改善

|ID/重大度|問題と根拠|必要な改善|
|---|---|---|
|R1 Blocker|今回の結合物について確認したのは保存ログの再計算まで。旧 `fresh-extracted-replay.json` は別archiveのhash。再評価と動力学再実行を混同できない|固定依存の隔離環境で改善版を実mj_step再実行し、同seed repeat・no-close・元qposとの差を保存|
|R2 Major|`decompose_mesh` はreportがあればsource hash・尺度・part実体を確認せず返す。改変hash+不正OBJの対照を実際に受理した|source/尺度/part数と実体hashを検査し、staleを明示拒否|
|R3 Major|`prepare_inputs` は祖先ディレクトリへfallbackし、input hash manifestを無条件で再生成する。元作業書の「外部pathへfallbackしない」とコードの契約が違う|同梱入力を唯一のsourceとし、不足/改変を停止。manifestを書き直して改変を正当化しない|
|R4 Major|compiled capの6自由度へdamping=100を追加しても `validate_model` はerrors=[]。自由jointという名前だけでは隠れた支持を排除できない|cap spring/damping/frictionloss、流体支持、tendon/pluginを検査。独立raw監査の制約を通常判定にも適用|
|R5 Major|mass/friction/duration/timestepのNaN/Inf/非正値が事前拒否されない。Ctrl-Cはpartial traceを残すが結果生成を飛ばす|出力作成前に検証。中断を失敗として部分証拠・result保存。policy hashも照合|
|R6 Major|全pair分類は全pairの衝突試験ではない。隣接arm body全体・同剛体・取り付けbody pairsが除外される。「非干渉」の範囲を過大に読める|除外一覧と限界を公開。「宣言したpolicyで禁止接触なし」と限定。局所取り付けROIの衝突保証や実機の全可動域を主張しない|
|R7 Major|成果物約500MiBには重複frozen model/rawと実写が含まれる。現在のpush先はPUBLIC。archive全体のstageは不適切|再現code/mesh/lock、合成証拠、技術記録を明示選択。raw contactは可逆gzip。実写/会話/元archiveはローカル保管|
|R8 Minor|完成作業書のrun経路は引継ぎroot前提。reportは外部実写を自動コピーし、成功summaryをhardcodeする|standalone実行経路と公開reportへ修正。実行結果からstatusを決定し、外部入力を自動取り込まない|

## 修正しないモデル上の限界

摩擦0.7、cap1.5g、箱50mm、cap中心[0,180,57.5]mm、contact impratio10、力上限1Nm/0.08Nm、gain、元の成功閾値は変更しない。元の失敗001–006や感度失敗も保全する。impratio10は成功を可能にした未計測の数値モデルであり、実材料の校正ではない。半刻みで漂移が0.759→1.427mmに増えるため数値依存は残る。

全motorの接触形状、C7の小穴、softtip内部空洞/弾性、ケーブルは近似または欠落。65°holderは候補で現物65/75°区別は未確定。servo count↔CAD角、base↔cameraの外部校正は未確認。これらを今回のコード修正で「実機検証済み」に昇格させない。

## 改善後の追跡

改善版の独立raw監査はPASS。新環境でnominal/repeatはSUCCESS、no-closeはFAILURE。新nominalは36.580984mm/2秒/99.65%/1.385053mmで、元の37.723014mm/0.758806mmとは異なる。同PCの9状態系列はbit-exactだが、元別環境とは不一致。再生成IKの差<=1.5e-15radから接触後の差へ増幅する観察があるが、因果を隔離した実験ではない。cross-platformの数値頑健性は未確認として残す。

MuJoCoの[受動力仕様](https://mujoco.readthedocs.io/en/3.13.0/computation/index.html#passive-forces)に照らしてspring/damping/流体等を通常判定へ追加した。[接触・滑り仕様](https://mujoco.readthedocs.io/en/3.13.0/modeling.html#preventing-slip)は名目solverの説明根拠であり、実材料の物性同定ではない。歴史的trialのproducer sourceは全版同梱ではない。raw states/contact/controlは残るが、最終コードのrunコマンドで全過去版を再現できるとは主張しない。

実施結果は同ディレクトリのWORKDOC.md、packageのreview-verification.json、REPORT.html、tests/test_integrity.pyへ記録する。原履歴と改善版の実行結果は別のtrial名に分ける。公開の選択データはarchive原本の代替ではなく、再現に必要な実体と合成証拠を選んだもの。
