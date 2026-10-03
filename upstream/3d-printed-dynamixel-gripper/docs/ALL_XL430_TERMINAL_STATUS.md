# 全XL430末端の設計状態

更新: 2026-09-23。状態: **診断候補。製作・通電・実カメラ校正は未承認。**

再監査による訂正: 下の結果は旧runの限定的記録。全DoD達成は撤回した。
「平行ジョー運動学」は与えた並進の自己照合であり、実歯・案内の機構成立ではない。
末端干渉のcandidate集合には出力したfastener全体や実カメラが含まれておらず、
全occurrence数だけで全組付けを網羅したとは言えない。
PG2別候補と是正後の状況は`REVIEW_PG2_AND_SELF_AUDIT.md`を参照。

## 目的と構成

既存R3アームのP05固定カメラと手首ロールを維持し、下流XL430で左右が平行に動く
ジョーを駆動する。物理ID5はロール候補であり、ジョーへ転用しない。ジョー駆動XL430の
物理bus IDは未割当である。CAD名J5/J6と物理ID4/5を同一視しない。

暫定機構は対向rackと中央pinionである。片側ホーンだけへ曲げ荷重を持たせず、反対側支持を
必要とする。現在寸法は把持対象、必要開口、把持力、速度、duty、PLA公差が未定のため
`concept_only`であり、production STEP/STL/G-codeではない。

カメラはP05中央bridgeを前後から挟む交換式carrierで、J5出力rollに追従しない。正確な
カメラ型番と光学frameは未確定で、CAD carrier法線はkinematic proxyに限って使用する。

## 検証結果

| 項目 | 結果 | 証拠 |
| --- | --- | --- |
| XL430出力interface | PCD16、旧PCD12は半径差2.000 mmで拒否 | `specs/interfaces_all_xl430.yaml`, interface tests |
| 平行ジョー運動学 | 21点で平行・左右対称・単調、開口32〜48 mm | `tests/test_parallel_jaw.py` |
| 末端assembly | 3開口姿勢でsource/candidate有体積干渉0、boolean error 0 | `outputs/terminal-all-xl430-20260922-r3/validation.json` |
| occurrence coverage | 217件: solid 151、shell 66、wire/empty 0 | 同上 |
| 出力面候補 | 距離0 mm、probe接触面積208.006 mm2 | 同上。締結証明ではない |
| jaw締結台帳 | output/idler/反対側支持を全列挙、実hardware未選定で全てUNKNOWN | `specs/jaw_fastener_ledger.yaml` |
| カメラジグ | P05/候補干渉0、接触面成立、bench先付けとclamp工具PASS | `outputs/camera-jig-20260922-r11/` |
| 装着後カメラ保守 | 直線工具で22 hit、非solid query 5 error | 装着後交換不可。FAILを保持 |
| MuJoCo AprilGrid | EGL、640x480、12非同一frame、全frame複数tag | E2E manifest |
| 合成内部校正 | RMS 0.3309 px、fx/fy誤差0.209%/0.118%、主点0.14 px以内 | calibration report |
| 合成外部校正 | 最大回転0.164 deg、最大並進1.861 mm | calibration report |
| 誤tag寸法対照 | 1.25倍で最大並進誤差125.527 mm、FAIL | wrong-scale report |

66件のshellをsolid 0干渉へ読み替えない。末端の局所無干渉を、既存R3アーム全体の運用承認へ
読み替えない。質量は密度未確定で、記録値は体積重心だけである。

## Release gate

`fabrication_approved=false`、`powered_operation_approved=false`、
`real_camera_calibration_approved=false`を維持する。解除条件は
[未解決事項](OPEN_ISSUES.md)を参照する。
