# My DYNAMIXEL Arm Sandbox

Ubuntu上の5台のXL430-W250を、情報読み取り専用で確認するuvプロジェクトです。
DXHUB E148経由、Protocol 2.0、1 Mbps、ID 1〜5を既定としています。

```bash
cd ~/Project/my_dynamixel_arm_sandbox
rtk proxy uv sync --locked
rtk proxy uv run arm-status ports
rtk proxy uv run arm-status status --scan
```

`ports` は接続候補の一覧だけを表示します。`scan` はID 0〜252をPingします。
`status` はID 1〜5の設定と状態を読み、3回の状態観測をJSONとMarkdownへ保存します。
`--scan` を付けると全IDの検索結果も記録します。数値オプションは次のように指定できます。

```bash
rtk proxy uv run arm-status status --ids 1 2 3 4 5 --samples 3 --interval 0.25
rtk proxy uv run arm-status scan
rtk proxy uv run pytest
rtk proxy uv run ruff check src tests scripts
```

接続先と想定IDは [config/arm.toml](config/arm.toml) で管理します。
`--device` と `--baudrate` はPC側の接続条件の指定で、モーターの保存設定を書き換えません。
Wizard等がポートを使用していると終了します。確認後・失敗時・中断時にはポートを閉じます。

CLIの実機命令はユニキャストのPing/Readと、範囲を固定したSync Readだけです。
送信直前にも命令種別と読取範囲を検査し、
書き込み、トルク変更、移動、LED変更、再起動、初期化、ファームウェア更新は拒否します。
読み取り専用なので、既にトルクONだったモーターをOFFにする処理もありません。
Ping/Readは有効なBus Watchdogの通信期限を更新し得るため、既に動作中のモーターを
このCLIで止められるとは扱いません。

終了コードは `0` が読取完了、`1` が接続・設定・保存等の失敗、`2` が応答なし／読取不足／
未対応モデル、`130` が中断です。読取完了は可動範囲や負荷時の安全性の確認を意味しません。

確認内容はEEPROM設定、RAM設定、目標と現在位置、速度、PWM、推定負荷、電圧、温度、
ハードウェアエラー、PID、位置・速度・PWM制限、動作プロファイル、Watchdog等です。
ファームウェア45以降のStartup ConfigurationとBackup Readyは、旧版では読みません。
XL430のPresent Loadは推定値で、電流や実測トルクではありません。
角度換算はエンコーダ基準であり、アーム関節のゼロ点や可動範囲は未校正です。

| 保存先 | 内容 |
|---|---|
| `src/arm_observer/` | 読み取り専用CLI・Pythonパッケージ |
| `config/arm.toml` | 接続条件、ID、仮の関節役割 |
| `reports/` | 日時付きの詳細状態JSON・Markdown |
| `diary/` | 作業記録と実機状態の考察 |
| `skills/dynamixel-readonly-status/` | 実機状態確認スキル |
| `skills/imported/` | 2プロジェクトからコピーしたスキル |
| `upstream/` | コピーしたスクリプト・モジュール・仕様と出典 |

参照元は `../low_cost_robot` と `../3d-printed-dynamixel-gripper` です。
グリッパーの設計仕様はID5を開閉、ID4を直前の関節としています。実機の物理順序は通信だけでは
確定できないため、設定では `physical_order_verified = false` としています。

