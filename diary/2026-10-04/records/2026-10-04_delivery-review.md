# 他エージェント納品レビュー（2026-10-04）

判定：**修正が必要**。既存テストは通るが、実機制御の前提・成功判定・校正の出所・会話書き出しに7件の再現可能な欠陥がある。今回はコードの修正・シリアル接続・モーター指令を実施していない。追加のスタンバイ／電源OFF姿勢は別仕様・別作業書で扱う。

## レビュー対象と確認範囲

対象sandboxのmainは `6e1c16bc6cac672cfe82c932cd7318dacc709256`。GitHub PRIVATE・既定main、local HEADとremote mainの一致をread-onlyで確認。初回482ファイル＋clean JSONの計483 tracked filesを分類した。維持対象のsrc全16モジュール、運動用guard、主要テスト、5スキルの本文・スクリプト、資料、保存実測を確認した。upstream/に取り込まれた171ファイルと全ての技能参照文書を一から全行監査したという意味ではない。

gripper側 `simulation/current_arm_viewer/` は未コミットの別変更。こちらもserver、live入力、方向記録、HTML、モデル生成／provenanceと関連100テストを検査した。レビュー用の新規ファイル以外のproductionコードを変更していない。

## 再現した欠陥

### R-1 [P1] 他モーターのSecondary IDが3なら、ID3限定guardを通過して他モーターへRAM書込みされる

