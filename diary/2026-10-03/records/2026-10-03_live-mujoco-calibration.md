# 2026-10-03：read-only live MuJoCoと校正画面
記録者Codex。ソフト実装と実測の記録。現物校正・肘の動作試験は未完了。

[前の現状調査](2026-10-03_current-arm-findings.md)を基に、[live作業書](../workdocs/workdoc_Oct03-2026_live_mujoco.md)をwrite-workdoc-uv/review-written-workdoc/start-work-with-docsで作成・実行した。実機を描画する受け口だけでなく、現在値を連続取得するbridgeを実装した。

## 実装
新workspaceの `arm-live` はtyped immutable LiveSnapshotを持つlocalhost HTTP bridge。constructorとGET statusはシリアルを開かない。画面の明示startでopen_bus（ownership/exclusive/guard）を通じて取得し、既存Reader/observeを使う。定格20Hz sync、metadata30秒。JSONL v2を各行flushで保存し、終了後にend/port_closed=trueを記録する。
stopは読取りの取消でありTorque OFFを書かない。通信中はstopping/closed=false、worker完了後のみclosed=true。例外では閉鎖をunknownとし、未確認を成功扱いにしない。通信先・ID・Mode等をHTTPから変更するAPIはない。SDK/transport/guardをrendererへコピーしていない。

隣gripperのMuJoCo viewerは `--live-url` でbridgeを受け、パッシブなpollを描画と別threadで行う。ユーザーは手動表示と校正済みREAD姿勢を切り替えられる。R3/C7/長尺R5候補のmodel/meshは変更していない。描画はmj_forwardのみ、動力学・安全範囲の合格ではない。

## 校正画面
ID、CAD関節J1〜J4/PG3、基準count、sign±1、PG3 θを入力し、現物対応・基準姿勢・方向・適用の4確認を行う。基準はJ1〜J4=0°と入力したPG3角のCAD姿勢。「現在値取込」は現物がこの基準と一致した確認後に使う。任意の折畳状態をCAD0°とする機能ではない。
校正JSONを保存/読み込みできる。import時は確認を外し、CAD版不一致とsynthetic校正のhardware流用を拒否。校正をsession、CAD+scene/provenance signature、ID/model/FW、mode/drive/homing/baud/protocol、Torqueへbindする。
fresh frameはtimezone付きで1秒未満、metadata31秒未満を要求。metadataの変更検知は30秒refresh周期であり、瞬時にあらゆる外部変更を検知すると保証しない。mode3は最短4096count差、mode4は線形。座標系が変わる入力やfault/alert/欠損/古さ/終了でlast poseを保持し、校正を無効化して再確認を要求する。

## 実機READ（21:22 JST）
[検証JSON](../reports/live_hardware_validation.json)、[browser JSON](../reports/live_hardware_browser.json)、[active画面](../reports/live_hardware_active.png)。
1回の有限10秒、200frame、約19.999775Hz、incomplete=0、deadline_misses=0、202 JSONL record schema適合。1000motor sampleのfault/alert/hardware error/position null=0。全Torque OFF。終端のport_closed=true。
countのmin/maxはID1=2051〜2054、ID2=3354、ID3=1153、ID4=2058〜2059、ID5=2059。終了時9.0〜9.1V、35〜36°C。これは記録時点の観測で、現在継続READ中と表示しない。実物校正がないためsource=manual/can_render=falseを維持した。motor writeは0。
実物の動きを起こした試験ではない。ID1の微小変化はREADの事実であり、今回送信した目標による動作と扱わない。

## synthetic対照と品質
[synthetic browser JSON](../reports/live_synthetic_browser.json)と[画像](../reports/live_synthetic_calibrated.png)は実機と別のlocalhost fixture。fixtureでcounts1128/936/1000/1000/1128、zero1000、sign1/-1/1/-1/1からJ1=11.25°/J2=5.625°/J3=0/J4=0、PG3 θ101.25°をactual compiled MuJoCoへ反映した。確認を省いた適用を拒否。古いframeを送ると同姿勢を保持し校正を解除した。fixture用calibration-test folderとsimulated=trueを用い、実物校正と混同しない。
observerのPython77件、ruff、ty、complexity最大10/閾値10、Rust3件、Clippy成功。viewerは新40+既存14=54件、対象ruff成功。各結果は[reports](../../../reports)のlive_quality_*とlive_final_viewer_*を参照。v2 schema/fixtureは不変。
Playwrightは専用headless2session。decoded1060×760/frame増加を確認。ユーザー用headed browserの既存3tabを残し、MuJoCo tabを更新した。初回scriptのrequire未定義、fixture CORS/import path、windowの実行文脈エラーを修正して再検証。これらをhardware試行として数えない。consoleの過去restart中接続エラーと、安定run時0errorを区別した。

