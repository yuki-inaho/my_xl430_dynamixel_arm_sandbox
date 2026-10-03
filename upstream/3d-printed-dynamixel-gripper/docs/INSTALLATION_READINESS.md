# PG3実機装着の受入状況

2026-09-23。対象: PG3 C92 J28 C9、全XL430アーム、P05固定カメラ。
**未完了。印刷・実機装着・通電を承認していない。**
局所検査のPASSを、全体の実機装着DoDへ置き換えない。

## 2026-09-24 回答反映

- カメラ未購入。28x28 mm四穴の参考相当取付で設計継続可。型番/光学/質量の合格ではない。
- ロール不要。先行する左右30度要求とID5ロール予約を後続指示が上書きした。
  ID5で開閉・追加モーターなしにユーザー確定。以下r5は旧配置の履歴である。
- 把持対象はキューブ、辺長/重量未定。試験寸法の提案を実要求に置き換えない。
- P05の最小局所配線逃げ候補と再印刷案は許可済み。
  原本・穴・締結/接触面・支持機能を保持。実印刷/通電は未承認。
- XL430付属M2.6x5タッピングねじはない/不明。汎用同径ねじを適合品と断定しない。

現行の仕様/作業は[ID5単独設計](PG3_ID5_ONLY_DESIGN.md)と
`temp/workdoc_Sep24-2026_pg3_id5_only.md`。
新配置のr1は257要素、3開度で各16920PASS/35ERROR/10UNKNOWN。
全体/三面図を生成。P05は未変更の組立比較案であり、配線窓は別候補として検証中。
旧r5のBOM/ロールsceneは新構成に適用しない。
次はこの配置で配線窓とカメラ視点を再設計する。
旧r5のM05出口座標を新構成へ自動流用しない。全体DoDは未達のまま。

## 対象版と確認済みの範囲

- 最新固定候補: `outputs/pg3-installable-candidate-r5/`。3姿勢、各309 occurrence。
- クランク修正を既定生成へ統合。提供元と同じ
  寸法/CSGで中間cleanを遅延し、元製作用STEPとの材料差分0/0を確認。
  全体3姿勢を保存し、元r4やZIPは上書きしていない。
  simulationは改修済み組立midからmesh化する。旧経路のneutral形状流用は修正済み。
- P06対PG3 frameの旧交差240.5625mm3は、局所変更後0、名目隙間0.5mm。
  変更mask外の欠損0。これは強度や全相手の適合承認ではない。
- 4pivotのbench先組み候補を検証。17段153対の単品搬入、治具からの抜去、
  別体spacerを含む18部品のframeへの搬入、工具包絡の部分証拠がある。
- 開閉の運動学、保存CAD、headless画像、部品別のカメラ遮蔽診断を取得。
  重力・接触・把持力・PLAクリープを成立させた力学シミュレーションではない。
- 専用headless Chili3Dにmid STEPを取り込み、DOMの名前付き309部品と
  STEP occurrenceが一意に一致。全体/末端画像を目視。形状は変更していない。

全回帰テストは作業書§42で392passed/8warnings/712.85s。試験件数と実機受入は別判定。

§43でr5保存版の締結・bench搬入を再照合。3姿勢のcamera関連5対、support/M05、
spacer/hornは非侵入の補足証拠、14ねじ接触は受け側領域の公称幾何を確認した。
raw判定は変更しない。§44で表示分割1対の公称上界を追加したが、内部参照32対と
実物条件は未承認のまま残す。
[PG3末端BOM草稿](BOM_DRAFT.md)も旧ラック案から修正し、95 CAD要素/94実体品目を
保存STEPへ照合した。ただし配線/実型番を含む完成調達BOMではない。
§44では上流固定の25〜135度開閉を再検査し、11079対の非接触、187対の不変剛体関係、
5対の公称接触に整理。正の隙間と接触を区別し、配線/軸遊び/実機全姿勢の保証にしない。
公式STEPとR3の同じ番号が別要素になることも検出し、元部品の対応を追跡した。
外接寸法一致だけでは材料同等性や内部接触を承認できないため、32対は未承認を維持する。

## 完了条件との照合

定義は[要求書](REQUIREMENTS.md)および作業書§6。以下の部分証拠は完了印ではない。

