"""Survey arm link-to-servo fastener sites from coaxial bores (no screws are modeled).

For every link ARM_P0*, concave cylinders are matched to concave cylinders of the
servo occurrences (ARM_M0*_ref*, and PG3_XL430_fixed for the ID5 case) when the
axes coincide. Each match is one fastening site. The report lists the servo bore
diameter, link bore diameter, axis, side of the servo centre and the link bore
length. It counts sites only: thread identity, usable depth, screw length and
tool access are not established by coaxial cylinders.
"""

import argparse
import json
import re
from collections import Counter
from pathlib import Path

import numpy as np
from cadre.probes import cylinder_surface_sense
from OCP.BRepAdaptor import BRepAdaptor_Surface

from scripts.assembly_io import bounds
from scripts.step_cache import read_rows

DEFAULT_ASSEMBLY = Path("outputs/camera-mount-id5-overhead-d405-r5/CAD/ID5_D405_mid_ASSEMBLY.step")


def concave_bores(shape, radius_min, radius_max):
    found = []
    for face in shape.Faces():
        if face.geomType() != "CYLINDER":
            continue
        cylinder = BRepAdaptor_Surface(face.wrapped).Cylinder()
        if not radius_min <= cylinder.Radius() <= radius_max:
            continue
        if cylinder_surface_sense(face) != "concave":
            continue
        axis = cylinder.Axis()
        direction = np.array([axis.Direction().X(), axis.Direction().Y(), axis.Direction().Z()])
        point = np.array([axis.Location().X(), axis.Location().Y(), axis.Location().Z()])
        box = bounds(face)
        span = sorted(float(np.array(corner) @ direction) for corner in (box[:3], box[3:]))
        found.append({"radius": cylinder.Radius(), "dir": direction, "point": point, "span": span})
    return found


def coaxial(first, second, tolerance_mm=0.05):
    if abs(abs(first["dir"] @ second["dir"]) - 1) > 1e-4:
        return False
    offset = second["point"] - first["point"]
    return np.linalg.norm(offset - (offset @ first["dir"]) * first["dir"]) < tolerance_mm


def survey(path):
    shapes = {row.name: row.world for row in read_rows(path)}
    servo_bores, centres = {}, {}
    for name, shape in shapes.items():
        match = re.match(r"ARM_(M0\d)_ref(\d+)$", name)
        servo = match.group(1) if match else ("M05" if name == "PG3_XL430_fixed" else None)
        if servo is None:
            continue
        servo_bores.setdefault(servo, []).extend(concave_bores(shape, 0.8, 1.7))
        if name.endswith("ref00") or name == "PG3_XL430_fixed":
            box = bounds(shape)
            centres[servo] = (np.array(box[:3]) + np.array(box[3:])) / 2
    report = []
    for link, shape in sorted((n, s) for n, s in shapes.items() if re.match(r"ARM_P0\d", n)):
        bores = concave_bores(shape, 0.8, 3.5)
        used, sites = set(), Counter()
        for servo, candidates in sorted(servo_bores.items()):
            for index, bore in enumerate(bores):
                if index in used:
                    continue
                partner = next((c for c in candidates if coaxial(bore, c)), None)
                if partner is None:
                    continue
                used.add(index)
                middle = bore["point"] + bore["dir"] * (
                    sum(bore["span"]) / 2 - bore["point"] @ bore["dir"]
                )
                side = int(np.sign((middle - centres[servo]) @ bore["dir"]))
                key = (
                    servo,
                    round(2 * partner["radius"], 2),
                    round(2 * bore["radius"], 2),
                    "XYZ"[int(np.argmax(np.abs(bore["dir"])))],
                    side,
                    round(bore["span"][1] - bore["span"][0], 2),
                )
                sites[key] += 1
        unmatched = Counter(
            (round(2 * b["radius"], 2), "XYZ"[int(np.argmax(np.abs(b["dir"])))])
            for i, b in enumerate(bores)
            if i not in used
        )
        report.append(
            {
                "link": link,
                "sites": [
                    {
                        "servo": k[0],
                        "servo_bore_d_mm": k[1],
                        "link_bore_d_mm": k[2],
                        "axis": k[3],
                        "side": k[4],
                        "link_bore_length_mm": k[5],
                        "count": n,
                    }
                    for k, n in sorted(sites.items())
                ],
                "unmatched_bores": [
                    {"d_mm": d, "axis": a, "count": n} for (d, a), n in sorted(unmatched.items())
                ],
            }
        )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("assembly", nargs="?", type=Path, default=DEFAULT_ASSEMBLY)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    report = survey(args.assembly)
    for row in report:
        print(row["link"])
        for s in row["sites"]:
            print(
                f"  {s['servo']:4s} servo d{s['servo_bore_d_mm']:<4} link d{s['link_bore_d_mm']:<4}"
                f" axis {s['axis']} side {s['side']:+d} length {s['link_bore_length_mm']:<5} x{s['count']}"
            )
        for u in row["unmatched_bores"]:
            print(f"  unmatched d{u['d_mm']} axis {u['axis']} x{u['count']}")
    if args.out:
        args.out.write_text(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
