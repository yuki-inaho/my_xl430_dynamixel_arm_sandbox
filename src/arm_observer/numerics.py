"""Pure calibration conversions; no actuator commands or serial imports."""

import numpy as np
from beartype import beartype
from jaxtyping import Float64, Int8, Int32, jaxtyped


@jaxtyped(typechecker=beartype)
def joint_positions_radians(
    position_counts: Int32[np.ndarray, "motors"],
    zero_counts: Int32[np.ndarray, "motors"],
    directions: Int8[np.ndarray, "motors"],
    gear_ratios: Float64[np.ndarray, "motors"],
) -> Float64[np.ndarray, "motors"]:
    if not np.all(np.isin(directions, (-1, 1))):
        raise ValueError("Directions must be -1 or 1")
    if not np.all(np.isfinite(gear_ratios) & (gear_ratios > 0)):
        raise ValueError("Gear ratios must be finite and positive")
    delta = position_counts.astype(np.float64) - zero_counts.astype(np.float64)
    return delta * directions * (2 * np.pi / 4096) / gear_ratios


@jaxtyped(typechecker=beartype)
def velocities_radians_per_second(
    velocity_raw: Int32[np.ndarray, "motors"],
) -> Float64[np.ndarray, "motors"]:
    return velocity_raw.astype(np.float64) * (0.229 * 2 * np.pi / 60)
