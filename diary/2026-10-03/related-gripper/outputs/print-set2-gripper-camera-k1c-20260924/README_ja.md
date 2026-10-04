# 2台目用 1プレート印刷（PG3グリッパー11部品＋D405カメラ台2部品）

2026-09-24。K1C（220×220）。SDカード名 `set2all.gcode`、SHA-256 `a99484440ea760bc46ae3862e1b35c1420a0c26b7953ebea1dcd649246afb8d7`。

- 入力STL: `STL/`（`SHA256SUMS`）
  - グリッパー: `print-pg3-id5-trial-k1c-20260924-r3/STL` と同じ11部品
  - カメラ台: `camera-mount-id5-overhead-d405-r5/STL` の2部品
- 共通設定: K1Cシステムプリセットを継承展開したもの（0.20mm Standard / CR-PLA）を使い、前回のグリッパー印刷（`pg3axis.gcode`）に合わせた。
  - 壁3周、インフィル15%、自動サポート（normal、しきい値30°）、auto brim、チャンバー0
- カメラ台2部品だけ部品ごとに上書き（`project/set2_percam.3mf` の model_settings）: サポートなし、壁4周、インフィル40%
- 配置: `--arrange 1 --allow-rotations=0`。13部品が1プレートに収まる（配置図 `layout/comparison.png`）。
- 結果: 366層、推定3時間13分、60.5 g。M191/M600なし、START_PRINT/END_PRINTあり、警告なし。
- 部品ごとの検証:
  - 押出量はカメラ単体版・前回グリッパー版と一致（比率0.996〜1.003）
  - カメラ部品のサポートは0
  - グリッパーのサポートは前回と同等
- 再スライス: `OrcaSlicer --slice 0 --outputdir slice project/set2_percam.3mf`（`QT_QPA_PLATFORM=offscreen`）
