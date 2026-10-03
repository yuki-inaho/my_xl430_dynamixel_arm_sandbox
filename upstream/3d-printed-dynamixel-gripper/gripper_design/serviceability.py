import math
from dataclasses import dataclass
from typing import Any

import cadquery as cq

from gripper_design.assembly_contracts import ContractResult


@dataclass(frozen=True)
class FastenerStack:
    screw_length_mm: float
    grip_mm: float
    available_thread_depth_mm: float
    minimum_engagement_mm: float
    tip_clearance_mm: float
    dimensions_confirmed: bool = True
    screw_tip_lead_mm: float | None = None
    receiver_entry_relief_mm: float | None = None
    unthreaded_reach_into_receiver_mm: float | None = None
    receiver_bottom_relief_mm: float | None = None


@dataclass(frozen=True)
class ToolApproach:
    tip: tuple[float, float, float]
    axis: tuple[float, float, float]
    shaft_radius_mm: float
    shaft_length_mm: float
    handle_radius_mm: float
    handle_length_mm: float
    dimensions_confirmed: bool = True
    motion_model: str = "straight_cylindrical"


def check_fastener_stack(stack: FastenerStack, *, tolerance_mm: float = 1e-6) -> ContractResult:
    """Check insertion and full-form axial overlap separately, not thread strength.

    Relief dimensions use depth from the receiver entry plane, positive inward.
    Unknown incomplete-thread lengths cannot silently become zero.
    """
    values = (
        stack.screw_length_mm,
        stack.grip_mm,
        stack.available_thread_depth_mm,
        stack.minimum_engagement_mm,
        stack.tip_clearance_mm,
    )
    reliefs = (
        stack.screw_tip_lead_mm,
        stack.receiver_entry_relief_mm,
        stack.unthreaded_reach_into_receiver_mm,
        stack.receiver_bottom_relief_mm,
    )
    known = (*values, tolerance_mm, *(v for v in reliefs if v is not None))
    if (
        any(not math.isfinite(value) or value < 0 for value in known)
        or stack.screw_length_mm <= 0
        or stack.minimum_engagement_mm <= 0
    ):
        return ContractResult("ERROR", "invalid_fastener_dimension")

    engagement = stack.screw_length_mm - stack.grip_mm
    maximum_engagement = stack.available_thread_depth_mm - stack.tip_clearance_mm
    metrics = {
        "engagement_mm": engagement,
        "minimum_engagement_mm": stack.minimum_engagement_mm,
        "maximum_engagement_before_bottoming_mm": maximum_engagement,
        "dimensions_confirmed": stack.dimensions_confirmed,
        "insertion_mm": engagement,
        "full_form_engagement_mm": None,
        "thread_strength_verified": False,
    }
    if engagement < stack.minimum_engagement_mm - tolerance_mm:
        return ContractResult("FAIL", "insufficient_engagement", metrics=metrics)
    if engagement > maximum_engagement + tolerance_mm:
        return ContractResult("FAIL", "bottoms_out", metrics=metrics)
    if not stack.dimensions_confirmed:
        return ContractResult("UNKNOWN", "fastener_dimensions_unconfirmed", metrics=metrics)
    if any(value is None for value in reliefs):
        return ContractResult("UNKNOWN", "full_form_dimensions_unconfirmed", metrics=metrics)
    start = max(stack.receiver_entry_relief_mm, stack.unthreaded_reach_into_receiver_mm)
    end = min(
        engagement - stack.screw_tip_lead_mm,
        stack.available_thread_depth_mm - stack.receiver_bottom_relief_mm,
    )
    full_form = max(0.0, end - start)
    metrics.update(
        full_form_engagement_mm=full_form,
        full_form_interval_depth_mm=[start, end] if end >= start else None,
    )
    if full_form < stack.minimum_engagement_mm - tolerance_mm:
        return ContractResult("FAIL", "insufficient_full_form_engagement", metrics=metrics)
    return ContractResult("PASS", "fastener_stack_valid", metrics=metrics)


