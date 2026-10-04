# スタンバイ姿勢と電源OFF姿勢（2026-10-04）

**13:03更新：実機でスタンバイ移行と元姿勢への復帰・全TorqueOFFを実行した。**
肩を現在位置近傍で保持し、肘を30°刻みで開き、手首を下向きに動かした。
カメラ原画像で前腕前方・先端下向きを確認。正確な世界角の校正は未完了。
スタンバイ時READは2064/3115/1969/1721/2059、脱力後は2064/3118/1159/2050/2059。
脱力後10秒200frameでspanは0/1/0/1/0count、全台OFF、欠測0、ポート閉鎖。
[実機の結果と原画像](../reports/robot-completion-20261004/standby-stage-resumed/STANDBY_ja.md)。
実電源OUTPUT OFFとクッションの荷重支持はまだ未確認。以下のnullや未実行表現は
初期検討時の履歴で、新実行記録で示した相対動作についてはこの更新を参照する。

**13:06追記：ユーザーが「電源きりました」と報告。** 報告後にカメラ3frameを
保存し、元の畳み姿勢付近を保つことを外観確認した。実電圧測定と支持荷重経路は
未確認。ユーザー指定で実機作業を一時停止し、記録・スキル・HTMLレポートだけを更新する。
電源OFF後の新しいモーターREAD／WRITEは行っていない。

**2つを別の名前で定義する。** スタンバイは前腕を前へ水平にし、ID5を下向き30°にする通電中の待機姿勢。電源OFFは、ユーザーが安定していると確認した現在程度の姿勢とクッションの配置を維持する状態にする。前側クッションは約5 mmという回答があり、荷重を実際に預ける接触点はまだ確定していない。

追加された[現状写真](../reports/standby-position-20261004/current-photo.jpeg)では、肩を引いて肘を畳んだ裸アームに見える。C7爪・D405ホルダーは見えていないため、[写真と裸アーム候補の比較HTML](../reports/standby-position-20261004/POSE_COMPARISON.html)を別途作成した。下記のC7/R5付き画像は将来装着を想定した比較例で、現在状態の再現ではない。

姿勢候補はMuJoCoで検討した。11:01の継続作業では、許可済みのID3限定約10°開閉試験だけを実機で実行し、元の位置へ復帰した（§5）。スタンバイ／電源OFFへの全軸移動は未実行。全軸の校正が未確定なので、実機へ送る姿勢目標カウントは未設定である。

## 1. STANDBY_FORWARD_DOWN30

世界前方を台座の正面+Y、上を+Zとする。中立yawがこの方向と一致することは実機で別に確認する。ID3の「手先リンク」は肘→手首の前腕リンク、ID4の30°は手首→ID5支持／ホーン軸の世界水平からの角度、として定義した。爪先やカメラ光軸の角度とは異なる。

| 実機ID・役割（ユーザー指定） | 待機時の要求 | R3 CADでの関係 | 未確定の実機値 |
|---|---|---|---|
| ID1 台座 | 中立、正面を向く | q1=0°をneutralに対応 | **現在neutral=2062 count**（D7）／方向sign未検証 |
| ID2 肩 | 現在程度に肘を引く | 校正した現在q2を維持 | q2、zero、sign |
| ID3 肘 | 前腕を世界前方へ水平 | **q3=q2** | target count、zero |
| ID4 手首 | ID5支持軸を水平から30°下向き | **q4=−30°**（前腕水平時） | target count、zero、sign |
| ID5 開閉 | 現物の中立角 | 現在neutralを維持 | **現在neutral=2059 count**（D7）／C7 θは未校正、現状は爪未装着 |

この式はR3のCAD軸Z/−X/+X/+Xだけに成立する。CAD相対角の名前と実機IDの一致は実物で確認が必要。工場の2048 countを各関節の中立やCADゼロとして自動採用しない。

MuJoCoでの例は **[q1,q2,q3,q4]=[0,−20,−20,−30]°、C7 θ=90°**。肩−20°とθ90°は表示用の仮値で、現在姿勢や実機中立の測定値ではない。肩を−20/0/+20°へ変えても前腕水平・ID5方向−30°になることを、実モデルの変換後の関節位置から確認した。

| 数値検査 | 結果 |
|---|---|
| 肘→手首の世界単位ベクトル | (0,1,0)、pitch0° |
| 手首→ID5支持の世界単位ベクトル | (0,0.8660254,−0.5)、pitch−30° |
| 3つの肩角例 | 全て向きPASS |
| 自己干渉／経路 | UNKNOWN、元Boolean入力対照ERROR |
| 無通電安定 | UNKNOWN、描画モデルは動力学未検証 |

[側面のMuJoCo表示](../reports/standby-position-20261004/standby-side.png)、
[斜め表示](../reports/standby-position-20261004/standby-iso.png)。
この通電待機候補では、ID5/爪/ホルダーの最下点は約95.33 mmで、5 mmクッション上面から約90.33 mm離れている（xy footprint未測定）。**この姿勢でそのまま電源を切る運用は定義しない。**

## 2. POWER_OFF_SUPPORTED_CURRENT

