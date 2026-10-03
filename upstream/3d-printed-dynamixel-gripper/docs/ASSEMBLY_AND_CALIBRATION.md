# 組立と校正の手順

## 組立順

1. 通電せず、P05、J5/J6候補、XL430 output/idlerの実部品対応を確認する。
2. bench上でカメラをcarrierへ取り付け、M2ねじのgrip、かかり、底付き、頭部、工具を実測する。
3. carrierをsaddleへ取り付ける。captive nut候補の保持と工具アクセスを確認する。
4. saddleとfront jawでP05中央bridgeを挟み、M3を交互に締める。側板を押し曲げない。
5. カメラケーブルのconnector、strain relief、最小曲げ半径を確認する。
6. 下流XL430のoutput/idler両側へjaw baseと反対側支持を仮組みする。片持ち状態で荷重試験しない。
7. rack/pinion、左右carriage、hard stopを組み、無通電で全開口を動かす。
8. 穴中心だけでなく、座面接触、ねじ深さ、底付き、工具、対向保持、組立工程を記録する。
9. PLA試作の実寸、亀裂、変形、backlashを測定してからCAD公差を更新する。

現在、カメラねじの装着後保守はFAILである。bench先付けを必須工程とし、これを「全工具アクセス
PASS」と表現しない。jaw側の実ねじと支持部品は未選定なので手順6以降は未承認である。

## 合成校正の再現

```bash
rtk proxy uv sync --locked
rtk proxy env MUJOCO_GL=egl uv run python scripts/run_calibration_demo.py \
  --config specs/simulation_calibration.yaml \
  --out outputs/calibration-demo-next
```

出力にはdimensioned AprilGrid、12 RGB、K/T真値、検出overlay、校正JSON/Markdown、
CAD 4面、全artifact SHAが入る。既存runは上書きしない。固定gateは12 frame以上、各2 tag/
8 corner以上、RMS 0.5 px、fx/fy 1%、cx/cy 2 px、回転0.5 deg、並進2 mmである。

## 実カメラ校正へ進む条件

1. カメラ型番、解像度、lens、focus、露出固定可否を記録する。
2. AprilGridを100% scaleで平面へ出力し、tag黒枠外周30 mmを複数箇所で実測する。
3. 640x480以上、12枚以上、3距離以上、傾斜を含み、blur/遮蔽/境界切れを避けて撮影する。
4. 実画像用import処理を追加し、合成真値比較とは別reportを作る。
5. 再投影誤差だけで合格にせず、再撮影hold-out、board scale、取付再現性を確認する。

現在のpipelineは合成画像検証用であり、実画像を自動的に合格へ変換する入口はまだない。
