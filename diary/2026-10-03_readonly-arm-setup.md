# 2026-10-03 実機状態確認と新しいuv作業環境

## 依頼と範囲

5台をデイジーチェーン接続した現状を詳しく確認し、今後の作業場所を
`~/Project/my_dynamixel_arm_sandbox` に用意した。実機操作は情報読み取り専用。
状態確認スキルを `skills/` に作成し、`low_cost_robot` と
`3d-printed-dynamixel-gripper` のスキル・関連スクリプトもコピーした。

日時は `date --iso-8601=seconds` で確認した。作業開始は2026-10-03 18:29 JST。
接続はDXHUB E148、安定したデバイス名は
`/dev/serial/by-id/usb-BestTechnology_E148_E148-if00-port0`、実体は `/dev/ttyUSB0`。
確認前に `fuser` で占有なしを確認し、終了後にも占有なしを確認した。

## 実機で確認できたこと

最初の詳細読み取りは18:30:45開始、正式CLIでの再確認は18:37:24〜18:37:39。
正式確認ではID 0〜252を1 Mbps・Protocol 2.0で検索し、ID 1〜5だけが応答した。
全台モデル番号1060、XL430-W250。読み取り失敗なし。

| ID | Firmware | 現在位置の観測範囲 | 入力電圧 | 温度 | Torque | Hardware Error |
|---|---:|---:|---:|---:|---|---:|
| 1 | 43 | 2550〜2551 | 9.2 V | 33 C | OFF | 0 |
| 2 | 42 | 3336〜3337 | 9.2 V | 34 C | OFF | 0 |
| 3 | 42 | 1135 | 9.0 V | 34 C | OFF | 0 |
| 4 | 42 | 2059 | 9.1 V | 33 C | OFF | 0 |
| 5 | 43 | 2059 | 9.1 V | 32 C | OFF | 0 |

全台、設定読取時と3回のテレメトリ観測でTorque OFF、Moving=0、現在速度=0、
Present PWM=0、Present Load=0、Hardware Error=0だった。
ID1とID2に1カウントの変化があるため「完全に位置変化なし」とは報告しない。
最初の確認と再確認の間では、ID2は3332から3336〜3337へ、ID4は2058から2059へ変わった。
受動的な姿勢変化や計測の揺れ等の原因を読み取りだけで断定しない。

Present Loadは推定負荷で、電流やトルクセンサーの測定ではない。
位置はエンコーダの生値。物理的な関節ゼロ点、可動範囲、IDの土台からの順番は未確認。
ID5=グリッパー開閉、ID4=その直前、という配置は設計資料とユーザーの設定方針による。

## 全台に共通する保存設定・RAM設定

| 項目 | 読み取った値 | 意味 |
|---|---:|---|
| Baud Rate | 3 | 1,000,000 bps |
| Protocol Type | 2 | Protocol 2.0 |
| Return Delay Time | 250 | 応答遅延500 us |
| Drive Mode | 0 | 通常方向、速度ベースのプロファイル |
| Operating Mode | 3 | 位置制御 |
| Secondary ID | 255 | 無効 |
| Homing Offset | 0 | オフセットなし |
| Temperature Limit | 72 | 72 C |
| Min/Max Voltage Limit | 60 / 140 | ソフトウェア上の検出閾値6.0 / 14.0 V |
| PWM Limit | 885 | 約100%のPWM上限 |
| Velocity Limit | 265 | 約60.685 rpm |
| Min/Max Position Limit | 0 / 4095 | 全周、機構に合わせた制限は未確認 |
| Shutdown | 52 | 過負荷・Electrical Shock・過熱の停止設定 |
| Status Return Level | 2 | 個別の読取・書込命令への応答あり |
| Position P / I / D | 640 / 0 / 3600 | 全台同じ読取値、変更していない |
| Velocity P / I | 100 / 1000 | 全台同じ読取値 |
| Feedforward 1st / 2nd | 0 / 0 | 全台同じ読取値 |
| Profile Velocity / Acceleration | 0 / 0 | 有限の速度・加速度プロファイル制限なし |
| Bus Watchdog | 0 | 無効 |
| Goal PWM / Goal Velocity | 885 / 265 | 保存されていたRAM値。今回の出力は0 |