レジスタの根拠: [ROBOTIS XL430-W250 e-Manual](https://emanual.robotis.com/docs/en/dxl/x/xl430-w250/)。

## 継続監視とメタ情報

```bash
rtk proxy uv run arm-status metadata
rtk proxy uv run arm-status metadata --full
rtk proxy uv run arm-status watch --rate 20 --duration 10
rtk proxy uv run arm-status watch --rate 20 --duration 0 --count 100 --format jsonl
```

`metadata` はID、機種、FW、通信条件、モード、オフセットを取得します。
`--full` は対応する全レジスタ、`watch` は位置・速度・PWM・推定負荷・電圧・温度・
トルク・エラー・Realtime Tickを繰り返し読みます。メタ情報の再取得は既定30秒間隔で、
`--metadata-every 0` なら開始時だけです。ログは `reports/watch_*.jsonl` に逐次保存します。
`--duration 0` かつ `--count 0` はCtrl+Cまで継続します。

既定のSync Readは2パケットで5台を読みます。個別Readとの比較には
`--mode unicast` を使えます。欠測は `null` とエラー情報になり、前回値で埋めません。
観測周期、読取時間、期限超過、実測Hzを記録しますが、ハードリアルタイムではなく、
2ブロックと各モーターの値が厳密に同時刻のサンプルとも限りません。

2026-10-03の実機確認では20 Hz指定で実測20.00 Hz、100フレーム欠測・期限超過なし。
50 Hz指定では25.00 Hz、個別Readの20 Hz指定では1.11 Hzでした。
詳細とログは [diary](diary/2026-10-03_typed-readonly-monitoring.md) にあります。
USB設定、Return Delay、FW、モーター設定は変更していません。

## 型と移植性

ドメインデータは `frozen/slots dataclass`、小さな結果束は `NamedTuple`、
読み取り接口は `Reader Protocol` です。辞書は主にTOML/JSON境界と定義の索引に限定します。
SDK、観測周期、診断、保存を分離し、Rust等への移植時も取得ロジックとデータ契約を
切り分けられる構成です。数値変換ではjaxtypingとbeartypeが配列の型・形状を検査します。
校正関数を使うにはゼロ点、方向、減速比を明示する必要があります。運動指令はありません。

JSONLは `metadata` / `frame` / `end` の3種、`schema_version = 2` です。
[JSON Schema](contracts/stream-v2.schema.json) はPythonの型から生成します。
[Rust crate](rust/arm-observer-contract/src/lib.rs) はSerdeで型付きデコードします。
Rust版はログの消費側で、シリアル通信や制御の完全なRust移植ではありません。
旧版レポートの形式は上書きせず残しています。設計詳細は
[読み取り専用アーキテクチャ](docs/readonly-architecture.md) を参照してください。

`my_dynamixel_arm_sandbox/src/arm_observer/` はPythonのsrcレイアウトです。
外側は作業フォルダ、内側は `import arm_observer` の名前で、二重管理ではありません。
uvの配布名は `my-dynamixel-arm-sandbox`、コマンド名は `arm-status` のままです。
説明中のソースパスはプロジェクトルートからの相対パスで表します。

## 品質確認

```bash
rtk proxy uv run pytest
rtk proxy uv run ruff check src tests scripts
rtk proxy uv run ty check
rtk proxy uv run scripts/check_quality.py --output reports/code_quality_v2.json
rtk proxy uv run scripts/export_contract.py
rtk proxy cargo test --locked --manifest-path rust/arm-observer-contract/Cargo.toml
rtk proxy cargo clippy --locked --manifest-path rust/arm-observer-contract/Cargo.toml --all-targets -- -D warnings
rtk proxy cargo run --locked --quiet --manifest-path rust/arm-observer-contract/Cargo.toml --example read_jsonl < tests/fixtures/stream_v2.jsonl
```

beartypeは型付きレコードと取得サービス、jaxtypingは数値変換、tyは静的型検査、
Radonは保守対象 `src/` の複雑度検査に使用します。最大循環的複雑度は10以下を検査します。
コピーした `upstream/` は実行・改修対象から分離し、この品質ゲートには含めません。

現状の部品版・元ブランチ・制御実装・可動域・保存済み実機観測・MuJoCoの集約は
[2026-10-03の調査レポート](diary/2026-10-03_current-arm-findings.md) にあります。
[作業書兼実行記録](temp/workdoc_Oct03-2026_current_arm_findings.md) を正本として逐次確認しています。
実機の現在角を継続反映する描画モードは追加要求で、校正値と実機READの接続が必要です。

## 実機READ liveと校正画面（2026-10-03追加）
このworkspaceで `rtk proxy uv run arm-live --port 8085` を起動し、隣のgripper workspaceで `rtk proxy uv run --no-sync python simulation/current_arm_viewer/server.py --port 8084 --live-url http://127.0.0.1:8085` を起動する。[viewer](http://127.0.0.1:8084)の「読取り開始」で接続、「読取り停止」で終了する。両serverの起動時は未接続。ユーザー用は停止まで継続、agent検査は10秒の有限runを選ぶ。
校正パネルで物理ID・基準count・方向・PG3基準角を現物と照合して入力する。未校正時はID別の読値だけ、確認済み校正後はMuJoCoへ姿勢を反映する。importは現物の確認をやり直す。画面操作はmotor Goal/Mode/Torqueを書かない。
[結果日誌](diary/2026-10-03_live-mujoco-calibration.md)、[live作業書](temp/workdoc_Oct03-2026_live_mujoco.md)、[追加ID3作業書](temp/workdoc_Oct03-2026_id3_open_10deg.md)、[汎用スキル](skills/robot-live-calibration/SKILL.md)を参照。実測20Hz/200frame/10秒/欠測0/期限超過0/port closure確認済み。実物校正とID3約10°の動作は未実施。

## ID3（肘）を約10°開く限定コマンド（2026-10-04追加）
`arm-id3-open` は、[作業書](temp/workdoc_Oct03-2026_id3_open_10deg.md)の動作試験専用のコマンドで、読み取り専用の `arm-status`／`arm-live` とは別にしてある。書き込みはID3のRAM 64/100/108/112/116だけで、送信は実行ごとの範囲（envelope）でガードする（`motion_guard.py`）。既定はdry run。

```bash
rtk proxy uv run scripts/derive_id3_direction.py --read-log reports/live_<完了したREAD>.jsonl --output reports/id3_direction_cad_<ts>.json
rtk proxy uv run arm-id3-open --evidence reports/id3_direction_cad_<ts>.json            # dry run（書込みなし）
rtk proxy uv run arm-id3-open --evidence reports/id3_direction_cad_<ts>.json --execute  # 実動作
```

流れ: 事前READ → PV=5/PA=1/Goal PWM 350 → 現在値をgoalにしてTorque ON → +114 count → 重力偏差を目標の補正で吸収（最大30 count）→ 2 s保持 → 元の位置へ戻す → Torque OFFを読戻しで確認 → 設定を復元。
終了コード: 0 収束、2 拒否・中止・偏差残り（Torque OFFは確認済み）、130 シグナルで停止、3 **Torque OFF未確認**（安定化電源OUTPUT OFFを押す）。

2026-10-04 00:20の実機結果は、1154→1264（目標1268、誤差−4 count）で収束し、もとの位置へ戻してTorque OFFを確認した（[日誌](diary/2026-10-04_id3-open-10deg.md)）。仕様と限界（SIGKILL・USB断ではトルクが残りうる）は [docs/id3_motion_spec.md](docs/id3_motion_spec.md)。ほかのモーターや動作へ流用しないこと（AGENTS.md）。

## Gitに含めないもの
作業書（`temp/workdoc_*.md`）・作業用スクリプト・`.claude/`・`.codex/` は、ユーザーのグローバル設定
`~/.config/git/ignore` により追跡しない（ローカル専用）。日誌や README の `temp/` へのリンクは、この
作業マシン上の記録を指す。スキルの正本は `skills/`、仕様は `docs/`、検証スクリプトは `scripts/` にある。