def check_head_clearance(
    head: Any,
    obstacles: dict[str, Any],
    *,
    tolerance_mm3: float = 1e-6,
) -> ContractResult:
    try:
        collisions = _collisions(head, obstacles, tolerance_mm3)
    except Exception as exc:  # noqa: BLE001 - OCP exposes multiple kernel exception types.
        return ContractResult("ERROR", "geometry_query_failed", detail=str(exc))
    if collisions:
        return ContractResult("FAIL", "head_collision", metrics={"collisions": collisions})
    return ContractResult("PASS", "head_clearance_valid", metrics={"collisions": []})


def check_tool_access(
    approach: ToolApproach,
    obstacles: dict[str, Any],
    *,
    stage: str,
    tolerance_mm3: float = 1e-6,
) -> ContractResult:
    metrics: dict[str, Any] = {
        "stage": stage,
        "dimensions_confirmed": approach.dimensions_confirmed,
        "motion_model": approach.motion_model,
    }
    if approach.motion_model != "straight_cylindrical":
        return ContractResult("UNKNOWN", "unsupported_tool_motion", metrics=metrics)
    try:
        axis = cq.Vector(*approach.axis).normalized()
        tip = cq.Vector(*approach.tip)
        shaft = cq.Solid.makeCylinder(
            approach.shaft_radius_mm,
            approach.shaft_length_mm,
            tip,
            axis,
        )
        handle_start = tip + axis.multiply(approach.shaft_length_mm)
        handle = cq.Solid.makeCylinder(
            approach.handle_radius_mm,
            approach.handle_length_mm,
            handle_start,
            axis,
        )
        shaft_hits = _collisions(shaft, obstacles, tolerance_mm3)
        handle_hits = _collisions(handle, obstacles, tolerance_mm3)
    except Exception as exc:  # noqa: BLE001 - classify every kernel failure as ERROR.
        return ContractResult("ERROR", "geometry_query_failed", detail=str(exc), metrics=metrics)

    metrics.update({"shaft_collisions": shaft_hits, "handle_collisions": handle_hits})
    if shaft_hits:
        return ContractResult("FAIL", "tool_shaft_collision", metrics=metrics)
    if handle_hits:
        return ContractResult("FAIL", "tool_handle_collision", metrics=metrics)
    if not approach.dimensions_confirmed:
        return ContractResult("UNKNOWN", "tool_dimensions_unconfirmed", metrics=metrics)
    return ContractResult("PASS", "tool_access_valid", metrics=metrics)


def check_counterhold(
    *,
    required: bool,
    primary_access: bool,
    opposite_access: bool,
) -> ContractResult:
    metrics = {
        "required": required,
        "primary_access": primary_access,
        "opposite_access": opposite_access,
    }
    if not primary_access:
        return ContractResult("FAIL", "primary_tool_unavailable", metrics=metrics)
    if required and not opposite_access:
        return ContractResult("FAIL", "counterhold_unavailable", metrics=metrics)
    return ContractResult("PASS", "counterhold_valid", metrics=metrics)


def _collisions(
    candidate: Any,
    obstacles: dict[str, Any],
    tolerance_mm3: float,
) -> list[dict[str, float | str]]:
    collisions = []
    candidate_box = candidate.BoundingBox()
    for name, obstacle in obstacles.items():
        obstacle_box = obstacle.BoundingBox()
        if not _boxes_overlap(candidate_box, obstacle_box):
            continue
        volume = float(candidate.intersect(obstacle).Volume())
        if volume > tolerance_mm3:
            collisions.append({"obstacle": name, "volume_mm3": volume})
    return collisions


def _boxes_overlap(first: cq.BoundBox, second: cq.BoundBox) -> bool:
    return not (
        first.xmax < second.xmin
        or second.xmax < first.xmin
        or first.ymax < second.ymin
        or second.ymax < first.ymin
        or first.zmax < second.zmin
        or second.zmax < first.zmin
    )
