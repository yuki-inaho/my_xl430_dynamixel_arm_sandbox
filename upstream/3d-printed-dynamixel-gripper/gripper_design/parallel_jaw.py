import math
from dataclasses import dataclass

import cadquery as cq


@dataclass(frozen=True)
class ParallelJawParameters:
    pinion_pitch_radius_mm: float = 8.0
    base_opening_mm: float = 40.0
    theta_min_rad: float = -0.5
    theta_max_rad: float = 0.5
    jaw_thickness_mm: float = 8.0
    jaw_length_mm: float = 40.0
    jaw_height_mm: float = 24.0
    left_rack_direction: int = -1
    right_rack_direction: int = 1
    output_pitch_circle_diameter_mm: float = 16.0
    output_bore_diameter_mm: float = 2.0
    design_state: str = "concept_only"


@dataclass(frozen=True)
class JawState:
    theta_rad: float
    analytic_opening_mm: float
    measured_opening_mm: float
    left_inner_x_mm: float
    right_inner_x_mm: float
    left_face_normal: tuple[float, float, float]
    right_face_normal: tuple[float, float, float]
    orientation_error_deg: float


def validate_parameters(parameters: ParallelJawParameters) -> None:
    if parameters.pinion_pitch_radius_mm <= 0:
        raise ValueError("pinion pitch radius must be positive")
    if parameters.left_rack_direction != -parameters.right_rack_direction:
        raise ValueError("rack directions must be opposed")
    if parameters.left_rack_direction not in {-1, 1}:
        raise ValueError("rack directions must be +/-1")
    if parameters.theta_min_rad >= parameters.theta_max_rad:
        raise ValueError("theta interval must be ordered")
    if (
        min(
            opening_mm(parameters, parameters.theta_min_rad),
            opening_mm(parameters, parameters.theta_max_rad),
        )
        <= 0
    ):
        raise ValueError("opening must remain positive over the declared interval")
    if (
        min(
            opening_mm(parameters, parameters.theta_min_rad),
            opening_mm(parameters, parameters.theta_max_rad),
        )
        <= 2 * parameters.pinion_pitch_radius_mm
    ):
        raise ValueError("opening must exceed the pinion diameter")
    if min(parameters.jaw_thickness_mm, parameters.jaw_length_mm, parameters.jaw_height_mm) <= 0:
        raise ValueError("jaw dimensions must be positive")
    if not math.isclose(parameters.output_pitch_circle_diameter_mm, 16.0, abs_tol=1e-9):
        raise ValueError("all-XL430 concept requires the measured PCD16 output interface")
    if parameters.design_state != "concept_only":
        raise ValueError("unverified jaw parameters must remain concept_only")


def opening_mm(parameters: ParallelJawParameters, theta_rad: float) -> float:
    return parameters.base_opening_mm + 2.0 * parameters.pinion_pitch_radius_mm * theta_rad


def jaw_state(parameters: ParallelJawParameters, theta_rad: float) -> JawState:
    validate_parameters(parameters)
    if not parameters.theta_min_rad <= theta_rad <= parameters.theta_max_rad:
        raise ValueError("theta is outside the declared hard-stop interval")
    opening = opening_mm(parameters, theta_rad)
    left_inner = -opening / 2.0
    right_inner = opening / 2.0
    measured = right_inner - left_inner
    return JawState(
        theta_rad=theta_rad,
        analytic_opening_mm=opening,
        measured_opening_mm=measured,
        left_inner_x_mm=left_inner,
        right_inner_x_mm=right_inner,
        left_face_normal=(1.0, 0.0, 0.0),
        right_face_normal=(-1.0, 0.0, 0.0),
        orientation_error_deg=0.0,
    )


def build_parallel_jaw(
    parameters: ParallelJawParameters,
    *,
    theta_rad: float,
) -> dict[str, cq.Shape]:
    state = jaw_state(parameters, theta_rad)
    base = cq.Solid.makeBox(80, 55, 6, cq.Vector(-40, -27.5, 0))
    for x, y in ((8, 0), (-8, 0), (0, 8), (0, -8)):
        base = base.cut(
            cq.Solid.makeCylinder(
                parameters.output_bore_diameter_mm / 2,
                8,
                cq.Vector(x, y, -1),
            )
        )
    base = base.cut(cq.Solid.makeCylinder(5.5, 8, cq.Vector(0, 0, -1)))

    left_jaw = cq.Solid.makeBox(
        parameters.jaw_thickness_mm,
        parameters.jaw_length_mm,
        parameters.jaw_height_mm,
        cq.Vector(
            state.left_inner_x_mm - parameters.jaw_thickness_mm,
            -parameters.jaw_length_mm / 2,
            6,
        ),
    )
    right_jaw = cq.Solid.makeBox(
        parameters.jaw_thickness_mm,
        parameters.jaw_length_mm,
        parameters.jaw_height_mm,
        cq.Vector(
            state.right_inner_x_mm,
            -parameters.jaw_length_mm / 2,
            6,
        ),
    )
    rack_length = state.measured_opening_mm / 2 - parameters.pinion_pitch_radius_mm
    left_rack = cq.Solid.makeBox(
        rack_length,
        5,
        4,
        cq.Vector(
            state.left_inner_x_mm,
            -parameters.pinion_pitch_radius_mm - 5,
            9,
        ),
    )
    right_rack = cq.Solid.makeBox(
        rack_length,
        5,
        4,
        cq.Vector(parameters.pinion_pitch_radius_mm, parameters.pinion_pitch_radius_mm, 9),
    )
    left_jaw = left_jaw.fuse(left_rack).clean()
    right_jaw = right_jaw.fuse(right_rack).clean()
    pinion = cq.Solid.makeCylinder(parameters.pinion_pitch_radius_mm, 6, cq.Vector(0, 0, 6))

    left_post = cq.Solid.makeBox(5, 10, 12, cq.Vector(-16, -5, 6))
    right_post = cq.Solid.makeBox(5, 10, 12, cq.Vector(11, -5, 6))
    top = cq.Solid.makeBox(32, 10, 4, cq.Vector(-16, -5, 18))
    opposite_support = left_post.fuse(right_post, top).clean()
    opposite_support = opposite_support.cut(cq.Solid.makeCylinder(4.1, 6, cq.Vector(0, 0, 17)))

    return {
        "base": base.clean(),
        "left_jaw": left_jaw,
        "right_jaw": right_jaw,
        "pinion": pinion,
        "opposite_support": opposite_support,
    }
