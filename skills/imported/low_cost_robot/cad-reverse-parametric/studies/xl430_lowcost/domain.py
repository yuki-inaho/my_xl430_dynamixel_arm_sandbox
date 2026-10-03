"""Domain layer: Dynamixel XL330 -> XL430 specifics for the low_cost_robot arm.

This is the ONLY place that knows about servos. It supplies the generic `cadre`
core with: the two servo components, a Dynamixel keyword policy, a classifier,
and metric screw bands. Swap this module to retarget the toolkit elsewhere.

Catalog values — verify before trusting:
  XL330-M288-T : https://emanual.robotis.com/docs/en/dxl/x/xl330-m288/
  XL430-W250-T : https://emanual.robotis.com/docs/en/dxl/x/xl430-w250/
"""
from __future__ import annotations

from cadre import Envelope, Component, KeywordPolicy, RuleClassifier

XL330 = Component(
    name="XL330-M288-T",
    envelope=Envelope(20.0, 34.0, 26.0),
    # stall torque 0.52 N·m @ 5.0 V (e-Manual). Case/horn mounting M2.
    meta={"mass_g": 18.0, "voltage_nominal_v": 5.0, "voltage_range_v": [3.7, 6.0],
          "mount_screw": "M2", "horn_screw": "M2", "stall_torque_nm": 0.52,
          "horn_type": "integrated plastic horn; FPX330 idler set", "protocol": "TTL"},
)

XL430 = Component(
    name="XL430-W250-T",
    envelope=Envelope(28.5, 46.5, 34.0),
    # Case mounting is M2 (M2x5); M2.5x14 is included for frame/horn assembly only.
    # Stall torque 1.4 N·m @ 11.1 V nominal (1.5 N·m is the 12.0 V figure).
    meta={"mass_g": 57.2, "voltage_nominal_v": 11.1, "voltage_range_v": [6.5, 12.0],
          "mount_screw": "M2", "horn_screw": "M2.5", "stall_torque_nm": 1.4,
          "horn_type": "HN11-N101 idler horn; FR-series frames", "protocol": "TTL"},
)

# Dynamixel-aware keyword policy injected into the generic text probe.
DXL_KEYWORDS = KeywordPolicy({
    "xl330": r"xl330|fpx330|fp04|fr11",
    "xl430": r"xl430|fr12|hn11|hn12",
    "connector": r"connector",
    "gripper": r"gripper",
    "servo": r"servo|dynamixel|dxl",
})


def build_classifier() -> RuleClassifier:
    """Impact tier from text-probe keyword counts (Dynamixel policy)."""
    def has(kw, *names):
        return any(kw.get(n, 0) > 0 for n in names)
    return RuleClassifier(rules=[
        ("direct", lambda t: has(t["keywords"], "xl330", "xl430")),
        ("likely", lambda t: has(t["keywords"], "connector", "servo")),
        ("review", lambda t: has(t["keywords"], "gripper")),
    ], default="indirect")


def envelope_delta() -> dict:
    return {"servo": "XL330 -> XL430", **XL330.envelope.ratio_to(XL430.envelope),
            "mass_ratio": round(XL430.meta["mass_g"] / XL330.meta["mass_g"], 3),
            "torque_ratio": round(XL430.meta["stall_torque_nm"]
                                  / XL330.meta["stall_torque_nm"], 3)}