## 5回の自己レビューとスキル化
[skill](../../2026-10-04/skill-notes/robot-live-calibration/SKILL.md)をproject-localに作成し `.codex/skills` で発見できるようにした。汎用の[検証表](../../2026-10-04/skill-notes/robot-live-calibration/references/verification-matrix.md)とGET-only probeを含む。probeは実行しframe進行/renderer errorなし、skill quick_validateはgripper既存uv環境でPASS（observer環境にはPyYAMLがなくvalidatorは起動不可だったため、不要な依存追加を避けて既存環境を使用）。

| 自己レビュー | 見つけたこと・改善 |
|---|---|
| 1：lifecycle | constructor無通信、finally終了前の閉鎖表記を区別。例外のclosedをunknownにした |
| 2：校正/数値 | ID一意、sign/bool/int境界、mode wrap、metadata/torque/session失効を正負対照にした |
| 3：browser再現性 | require/file writeの環境差を避けreturn値で保存。decoded画像とframe増加を待つ |
| 4：試験と実物 | synthetic校正を別folder/flagに分離しhardware流用を拒否。import CAD版も確認 |
| 5：視点と移植性 | 最初の135°斜めは爪が隠れるため225°へ変更。「爪を拡大」も確認。skillのdevice/path/URLは引数・repo設定にする |

これはCodex自身の5観点レビューで、独立agent5名のレビューではない。表示と試験が成功しても、旧CAD collision Boolean ERROR/UNKNOWN、75°版との区別、実物取付可否は未解決。

## ID3を低速約10°開く追加要求
ユーザーはID3=肘、現在完全に畳んでいることと、開く方向を確認した。これは現物報告で、1153countだけから推定した情報ではない。
[専用作業書](../workdocs/workdoc_Oct03-2026_id3_open_10deg.md)へ全6手順×4行をwrite/review済み。最初のintakeをstart-work-with-docsで進め、次に開くcount増減・CAD基準・重力支持/停止手段を確定する。その後に単一ID3/最新count起点/約114count=10.0195°/低速/有限/異常監視の専用controlを試験・実行し、現物/READ/MuJoCoを照合する。read-only observer guardは変更しない。
動作未実施。方向/基準/支持情報を質問中。最新READなしで21:22の1153を目標の基準へ固定しない。
速度ベースのProfile Velocityは0.229rev/min単位、0は無制限なので、現状のprofile0で「ゆっくり」としない。元のdocs.robotis.com URLはweb toolから取得不可だったため、[ROBOTIS公式eManual](https://emanual.robotis.com/docs/en/dxl/x/xl430-w250/)と[公式repository](https://github.com/ROBOTIS-GIT/emanual/blob/master/docs/en/dxl/x/xl430-w250.md)で再確認した。Torque OFF時のposition表現とTorque ONの座標変化も動作仕様の対象。

## 終了時の照合と次の停止点
live作業書の通常32項目とDoD4項目は完了。ID3専用作業書は手順1の4項目を完了し、手順2の現物情報が未確定なので未チェックを維持した。[motion intake](../reports/id3_motion_intake.json)はmotion_ready=false。Motor writeは未実施。
最終の元入力照合では36件中33SHA不変、observer.pyとpyproject.tomlの意図した2変更、版照合REPORTの1更新を確認した。REPORTは20:59:22に更新されlive作業開始より前で、P05配線窓の追記がある。全文とSHAを確認して履歴の更新として保存し、候補版/実物未確認の扱いは維持した。初回検査の失敗を見落としてチェックを早く付けた誤りは作業書で取消して再検査した。
[最終検査JSON](../reports/live_document_validation.json)はローカルリンク欠落0、両repo diff check0、R3 STEP/C7 donor sourceのSHA一致を確認する。Skill validator/probeも再実行PASS。actual viewer8084/bridge8085は利用でき、bridgeはidle相当のstoppedでポート閉鎖済み。試験専用8086/8087は停止した。新規文書・スキル・実装はローカル保存のみ。

