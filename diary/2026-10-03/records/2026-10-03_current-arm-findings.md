# 2026-10-03 現状アーム・実機観測・MuJoCo調査の集約

作業先は `/home/inaho-omen/Project/my_dynamixel_arm_sandbox`。集約の実行開始は **2026-10-03 20:38:47 JST+0900**。本レポートは実物の写真、保存済み実機ログ、CADとコードの調査、現在のビューアを照合したもの。今回の集約では新たな実機通信を行っていない。

現状は **R3系アーム＋旧C7爪＋長尺D405 R5（65°が第一候補）** に近い。5台のXL430は過去の保存済み読取で確認されているが、部品の細かな版、物理ID順、関節のゼロ点・回転方向、自己干渉しない連続可動域は未確定。MuJoCoは候補を仮組みした画面操作モードで描画できる。**実機の現在角を継続反映するモードは最終要求として追加され、実機接続・校正まで含む実装と確認がこれから必要**。

## 写真と部品版

| 部分 | 有力候補 | 残る不確定点 |
| --- | --- | --- |
| アーム | 全XL430向けR3系のP01〜P05、M01〜M05 | R1/R2との差、局所修正、印刷元コミットは断定できない |
| 爪 | PG3 C92の旧C7 | 細い接触板・三角リブなし。C7より古い同系統は完全には排除できない |
| D405ホルダー | 9/24の長尺65° R5が第一候補 | 似ている75°短縮版との区別は未確定。低背30°版は現物候補と違う |

アーム写真には爪・ホルダーが装着されていない。3枚を組み合わせた候補配置を、装着済み実機を見た事実へ読み替えない。C7の爪板前後長は設計12.1 mm、C9 J28は28.0 mm、最新版低配置V2は48.0 mm。作成済み組立マニュアルの対象はV2で、写真の旧C7の完成外観・パッド寸法とは区別する。

D405→ホルダーの設計固定は **M3×6 mm・2本・座金なし**。6 mmは頭を除く。取付板4 mm−座ぐり1 mm＝有効厚3 mmに対し、ねじ込み3 mm、背面穴の図面上限4 mm。現物の板厚・座ぐり・実ねじ長は写真だけで未確認。

根拠：[写真の版照合](../related-gripper/temp/photo-version-check_20261003/REPORT_ja.md)、[D405 R5設計](../related-gripper/docs/CAMERA_MOUNT_ID5_D405_R5.md)、[V2マニュアル](../related-gripper/temp/gripper-assembly-20261003/MANUAL.md)。

## 元ブランチと直近の作業

`low_cost_robot`はAlexanderKoch-Kochのfork。ユーザーの印刷元の記憶は `feature/all-xl430-arm` だが「多分」とされている。

| 版 | コミット | 意味 |
| --- | --- | --- |
| feature/all-xl430-arm | `ecdc3e6d7424d93718e24388e5ee9654d8e9d348` | 6/14。印刷元の候補。写真のR3の確定証拠ではない |
| low_cost_robotの現checkout | `f29f33b3b99320b3ad35171ec08897bede459fbb` | fix/cadre-geometry-review-20260918。9/25までの修正を含む |
| 写真に近いR3 | `XL430_collision_R3_20260919.zip`／受領STEP | Gitブランチ名とは別の入力CAD |

featureと現checkoutのhardware/simulation差分は空。旧シミュレーションは混在サーボ由来で、ブランチ名だけで全XL430/R3対応を証明しない。R3 STEP SHA256は `3274fab5106793de65f86bb3391a660ff6d09eb55a9d8166e072e9d1bd4625cb`。

9月の関連作業は、9/18のCAD生成器修正、9/19の改訂とR3印刷案件、9/22の組立・アイドラ、9/23のPG3統合、9/24のID5-only開閉とD405 R5・P05配線窓、9/25のBOM・試験高速化、9/26のOnshape・低背30°／爪+20 mm V2・OCCT8追試・HN11案。9/30のログは既存配信サーバーの終了で、新設計の証拠ではない。10/3にはこの新workspaceで読取専用observerが作成され、別repoで今回の版・制御・可動域調査とMuJoCo表示が進んだ。

直近1か月の関連会話は8個の `*_clean.json` と索引に保存されている：[関連作業レビュー](../related-gripper/temp/recent-work-review_20261003/README_ja.md)。OpenCodeの2件はSQLiteからの読み取り専用抽出で、JSONL用バイナリで変換したものとは区別する。

## 制御実装の確認

旧 `low_cost_robot/dynamixel.py` をオフラインで公式仕様と照合した。実コードは改修していない。

