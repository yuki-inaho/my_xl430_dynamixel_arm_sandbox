"""Driver: wire the generic `cadre` core with the Dynamixel domain over a parts tree.

    uv run python studies/xl430_lowcost/run.py <parts_dir> --out <out_dir>

Thin on purpose: all reusable logic lives in `cadre`; all servo knowledge lives
in `domain`. This file only connects them.
"""
from __future__ import annotations
import sys
import json
import argparse
from pathlib import Path

from cadre import ImpactConfig, analyze_tree, report
import domain


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("parts_dir", type=Path)
    ap.add_argument("--out", type=Path, default=Path("outputs/xl430_impact"))
    ap.add_argument("--no-brep", action="store_true")
    a = ap.parse_args(argv)

    config = ImpactConfig(
        classifier=domain.build_classifier(),
        keyword_policy=domain.DXL_KEYWORDS,
        target_envelope=domain.XL430.envelope,
    )
    analysis = analyze_tree(a.parts_dir, config, use_brep=not a.no_brep)

    d = domain.envelope_delta()
    intro = [
        "## Servo envelope delta\n",
        f"- {domain.XL330.name}: {domain.XL330.envelope.as_tuple()} mm, "
        f"{domain.XL330.meta['mass_g']} g, {domain.XL330.meta['voltage_nominal_v']} V",
        f"- {domain.XL430.name}: {domain.XL430.envelope.as_tuple()} mm, "
        f"{domain.XL430.meta['mass_g']} g, {domain.XL430.meta['voltage_nominal_v']} V",
        f"- Growth: W ×{d['w_ratio']:.2f}, H ×{d['h_ratio']:.2f}, "
        f"D ×{d['d_ratio']:.2f}; mass ×{d['mass_ratio']:.2f}; "
        f"torque ×{d['torque_ratio']:.2f}",
        "",
        "> `target fits` = does the XL430 body fit *inside* the part bbox. For open "
        "brackets this is usually False and is NOT the swap criterion; the hole "
        "families in `brep.json` are. Treat it as an enclosure-only signal.",
    ]
    res = report.write_all(analysis, a.out,
                           "XL330 → XL430 CAD Impact (low_cost_robot)", intro)
    print(json.dumps({**res, "delta": d}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
