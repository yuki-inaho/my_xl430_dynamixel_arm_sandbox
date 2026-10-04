# 短縮D405候補のURDF（運動学用）

250 g比較候補 C_y185_z250_p75 の新しい出力です。旧R5 URDFとは別で、今回のカメラホルダー、glass中心 [-0.2,185,250] mm、手首制限を反映しています。

[出力元Onshape V2を開く](https://cad.onshape.com/documents/7b85d8922959cbe564b6e0cb/v/e21cffef1877c8f91d2b03f8/e/848ae15cd82797bd99cdc330)。全13 mateがOK、基部だけ固定です。読み取り専用の保存版なので、編集する場合は元のworkspaceを開きます。

## 使うファイル

- `robot.urdf` と `assets/` を同じフォルダ構成で保持します。12個のSTLは新V2から実際に取得したものです。
- `robot.onshape-raw.urdf` は onshape-to-robot 1.8.3 の未加工出力。利用版は相対mesh参照、固定jointの不要axis/limit除去、未測定のゼロ慣性除去を行ったものです。
- `source-manifest.json` にCAD、版、URDF、STLのSHA256を記録しています。
- `pg3_states.py` がグリッパの非線形連動を返します。`validate_robot.py` はローカルで再検証できます。
- `native-reference.json` はOnshapeの実11姿勢。`validation.json` は検証結果。ライセンスは `licenses/` と `NOTICE.md` に保存しています。

## 再検証と姿勢の利用

Python環境にnumpyとtrimeshが必要です。この作業環境では次を実行できます（cwdはonshape）。

```bash
rtk proxy uv run --project . --no-sync python outputs/optimization-250g/robot/validate_robot.py
rtk proxy uv run --project . --no-sync python outputs/optimization-250g/robot/pg3_states.py 90
```

`joint_states(theta_deg)` の入力はCAD角25〜135°、90°が基準です。返値は回転rad、直動m。`gripper_drive` だけを動かさず、返されたjaw_left/rightとcoupler_left/rightを同時に適用します。これは単純なURDF mimicでは表せない連動です。アーム4軸を動かす場合は、返値の該当joint値を上書きします。駆動角は `q=rad(90-theta)`、左右スライダは符号が逆です。

手首 `joint4_wrist` はURDFで −106〜+138°（CAD物理回転の−138〜+106°と符号が逆）。camera_bodyは配置を示すボディフレームで、校正済みROS optical frameではありません。

## 実行済み検証

16 links / 15 joints（5能動、4受動、6固定）、12 mesh、全参照とSI寸法を検証しました。441点の左右閉リンク位置誤差は最大 **0.231 µm**、Onshape実11姿勢×12リンクとの行列要素差は最大 **8.551e-6**（許容2e-5）。この行列指標は回転・並進の要素を含むため、全体を距離と呼ばないでください。

旧R5とのSTL厳密同一比較はforearm/wristで不成立でした。再取り込みの分割差を含み、面サンプル距離は最大0.35/0.71 µm。失敗結果を残し、旧meshへ差し替えていません。元の非カメラ236 CAD occurrenceの体積・boundsは従来roundtrip基準内です。詳細は [出力元照合](../reports/export-provenance.json) と [面サンプル診断](../reports/mesh-surface-diagnostic.json)。完全な面同一性の証明ではありません。

## 使用範囲と未確認事項

運動学・表示用のモデルです。材料/積層/実重量/慣性は未確定で、inertialはありません。effortとvelocityの0は未測定の仮値です。制御・動力学シミュレーション・250 g連続運転の認定値として使わないでください。原点復帰、モータ符号、関節校正は実機未確認です。

既存ねじ6組の干渉、供給元sheet4組の未解決包絡、M01〜M04の未分割外観ボディを保持しています。全アームの連続軌道衝突検証、疲労・クリープ・破壊試験は未実施です。設計比較と画角の条件は [REPORT](../REPORT.md) を参照してください。