Profile VelocityとProfile Accelerationの0は「低速」を意味しない。
今後動かす段階では機構の可動範囲と有限のプロファイルを検討する必要があるが、
今回の読み取り作業では設定変更もTorque ONも行っていない。
温度・電圧の検出閾値はモーターの定格電圧や推奨供給電圧とは別の値である。

Firmware 42/43が混在している。今回の読み取りに問題はなく、更新していない。
Startup Configuration(60)とBackup Ready(147)はFirmware 45以降の機能。
最初の手動詳細読み取りでは両アドレスが0を返したが、旧Firmwareで有効な設定とは
解釈しない。正式CLIはバージョンに応じて両項目をスキップし、理由を記録する。

根拠: [ROBOTIS XL430-W250 e-Manual](https://emanual.robotis.com/docs/en/dxl/x/xl430-w250/)。

## 作成した環境・スキル

uv環境はPython 3.13.9、dynamixel-sdk 4.1.0、pyserial 3.5。
`uv.lock` を生成し、`uv sync --locked` で再現できる。
独立したGitリポジトリを初期化した。コミットは作成していない。

`arm-status` のサブコマンドは `ports`、`scan`、`status` の3種類。
送信経路でユニキャストのProtocol 2.0 Ping/Readだけを許可し、
読取範囲もXL430の診断用レジスタ一覧に限定する。
書き込み、Torque変更、LED変更、再起動、初期化等は送信前に拒否する。
既にTorque ONだった場合にOFFへ変更する動作も含めていない。
Bus Watchdogが有効な場合、読取通信も通信期限を更新し得る。

ポート占有確認と排他設定を追加した。別プロセスを終了しない。
成功・失敗・中断時にポートを閉じ、レポート保存は閉じた後に行う。
未対応モデルはPingによる識別までにとどめ、XL430用のレジスタを当てはめない。

スキル本体は `skills/dynamixel-readonly-status/SKILL.md`。
`~/.codex/skills/dynamixel-readonly-status` を本体へのシンボリックリンクとして登録した。
呼び出し名は `$dynamixel-readonly-status`。

## 取り込んだ資料

| 元プロジェクト | コピーしたファイル | スキル数 | scripts直下のPythonスクリプト |
|---|---:|---:|---:|
| low_cost_robot | 137 | 4 | 7 |
| 3d-printed-dynamixel-gripper | 197 | 8 | 66 |

スキルは `skills/imported/<元プロジェクト>/`、スクリプト・関連モジュール・仕様・
README・pyproject・lock・存在するライセンスは `upstream/<元プロジェクト>/` にコピーした。
未コミットの現状も含むソースのスナップショットである。
各ファイルの元パス、コピー先、サイズ、SHA-256を `upstream/import_manifest.json` に保存し、
全334ファイルのコピー後のハッシュを再検証した。
仮想環境・キャッシュ・生成物・バイナリCAD・メッシュ・画像等はコピー対象外。
元プロジェクトのファイルは変更していない。

`teleoperate_real.py`、`bimanual_teleop.py`、`teleoperate_sim.py` は実機への書き込みを含む。
名前にsimがあっても読み取り専用ではない。コピーしたコードは実行せず、
メイン環境にlow_cost_robotやCAD用の依存関係を追加していない。
関連CAD入力・相対パス・別環境の依存関係が必要なスクリプトもあり、
コピーした全スクリプトの単独実行可能性は今回の検証範囲に含めない。

## 検証と成果物

オフラインテスト34件成功、Ruff検査成功、状態確認スキルのquick_validate成功。
テストでは実SDKによるPing/各レジスタReadの送信を確認し、Torque書込を含む
禁止命令がシリアルへ到達しないこと、符号変換、占有時の停止、中断時のクローズ、
通信失敗を未知として扱うこと、旧Firmware・未対応モデルの扱いを確認した。

- [最初の状態JSON](../reports/initial_20261003T183045+0900.json)
- [新CLIで取得した詳細Markdown](../reports/status_20261003T183739_731022+0900.md)
- [新CLIで取得した詳細JSON](../reports/status_20261003T183739_731022+0900.json)
- [状態確認スキル](../skills/dynamixel-readonly-status/SKILL.md)
- [取り込み一覧](../upstream/import_manifest.json)

実行した確認は読み取り専用。モーターに対する設定変更・移動・Torque変更なし。
最後にポートを解放し、Wizardから接続できる状態に戻した。
