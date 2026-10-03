# フォロワーアーム幾何改訂 study

2026-09-19に受領したCAD改訂を、`low_cost_robot`の元STEPを入力として再生成・検証するstudyです。

この改訂は全関節のXL430化ではありません。元のXL430 2台とXL330系4台の混在構成を維持し、次の3部品だけを局所変更します。

- `elbow_to_wrist_extension_round`: 延長リンクの耳周辺を補強
- `base_idler_clearance`: 台座にアイドラ逃げを追加
- `elbow_to_wrist_standoff`: 手首ブラケットに一体スペーサーを追加

元の`hardware/follower/step/arm.step`と`elbow_to_wrist_extension.step`はSHA-256で固定し、別版が入力された場合は生成を停止します。元の`hardware/`は上書きしません。

## 再生成

```bash
cd skills/cad-reverse-parametric/studies/follower_geometry_revision
rtk uv run python source/rebuild.py --render
```

生成先は`skills/cad-reverse-parametric/outputs/follower_geometry_revision/`です。`CAD/parts/`に7部品のSTEP/STL、`CAD/follower_geometry_checked.step`に組立、`reports/`に検証結果が出力されます。

## 検証

```bash
cd skills/cad-reverse-parametric/studies/follower_geometry_revision
rtk env CAD_RELEASE_DIR=../../outputs/follower_geometry_revision uv run python -m pytest -q source/test_revision.py
rtk env CAD_RELEASE_DIR=../../outputs/follower_geometry_revision uv run python source/make_report.py
```

合格条件は、保存後STEPの再読込、単一ソリッド、閉じたSTL、5組の取付穴軸、延長リンク8か所の2.5 mm余肉、基準姿勢での物理部品間干渉0件です。これらは実機の公差・強度・締結・全角度の干渉・物理印刷を証明しません。