対象：[`id3_motion.py:584`](../../../src/arm_observer/id3_motion.py#L584) の `read_settings`／prepare、[`id3_motion.py:466`](../../../src/arm_observer/id3_motion.py#L466) の書込み開始。

事前設定確認はID3だけを読む。他の4台のSecondary ID(12)を確認せず「packet ID=3」だけで対象を限定する。しかしXL430はSecondary IDを共有したモーターにもRAM指令を適用する。[ROBOTIS公式仕様](https://emanual.robotis.com/docs/en/dxl/x/xl430-w250/#secondaryshadow-id12)。

実際のSDKとEmuSerialに公式のSecondary IDルーティングを加え、ID1のSecondary ID=3を設定した反例では、送信先packet IDは全て3なのに、ID1へPA=1、PV=5、PWM=350、Goal=1153、Torque ONが届いた。その後の監視は「ID1 torque turned ON」で停止するが、別モーターへの通電後である。過去の実機でこの設定だったという主張ではない。

対応：初回write前に全接続モーターの主ID・Secondary ID・必要設定を新鮮なREADで検証し、ID3宛てRAM書込みの物理受信者が1台だけと確かめる。未知・欠測・aliasは拒否。transport対象IDだけを見た試験に加えて、aliasを実装した通信層の反例を品質ゲートへ入れる。

### R-2 [P1] CAD証拠のhashは、動作方向や実測ログとの関係を証明していない

対象：[`id3_motion.py:202`](../../../src/arm_observer/id3_motion.py#L202)、[`id3_motion.py:211`](../../../src/arm_observer/id3_motion.py#L211)、[`id3_motion.py:218`](../../../src/arm_observer/id3_motion.py#L218)、[`derive_id3_direction.py:67`](../../../scripts/derive_id3_direction.py#L67)。

CAD入力のSHAが合うことと、JSON内の2つのsignが一致することだけを検査する。本来のR3 sourceを変更せず、トップとderivationのsignを同時に+1→−1へ変えても受理した。任意の非CADテキストのSHA、存在しないREAD log、自己申告のfolded countでも受理する。方向とsource geometryを実行時に再計算して照合していない。

生成側も `simulated:true`、hardware_error=32、device_alert=trueの50静止frameとend(port_closed=true)を持つログを受理した。今回は偽入力だけのoffline反例であり、保存済み実機logが偽物だとは言っていない。

対応：固定された期待source構成・CAD幾何からdirectionを再計算する。READ logの存在とhash、schema/identity、simulated=false、device fault、終了・安定条件を実体から検査する。JSONの自己整合と物理方向の検証を分ける。実機側の校正不明を任意の符号で補わない。

### R-3 [P1] hold/followでID3の予期しないTorque OFFを検知しない

対象：[`id3_motion.py:439`](../../../src/arm_observer/id3_motion.py#L439) のholdとTrackerの更新。

Torque ON直後には確認するが、その後のholdは他モーターとposition driftだけを確認する。ID3のtorqueがOFFでも、支持によってcountが変わらないと2秒・40sampleを正常に通過する反例を再現した。「hold関数が受理した」という範囲の結果で、実機で実際に脱力した、またはこの反例だけでCLI全体がexit0になるという主張ではない。

対応：motion/follow/holdの各phaseでID3 Torque ONを必須条件にし、解放phaseとは別の不変条件にする。支持されてcountが変わらない脱力の反例を追加する。

### R-4 [P2] 帰還誤差20 countでもconverged／exit0になる

対象：[`id3_motion.py:357`](../../../src/arm_observer/id3_motion.py#L357) のsettle_limit、[`id3_motion.py:484`](../../../src/arm_observer/id3_motion.py#L484) のreturn、status生成。

returnも25 countのsettled許容を使い、最後のstatusは開く側の誤差のみを見る。復帰が20 count（約1.76°）不足する模擬入力で、`return_error_counts:20`、`status:converged`、exit0を再現した。

対応：開きと帰還の両方に終点許容を適用し、帰還未達を別状態／非ゼロ終了にする。保存済み実機motion2のreturnは0 countで、過去の実測結果を撤回する指摘ではない。

### R-5 [P2] 設定復元の失敗が成功終了へ反映されない

対象：[`id3_motion.py:687`](../../../src/arm_observer/id3_motion.py#L687)、[`id3_motion.py:692`](../../../src/arm_observer/id3_motion.py#L692)。

PV=0への復元だけが失敗する反例で、`release_problems`にwrite failedが残り、PVは5のまま、torque_off_confirmed=true、status=converged、exit0となる。呼び出し元は完了扱いして次の作業を進めうる。

対応：Torque OFF確認・姿勢達成・設定復元を独立した終了条件として判定し、restore失敗も非ゼロ終了にする。復元はwrite成功だけでなくreadbackを証拠にする。

### R-6 [P2] 試験用校正で実機READの表示に切り替わる

対象gripper：`simulation/current_arm_viewer/live_input.py:109,154` のcurrent_context／convert_pose、UI badge。

bind時にはsynthetic→hardwareを拒否するが、その後のconvertではsimulatedを照合しない。校正contextにもこの入力属性が含まれない。同一session・同一metadataでsnapshotのsimulatedだけtrue→falseへ切替えると、試験用校正のままcan_render=trueを維持し、badgeは「実機READ · 校正済み」に変わる。

これはPlaywright＋専用HTTP mock＋実際のMuJoCo rendererで再現した。通常の新しい実機sessionはUUIDが異なるので、今回の試験だけから現運用で必ず混在すると断定はしない。それでも「試験用校正をhardwareに適用しない」という制約をconvert段階でも守る必要がある。

対応：校正contextへsource種別を含め、変化時に校正を失効させる。全変換入口でsimulatedの型・出所・一致を検査し、UIもcalibration/source両方から状態を決める。

### R-7 [P2] 再利用用の会話exportスクリプトがAPI側Codex会話を欠落させて成功する

対象：[`bundle_clean_json.py:43`](../../../skills/session-clean-export/scripts/bundle_clean_json.py#L43) のextract。

agent-jsonl-compactのchannelを指定せずterminal既定で処理する。実在するCodexログからsession_meta＋API user message1件を抜いたfixtureに、納品された無変更スクリプトを使うと、結果はsession1件・user0件、exit0になった。SKILL本文は新形式ではapiを使うと述べるが、scriptに選択機能／自動判別／欠落検知がない。

対応：channelの明示選択またはformatに基づく判別を実装し、会話イベントが全滅していないことをsourceと照合する。割込み発言の補完と重複処理もschema別にテストする。

**今回のClaude clean JSONは有効**。この指摘は再利用性の欠陥であり、既に納品されたClaude会話の欠落を示すものではない。

## 確認できた実績

### 会話書き出しと合意の原文

clean JSON 2,074,511 bytes。記録されたraw snapshot prefixは10,270,002 bytes・2096 recordsで、保存SHA256に一致。normalized704 events、supplemental40件（割込みuser6・queued system34）を照合した。最終prefix timestampは2026-10-04 08:29:17 JST。そこより後の会話は含まれない。user eventにはtool/skill/local-command注入もあり、人間の発言37件と単純に数えるべきではない。

初期の表示照合要求だけで判断せず、後続の「最後はエンコーダが意図した角度に収束したかで十分」「完全自律」「8084をPlaywrightで操作」「翌10時まで就寝中」の原文を確認した。最終小動作のvisual照合を外したD-4には根拠がある。全体の実機ライブ表示・校正という元の目標は残っている。

### 保存された実機の動作

| run | 開き側 | 帰還誤差 | 終了 |
|---|---|---:|---|
| motion1 00:16:21 | 1153→1248 count、約8.35°、targetとの差−19 | 1 count | settled_off_target、Torque OFF・port closed |
| motion2 00:20:34 | 1154→1264 count、約9.67°、targetとの差−4 | 0 count | converged、Torque OFF・port closed |

motion2は補正20 countを使用。実測移動110 count、他IDの最大差はID4の1 count、ほか0。開く区間約10.414秒。保存logを独立集計して確認した。現在の実機状態を今回READした結果ではない。

### 品質ゲート

| 検査 | 再実行結果 |
|---|---|
| sandbox pytest | 217 passed |
| gripper viewer/live/direction pytest | 100 passed |
| ruff / ty | PASS |
| complexity | 最大10、閾値10 |
| Rust契約テスト | 3 passed |
| clippy | PASS |
| 新規5スキルの形式 | PASS（挙動の正しさとは別） |

217テストと通信層エミュレータの導入には価値がある。今回の反例は既存テストが未包含の前提／終了条件を調べたものである。

### PlaywrightとMuJoCoの実体

専用headless `delivery-review-20261004`、専用viewer18084/mock18085を使用。既存8084と他browser/serverは変更していない。MuJoCo3.13.0、nq7、geom65のモデルをcompileし、既知count→CAD姿勢(11.25,5.625,0,0)、θ101.25°を描画。独立qpos照合とdecoded画像を確認した。爪・長尺65°／75°切替、gripper拡大、θ25/135で開口48.90/0.93 mm、390px幅で横overflowなし、console警告／エラー0。

確認した防御：校正未確認では適用拒否、telemetry中のmanual上書き400、範囲外／boolean角度400、stale時の最後の姿勢保持、drive_mode変化後の校正失効と再適用要求、方向record保存後のbaseline消費。syntheticの方向2点は1153→1267、+114 countと保存され、hardware証拠としては使用しない。

**実行中8084はmanual・未校正、8085への接続拒否**。画像が動くことを「現在のロボットを反映している」とは扱えない。接触は全geomで無効、gravity=0、慣性はplaceholderである。これは姿勢表示モデルで、自己干渉ゼロ・無通電安定・急落しないことの試験にはならない。

## スキル／資料を育てる際の修正順

1. bounded-servo-motionへSecondary IDを含む物理受信者の確認、全phaseのtorque不変条件、帰還・restore判定を追加する。今回のagentのovernight許可を、別ユーザーや別ロボットへの無条件の無人運転許可へ一般化しない。
2. robot-live-calibrationへsource種別とsession/model/metadataの照合を各変換入口で行う規則を追加する。物理ID、CAD軸、encoderの基準角は別項目として持つ。
3. session-clean-exportはchannelを実装に反映し、Claude/Codex両fixtureで期待発言のcoverageを測る。quick_validateだけをDoDにしない。
4. 監視／復元logにはcode/spec/evidenceのhashを残し、設定復元結果とclosureをdistinctにする。
5. docsの過去時点と現況を統合する。READMEのID3未実施という旧記述、tempリンク、gripper側未コミットviewerの所有repoと起動経路を明確にする。

既存のmanual・印刷データや図面を最新版として承認し直すレビューではない。ホルダー65°/75°、爪C7の現物一致、全軸ゼロ・回転方向、配線、荷重・クッション接触は未確定。

## 証拠と再現

証拠ディレクトリ：[`reports/delivery-review-20261004/`](../reports/delivery-review-20261004)。

- `source-audit.json`、`tracked-manifest.json`、`scope-user-messages.json`：Git・clean/raw比較・合意原文。
- `motion-log-audit.json`：実測の独立再集計。
- `adversarial-probes.json`：R-1〜R-5、synthetic/faulted READ受理。
- `codex-export-probe.json`、`codex_script_probe_clean.json`：R-7。
- `browser-calibration.json`、`browser-negative.json`、`browser-final-check.json`、`model-ui-state.json`：R-6とUI/qposの実体。
- `actual-8084.png`、`gripper-manual.png`、`synthetic-calibrated.png`、`synthetic-source-flip.png`、`mobile.png`：画面証拠。
- `pytest.txt`、`viewer-tests.txt`、`ruff.txt`、`ty.txt`、`complexity.json`、`rust-tests.txt`、`clippy.txt`：既存ゲート。

再現コードはsandbox `temp/audit_delivery_source.py`、`temp/audit_motion_logs.py`、`temp/audit_adversarial_probes.py`、`temp/review_codex_fixture.jsonl`、gripper `temp/delivery_review_bridge.py`、`temp/delivery_review_viewer.py`、`temp/delivery_review_qpos.py`。どれも今回の検証で実機接続に使用していない。

実機再実行の前にR-1〜R-3を修正し、終了判定R-4/R-5を解決する。ライブ表示の実機化にはR-6・全軸校正が必要である。未修正のまま今回のレビューを実機運転の承認へ読み替えない。

## 追加要求：待機・電源OFF姿勢と現状写真

[姿勢定義](../reference-docs/STANDBY_POWER_OFF_POSITIONS.md)と[比較HTML](../reports/standby-position-20261004/POSE_COMPARISON.html)を作成した。追加写真を電源OFFの形状基準とし、裸アームのstandby方向をMuJoCoで検証した。肩角/neutralは未校正なので実機targetsはnull。写真近似のCAD角も実測ではない。5回の自己レビューと新規汎用skillを保存した。

レビュー用18084/18085 mockは終了し、18084はREAD bridge無しのmanual-only姿勢previewへ置き換えた。既存8084/他session不変。実機指令は実行していない。
