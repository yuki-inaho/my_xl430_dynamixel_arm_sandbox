# Onshape検証の使い方と判断メモ

この作業で実際に通した手順。まず [再作成モデル](https://cad.onshape.com/documents/531556789fcbb8dfdcac2689/w/f18636c9c4ee7993d5afbbaa/e/a0b147c03da145430a3c0bf1) の `Robot Assembly - URDF` を開く。画面に全体が入らない場合は描画領域へフォーカスしてF（Zoom to fit）。

## 1. 静止状態のチェック

左のInstancesは12、Mate featuresは13。赤いMate、missing reference、抑制状態、base以外の意図しないFixを確認する。今回の最終13 Mateは全てOK。

ただし「OK」は姿勢一致や可動性の証明ではない。初回には軸反転でモデルが180°反転した状態や、制限の数値がゼロに残って動けない状態があった。原本取り込みVersionと見比べ、APIを使う場合はoccurrenceの変換行列も照合する。

## 2. アニメーション

1. `dof_gripper_drive` を右クリック → **Animate…**。
2. Start −45 deg、End 65 deg。これは機構角theta=135°（閉）→25°（開）。90°がURDFゼロ。
3. Stepsは例えば300、Playback typeはSingleまたはReciprocate。
4. Playを押し、**Current valueが変わり、左右の指とリンクが連動する**ことを見る。
5. Stop後にダイアログを閉じる。アニメーション終了後の保存姿勢は見た目だけで判断せず、Resetまたはmatevaluesで中立へ戻す。

実績画像: `onshape-animation.png`、`rebuild/animation.png`。

「Unable to compute any steps ... Instance(s) may be constrained」が出た場合は、Fix、過剰拘束、軸、制限を切り分ける。今回、APIの表示式と内部value/unitsが不一致だった。全制限を恒久的に削除して解決扱いにはせず、正しい制限を復旧して両端まで動くことを再確認した。

APIでグリッパだけ動かすと、他の自由なアームMateが微小に変わる場合がある。比較用の姿勢要求ではアーム4軸を0として同時に指定する。返却された値が要求に達したこと、閉ループの両点が一致したことまで見る。

## 3. 干渉検出

1. 右下の解析メニュー → **Interference detection…**。
2. Instances to analyzeに対象を指定。今回は左ツリーの `base_link <1>` をクリックし、Shiftを押して最後の `camera_body <1>` をクリックし12個を選択。
3. Interferencesに出る各行をクリック/hoverして、ハイライトの位置とバウンディングボックスを確認する。
4. 選択範囲、姿勢、結果数、組合せを記録し、姿勢を変えたら検査し直す。

今回の両ドキュメントの全開・中間・全閉では各6件。

|Onshapeの組合せ|件数|同じ入力SHAの既存CADレポートとの対応|
|---|---:|---|
|wrist / camera_mount|4|CAM5_BASE_TAP_0..3 と PG3_XL430_fixed。既存レポートは意図したねじ形成接触の領域を指定|
|camera_body / camera_mount|2|CAM5_D405_SCREW_0..1 と CAM5_D405_BODY。既存レポートは背面M3受け領域内の交差を記録|

画像は `onshape-interference-*.png` と `rebuild/interference-*.png`。`inherited-contact-evidence.json` は既存レポートの抜粋で、今回新たにそのBRep計算を実行したものではない。

干渉の件数だけを小さくする目的でねじや受け形状を削らない。意図した締結と意図しない衝突を、形状の位置と設計用途で区別する。ただし意図した交差でも締結強度・公差・挿入深さの実機検証とは別。

閉じたcomposite内の干渉やシート形状は、このリンク間検査の保証範囲外。アームの全姿勢を連続走査した検証でもない。

## 4. URDF側の検証

- メッシュが全て存在し、長さがm、角度がradであること。
- 親子が一意で、循環のない木としてbase_linkから全16linkへ届くこと。
- ゼロ姿勢と元メッシュ配置の一致、関節軸、制限の符号。
- theta25〜135°を0.25°刻み（441点）で与え、左右のclosingフレームの位置残差を計算。
- 再取込前後のメッシュを座標で比較。STLのバイト列は三角形順序により異なることがある。今回は12形状全てで双方向最近傍頂点距離0、三角形数・面積も一致。

今回の最大URDF閉ループ位置残差は約0.23 µm。これはエクスポータの6桁程度の数値丸めも含む計算誤差で、実機の加工・把持精度を表すものではない。

## 公式資料

- [Interference detection](https://cad.onshape.com/help/Content/View/interference_detection.htm)
- [Mates](https://cad.onshape.com/help/Content/Assembly/mates.htm)
- [Mate値を使った位置指定](https://www.onshape.com/en/resource-center/tech-tips/precisely-position-mates)
- [Error indicators](https://cad.onshape.com/help/Content/Home/error_indicators.htm)
- [onshape-to-robot: 設計規約](https://onshape-to-robot.readthedocs.io/en/latest/design.html)
- [onshape-to-robot: 閉ループ](https://onshape-to-robot.readthedocs.io/en/latest/kinematic_loops.html)
