# 3D Print Checklist

XL430部品の設計・印刷可否の現状は [xl430_part_completion_status.md](xl430_part_completion_status.md) を参照してください。

2026-09-19の混在サーボ構成向け改訂は [follower_geometry_revision_20260919.md](follower_geometry_revision_20260919.md) に分離して記録しています。

全6関節XL430静止組立の受領レビューは [all_xl430_revision_20260919.md](all_xl430_revision_20260919.md) に記録しています。置換後の静止干渉が54件あるため、全XL430版の印刷チェック項目とG-codeはまだ作成していません。

## 2026-09-19 All-XL430 Prototype: Blocked

`skills/cad-reverse-parametric/outputs/all_xl430_revision/unaccepted/current/`には再生成した診断用STEPと検証レポートがありますが、`CAD/arm_all_XL430_static_UNACCEPTED.step`は印刷承認済み成果物ではありません。

流用された7部品は混在サーボ版ではメッシュ検査とOrcaSlicer検査に合格しています。しかし、全XL430置換後の組立では外部部品間の静止干渉54件（同一モーター内部の重複168件は別集計）と取付軸が未解決なので、同じSTLを全XL430対応部品として重複掲載しません。`source/study.py print-package`（および`prepare_print_package.py`）が毎回再検証して停止している間は、全XL430版の印刷チェックリストを追加しない方針です。

This document is a simple print-tracking checklist. The checkbox only means
"physically printed"; it does not mean CAD validation, slicer validation, assembly
fit, screw fit, or operation has passed.

## 2026-09-19 Follower Geometry Revision Package

This is a mixed-servo geometry revision, not a full XL430 conversion. The
regenerated CAD and slicer package are under
`skills/cad-reverse-parametric/outputs/follower_geometry_revision/` and
`skills/cad-reverse-parametric/outputs/follower_print_package/`.

The package contains seven accepted parts and two validated K1C plates. See
[the revision record](follower_geometry_revision_20260919.md) and its
`README_ja.md` for the geometry and slicer evidence.

| Printed | Part / file |
|---|---|
| [ ] | `skills/cad-reverse-parametric/outputs/follower_print_package/STL/base_idler_clearance.stl` |
| [ ] | `skills/cad-reverse-parametric/outputs/follower_print_package/STL/elbow_to_wrist_extension_round.stl` |
| [ ] | `skills/cad-reverse-parametric/outputs/follower_print_package/STL/elbow_to_wrist_standoff.stl` |
| [ ] | `skills/cad-reverse-parametric/outputs/follower_print_package/STL/shoulder_rotation_unchanged.stl` |
| [ ] | `skills/cad-reverse-parametric/outputs/follower_print_package/STL/shoulder_to_elbow_unchanged.stl` |
| [ ] | `skills/cad-reverse-parametric/outputs/follower_print_package/STL/gripper_static_unchanged.stl` |
| [ ] | `skills/cad-reverse-parametric/outputs/follower_print_package/STL/gripper_moving_unchanged.stl` |

Physical printing and assembly fit remain unchecked.

## XL430 Mesh-Checked Investigation Package

Use this set for the current XL430 investigation output package.

The slicer-ready package is generated at
`skills/cad-reverse-parametric/outputs/xl430_print_package/`. Its
`GCODE/xl430_arm_parts_PLA.gcode` contains the five accepted parts on one K1C
plate with support enabled. See
[the STEP-to-slicer workflow](../skills/cad-reverse-parametric/references/step-to-slicer.md)
and the package `README_ja.md` for the exact validation record.

The 2026-09-18 review found that the existing `elbow_to_wrist_xl430` model is not
source-equivalent: an outside rounded profile had been mistaken for a bore.
Existing files under `outputs/parts` and `outputs/print` may predate that finding.
Mesh-printability results alone do not validate those files for assembly. The
revised driver blocks normal XL430 export and labels optional diagnostic models
`*_prototype`. See [the review](cadre_review_20260918.md).

| Printed | Part / file |
|---|---|
| [ ] | `skills/cad-reverse-parametric/outputs/xl430_print_package/STL/shoulder_rotation_orig.stl` |
| [ ] | `skills/cad-reverse-parametric/outputs/xl430_print_package/STL/shoulder_to_elbow_xl430.stl` |
| [ ] | `skills/cad-reverse-parametric/outputs/xl430_print_package/STL/elbow_to_wrist_extension_xl430.stl` |
| [ ] | `skills/cad-reverse-parametric/outputs/xl430_print_package/STL/gripper_static_part_xl430.stl` |
| [ ] | `skills/cad-reverse-parametric/outputs/xl430_print_package/STL/gripper_moving_part_xl430_print.stl` |

`elbow_to_wrist_xl430.stl` は設計レビューで未承認のため、この表とG-codeへ含めない。

## Follower Arm Original STL Set

| Printed | Part / file |
|---|---|
| [ ] | `hardware/follower/stl/arm.stl` |
| [ ] | `hardware/follower/stl/base.stl` |
| [ ] | `hardware/follower/stl/shoulder_rotation.stl` |
| [ ] | `hardware/follower/stl/shoulder_to_elbow.stl` |
| [ ] | `hardware/follower/stl/elbow_to_wrist.stl` |
| [ ] | `hardware/follower/stl/elbow_to_wrist_extension.stl` |
| [ ] | `hardware/follower/stl/gripper_static_part.stl` |
| [ ] | `hardware/follower/stl/gripper_moving_part.stl` |

## Leader Arm Original STL Set

| Printed | Part / file |
|---|---|
| [ ] | `hardware/leader/stl/leader_arm.stl` |
| [ ] | `hardware/leader/stl/base.stl` |
| [ ] | `hardware/leader/stl/shoulder_to_elbow.stl` |
| [ ] | `hardware/leader/stl/elbow_to_wrist.stl` |
| [ ] | `hardware/leader/stl/elbow_to_wrist_extension.stl` |
| [ ] | `hardware/leader/stl/gripper_handle.stl` |
| [ ] | `hardware/leader/stl/gripper_trigger.stl` |
