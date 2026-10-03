import math
from pathlib import Path
from typing import Any

import yaml


class InterfaceMismatch(ValueError):
    """Raised when two geometric interface contracts cannot mate coaxially."""


def load_interface_contract(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict):
        raise InterfaceMismatch("interface contract root must be a mapping")
    return data


def validate_bolt_circle(
    candidate: dict[str, Any],
    reference: dict[str, Any],
    *,
    tolerance_mm: float = 0.05,
) -> float:
    candidate_pcd = _positive_number(candidate, "pitch_circle_diameter")
    reference_pcd = _positive_number(reference, "pitch_circle_diameter")
    radial_mismatch = abs(candidate_pcd - reference_pcd) / 2.0
    if radial_mismatch > tolerance_mm:
        raise InterfaceMismatch(
            f"bolt-circle radial mismatch {radial_mismatch:.3f} mm exceeds {tolerance_mm:.3f} mm"
        )

    candidate_bore = candidate.get("bore_diameter")
    reference_bore = reference.get("bore_diameter")
    if candidate_bore is not None and reference_bore is not None:
        bore_mismatch = abs(float(candidate_bore) - float(reference_bore))
        if bore_mismatch > tolerance_mm:
            raise InterfaceMismatch(
                f"bore-diameter mismatch {bore_mismatch:.3f} mm exceeds {tolerance_mm:.3f} mm"
            )
    return radial_mismatch


def validate_contract_geometry(contract: dict[str, Any]) -> None:
    if contract.get("schema_version") != 1:
        raise InterfaceMismatch("schema_version must be 1")
    interfaces = contract.get("servo_interfaces")
    if not isinstance(interfaces, dict) or set(interfaces) != {"J5", "J6"}:
        raise InterfaceMismatch("servo_interfaces must define J5 and J6")

    for joint_name, joint in interfaces.items():
        for side_name in ("output_side", "idler_side"):
            side = joint.get(side_name)
            if not isinstance(side, dict):
                raise InterfaceMismatch(f"{joint_name}.{side_name} must be a mapping")
            vectors = side.get("four_bore_radial_vectors")
            if not isinstance(vectors, list) or len(vectors) != 4:
                raise InterfaceMismatch(f"{joint_name}.{side_name} must have four bore vectors")
            expected_radius = _positive_number(side, "pitch_circle_diameter") / 2.0
            normalized = set()
            for vector in vectors:
                if not isinstance(vector, list) or len(vector) != 3:
                    raise InterfaceMismatch(f"{joint_name}.{side_name} has an invalid vector")
                radius = math.sqrt(sum(float(value) ** 2 for value in vector))
                if not math.isclose(radius, expected_radius, abs_tol=1e-6):
                    raise InterfaceMismatch(
                        f"{joint_name}.{side_name} vector radius {radius:.6f} "
                        f"does not match PCD radius {expected_radius:.6f}"
                    )
                normalized.add(tuple(float(value) for value in vector))
            if len(normalized) != 4:
                raise InterfaceMismatch(f"{joint_name}.{side_name} bore vectors are not unique")
            axial_range = side.get("bore_axial_range")
            if (
                not isinstance(axial_range, list)
                or len(axial_range) != 2
                or float(axial_range[0]) >= float(axial_range[1])
            ):
                raise InterfaceMismatch(f"{joint_name}.{side_name} axial range is invalid")


def _positive_number(item: dict[str, Any], key: str) -> float:
    try:
        value = float(item[key])
    except (KeyError, TypeError, ValueError) as exc:
        raise InterfaceMismatch(f"{key} must be numeric") from exc
    if value <= 0:
        raise InterfaceMismatch(f"{key} must be positive")
    return value
