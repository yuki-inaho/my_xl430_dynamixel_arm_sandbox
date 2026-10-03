# PG3 C92 J28 C9: アーム・カメラ組付け診断

更新: 2026-09-23。対象repo: project root (`3d-printed-dynamixel-gripper`)。
**取込・表示・運動学シミュレーションに対応。ただし実機装着はFAIL、印刷/通電は未承認。**
ユーザー要求は改訂ZIPを利用できるようにし、カメラホルダを含む組付けとシミュレーションを行うこと。
原形の全面再設計、未知条件の推測合格、既存支持部の無断削除は行わない。

最新出力: `outputs/pg3-c9-arm-camera-r2/`。
- [全腕・カメラ・PG3組立画像](../outputs/pg3-c9-arm-camera-r2/whole_arm_open.png)
- [開閉アニメーション](../outputs/pg3-c9-arm-camera-r2/simulation/opening_cycle.gif)
- [全腕STEP・開状態](../outputs/pg3-c9-arm-camera-r2/arm_camera_open_UNVALIDATED.step)
- [全検査結果](../outputs/pg3-c9-arm-camera-r2/review.json)
- 作業書: `temp/workdoc_Sep23-2026_pg3_camera_simulation.md`。

## 1. 入力と設計差分

- 入力: 受領アーカイブ。展開済み参照は`references/pg3-c9/PG3_C92_J28/`。
- SHA256: `07f36b6c23ddfbf7d651394549b23a3f89423c5a26c87c1facf21f4452f935fc`。
- 保存先: `references/pg3-c9/PG3_C92_J28/`、receiptは親の`intake.json`。
- `SHA256SUMS.txt`の81ファイルを照合。自己同梱SHAは整合性証跡であり作者認証ではない。
- donor Pythonを実行/importせず、保存STEPを読み取って独立に動かす。
- PG2/R5、旧ラック概念は別候補として維持。PG2の寸法・角度・検証結果を流用しない。

| 項目 | PG3 C9 |
|---|---|
| アクチュエータ | XL430-W250-T、物理bus IDは未確定 |
| 機構 | 中央クランク、左右リンク、印刷角形ガイド |
| 幅・高さ | 92.0 × 63.25 mm |
| 爪長 | 28 mm。C7の12.1 mmから延長 |
| クランク半径・リンク長 | 14 / 24 mm |
| 機構相対角 | 25～135度。サーボ絶対角ではない |
| パッド内側開口 | 約48.895～0.927 mm |
| 印刷物 | 9種類11個。原STEP/STLを保存済み |
| カメラ | ZIPに含まれない。既存P05固定ホルダを組み込む |

変更4種のSTLは`STL/changed_parts/`、継承5種は`STL/unchanged_C7/`。
部品STEPは`CAD/parts/`、単体機構の57 occurrence組立は`CAD/C92_J28_{open,mid,closed}.step`。
この一覧は印刷許可ではない。ねじ/工具、PLA、荷重、配線のゲートは未完。

## 2. 座標と置換範囲

内部construction軸: X=開閉、Y=上、Z=前。donor保存STEPはこれをRx(+90度)したもの。
保存STEPをRx(-90度)してから、アームへ`Ry(+90度), t=(-0.2,234.9,164.6) mm`で配置する。
原M06_ref00とdonorモーターの479頂点、面積、体積が一致。最大頂点差約2.86e-14 mm。
有限signature照合であり全曲面の厳密同等性や締結成立の証明ではない。

元アーム217 occurrenceからP07可動爪とM06_ref00を除き、PG3 57 occurrenceと
カメラ/ホルダ/締結21 occurrenceを加えた**293 occurrence**。他のM06参照部品は残す。
P06固定爪はモーター支持も兼ねるため保持する。全削除すると新グリッパが支持されなくなる。
この保持判断で発生する干渉は隠さず、`UNVALIDATED.step`に残している。

## 3. 干渉と締結に関する判定

最初の全検査`outputs/pg3-c9-arm-camera-r1/`で以下を確認。
追加PG3/カメラ対全既存部＋追加部相互を対象とし、**19,773ペア×3姿勢**を検査した。
元のARM-ARMペアは変更しておらず、今回は再認定対象外。

| 姿勢 | PASS | FAIL | UNKNOWN | ERROR |
|---|---:|---:|---:|---:|
| open 25度 | 19692 | 2 | 11 | 68 |
| mid 90度 | 19688 | 2 | 11 | 72 |
| closed 135度 | 19676 | 4 | 11 | 82 |

確定した交差:

- 全姿勢: **P06対PG3 frame = 240.5625 mm3**。
  交差領域のアーム座標bboxはX[16.8,22.8], Y[241.9,262.9], Z[146.35,150.35] mm。
- mid: P06対carriage_R = **47.36 mm3**。
- closed: P06対carriage_R = **119.5412 mm3**、finger_R_14 bolt = **4.1671 mm3**、nut = **8.5280 mm3**。
- open: P06対pivot_drive_R nut = **0.08005 mm3**。小さい重なりも黙って無視しない。

重要: `isValid()`だけではBooleanを信用できなかった。各operandの自己差分(期待0)と
自己共通(期待元体積)を対照検査する。一部モーター/回転後crankでは自己差分が元体積規模に
なる。これはカーネル/入力表現の未解決であり、ERRORを物理干渉や無干渉へ読み替えない。
原neutral crankは自己差分0だが、回転後は失敗することも再現した。原因は未確定。
カメラ参照形状も約1.08e-4 mm3の自己共通差が厳格な1e-4閾値を超え、ERRORになる。
閾値は後から合格させるために緩めていない。

