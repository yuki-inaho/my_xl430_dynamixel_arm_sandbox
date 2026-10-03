import math
from dataclasses import dataclass, field
from typing import Any, Literal

import cadquery as cq

Status = Literal["PASS", "FAIL", "UNKNOWN", "ERROR"]


@dataclass(frozen=True)
class ContractResult:
    status: Status
    reason_id: str
    detail: str = ""
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PlanarSeat:
    face: Any
    origin: tuple[float, float, float]
    normal: tuple[float, float, float]


@dataclass(frozen=True)
class HoleAxis:
    center: tuple[float, float, float]
    direction: tuple[float, float, float]
    diameter_mm: float


@dataclass(frozen=True)
class AssemblyOccurrence:
    name: str
    kind: Literal["solid", "shell", "wire", "empty"]
    geometry: Any
    source: str = "unspecified"
    exclusion_reason: str | None = None


def check_planar_mate(
    first: PlanarSeat,
    second: PlanarSeat,
    *,
    gap_tolerance_mm: float = 0.05,
    normal_tolerance_deg: float = 0.1,
    minimum_contact_area_mm2: float = 1.0,
) -> ContractResult:
    try:
        n_first = _unit(first.normal)
        n_second = _unit(second.normal)
        delta = tuple(b - a for a, b in zip(first.origin, second.origin, strict=True))
        gap = abs(_dot(delta, n_first))
        opposed_angle = math.degrees(math.acos(_clamp(_dot(n_first, tuple(-v for v in n_second)))))
    except Exception as exc:  # noqa: BLE001 - OCP exposes multiple kernel exception types.
        return ContractResult("ERROR", "geometry_query_failed", str(exc))

    metrics = {
        "gap_mm": gap,
        "opposed_normal_error_deg": opposed_angle,
    }
    if opposed_angle > normal_tolerance_deg:
        return ContractResult(
            "FAIL",
            "seat_normals_not_opposed",
            "Mating seat normals must face one another.",
            metrics,
        )
    if gap > gap_tolerance_mm:
        return ContractResult(
            "FAIL",
            "seat_gap",
            "Coaxiality does not establish axial seat contact.",
            metrics,
        )
    try:
        # Compute on the actual trimmed faces, retaining holes. Translate only
        # the permitted axial gap; never substitute bounding rectangles.
        a = _planar_face(first.face)
        b = _planar_face(second.face)
        for face, seat, normal in ((a, first, n_first), (b, second, n_second)):
            face_normal = face.normalAt().toTuple()
            if abs(_dot(face_normal, normal)) < math.cos(math.radians(normal_tolerance_deg)):
                raise ValueError("declared seat normal does not match geometry")
            if (
                abs(
                    _dot(tuple(v - o for v, o in zip(face.Center().toTuple(), seat.origin)), normal)
                )
                > 1e-6
            ):
                raise ValueError("declared seat origin is not on its plane")
        offset = _dot(delta, n_first)
        aligned = b.translate(tuple(-offset * v for v in n_first))
        area = float(a.intersect(aligned).Area())
        if not math.isfinite(area):
            raise ValueError("nonfinite contact area")
        metrics["trimmed_contact_area_mm2"] = area
    except Exception as exc:  # noqa: BLE001
        return ContractResult("ERROR", "geometry_query_failed", str(exc), metrics)
    if area < minimum_contact_area_mm2:
        return ContractResult(
            "FAIL",
            "insufficient_trimmed_contact_area",
            "Infinite planes overlap, but their trimmed faces do not provide enough contact.",
            metrics,
        )
    return ContractResult("PASS", "planar_mate_valid", metrics=metrics)


def check_hole_correspondence(
    first: list[HoleAxis],
    second: list[HoleAxis],
    *,
    center_tolerance_mm: float = 0.05,
    axis_tolerance_deg: float = 0.1,
    diameter_tolerance_mm: float = 0.05,
) -> ContractResult:
    if len(first) != len(second):
        return ContractResult(
            "FAIL",
            "hole_count_mismatch",
            metrics={"first_count": len(first), "second_count": len(second)},
        )
    unmatched = set(range(len(second)))
    matches: list[dict[str, float | int]] = []
    for first_index, source in enumerate(first):
        candidates = []
        source_axis = _unit(source.direction)
        for target_index in unmatched:
            target = second[target_index]
            center_error = _distance(source.center, target.center)
            target_axis = _unit(target.direction)
            axis_error = math.degrees(math.acos(_clamp(abs(_dot(source_axis, target_axis)))))
            diameter_error = abs(source.diameter_mm - target.diameter_mm)
            if (
                center_error <= center_tolerance_mm
                and axis_error <= axis_tolerance_deg
                and diameter_error <= diameter_tolerance_mm
            ):
                candidates.append(
                    (
                        center_error + diameter_error,
                        target_index,
                        center_error,
                        axis_error,
                        diameter_error,
                    )
                )
        if not candidates:
            return ContractResult(
                "FAIL",
                "hole_has_no_unique_mate",
                metrics={
                    "unmatched_first_index": first_index,
                    "remaining_second": sorted(unmatched),
                },
            )
        _, target_index, center_error, axis_error, diameter_error = min(candidates)
        unmatched.remove(target_index)
        matches.append(
            {
                "first_index": first_index,
                "second_index": target_index,
                "center_error_mm": center_error,
                "axis_error_deg": axis_error,
                "diameter_error_mm": diameter_error,
            }
        )
    return ContractResult("PASS", "one_to_one_hole_match", metrics={"matches": matches})


