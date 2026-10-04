# 2026-10-03 型付き読み取り専用監視

日時確認: `date --iso-8601=seconds` は `2026-10-03T18:58:45+09:00`。
作業先は `~/Project/my_dynamixel_arm_sandbox`。従来のレポート、設定、コピー済み
スキル/スクリプトは保持し、モーターへの書き込みは行っていない。

## 実装

- 設定、識別情報、レジスタ、状態、障害、フレーム、終了情報を型付き不変レコードへ整理。
- 小さな束はNamedTuple、ドメインモデルはfrozen/slots dataclass。
- Reader ProtocolとSDKアダプターを分離し、観測、診断、保存を独立させた。
- metadataとwatchを追加。低頻度のメタ情報と高頻度の状態読み取りを分離。
- 通常Sync Readの2ブロックに限定した送信ガードを追加。書き込みは引き続き拒否。
- SDKの前回成功フラグ、応答エラーバイト破棄、短い応答を補い、欠測をnullで表現。
- monotonicスケジューラー、期限超過、実測周期、逐次JSONL保存を追加。
- jaxtyping/beartypeで校正用配列の型・形状とレコード/service型を検査。
- Python型由来のJSON Schema v2、Rust Serde消費側、符号付き値/欠測の共通fixtureを追加。
- ty、Ruff、Radonによるゲートを追加。Radonの変更前最大28から現在10へ低減。
- srcの二重に見える名前はプロジェクトルートとimportパッケージの区別。重複ファイルではない。

## 実機状態

18:59:14〜15の詳細スナップショット:
[JSON](../reports/status_20261003T185915_405929%2B0900.json)、
[Markdown](../reports/status_20261003T185915_405929%2B0900.md)。

| ID | Model | FW | Torque | Position counts | Voltage V | Temperature C | Error |
|---|---|---|---|---|---|---|---|
| 1 | XL430-W250 / 1060 | 43 | OFF | 2550 | 9.2 | 35 | 0 |
| 2 | XL430-W250 / 1060 | 42 | OFF | 3354 | 9.2 | 37 | 0 |
| 3 | XL430-W250 / 1060 | 42 | OFF | 1153 | 9.0 | 35 | 0 |
| 4 | XL430-W250 / 1060 | 42 | OFF | 2059 | 9.1 | 36 | 0 |
| 5 | XL430-W250 / 1060 | 43 | OFF | 2059 | 9.1 | 35 | 0 |

3サンプルで位置変化なし。速度/PWM/推定負荷は0。Protocol 2.0、Baud=3 / 1 Mbps。
前回よりID2/3の位置が18カウント増えているが、間の姿勢変化の原因は未確認。
今回の読み取り中に位置が変化しなかったことから、負荷時の安定性や物理ID順序は判断できない。
FW45以降のレジスタはスキップ。可動範囲/プロファイル/Watchdogの未整備は従来通り。

## 性能確認

| Read mode | Requested Hz | Duration s | Frames | Achieved Hz | Missing | Late | Mean read ms | P95 read ms |
|---|---|---|---|---|---|---|---|---|
| Sync | 20 | 5 | 100 | 20.00 | 0 | 0 | 30.39 | 37.54 |
| Sync | 50 | 3 | 75 | 25.00 | 0 | 75 | 30.54 | 37.53 |
| Unicast | 20 | 3 | 4 | 1.11 | 0 | 4 | 873.28 | 878.00 |

ログ:
[Sync 20 Hz](../reports/watch_20261003T185915_978979%2B0900.jsonl)、
[Sync 50 Hz](../reports/watch_20261003T185930_745502%2B0900.jsonl)、
[Unicast](../reports/watch_20261003T185935_192160%2B0900.jsonl)。

期間内の全フレームでトルクOFF、ハードウェアエラー0。電圧最小9.0 V、温度最大37 C。
全JSONLレコードをDraft202012Validatorで検証。実機のUnicastログをRust例でデコードし、
ID/位置/トルクの一致を確認。50 Hzは読取時間が20 ms周期を超えるため、スロットを
スキップして25 Hzとなった。USB遅延等の寄与は未切り分けで、設定は一切変更していない。
Unicastは読み取り終了待ちのため指定3秒に対して実経過3.58秒。

今回の20 Hzは観測に使える実測値であり、将来の制御周期や負荷下の保証ではない。
ポートは各CLI終了時に閉じ、最後の `fuser -v /dev/ttyUSB0` は所有者なし。

## 品質確認と残る境界

pytest 65 passed。ty/Ruff成功。Radon最大10でゲート成功。
Rust 3 tests passed、cargo fmt、Clippy -D warnings成功。
根拠と設計判断は [architecture](../../2026-10-04/reference-docs/readonly-architecture.md) に一次資料リンク付きで記載。

Rustは通信制御の移植ではなくデータ消費側。制御開始には物理ID順序、関節ゼロ点/方向/限界、
速度/加速度、給電余裕、非常停止手段などを別途確認する必要がある。トルクONは今回未実施。