14種のカメラ用shaft+handle公称包絡と293部品、計4102ペアのmid検査:
PASS4007 / FAIL39 / UNKNOWN29 / ERROR27。これは39本のねじが不適合という意味ではない。
装着後の工具経路が複数部品を横切る検査で、先付け・対向保持・実工具選定を別途要する。
PG3全ねじの実長/深さ/工具工程は、このカメラ用工具検査では認定していない。

## 4. シミュレーションの意味

`simulation/pg3_scene.py`は保存形状から実メッシュを生成する。
crank hinge、左右slider、左右link hinge、手首J5 rollの6自由度、2閉ループsite拘束。
PG3開閉は25～135度を0.5度間隔221姿勢で`mj_forward`により評価する。
式で与えた関節位置に対し、実site位置の閉ループ残差とパッド間隔を測る。
最終r2で最大残差6.65e-12 mm未満、開口誤差4.2e-12 mm未満を確認済み。

**これは運動学であり、物体をつかむ力学・摩擦・ねじプリロードのシミュレーションではない。**
接触は無効、重力0、慣性は正値ダミー。B-rep検査は別に実施。
ロール±30/0度は診断サンプルであり運用可動域ではない。P05カメラの位置・向きが一定で、
下流部が動くことを検査する。上流アームは固定。M05側サプライヤーホーンは未分割で表示上固定。

カメラFOV50度、光学中心は参照筐体の先に仮定。実カメラ選定・校正は未実施。
現ホルダの仮視点では遮蔽があり、open/closedでパッド可視pixel=左右とも0、midでも片方のみ。
仮想カメラをアームX=50/80/110/140 mmへ横移動し対象へ向けた比較も保存する。
X=140 mmでは両パッドのpixelが得られるが、現位置から約140 mm張り出す取付設計を
承認したわけではない。仮想sensorのみ移動し、実ホルダ/筐体は元の場所に残している。
可視pixel数だけで有効な把持対象視野・分解能・機構クリアランスを合格にしない。

## 5. 再現手順

repo rootで実行。既存runへは上書きしない。

```bash
rtk proxy uv sync --locked
rtk proxy env MUJOCO_GL=egl uv run python -m scripts.review_pg3 review \
  --out outputs/pg3-next
rtk proxy env MUJOCO_GL=egl uv run pytest -q
rtk proxy uv run python -m scripts.audit_pg3_run outputs/pg3-next \
  --out temp/pg3-next-evidence-audit.json
rtk proxy uv run ruff check .
rtk proxy uv run ruff format --check .
```

レビューCLIのexit 2は診断上の未承認を意味する。例外exit 1は実行失敗。
原ZIPを再取込する場合は`review_pg3 import <zip> --out <未使用ディレクトリ>`。
その場合`review --source <取込先>/PG3_C92_J28 --out <未使用run>`を指定する。

出力: 開/中/閉の全腕STEP、再読込signature、全件collision JSON、カメラ工具JSON、
各姿勢の全腕画像と末端X/Y/Z/斜視、MuJoCo XML/OBJ、撮像PNG、開閉GIF、
コードsnapshot/入力receipt/runtime/全生成物SHA。再現の正本は`review.json`と`provenance/`。

最終r2はr1の全干渉集計を再現。独立した証跡監査CLIで357 artifactのSHA、
原アーム/リンク/カメラ3入力のSHA、実行コードsnapshot、42 PNGの非blank、
47 GIFフレーム、6自由度/2拘束、ロール時カメラ固定を確認した。
`temp/pg3-c9-r2-evidence-audit.json`の**evidence_audit=PASS / engineering_status=FAIL**を区別する。
segmentationはMSAAのID色混合でIndexErrorが発生したためoffsamples=0へ修正して再生成。
既存物理モデルを消す、無効pixelを0へ丸める、といった回避はしていない。

最終回帰: **119 passed**、ruff check/format成功。1 mmの誤配置/リンク端点/関節位置、
カメラ誤parent、空/改変manifestを含む負例を検査。テストの成功は実機装着の承認ではない。

## 6. 次の設計ゲート

1. P06をモーター支持と旧指に機能分解する。全取付穴/座面/壁/荷重経路を保護領域として
   特定し、上記交差bboxと対照。不要な指のみを局所除去できるか検査する。
   bboxで機械的に切断したり、支持ごと消してテストを通したりしない。
2. ねじ中心、穴径、座面、長さ・有効かかり、ケース深さ、回転ピボットの締付分離を照合する。
   厚いスペーサで逃がす場合も、ねじ長と片持ちモーメントの変更を明示する。
3. カメラを把持域が見える姿勢に再配置する。ただし短い荷重経路、ケーブル/コネクタ、
   工具工程を優先。仮想X=140 mm案をそのままPLAの長い片持ちホルダにしない。
4. カーネル問題の最小再現を比較環境で検査し、原本不変のままBoolean信頼性を回復する。
   未知ペアを除外して無干渉を宣言しない。姿勢/角度間を含む掃引は別ゲート。
5. 実カメラ、ねじ/工具、ケーブル、把持対象/荷重、PLA実測を確定し、
   試験片→非通電仮組み→低負荷の実機確認へ進む。今回はここまでの承認をしていない。
