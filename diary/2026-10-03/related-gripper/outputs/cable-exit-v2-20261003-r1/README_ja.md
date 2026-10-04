# 最新版V2のID5支持部 P05

最終V2 STEPの `ARM_P05_wrist_XL430` を組立world座標のまま抽出した。
新たな形状変更はしていない。単位mm。STEPとSTLは個別の部品確認用で、印刷姿勢の指定ではない。

- `P05_ID5_support_V2_EXTRACTED_CANDIDATE.step`：CAD部品。
- `P05_ID5_support_V2_EXTRACTED_CANDIDATE.stl`：同部品の形状確認用メッシュ。
- 左右の側壁に各1個、幅3 mm・全高8 mm・端部R1.5 mmの配線窓がある。
- P05はID4からID5を支えるアーム側部品。グリッパ11部品＋カメラ2部品の `set2all.gcode` には含まれていない。
- 実ケーブル径・曲げ半径・コネクタ通過、支持強度、実物の部品対応は未確認。製作承認はfalse。

出所・SHA・再読込とメッシュ確認・旧版との形状比較は `provenance.json`。