現在の安定姿勢を基準にする、というユーザーの指定を採用する。これを任意の「全軸0°」「全軸2048」「完全折畳みCAD姿勢」へ置き換えない。追加写真の形へ近づけたMuJoCo例は[0,−30,−75,+25]°だが、これは2D投影からの仮定で、現在関節角の復元・encoder校正・実機指令値ではない。裸アームのstandby例は[0,−30,−30,−30]°を使った。肩角は双方とも仮値である。

| 条件 | 定義 |
|---|---|
| 姿勢 | 今の安定した姿勢程度を保つ |
| 支持 | 台座前側のクッション、上面高さ約5 mm（ユーザー回答） |
| 荷重を預ける箇所 | 構造リンクの適切な箇所。実物の接触点・荷重経路は未記録 |
| 避ける支持 | カメラホルダー・レンズ・細い爪・ケーブルだけで重さを受ける |
| 最終状態 | 物理支持が成立し、Torque OFF後も予期しない移動がなく、その後に電源OFF |
| target counts/CAD角 | 未校正なのでnull。現在のsupported postureをfresh READと物理確認で記録後に設定 |

姿勢検討当初に使ったREADは **2026-10-04 00:21:38 JST**、ID1..5は **2054 / 3354 / 1154 / 2058 / 2059 count**、全Torque OFFだった。[履歴の出典とmetadata](../reports/standby-position-20261004/baseline-evidence.json)。継続作業で取得した現在の参照値は§5に記録する。どちらも再生指令ではない。

比較のため、R3の上腕と前腕を平行に畳むCAD例q3≈−97.78°・他軸0°も計算した。しかし仮組みした長尺カメラ／C7を含む幾何が机の下に約48.49 mm達した。この例は現在姿勢と一致しないため**電源OFF候補に採用しなかった**。現物の装着状態、肩・手首の角度を無視して「畳めば安定」と扱わない。

## 3. 状態遷移と停止手順

この遷移は仕様であり、スタンバイ／電源OFFの自動移動コマンドは未実行。[制御レビュー](../records/2026-10-04_delivery-review.md)の7修正と追加UI修正は継続作業で検証したが（§5）、全軸校正と支持・経路の実証は残っている。既存ID3限定commandを複数軸の移動へ拡張しない。

| 状態 | 次の状態 | 成立条件 |
|---|---|---|
| POWER_OFF_SUPPORTED_CURRENT | READ_CHECK | 支持を保ち電源を入れ、初めにREADのみで実角/設定を確認する |
| READ_CHECK | STANDBY_FORWARD_DOWN30 | 全軸校正・neutral・接続設定が確認済みで、支持解除と連続経路の検証が完了したときだけ |
| STANDBY_FORWARD_DOWN30 | LOWER_TO_SUPPORTED_CURRENT | 把持物を置き、校正済みの支持姿勢までの経路が確認済み |
| LOWER_TO_SUPPORTED_CURRENT | SUPPORT_VERIFIED | クッションが動かず、必要なリンクが荷重を受け、重心が支持から外れないことを確認 |
| SUPPORT_VERIFIED | TORQUE_OFF_VERIFIED | 支持を維持して脱力し、すべての関節が予期しない方向に動かず、Torque OFFをREAD確認 |
| TORQUE_OFF_VERIFIED | POWER_OFF_SUPPORTED_CURRENT | 動作が止まり、荷重が支持に預けられたことを確認して電源OUTPUT OFF |
| 条件未成立／異常 | STOP_WITH_SUPPORT | 腕を支える。通信切断と物理支持を別々に扱い、空中で自動脱力しない |

すでに現在姿勢で全Torque OFFなら、待機姿勢へ移すためだけにトルクを入れる必要はない。支持が成立しているその状態を電源OFFの基準として先に記録する。再起動時も保存済みの古い目標へ急に動かさず、現在位置・mode・direction・alias・エラーをREADしてから制御を開始する。

## 4. 再現と機械可読仕様

[positions.json](../reports/standby-position-20261004/positions.json)はsimulation_only=true、hardware_targets=null。standbyの肩角とID5 physical neutral、電源OFFのtarget/接触点はnullを残している。
[支持面との差の検査](../reports/standby-position-20261004/support-geometry-check.json)はmesh頂点の幾何結果であり、接触・摩擦・重力安定の検査ではない。

再現スクリプトは[`verification/evaluate_arm_park_pose.py`](../reports/standby-position-20261004/verification/evaluate_arm_park_pose.py)。これは解析用artifactで、MuJoCoを含むgripperのuv環境から、2つのworkspaceを明示して実行する。sandboxの監視パッケージへ描画依存を追加していない。

```bash
cd /home/inaho-omen/Project/3d-printed-dynamixel-gripper
rtk proxy uv run --no-sync python \
  /home/inaho-omen/Project/my_dynamixel_arm_sandbox/reports/standby-position-20261004/verification/evaluate_arm_park_pose.py \
  --simulation-root /home/inaho-omen/Project/3d-printed-dynamixel-gripper \
  --baseline /home/inaho-omen/Project/my_dynamixel_arm_sandbox/reports/standby-position-20261004/baseline-evidence.json \
  --output-dir /home/inaho-omen/Project/my_dynamixel_arm_sandbox/reports/standby-position-20261004 \
  --example-shoulder-deg -20
```

