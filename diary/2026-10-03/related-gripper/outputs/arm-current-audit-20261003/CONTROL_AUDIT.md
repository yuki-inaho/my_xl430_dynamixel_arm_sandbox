# 全XL430・ID5開閉構成の制御実装確認（2026-10-03）

対象は `/home/inaho-omen/Project/low_cost_robot` のコミット `f29f33b3b99320b3ad35171ec08897bede459fbb`。コードを読み、ROBOTIS公式仕様と公開実装をWebで照合した。一部はSDKをimportしないオフライン偽応答で再現した。元コードの修正や実機への送信は行っていない。

## 1. 指摘の検証結果

| 項目 | 現コード | 全XL430構成で必要な扱い | 根拠 |
|---|---|---|---|
| Operating Mode | `dynamixel.py:155`、address 11にwrite2ByteTxRx | **11は1バイト**。12のSecondary IDまで書込み要求の対象になる。不適切な設定や拒否の可能性がある。実機がどう応答したかは未確認 | [XL430公式Control Table](https://emanual.robotis.com/docs/en/dxl/x/xl430-w250/#control-table-of-eeprom-area)、公式SDKのwrite2ByteTxRx実装 |
| 電圧 | `ReadAttribute.VOLTAGE=145` | **144から2バイト、0.1 V単位**。定数が1バイトずれる。専用read_voltageメソッドはないので、既存呼出し全部が誤読したとは断定しない | [公式RAM表](https://emanual.robotis.com/docs/en/dxl/x/xl430-w250/#control-table-of-ram-area) |
| read_current | address 126をCURRENTと呼ぶ | XL430では **Present Load、推定負荷0.1%単位**。電流mAや実測トルクとして使わない | [Present Load](https://emanual.robotis.com/docs/en/dxl/x/xl430-w250/#present-load126) |
| 使用可能モード | enumに5があり4がない。モデル別制限なし | XL430は **1/3/4/16**。電流ベース位置制御5は非対応。enumにあるだけで5が現在実行されたとは言えない | [Operating Mode](https://emanual.robotis.com/docs/en/dxl/x/xl430-w250/#operating-mode11) |
| Hardware Alert | `_process_response` と `_read_value` がerror=128を電圧エラーとして無視 | **0x80はHardware Alert全般**。Hardware Error Status 70で原因を読む。正常扱いしない | [Protocol 2.0 Error](https://emanual.robotis.com/docs/en/dxl/protocol2/#error) |
| 読出しの副作用 | `read_home_offset` が64へ0を書き、読んだ後1を書く | 読出しは書込みをしない。設定変更では事前の状態を保存し、無条件にトルクONへ変えない | [偽応答による再現](control-offline-reproduction.json) |
| EEPROM | publicなモード・PWM Limit・Velocity Limit setterは自らTorque OFFを保証しない | Torque Enable=0で変更し、結果・readbackを確認する。Robot側のモード切替にはOFF処理があるがsetter単独は別 | [XL430公式EEPROM要件](https://emanual.robotis.com/docs/en/dxl/x/xl430-w250/#control-table-description) |
| Goal書込み結果 | `Dynamixel.set_goal_position` は返り値を無視。RobotのchangeParam/txPacketも未確認 | 送信・受信エラー、per-ID応答、更新成否、状態の鮮度を扱う | [偽応答による再現](control-offline-reproduction.json) |
| SyncRead失敗 | 最後のretry失敗でもgetDataに進む。isAvailable確認なし | 不完全／古い状態から次の目標を作らない。偽の失敗応答でも位置リストが返ることを再現 | `robot.py:72`、[再現結果](control-offline-reproduction.json) |
| 速度・加速度 | Profile Acceleration 108、Profile Velocity 112、Watchdog 98の初期化をこのラッパーで確認できない | モード変更後の設定とreadback、host側の時刻・追従監視が必要。profile=0は停止や低速の意味ではない | [公式Profile](https://emanual.robotis.com/docs/en/dxl/x/xl430-w250/#what-is-the-profile) |
| 符号変換 | signed32が `>` を使い0x80000000を正の2147483648として返す。PWM・offsetも符号を正規化しない | 2の補数の境界を含め、フィールドごとに型・単位・有効範囲を定義する | [境界値の再現](control-offline-reproduction.json) |
| IDの不一致 | Robotデフォルトは1〜5、`teleoperate_real.py` は1/2/3/4/6/7 | 5台の現物対応表を使い、leaderの値をそのまま送らない。ID5開閉は設計要求だが実機ID照合は未完 | [旧teleoperate_real.py](https://github.com/yuki-inaho/low_cost_robot/blob/f29f33b3b99320b3ad35171ec08897bede459fbb/scripts/teleoperate_real.py) |
| 衝突ガード | `set_goal_pos` に関節域、経路、カメラ、配線の検査がない | 目標と移動経路の可否を通信層に渡す前に判定する | 現コードの読み取り |

追加の確認: `_BAUDRATE_MAP[4_000_000] = 6` は公式表と一致する。6=4 Mbps、7=4.5 Mbpsであり、**この対応を不具合としては記録しない**。

Operating Modeの誤った呼出しは、偽PacketHandlerに対して「ID1、address11、size2、data3」と記録された。公式SDKでは2バイトのデータを連続アドレスへ送ることを確認した。副作用の危険はコードからの推論で、実機のSecondary IDが実際に変わったという観測ではない。

## 2. 旧IKの問題

`low_cost_robot/simulated_robot.py` はbody IDを取得して `d.geom_xpos[body_id]` を読み、そのbodyの重心ヤコビアン `mj_jacBodyCom` で誤差を補正する。body・geom・siteは別の添字で、位置とヤコビアンの対象点も合わせる必要がある。[MuJoCoデータ配列](https://mujoco.readthedocs.io/en/stable/APIreference/APItypes.html#mjdata)、[公式Jacobian API](https://mujoco.readthedocs.io/en/stable/APIreference/APIfunctions.html#mj-jacbodycom)。

旧proxyモデルを読み込み、実機と無関係な `mj_forward` のみで確認した結果:

- デフォルトのbody名 `end_effector` は存在せず、名前検索でエラーになる。
- `joint4` のbody ID=5をgeom添字に使うと、別部位 `xl430proxy_joint3` の位置を読む。
- `joint5` のbody ID=7をgeom添字に使うと、別部位 `joint4` の位置を読む。

証拠: [legacy-ik-index-diagnostic.json](legacy-ik-index-diagnostic.json)。既存IKは位置誤差に対する1回の疑似逆行列更新であり、収束判定、実物のTCP、4軸アームへの対応、衝突、速度・加速度の制約を保証するIKではない。

改善方針は、把持点を明示的なsite/TCPとして固定し、その点の位置と `mj_jacSite` 等のヤコビアンを合わせること。解を得た後に関節域と経路を検査する。現行はアーム4軸＋開閉1軸なので、任意の6自由度姿勢を自由に要求する仕様にはしない。

## 3. Webで調べた関連実装

取得は2026-10-03。OSSコードをコミット固定で保存し、[web-evidence/manifest.json](web-evidence/manifest.json) に取得日時、ファイルハッシュを記録した。インストールや実行はしていない。

| 実装 | 参考にできる部分 | このアームへ合わせる変更 |
|---|---|---|
| [ROBOTIS DynamixelSDK](https://github.com/ROBOTIS-GIT/DynamixelSDK/blob/f838bc90f72fcf5b9c279432d6e12fc24969daa8/python/src/dynamixel_sdk/protocol2_packet_handler.py) | サイズ別Read/Write、通信結果とデバイスエラー。確認コミットf838bc9 | XL430の正しいcontrol table、per-IDの状態・時刻管理を上に設ける。SDK自体はアームの衝突を判断しない |
| [LeRobot KochFollower](https://github.com/huggingface/lerobot/blob/ff71cae1ae2d09fd035553c35da65888ed6c8304/src/lerobot/robots/koch_follower/koch_follower.py) | 関節名とモデル・IDの対応、校正保存、SyncRead/Write、トルクOFFでの設定、任意の1回の目標差制限。確認コミットff71cae | 標準は6台・XL430/XL330混在。rollを除き、ID5を開閉にし、全モデルを実機と照合。標準gripper設定はモード5なのでXL430には移さない |
| [LeRobot tables.py](https://github.com/huggingface/lerobot/blob/ff71cae1ae2d09fd035553c35da65888ed6c8304/src/lerobot/motors/dynamixel/tables.py) | レジスタごとのサイズ、モデル別モード、4096分解能の辞書 | 汎用X_SERIES表は126をPresent_Currentと呼ぶ。**XL430では公式仕様のPresent_Load**を使う。共有表だから全フィールドが全モデルにあるとは扱わない |
| [MoveIt PlanningScene](https://moveit.picknik.ai/main/doc/examples/planning_scene/planning_scene_tutorial.html) | URDFのcollision形状による自己干渉・環境衝突、Allowed Collision Matrix | 現物版の衝突形状、4軸＋PG3の構成、限定した許容接触を作る。0°の接触相手を全姿勢で一括除外しない |
| [MoveIt Python path API](https://moveit.picknik.ai/main/doc/api/python_api/_autosummary/moveit.core.planning_scene.html#moveit.core.planning_scene.PlanningScene.is_path_valid) | 軌道に含まれる各状態の衝突・実行可能性検査 | このAPI名だけで中間の連続掃引が証明されるわけではない。サンプリング間隔と形状の変位上限、または連続判定を別途定義する |

LeRobotの `max_relative_target` は現在位置からの目標差を各軸でクリップする。`send_action` とそのhelperには全アームの衝突計算はなく、単独ではカメラと肩・台座の接触を防げない。これは確認したコードの範囲からの判断である。

MoveItの標準自己干渉検査はURDFの衝突形状を使う。環境向けpaddingがそのまま自己干渉の必要余裕になるとは仮定しない。いまの低背版URDFは版が違い、55面部品や未校正の動力学値もあるため、現物用として直ちに投入できる入力ではない。

## 4. 実装を進める場合の分担

通信・校正層で生のcountを物理角へ変換し、幾何・経路層で目標と移動経路を検査し、実行層で時刻・応答・追従・Hardware Alertを監視する。IKの解、校正した単軸の範囲、SDKの通信成功は、それぞれ別の証拠である。

現在必要な値を推測で埋めた実機設定ファイルは作っていない。[制御仕様の草案](CONTROL_SPEC_DRAFT.md) にnull相当の未確定項目を残す。
