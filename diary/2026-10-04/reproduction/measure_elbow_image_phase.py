"""Two-image elbow phase observation, not PnP or an executable calibration.

Under orthographic projection, with image X perpendicular to world gravity,
dx1/dx0 = cos(alpha + delta)/cos(alpha). Camera tilt/scale cancel in this ratio.
Perspective and erroneous gravity alignment do not cancel; retain this limitation.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path


def phase_before(dx0, dx1, delta_deg):
    if dx0 == 0 or delta_deg == 0:
        raise ValueError("Unobservable phase: zero projected lever or rotation")
    delta = math.radians(delta_deg)
    return math.degrees(math.atan((math.cos(delta) - dx1 / dx0) / math.sin(delta)))


def controls():
    for alpha in (-72, -40, 20):
        x0 = math.cos(math.radians(alpha))
        x1 = math.cos(math.radians(alpha + 30))
        assert abs(phase_before(x0, x1, 30) - alpha) < 1e-10
    for x0, delta in ((0, 30), (1, 0)):
        try:
            phase_before(x0, 1, delta)
        except ValueError:
            continue
        raise AssertionError("Degenerate observation accepted")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    controls()
    validation = args.run_dir / "validation.json"
    evidence = json.loads(validation.read_text())
    if evidence["verdict"] != "PASS" or not evidence["checks"]["opening_sign_positive"]:
        raise ValueError("Independent actual opening validation required")
    # Approximate axis-centre observations made directly from the original full frames.
    # These are VLM picks, not subpixel computer-vision measurements.
    elbow_x, wrist_before_x, wrist_open_x = 1151, 1038, 882
    delta = evidence["opened_delta_deg"]
    phase = phase_before(wrist_before_x - elbow_x, wrist_open_x - elbow_x, delta)
    upper_vertical_q2 = -math.degrees(math.atan2(14.8, 108.3))
    sources = [validation, *(args.run_dir / f"frame-{name}.jpg"
                            for name in ("before", "open", "return"))]
    report = {
        "method": "VLM axis-centre picks plus orthographic two-image displacement ratio",
        "pnp_used": False,
        "synthetic_controls": "three known phases and two degenerate inputs PASS",
        "actual_delta_deg": delta,
        "image_x_centres_px": {"elbow": elbow_x, "wrist_before": wrist_before_x,
                               "wrist_open": wrist_open_x},
        "forearm_pitch_before_deg_under_assumptions": phase,
        "q2_if_upper_arm_is_world_vertical_deg": upper_vertical_q2,
        "q3_under_both_assumptions_deg": phase + upper_vertical_q2,
        "assumptions": ["approximately orthographic camera over this motion",
                        "image X perpendicular to world gravity",
                        "observed upper arm world vertical for the q2/q3 hypothesis",
                        "observed forearm selects the -90..90 degree phase branch"],
        "limitations": ["perspective/systematic gravity alignment error not bounded",
                        "VLM centre picks are approximate",
                        "neither ID4 absolute reference nor other count signs are measured"],
        "calibration_verified": False, "hardware_targets": None,
        "total_angular_uncertainty_deg": None,
        "sources": [{"path": str(p.resolve()), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                    for p in sources],
    }
    args.output.open("x").write(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "sources"}))


if __name__ == "__main__":
    main()
