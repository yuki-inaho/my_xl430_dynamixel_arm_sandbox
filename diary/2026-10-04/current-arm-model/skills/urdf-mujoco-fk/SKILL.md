---
name: urdf-mujoco-fk
description: Convert a traced robot model to URDF and verify forward kinematics and MuJoCo browser rendering. Use for offline joint-angle previews and frame/mesh preservation without assuming physical calibration or actuator control.
---

# URDF・MuJoCoでFKを再現

関節角から位置・方向を示す要求に使う。入力モデル、選択構成、座標・単位、tool評価点、ソフトウェア版を記録。IKや実機制御を暗黙に追加しない。

## 変換と根拠

- sourceとaxis資料をhash固定。受領CAD版、Git branch/commit、写真の推定を別々に記録。branch名だけで印刷済み現物と一致と断定しない。
- mm→m、degree→radを境界で変換。joint originは親frame、axisはjoint frameに表す。世界配置や取り付け回転を二度適用しない。
- 未対応frame/mesh scale/複数jointを近似しない。変換器の対応範囲を示し、必要な変換と試験を追加する。
- visual/collisionを区別。surface-onlyもinventoryに含め、元meshのhashとcompiled後の位置を検査。mass/inertiaやlimitsが仮値なら明示する。
- 固定ホルダー等の追加は、選択部品名と元parent frameを構成仕様へ明記して同じexport経路で処理する。親に追従するvisualのために駆動jointを増やさない。sourceの別groupを丸ごと混入せず、指定した在庫・group・所属bodyを照合する。旧構成を保存し、追加形状も非ゼロ姿勢のworld配置検査へ含める。

MuJoCoのURDFではvisual/固定tool frameを残す目的に合わせ `discardvisual` / `fusestatic` を明示。**書いたURDFを実際にimport**し、保存MJCFへsite/照明を追加。別の元MJCF描画をURDF検証の代わりにしない。[公式拡張](https://mujoco.readthedocs.io/en/3.13.0/modeling.html#urdf-extensions)、[compiler](https://mujoco.readthedocs.io/en/3.13.0/XMLreference.html#compiler)

## FK・描画の検査

元モデル、独立FK、変換後MuJoCoの関節/手先位置・向きをゼロ・非ゼロ・範囲端で比較。全選択meshのworld boundsも検査。軸を誤らせた負例やhash改変で検出器の反応を試す。検証後にしきい値を緩めて合格させない。

FK専用なら `qpos` と `mj_forward` で配置できる。未同定の質量/接触で `mj_step` を回して姿勢を作らない。有限入力/表示範囲と補間幅を検査。停止で残り目標を消費し、再開だけで古い移動を始めない。

専用localhost viewer/Playwright sessionで入力・停止・視点・実フレームdecode・数値・mobile幅を確認。markerはケースに隠れる場合がある。方向線等を追加するなら端点とTCPの違いを表示。PNGだけでなくモデルhash/角度/FK値も保存。

現物countにはID→関節、基準count、回転方向、組立offsetが必要。未校正の写真姿勢や2048をゼロへ置換しない。FK一致は干渉・トルク・電源OFF安定性の証明にはしない。

## このrepoの実例

R3の実行コマンド、対応4軸tree、入力/検証artifactは[references/r3-example.md](references/r3-example.md)。この軸数・数値・範囲を一般規則としてコピーしない。