| 問題 | 確認結果 |
| --- | --- |
| Operating Mode書込み | addr11は1 byteなのに2 byte write。隣のSecondary ID addr12も送信範囲に入る |
| 電圧の読出し | 旧145ではなく、XL430は144から2 byte |
| read_current | addr126はXL430のPresent Load。実測電流として扱えない |
| mode5 | XL430では非対応。対応は1/3/4/16。旧wrapperは4も欠落 |
| hardware alert | error bit128を無視。Hardware Alertは電圧異常だけを意味しない |
| read_home_offset | 読むためにTorque OFF→ONを行う副作用がある |
| 失敗・符号 | 書込み応答、SyncRead欠測、signed32境界の扱いに問題 |
| 旧IK | body IDをgeom_xposの添字に使用し、参照点とJacobianの点がずれる |

Baud code6＝4 Mbpsは正しく、不具合とは扱わない。現在のobserverはこの旧Robotを構築せず、PING/READと検証済み2ブロックのSYNC_READに限定する送信ガードを持つ。実機readの成功を制御・校正の成功と扱わない。

WebでROBOTIS SDK、LeRobot Koch follower、MoveIt PlanningScene、MuJoCoの一次資料も調べた。標準Kochのサーボ構成や校正は今回のR3/XL430全台構成にそのまま移せず、LeRobotの相対目標制限も全腕の衝突検査ではない。関連実装はコミットとSHAを固定して保存した。

