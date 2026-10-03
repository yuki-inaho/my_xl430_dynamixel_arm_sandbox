# 3D CADのPDCAプロトコル

目的はCADを出す速度ではなく、不良を見逃さず、次の変更で何を良くしたか説明できること。
設計の詳細はINTERFACES、合否はVALIDATION、順序はWORK_PLANを正とする。

## P: Plan

1. 要求RとDoD Dを確認。未確定Q、停止ゲート、仮定、変更禁止境界を記録する。
2. 原本/メーカー/現物のSHA・版を固定し、実機IDの同定と座標系を先に決める。
3. 原本と無変更の独立コピー/再importに検査器をかけ、正常対照が成立することを確かめる。
4. 今回の変更を一つの仮説として書く。例: 「支持幅だけ増やすと拘束がなくなり、穴座面は保持できる」。
5. 変更mask、保持すべき穴/外形/座面、変更を伝播すべき接続、受入数値を決める。
6. 先に不良モデルを定義。片穴欠落、四穴群ずれ、工具だけ衝突、カメラだけ遮蔽などを混ぜない。

数値許容は CAD演算誤差、組立設計公差、FDM製造誤差の3種類を分ける。
未知のものに「一般に1 mm」を代入しない。閾値変更は旧/新で全モデルを再判定する。

## D: Do

1. 再現テストを追加し、期待する理由でREDにする。importエラーだけのREDで終わらせない。
2. 最小のパラメータ/形状変更を実装。既存非対称形状をbox/cylinderで置き換えない。
3. 新規グリッパは機構・支持・カメラを分離して構成。購入部品は型番別モデルで配置する。
4. 一意run IDへSTEP/STLとmanifestを出力。各instanceに原本、変更部、材質、質量の由来を保存。
5. 旧部品を除いた後に新部品を1個配置する。重ね表示を置換と呼ばない。

推奨run構成:

```text
outputs/<run-id>/
  inputs.json        # files/SHA, code revision + dirty diff SHA, uv.lock SHA
  parameters.yaml    # exact values and assumptions
  assembly.json      # every occurrence, source SHA, T_parent_child, category
  cad/               # parts and named assembly STEP
  mesh/              # per-print-part STL, not a fused robot mesh
  evidence/          # rule results, negative controls, images, DOM
  decision.md        # accepted/rejected/blocked, next hypothesis
```

## C: Check

1. 新規生成のメモリshapeだけでなく**再importした出力**に検査を行う。
2. 正常対照、意図した不良対照、前回候補、今回候補へ同じルール版を適用する。
3. 単体、相手部品との結合、全体、可動域、組立経路、工具/配線/視野を別々に測定。
4. ブラウザはheadless専用session。XYZ正投影または6面、isometric、全体アームを撮る。
   同じカメラ/倍率で原本と候補を比較し、自分で画像を開いて確認する。
5. DOMでモデル数/名前/エラー/選択ownerを調べ、owner transformとB-repに対応させる。
6. 設計者とは別のレビューで、穴以外も含めて輪郭/左右性/座面/肉厚/干渉の変化を確認。
   別エージェントが使えなければ独立監査と偽らず、自己レビューと明記する。

## A: Act

不合格を「仕様未達」「検査器/カーネル不成立」「資料欠落」に分ける。
同じ問題を2回試して改善しない場合は、さらに形状を盛る前に最小再現/仮説を見直す。
これは探索を打ち切る一律回数ではなく、無根拠な試行を防ぐ見直し点。
有効な不良対照を消す、相手を除外する、合格しやすい姿勢だけに絞る変更は禁止。
新たな知見でテストを修正する場合は、旧判定がなぜ誤りか原本/実物で証明し、
別の不良が隠れないことを監査してルール版を上げる。

## 引継ぐべき失敗と対策

| 過去の失敗/発見 | 再利用可能な対策 |
|---|---|
| フランジだけが合格、全体の輪郭/機能が破壊 | グローバル要求とchange maskを先に固定 |
| 全幅両方向extrudeが相手ケースへ侵入 | 押出の基準面・向き・範囲を数値化し、追加材と部品全体を両方検査 |
| 穴のfamily数だけ一致 | 内外円筒、貫通/盲、開口/座、隣接面、1対1の中心/軸/位相まで検査 |
| カラー部分だけ衝突0を全体0と報告 | delta scopeとwhole-part/whole-assembly scopeを別の結果にする |
| 重複穴を都合よくskip | 設計意図/元形状で正当化。外縁距離と穴間webを別ルールにする |
| isValid=true/自己cut空を同等性の証明にした | 独立copyと再import、両方向CUTとCOMMON、正体積保持を対照にする |
| CUTもCOMMONも空になった | 演算不整合ERROR。体積0を無干渉PASSにしない |
| 置いた状態で工具OK、部品を入れられない | 工程順と挿入/回転/引抜経路を別に検査 |
| 締めると両側ホーンに予圧が掛かる | 実支持幅/座面/回転支持と締付荷重経路を明示 |
| 緑選択はDOMのツリー選択と思い込む | Measure状態/owner occurrence/transformを読む。欠落は不明とする |
| ブラウザで前のモデル/別タブを検査 | session/tab URLとSTEP SHA、leaf manifestを毎run固定 |
| test greenを製作可にした | テスト器の合格と製品ゲートを別レポートにする |

## 技術上の未解決事項

旧STEPではCadQuery 2.7/OCP7.8と別版2.8/OCP7.9でBoolean同一性不成立が報告されている。
今回小課題の成功は旧STEPの修復ではない。正規化/healingを提案するなら原本との差分と
保持特徴を独立に証明する。証明不能なら、変更対象外の参照に限定し、対話CAD/メーカー
元データ/人手の同等性確認を必要な次工程として残す。
