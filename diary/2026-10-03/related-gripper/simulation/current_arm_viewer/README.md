# 現状候補アームのMuJoCoビューア

写真に近い **R3系アーム＋旧C7爪＋長尺D405 R5（65°を第一候補）** の仮組み姿勢を、ブラウザで操作・描画する。写真では爪とホルダーは未装着で、実際にこの一式が組み付くと確認したモデルではない。75°短縮候補にも切り替えられる。

版照合は [写真の報告](../../temp/photo-version-check_20261003/REPORT_ja.md)、可動域・元ブランチ・制御実装の調査は [調査報告](../../outputs/arm-current-audit-20261003/REPORT.md) を参照する。最新版V2のマニュアルと、この旧C7表示モデルを混同しない。

## 起動と操作

リポジトリのルートで、既存の固定環境を使用する。

```bash
rtk proxy uv sync --locked
rtk proxy uv run --no-sync python simulation/current_arm_viewer/build_model.py
rtk proxy uv run --no-sync python simulation/current_arm_viewer/server.py --port 8084
```

[http://127.0.0.1:8084](http://127.0.0.1:8084) を開く。四つのアーム関節、PG3機構角θ、連続再生・停止、ホルダー版、爪／カメラの表示を操作できる。「爪を拡大」で開閉を見やすくし、ドラッグ・ホイールと四つの視点ボタンで表示方向を変える。「全体」は全アーム表示へ戻す。

サーバーはlocalhost限定。MuJoCo 3.13.0のPython RendererをEGLで動かし、1060×760のJPEGを毎秒約20枚生成する。ブラウザは更新されたフレームを取得する。WASMや別の3D代理モデルは使っていない。非同期更新で描画・通信の遅延がある。ソフトウェアを再起動すると画面入力の姿勢は初期化される。終了は起動した端末でCtrl+C。

## モデルの範囲

- R3 STEPのM01〜M05／P01〜P05を180要素すべて採用。体積を持たない55要素の面も描画に保持。旧M06/P06/P07を含めない。
- J1〜J4はR3の保存軸・中心を使用。CAD J番号、物理ID、旧URDF joint番号を同一視しない。
- C7は元設計のθ=25〜135°、クランク半径14 mm、リンク24 mmの非線形閉路を再現。二つの受動スライダと二つのリンクの姿勢も追従する。アーム4自由度とPG3開閉1自由度で、独立rollはない。
- 表示用のメッシュ近似は元から線形偏差0.12 mm。元STEPの修復や衝突検査の許容値変更は行わない。
- モーター内部の参考部品はケースと一体で描画。実配線の変形は未再現。カメラは名目外形とケーブル出口の短い代理形状。

**運動学・姿勢のビューアであり、自己干渉の合格判定や物理動力学のシミュレーターではない。** 全表示形状の接触判定を無効にし、`mj_forward`で配置する。`mj_step`による積分、モーター制御、速度・加速度の実機設定は行わない。コンパイル用の質量・慣性は仮値で、荷重・保持トルク・落下・材料たわみを再現しない。

スライダの端は過去のCAD調査範囲を基にした「表示範囲」で、安全リミットではない。長尺65°の旧診断では手首+112°にカメラ取付板とM03の衝突があり、画面には+110°超で注記する。旧診断の除外ペアとBoolean対照には未解決点があるため、これを現物の安全限界として適用しない。

## 実機READログの入力

このサーバーにシリアルポート・DYNAMIXEL SDK・motor送信処理はない。[読み取り専用observer](../../../../../README.md) のschema_version=2 JSONLを参照する旧fileアダプターを備える。初版のfile検証では実機通信を行っていない。追加のlive pathと実機READ結果は末尾を参照する。

```bash
rtk proxy uv run --no-sync python simulation/current_arm_viewer/server.py --port 8084 \
  --telemetry-jsonl /absolute/path/to/watch_session.jsonl
```

校正なしでは生のID別countと欠測状況だけを表示し、実機姿勢への切替は無効になる。校正テンプレート [calibration.template.json](calibration.template.json) のnullは未確定値であり、そのまま使える設定ではない。各関節の実物ID、CAD保存姿勢でのPresent Position、回転方向、PG3の対応θを確認して別ファイルに保存した場合のみ、`--calibration /absolute/path/to/verified-calibration.json` を追加できる。両verifiedフラグとCAD SHAが合い、5役割・ID重複なし・整数のゼロ値・sign=±1であることを要求する。旗をtrueにするだけでは実測の代わりにならない。

変換は `sign × (count − zero_count) × 360 / 4096`。PG3だけ対応θを足す。Homing Offset、Operating Mode、回転周回数、モーター取付けを変更したら校正が失効する。このアダプターはEEPROM変更や未記録の周回を検知しないため、確認した同一構成・同一読値座標系に限って使用する。

2026-10-04追加: 現物の非ゼロCAD角が独立に確認された場合は、zero_count=null、
reference_countとreference_angle_degを保存できる。変換は
`reference_angle_deg + sign × count_delta × 360 / 4096`。mode3のcount_deltaは
最短の4096差、mode4は線形。ゼロ基準と観測基準の同時指定や不完全な観測を拒否する。
UIの「観測CAD角」を空欄にするのは、現物がCAD0°と一致すると確認した場合だけ。
装着状態bareではPG3 θ=nullを保持し、未装着の爪・ホルダーと開度を表示しない。
観測基準にも元の現物確認・source/session/context拘束が必要で、画像比較の仮角は
自動的に確認済み校正にならない。

最後の完全なフレームの時刻が1秒以内で、position欠測・Hardware Alert・ハードウェア異常・読取fault・ID重複がなく、全校正IDが存在し、変換角が表示範囲内の時だけ更新する。未完のJSONL行は無視し、EndEventは観測終了として扱う。実機入力中の欠測では最後の姿勢を保持し、画面に古いデータであることを示す。ゼロ角への置き換えはしない。長時間のログも末尾256 KiBだけを読む。

読み取りを開始するときはobserver側のAGENTS.mdと`dynamixel-readonly-status`スキルに従い、ポート所有者、電源、設定、読取り許可を確認する。既存ポート使用者を終了させない。旧`low_cost_robot.robot.Robot`を構築しない。監視READもBus Watchdogの時刻を更新し得る。

## 検証

```bash
rtk proxy env MUJOCO_GL=egl uv run --no-sync pytest -q tests/test_current_arm_viewer.py tests/test_current_arm_live.py tests/test_direction_observation.py
rtk proxy uv run --no-sync ruff check simulation/current_arm_viewer tests/test_current_arm_viewer.py tests/test_current_arm_live.py tests/test_direction_observation.py
```
2026-10-03 23:02時点で3ファイル計100件。

輸出してMuJoCoが読み込んだ実メッシュを、独立したC7 CADの6姿勢と比較する。曲面の再メッシュ化は表示近似0.12 mmの契約内で評価し、平面パッドの開度は0.00002 mmまで照合する。2°誤った開閉角を負の対照とし、近似範囲に紛れないことも確認する。実機ログは合成データで変換・方向・欠測・異常・未校正・終了・未完行・長いファイルを検査する。実機の校正値や動作の検証ではない。

Playwrightの検証と画像は [VIEWER_REVIEW.md](../../outputs/current-arm-mujoco-20261003/VIEWER_REVIEW.md)。生成モデルと出所は `outputs/current-arm-mujoco-20261003/scene.xml`、`model-provenance.json`。描画テストの合格で、CAD衝突検査のERROR/UNKNOWNを合格へ読み替えない。

## 実機liveと校正パネル（2026-10-03追加）
読み取りworkspaceで `rtk proxy uv run arm-live --port 8085` を起動する。本repoでは次のコマンドを使う。既存の8084を自分が起動していた場合は、その端末で終了してから再起動する。他人のserverを停止しない。
```bash
rtk proxy uv run --no-sync python simulation/current_arm_viewer/server.py --port 8084 --live-url http://127.0.0.1:8085
```
画面の「読取り開始」で実機へ接続し、「読取り停止」で読み取りを取り消す。Torque/Goalへの送信ではない。agentの確認は「10秒の確認」、ユーザーが連続表示する場合は「停止まで継続」を選べる。
校正パネルのID/基準count/sign/PG3 θを現物から入力する。J1〜J4=0°と入力したPG3 θの基準CAD姿勢を表示し、現物が一致したと確認してから現在値を取り込む。4確認をチェックし「校正を保存してlive表示」。importした値も確認をやり直す。校正JSONはmodel出力下へ保存し、画面からexportできる。
liveはsession、model、motor identity/settings/Torqueを校正条件として保持する。変更・欠損・古い入力・終了で更新を保留し再確認が必要。mode3は最短の4096count差、mode4は線形（表示範囲外なら拒否）。metadata refresh30秒、frame1秒・metadata31秒の期限を検証する。旧file adapterと異なりlive pathはmetadata/contextを検査する。
[実装・実測の記録](../../../records/2026-10-03_live-mujoco-calibration.md)。21:22の有限READは20Hz/200frame/10秒、欠測/期限超過0、終了port_closed=true。実物の校正値と安全範囲はまだ未確認。試験用校正はsimulated=true/calibration-testに分離し実物へ流用しない。

## 肘を開くcount方向の2点記録（2026-10-03追加）
「肘を開くとcountが増えるか記録」パネルは、同じREAD session・同じmotor設定・Torque OFFの2読値を、現物確認（完全に畳んだ位置／肘を開いた変化）付きで保存する。保存先は `outputs/current-arm-mujoco-20261003/direction-observations/{hardware,synthetic}/`。差分20 count未満（静止時の揺れ程度）と1024 count以上（周回の符号曖昧）は「未確定」として保存しない。1回の確認で1件だけ保存し、保存後はbaselineを消費する。再記録は「畳んだ位置」からやり直す。書込み失敗時に部分ファイルを残さない。
結果の `opening_count_sign` は「報告された開く動作中のcountの増減」であり、CAD校正の符号ではない。モーターへの書込み・校正値・表示姿勢は変更しない。ID3の約10°開く制御は読み取りworkspaceの `arm-id3-open`（既定はdry run）がこのhardware記録を入力に使う。
