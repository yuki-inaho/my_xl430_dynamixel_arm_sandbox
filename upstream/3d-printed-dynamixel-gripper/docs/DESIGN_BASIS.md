# 設計基準・参考機構・実寸法

確認日: 2026-09-22。数値はメーカー仕様、旧CAD観測、今回の仮設計値を混ぜない。

## 1. 参考グリッパ

### Mini Max

[Michael Ferguson, 2011-07-01](https://www.robotandchisel.com/2011/07/01/new-gripper-for-mini-max/)
はAX-12一台で両爪の平行運動を作る試作例。
[機構写真](https://www.robotandchisel.com/assets/images/2011-07-01-gripper-mechanism.png)
と[CAD画像](https://www.robotandchisel.com/assets/images/2011-07-01-gripper-cad.png)を目視した。
中央回転部と左右への連結部、爪を案内する枠が見える。
隠れた支点/摺動拘束の仕様・寸法は記事だけでは断定できない。
従って「既知寸法の完成リンク機構」として複製せず、1入力・対向平行運動というコンセプトを参照する。
記事上で製作CADと再配布許諾は確認できない。画像は調査キャッシュだけに保持する。

### Robonine

[リポジトリ](https://github.com/roboninecom/SO-ARM100-101-Parallel-Gripper)
の取得commitは `305ad0f6e8f19e4e739616160cbdc7cae1ab153f`。
組立画像で中央ピニオン、対向ラック、平行な案内棒、上方のカメラホルダーを確認した。
READMEはFeetech/Waveshare用とし、交換式カメラ取付を案内している。
採り入れるのは交換可能なカメラ台座と把持域を見る配置の考え方。
製品の把持力/寸法/ねじ/電気制御は本XL430設計の性能保証ではない。

再利用する場合は取得版の `LICENSING.md`, `NOTICE`, `REUSE.toml` を確認。
当該版はhardware=CERN-OHL-P-2.0、software=Apache-2.0、docs/images=CC-BY-4.0。
上流アーム由来メッシュ等に例外がある。古いリリースのライセンスを最新へ読み替えない。
今は参考キャッシュのみで、製作CADや画像を本repoの設計として再配布していない。

## 2. XL430-W250-Tのメーカー仕様

一次資料: [ROBOTIS e-Manual](https://emanual.robotis.com/docs/en/dxl/x/xl430-w250/)。

| 項目 | 値 | 設計への適用限界 |
|---|---|---|
| 外形 W×H×D | 28.5×46.5×34 mm | 全体包絡だけで穴・突出・プラグを決めない |
| 質量 | 57.2 g | ホーン/リンク/カメラ/締結を別加算し、二重計上しない |
| 電源 | 6.5〜12.0 V、推奨11.1 V | レジスタ上限値14 Vを定格電圧と誤読しない |
| ストールトルク | 1.4 N m @11.1 V、1.5 N m @12 V | 連続保持能力ではない |
| ストール電流 | 1.3 A @11.1 V、1.4 A @12 V | 常用電流/配線許容値ではない |
| 無負荷速度 | 57 rpm @11.1 V、61 rpm @12 V | 負荷時の速度保証ではない |
| 分解能 | 4096 count/rev | 実バックラッシュ・爪の再現性とは別 |
| 信号 | TTL半二重、3線 | 給電と信号の配線設計を分ける |
| 制御モード | velocity / position / extended position / PWM | current-based positionではない |

PWMとPresent Loadを校正された把持力センサとして扱わない。未知の効率/摩擦/弾性を含む
把持力推定には実測が必要。ストールで検査する、過負荷解除を繰り返す手順は設計検証に含めない。

## 3. 取付図面の数値

ROBOTIS作成の[XLシリーズ図面付き資料](https://media.distrelec.com/Web/Downloads/_t/ds/Dynamixel_XL-Series_eng_tds.pdf)
1ページ下部を画像で確認。配布はDistrelec、文書の明示改訂番号は未確認。
SHA-256: `a09f275fb4856a26c6582d132bfe53f2df779701c10a0c2d848b575016e31c5b`。

| 部位 | 図面表記・読み取り | 誤用防止 |
|---|---|---|
| ホーン四穴 | 4-M2 TAP、PCD16、DP3.5(MAX) | 正方形一辺16ではない。十字の半径8で位相は座標基準に依存 |
| 別の四穴 | φ1.7、PCD16、DP3.5(MAX) | M2 TAP群と区別。径だけで同じ締結機能にまとめない |
| ケースパイロット | φ2.1、DP4.0(MAX) | スルー穴/M2機械ねじと決めない |
| ケース前面の既存ねじ | 4-FHS M2.5×10 | 出荷時の内部締結。外部板厚のまま流用不可 |
| ケース別面の既存ねじ | FHS M2.6×8 TAPPING | 新リンクに適切なねじ長の指示ではない |

最大深さは最小必要掛かり長さではない。タップ深さと底/未完成ねじ部の関係を確認する。
標準ホーンの中心固定、四穴での駆動部固定、反対側idlerは役割が別。
未購入のidler/HN品番を取り付いている前提にしない。

e-Manualのフレーム組立例は側面2 mmフレームにM2.6×5タッピング、前面2 mmフレームに
スペーサリングとM2.5×14の例を示す。**3 mmのPLA板への指定ではない**。
各例の向き・支持面・深さを照合してから長さを再計算する。
[側面の深さ注意](https://emanual.robotis.com/assets/images/dxl/x/assembly/xl430/etc/xl430_4mm_mount_warning.png)、
[側面例](https://emanual.robotis.com/assets/images/dxl/x/assembly/xl430/etc/xl430_etc_assembly_example_side.jpg)、
[前面例](https://emanual.robotis.com/assets/images/dxl/x/assembly/xl430/etc/xl430_etc_assembly_example_front2_02.jpg)。

## 4. 公式CAD取得の状態

e-Manualは新旧XL430を分けている。新図面のリンクは
[PDF no=772](https://www.robotis.com/service/download.php?no=772)、
[STEP no=773](https://www.robotis.com/service/download.php?no=773)。
今回両方ともHTMLの404本文が返り、CAD/PDFとして取得失敗した。
HTTP成功や拡張子だけで受入しない。ヘッダー、形式、図面内容、SHAを確認する。
同梱アーム内のモーター形状は出自を保持して使えるが、手元品の製造改訂との一致は未確定。
文書・現物が一致しなければ、画像目盛から穴位置を推測せずメーカー資料/実測を追加する。

## 5. 機構案の比較を先に行う

| 案 | 長所として検討する点 | 先に検証する失敗条件 |
|---|---|---|
| 回転クランク+左右リンク/スライダ | 参考Mini Maxに近い、歯車不要 | 死点、平行拘束不足、ピン摩擦、片当たり、可変機械利得 |
| 1ピニオン+対向ラック+案内 | 左右同期と直線開閉が明確 | 歯形/噛合い/保持、歯底強度、摺動拘束、バックラッシュ |

手書きの歯の台形配列を「正常な歯車」にしない。選択時には実績ある歯車生成器/購入部品を
評価し、モジュール・圧力角・転位・バックラッシュの根拠とバージョンを記録する。
両案を同時に本実装しない。先にQ-03を確定し、重量・工程・工具・見える範囲を比較する。

理想対向ラックの概念計算例: ピッチ半径r[m]、角度差θ[rad]なら全開口変化g=2rθ。
損失なしの片爪法線力Fは τ=F dg/dθ=2Fr。`F=τ/r` とすると両爪合計との混同になる。
摩擦把持では両側合計支持力と滑り/接触圧を別に評価する。
この式は歯強度・サーボ連続トルク・効率・静止摩擦を証明しない。