根拠：[制御実装監査](../related-gripper/outputs/arm-current-audit-20261003/CONTROL_AUDIT.md)、[制御仕様草稿](../related-gripper/outputs/arm-current-audit-20261003/CONTROL_SPEC_DRAFT.md)、[公式XL430仕様](https://emanual.robotis.com/docs/en/dxl/x/xl430-w250/)。

## 可動域と自己干渉

R3の保存記録は、CAD保存姿勢からJ1±180°、J2±40°、J3±60°、J4±60°を5°刻みで検査したもの。単軸188姿勢で過去の干渉0、組合せ1125姿勢の36件で過去の干渉。旧M06/P06/P07を含む記録なので現物の件数ではない。`q3+q4>=−90°`の1080点が過去PASSでも連続安全範囲を保証しない。

長尺65°カメラの旧手首診断では、カメラなし−138〜+128°、カメラだけ−168〜+110°、共通−138〜+110°。+112°で取付板とM03の衝突を記録している。一方、旧checkerにはP05/M04の組を全域で除外する処理とBoolean絶対体積の使用があり、安全リミットとして採用できない。低背30°版の別の角度・符号へ読み替えない。

今回のR3裸アーム入力のBoolean独立対照は **125要素中97 PASS、28 FAILまたはERROR**。立方体の正負対照は通るが、一部輸入CADでCOMMONが元体積を保たない。OCCT8の代表10要素でも2 PASS／8 FAILまたはERROR。元CADを修復したり公差を緩めたりせず、新しい掃引の前に止めた。状態は `ERROR_INPUT_BOOLEAN_CONTROL`。

旧MuJoCoボックス代理モデルでも7.551 mmの貫通を再現し、1.474 mmの貫通が旧2 mm許容値で合格になる例があった。軸配置も今回と違うため、旧モデルのPASSや±180°placeholderを現物の安全範囲と扱わない。**物理的な角度限界・count限界・連続経路は未確定**。

根拠：[可動域の詳細報告](../related-gripper/outputs/arm-current-audit-20261003/REPORT.md)、[機械可読状態](../related-gripper/outputs/arm-current-audit-20261003/current-arm-status.json)。製作・実機書込み・通電・運転releaseはすべてfalse。

## 保存済み実機観測：18:59の状態

以下は **2026-10-03 18:59の保存済み観測**。20時台の現在値や現在のTorque状態ではない。今回はそのファイルをオフラインで再検証した。

| ID | Model | FW | 3サンプルの位置count | Torque | 電圧V | 温度°C | Hardware Error |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 1060／XL430-W250 | 43 | 2550／2550／2550 | OFF | 9.2 | 35 | 0 |
| 2 | 同上 | 42 | 3354／3354／3354 | OFF | 9.2 | 37 | 0 |
| 3 | 同上 | 42 | 1153／1153／1153 | OFF | 9.0 | 35 | 0 |
| 4 | 同上 | 42 | 2059／2059／2059 | OFF | 9.1 | 36 | 0 |
| 5 | 同上 | 43 | 2059／2059／2059 | OFF | 9.1 | 35 | 0 |

全台、Baud code3＝1 Mbps、Protocol2、Operating Mode3、Drive Mode0、Homing Offset0。Position Limit0〜4095、Profile Velocity/Acceleration0/0、Bus Watchdog0が保存されていた。0のプロファイルは有限の穏やかな動作設定を意味しない。各IDの役割は提案で、`physical_order_verified=false`。エンコーダ値とCAD角をまだ結び付けられない。

根拠：[status JSON](../reports/status_20261003T185915_405929%2B0900.json)、[その時の観測日誌](2026-10-03_typed-readonly-monitoring.md)、[接続・役割設定](../../../config/arm.toml)。

## 監視の実測と今回の再検証

| 保存ログのモード | 指定Hz | 実測Hz再計算 | フレーム | 期限超過 | schema適合レコード |
| --- | --- | --- | --- | --- | --- |
| Sync Read | 20 | 19.99955 | 100 | 0 | 102 |
| Sync Read | 50 | 24.99961 | 75 | 75 | 77 |
| Unicast | 20 | 1.11105 | 4 | 4 | 6 |

全185レコードをschema v2で再検証し、不正な文字列positionが拒否される負の対照も3本それぞれで確認した。期間内のposition欠測・read fault・Device Alert・Hardware Error・Torque ON件数は各0。末尾EndEventとport_closed=trueがあり、**いずれも観測終了したログ**。現在のlive入力として扱わない。20 Hzで観測できた実績はハードリアルタイム制御の保証ではなく、2ブロック・各モーターの厳密同時サンプルでもない。

今回の再検証の生値・集計・36入力ファイルのSHAは [current_arm_evidence_20261003.json](../reports/current_arm_evidence_20261003.json)。元ログやモーター設定は変更していない。

## MuJoCoの現在の実装

[ブラウザビューア](http://127.0.0.1:8084)をPlaywrightで起動済み。R3の180要素（55面部品を含む）＋旧C7＋選択式D405を表示し、4アーム関節と1開閉自由度、受動スライダ2個、リンク2個が追従する。「爪を拡大」、開閉、再生／停止、65°／75°切替、視点・ズームに対応。1060×760のMuJoCo 3.13.0描画を約20 fpsで更新する。

初期入力は画面操作。実機read JSONLの受け口はあるが、未校正では実機姿勢切替を無効にする。校正にはID→関節、CAD基準角でのcount、方向、PG3θ対応が必要。Homing Offset・Operating Mode等が変われば校正は失効するが、現アダプターはその自動検知をまだ行わない。古い・欠測・異常・終了ログをliveとして描画しない。

表示は`mj_forward`による運動学で、動力学・接触判定は無効。質量・慣性は仮値、実配線や変形・荷重は再現しない。前段の14件のCAD／ログ試験と5回の自己レビューは[既存検証記録](../related-gripper/outputs/current-arm-mujoco-20261003/VIEWER_REVIEW.md)。本作業の新たなブラウザ確認は作業書の手順5で実施して記録する。

実装と起動は[viewer README](../related-gripper/simulation/current_arm_viewer/README.md)。このworkspaceにviewer用のCAD依存を追加したり、旧制御コードを実行したりしていない。

## 実行中の作業書と次の作業

[集約の作業書](../workdocs/workdoc_Oct03-2026_current_arm_findings.md)をwrite-workdoc-uvで作成し、[レビュー](../workdocs/workdoc_Oct03-2026_current_arm_findings.review.md)の指摘を修正してPASSとした。start-work-with-docsで一項目ずつ実行中。observerの現行オフライン試験、独立ブラウザの状態確認、文書・SHA検査の結果は本書へ追記する。

追加要求は「最終的に、いまの実機状態を継続読取りしてMuJoCoへ反映するモードの実装」。校正の有無をユーザーへ確認しながら、実機READ経路・校正確認画面・設定変更時の失効・欠測表示の作業書を続けて作る。未校正の値を仮の関節角で実機確定姿勢として見せない。

| 残件 | 再開に必要な証拠・入力 |
| --- | --- |
| 部品版と装着 | 爪の窓・板長、ホルダー面角／印刷元、取付状態の確認 |
| 物理ID順 | IDと実物関節の照合。Ping成功だけでは足りない |
| ゼロ点・回転方向 | CAD保存姿勢に対応するcount、符号、PG3θの実測対応 |
| live描画モード | 現行read-only observerからの継続入力、校正との結合、設定変更・欠測時の試験 |
| 安全可動域 | 実CAD判定器の独立対照を解決し、装着構成・配線・机・連続経路を検査 |
| 運転設定 | 根拠付きの速度・加速度・停止条件と荷重・電源・異常時の仕様 |

日誌と作業書の完了は、これら実機校正・安全性の未解決項目を完了へ変えるものではない。

## 今回の実行結果

現行observerを `uv run --locked --no-sync pytest -q` でオフライン再確認し、**67 passed in 0.31s**。過去の日誌の65件とは別の今回の結果で、[出力](../reports/current_arm_offline_tests_20261003.txt)を保存した。

**20:49 JST**、専用headlessブラウザでビューアを再確認した。フレーム29630→29636、1060×760、19.9 fps、source=manual、telemetry未接続、error=null。これは描画サーバーの稼働で、実機の現在角を反映した事実ではない。[ブラウザ確認JSON](../reports/current_arm_viewer_check_20261003.json)。
