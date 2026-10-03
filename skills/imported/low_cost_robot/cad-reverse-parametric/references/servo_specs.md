# Servo spec drivers: XL330-M288-T → XL430-W250-T

These are the parameter values that drive the swap. They live in code in
`studies/xl430_lowcost/domain.py`. **Always verify against the ROBOTIS e-Manual**
before a real build — catalog pages are the source of truth, this table is a cache.

| field | XL330-M288-T | XL430-W250-T | ratio |
|---|---|---|---|
| envelope W×H×D (mm) | 20.0 × 34.0 × 26.0 | 28.5 × 46.5 × 34.0 | ×1.43 / ×1.37 / ×1.31 |
| weight (g) | 18 | 57.2 | ×3.18 |
| recommended voltage (V) | 5.0 | 11.1 | — |
| voltage range (V) | 3.7–6.0 | 6.5–12.0 | — |
| stall torque (N·m) | 0.42 @5V | 1.5 @11.1V | ×3.57 |
| mount screw | M2 | M2.5 | — |
| protocol | TTL | TTL | — |

Sources:
- XL330-M288-T: https://emanual.robotis.com/docs/en/dxl/x/xl330-m288/
- XL430-W250-T: https://emanual.robotis.com/docs/en/dxl/x/xl430-w250/

## What this means for the CAD swap

- **Body grows ~8–12.5 mm per axis.** Every clearance pocket and motor-facing
  bore must open up. The +12.5 mm height is the tightest constraint on short
  links.
- **Mass ×3.18.** Up-stream links and joints carry far more cantilever load;
  revisit wall thickness and ribbing, not just the pocket.
- **Torque ×3.57.** The interface can transmit much more — screw count / horn
  coupling should be checked, not blindly copied.
- **Voltage 5 V → 11.1 V.** Not a CAD issue, but note the repo's existing
  "ignore voltage error" workaround exists precisely because 5 V motors were run
  at 12 V; XL430 removes that mismatch.
- **Mount screw M2 → M2.5.** Hole diameters recovered as ~2.3–2.4 mm (M2) must
  become ~2.9 mm (M2.5) clearance; re-check head seats / counterbores.

> Geometric mounting detail (exact hole pitch, axis offsets) is **measured** from
> the original STEP via `brep_probe`, not taken from this table. See
> `workflow.md` and `outputs/xl430_impact/brep.json`.