| 条件 | 状態・根拠 | 残る証拠 |
|---|---|---|
| D-01 実機/CAD対応 | 未確認。`specs/project.yaml`のID4/5対応・採用arm版はnull | 実物写真/ラベルと使用STEPの対応 |
| D-02 全締結/工程 | 一部。P06軸/座面、候補工具、bench経路、crank修正を統合 | 実ねじ規格/工具、ねじ山/底付き/保持、全相手の最終受入 |
| D-03 把持性能 | 一部。名目平行開閉と閉ループ整合 | 対象物、開口/力/速度/精度と物理検証 |
| D-04 形状保存 | 一部。P06/guideの局所maskと保存版を検証 | 最終採用版全体の契約照合。未知の追加改修を承認しない |
| D-05 全可動域 | 一部。旧配置の上流固定PG3開閉を部分証明 | ロール不要の新配置、実運用ID4範囲、机/配線を含む全体掃引 |
| D-06 撮像/支持 | 未達。参照カメラと仮opticsのみ | 新配置のキューブ/把持域可視性、実カメラ、支持荷重/焦点/画像 |
| D-07 荷重/PLA | 未確認。カメラ腕は長い片持ち | 荷重/加速度/保持時間/温度/材料値と変形・クリープ検証 |
| D-08 配線/電源 | 未達。仮ケーブル出口とP05の干渉あり | 実ケーブル寸法/曲率、逃げ設計、定格/保護 |
| D-09 画像と同一版 | 一部。r5三面図とmidのDOM309照合を追加 | 最終採用版への再照合。表示は干渉承認ではない |
| D-10 製作/実物 | 未達。候補STEP/STLのみ、release=false | 承認版BOM/印刷公差/手順、非通電の版一致仮組み記録 |

最新r5の静的全相手走査は各姿勢24741PASS/44ERROR/10UNKNOWN。
元r4の24735PASS/50ERROR/10UNKNOWNは履歴として保持する。
補足証明を追加しても、未分類ペアを一括PASSへ書き換えていない。
r4のcrank horn screw0は全保存姿勢でERROR。上記修正候補では4本とも名目接触を
検証し、24ずれ負例を拒否できた。ただし実ねじ・PLA支持の承認ではない。
モーター内部の表示用重なりと、外部のねじ/支持接触も区別する。

## 確認が必要な入力

既存部品の観察・仕様確認のための表。未承認部品の印刷や通電を求めるものではない。

| 入力 | 必要な内容 | それまで確定しない判断 |
|---|---|---|
| P05変更範囲 | 局所逃げ候補は許可済み。新配置で具体maskと支持保存を確認 | 具体形状と配線/強度合格 |
| 把持対象と動作 | キューブ辺長mm、ID4範囲、重量、速度/保持時間。ロール不要 | カメラ視点、全域干渉、把持/支持性能 |
| カメラと配線 | 型番/レンズ、質量、USB/TTLケーブル・プラグ寸法と曲げ条件 | 参照28mm取付板の最終寸法、光学・配線合格 |
| 実機対応 | ID4/5の位置が分かる非通電写真、現在のリンクと採用CAD版 | 実アームへの適合寸法確定 |
| 締結/製作 | ねじ頭/長さ/ピッチ/先端、工具寸法、ホーン/idler、PLA校正結果 | 調達BOM、かかり長さ、印刷リリース |

型番未購入なら未購入と記録し、候補を実在品として選定した後に照合する。
M2.6同径同長でもOEMねじと同じとは限らない。候補のsmooth CADはねじ山の証明でない。

## 次の判断と禁止する短絡

1. 回答を`specs/project.yaml`へ出典付きで反映する。nullを0や自由条件に置き換えない。
2. P05許可済み。新モーター配置とケーブル条件に対して局所逃げを設計し、元形状保存と全体干渉を再検査。
3. キューブ/ROIとロール不要の構成に対してカメラ視点を選び、実体ホルダ/工具/支持/配線も同時更新。
4. 残接触と実ねじの締結を閉じ、最終版を一括再生成・検証してから製作/仮組みへ進む。

診断用の±30度、仮のFOV50度、カメラ参照CADを実機仕様として固定しない。
既存の局所PASSだけを増やすことや、さらに治具を増やすことを完了への代替にしない。
残るCAD課題はagent側の責務として残すが、未確定条件の最終設計を勝手に決めない。

## 主な証跡

- [設計・検証範囲](PG3_INSTALLATION_CANDIDATE.md)
- [実行記録・受入監査 §42](../temp/workdoc_Sep23-2026_pg3_installable.md)
- `outputs/pg3-installable-candidate-r5/review.json`
- `outputs/pg3-r5-browser-r1/{review.json,dom-owners.json,whole_arm.png,terminal.png}`
- `outputs/pg3-installable-candidate-r5-audit/{components_r1,bench_cluster_r1,bom_r2}.json`
- 同audit内`mating_regions_{open,mid,closed}_r1.json`と`drive_receivers_{open,mid,closed}_r1.json`
- 同audit内`motor_partition_r1.json`、`continuous_opening_r1.json`、`pivot_motion_r1.json`、
  `horn_sweep_r1.json`、`washer_contacts_r1.json`、`supplier_inventory_r1.json`
- 以下は入力版を固定した履歴。r5へ未再実行の部分証拠を自動継承しない。
- `outputs/pg3-installable-candidate-r4-audit/{attachments_mid_r1,crank_fasteners_r1,bench_loading_r2}.json`
- `outputs/pg3-occluders-r1/review.json`
- `outputs/pg3-browser-audit-r1/{review.json,dom-owners.json,whole_arm.png,terminal.png}`
- `outputs/pg3-crank-representation-r2/{review.json,arm_camera_mid_CANDIDATE.step,whole_arm_open.png}`
- `outputs/pg3-crank-representation-simulation-r1/{simulation.json,provenance.json}`