def check_occurrence_coverage(
    occurrences: list[AssemblyOccurrence],
    *,
    candidate_name: str,
    interference_tolerance_mm3: float = 1e-6,
) -> ContractResult:
    names = [item.name for item in occurrences]
    if len(names) != len(set(names)):
        return ContractResult("ERROR", "duplicate_occurrence_name")
    candidate = next((item for item in occurrences if item.name == candidate_name), None)
    if candidate is None or candidate.geometry is None:
        return ContractResult("ERROR", "missing_geometry", "Candidate geometry is absent.")

    supported_kinds = ("solid", "shell", "wire", "empty")
    counts = {f"{kind}_count": 0 for kind in supported_kinds}
    inventory: list[dict[str, Any]] = []
    issues: list[ContractResult] = []
    try:
        candidate_box = candidate.geometry.BoundingBox()
    except Exception as exc:  # noqa: BLE001
        return ContractResult("ERROR", "geometry_query_failed", str(exc), counts)
    for item in occurrences:
        record = {"name": item.name, "kind": item.kind, "source": item.source}
        inventory.append(record)
        try:
            if item.kind not in supported_kinds:
                record["resolution"] = "unsupported_occurrence_kind"
                issues.append(ContractResult("ERROR", "unsupported_occurrence_kind", item.kind))
                continue
            counts[f"{item.kind}_count"] += 1
            if item.kind != "empty" and item.geometry is None:
                record["resolution"] = "missing_geometry"
                issues.append(ContractResult("ERROR", "missing_geometry", item.name))
                continue
            if item.kind == "empty":
                if not item.exclusion_reason:
                    record["resolution"] = "empty_occurrence_without_reason"
                    issues.append(
                        ContractResult("UNKNOWN", "empty_occurrence_without_reason", item.name)
                    )
                    continue
                record["resolution"] = "declared_empty"
                record["reason"] = item.exclusion_reason
                continue
            if item.name == candidate_name:
                record["resolution"] = "candidate"
                continue
            obstacle_box = item.geometry.BoundingBox()
            if not _boxes_overlap(candidate_box, obstacle_box):
                record["resolution"] = "bounding_box_clear"
                continue
            if item.kind in {"shell", "wire"}:
                record["resolution"] = "unresolved_overlap"
                issues.append(
                    ContractResult(
                        "UNKNOWN",
                        "non_solid_overlap_requires_resolution",
                        detail=item.name,
                    )
                )
                continue
            overlap = candidate.geometry.intersect(item.geometry)
            volume = float(overlap.Volume())
            if not math.isfinite(volume) or volume < 0:
                raise ValueError("invalid intersection volume")
            record["intersection_volume_mm3"] = volume
            if volume > interference_tolerance_mm3:
                record["resolution"] = "interference"
                issues.append(
                    ContractResult(
                        "FAIL",
                        "solid_interference",
                        detail=item.name,
                    )
                )
                continue
            record["resolution"] = "boolean_clear"
        except Exception as exc:  # noqa: BLE001 - keep checking remaining occurrences.
            record["resolution"] = "geometry_query_failed"
            record["error"] = str(exc)
            issues.append(ContractResult("ERROR", "geometry_query_failed", str(exc)))

    if issues:
        priority = {"ERROR": 0, "FAIL": 1, "UNKNOWN": 2}
        worst = min(issues, key=lambda result: priority[result.status])
        return ContractResult(
            worst.status,
            worst.reason_id,
            worst.detail,
            {
                **counts,
                "occurrence_inventory": inventory,
                "issues": [
                    {"status": i.status, "reason_id": i.reason_id, "detail": i.detail}
                    for i in issues
                ],
            },
        )

    return ContractResult(
        "PASS",
        "occurrence_coverage_clear",
        metrics={**counts, "occurrence_inventory": inventory},
    )


def _unit(vector: tuple[float, float, float]) -> tuple[float, float, float]:
    magnitude = math.sqrt(sum(value * value for value in vector))
    if not math.isfinite(magnitude) or magnitude <= 1e-12:
        raise ValueError("zero-length direction")
    return tuple(value / magnitude for value in vector)


def _dot(first: tuple[float, float, float], second: tuple[float, float, float]) -> float:
    return sum(a * b for a, b in zip(first, second, strict=True))


def _distance(first: tuple[float, float, float], second: tuple[float, float, float]) -> float:
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(first, second, strict=True)))


def _clamp(value: float) -> float:
    return max(-1.0, min(1.0, value))


def _planar_face(shape: Any) -> cq.Face:
    if isinstance(shape, cq.Wire):
        shape = cq.Face.makeFromWires(shape)
    if not isinstance(shape, cq.Face) or shape.geomType() != "PLANE" or not shape.isValid():
        raise ValueError("seat requires a valid trimmed planar face or closed planar wire")
    return shape


def _boxes_overlap(first: cq.BoundBox, second: cq.BoundBox) -> bool:
    return not (
        first.xmax < second.xmin
        or second.xmax < first.xmin
        or first.ymax < second.ymin
        or second.ymax < first.ymin
        or first.zmax < second.zmin
        or second.zmax < first.zmin
    )