別のアームにも使う手順は[robot-park-pose-definition skill](../skill-notes/robot-park-pose-definition/SKILL.md)にまとめた。R3式はreferenceへ分離した。

操作用の[MuJoCoプレビュー](http://127.0.0.1:18084/)を起動している。初期値は裸アームのCAD検討例[0,−30,−30,−30]°で、READ bridgeは未設定、読取り開始ボタンも無効。実機の現在状態は反映していない。再起動はverificationの[`start_manual_preview.py`](../reports/standby-position-20261004/verification/start_manual_preview.py)へ`--simulation-root`と`--port 18084`を渡す。

写真比較画像の再生成は同じverificationディレクトリの[`render_arm_park_examples.py`](../reports/standby-position-20261004/verification/render_arm_park_examples.py)に、`--simulation-root`、`--output-dir`、`--photo`を明示して実行する。実機通信は含まない。

残件は全軸の物理校正、現物版と装着状態、支持点とクッションの変形、荷重／摩擦、全経路の衝突・配線確認である。姿勢の定義と向きの検証は完了したが、実機の新しいスタンバイ移動・電源OFF移動の実行値はまだ確定していない。

## 5. 11時台の実機確認と現在姿勢の参照

[継続作業書](../workdocs/workdoc_Oct04-2026_robot_completion.md)で7件の不具合と追加の校正UI問題を修正した。[品質ゲート](../reports/robot-completion-20261004/repair-gates.json)はPython252件、viewer108件、Rust3件、lint・型・複雑度・diff検査が成功。

11:01のID3試験では **1154 → 1264 count（約9.67°）→ 1154**、目標1268との差−4、復帰誤差0、他4台の最大変化0だった。最後の全台TorqueOFFとPWM/速度/加速度の復元をREADで照合した。[独立検証](../reports/robot-completion-20261004/id3-actual-validation.json)。これはencoderによる限定動作の確認であり、全軸校正や支持接触の証拠ではない。

[電源OFFの現在参照](../reports/robot-completion-20261004/power-off-current-reference.json)を事後READから保存した。全台TorqueOFFの5秒100サンプルで以下の値は変化しなかった。11:15台のブラウザREADでも同じcountだった。

| ID | 現在参照count | 5秒内のspan | CAD角／neutral |
|---|---:|---:|---|
| 1 | 2062 | 0 | 現在neutralをユーザー確認済み（D7） |
| 2 | 3354 | 0 | 未校正 |
| 3 | 1154 | 0 | 未校正 |
| 4 | 2058 | 0 | 未校正 |
| 5 | 2059 | 0 | 現在neutralをユーザー確認済み（D7）、C7機構角は未対応 |

参照ファイルは写真・実READのSHAとsession、各関節の座標設定を保存する。`motion_target_counts=null`、`execute_allowed=false`を維持する。ユーザーの「現在程度で安定」という報告とencoderの無変化は記録済みだが、クッションの接触点・荷重経路・実電源OFFは未実確認である。

新しい[実機READ／校正ビューアー](http://127.0.0.1:18096/)はREAD bridge 18097へ接続する。専用Playwrightによる10秒200回、約20Hz、欠測0、終了後port closedを確認した。[ブラウザ証拠](../reports/robot-completion-20261004/actual-live-browser-check.json)。全軸校正は未適用、実角描画は保留。基準CAD姿勢はボタンで表示できるが、写真の現在姿勢を全軸0°にはしていない。

D7でユーザーは現在のID1/ID5をneutral、爪とD405ホルダーを未装着と確認した。基準合わせは自動を希望している。現在PCにはvideo device／USBカメラが見つからない。元R3資料はCAD zeroとencoderを別に扱い、元robot.pyにも実機機械offsetは無い。全軸の自動基準合わせは、外部で観測した角度または組立時のcount対応が得られるまで未実行である。

## 6. 12時台の更新（過去の参照値を上書きしない）

上のカメラ未接続とcountは11時台の記録。12時台にUSBカメラを接続し、12:29の
再接続で映像を復旧した。台座移動後のID2は3129前後で、以前の3354ではない。
12:30にID3だけの30°試験を撮影し、1154→1498→1156 count、約30.23°の開きと
復帰を映像でも確認した。全台TorqueOFF、RAM復元READ一致、独立17項目PASS。
[原画像と記録](../reports/robot-completion-20261004/camera-id3-30/REPORT_ja.md)。
これは相対角確認であり、絶対CAD角の校正と新しいstandby移行は未完了。

校正ソフトはend_effector=bareを明示する場合にC7のθをnullで保存・変換する。
爪とホルダーを非表示にし、未装着機構の開度を数値で示さない。現物基準の確認、
実READのsource/session/context拘束は引き続き必須。J3のmanual/live表示範囲を
一致させたが、この表示範囲を安全可動域として採用しない。
