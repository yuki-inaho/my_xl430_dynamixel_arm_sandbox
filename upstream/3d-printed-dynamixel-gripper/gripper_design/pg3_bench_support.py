"""Removable nut support for bench fastening; never installed in the arm."""

import itertools
import math

import cadquery as cq

from scripts.assembly_io import bounds
from scripts.review_pg3_pivot_stacks import pick, profiles


def to_world(shape, frame):
    return shape.rotate((0, 0, 0), (1, 1, 1), 120).translate(frame["origin_world_mm"])


def to_print(shape, frame):
    return shape.translate(tuple(-v for v in frame["origin_world_mm"])).rotate(
        (0, 0, 0), (1, 1, 1), -120
    )


def build_support(shapes, *, post_radius_mm=1.9, tip_radius_mm=1.2):
    if (
        not all(math.isfinite(v) for v in (post_radius_mm, tip_radius_mm))
        or not 0 < tip_radius_mm < post_radius_mm
    ):
        raise ValueError("finite positive annular post dimensions required")
    seats = {}
    for kind in ("drive", "carriage"):
        for side in ("R", "L"):
            name = f"PG3_pivot_{kind}_{side}_nut"
            nut = pick(profiles(shapes[name]), 1, "concave")
            bolt_name = name.removesuffix("_nut") + "_bolt"
            bolt = pick(profiles(shapes[bolt_name]), 1, "convex")
            if math.dist(nut["axis_yz_mm"], bolt["axis_yz_mm"]) > 1e-6:
                raise ValueError("nut/bolt axes must match saved assembly")
            if tip_radius_mm <= bolt["radius_mm"]:
                raise ValueError("positive screw-tip radial clearance required")
            seats[name] = {
                "axis_yz_mm": nut["axis_yz_mm"],
                "nut_back_x_mm": nut["span_x_mm"][0],
                "bolt_name": bolt_name,
                "bolt_tip_x_mm": bolt["span_x_mm"][0],
                "tip_radial_clearance_mm": tip_radius_mm - bolt["radius_mm"],
            }
    for a, b in itertools.combinations(seats.values(), 2):
        if math.dist(a["axis_yz_mm"], b["axis_yz_mm"]) <= 2 * post_radius_mm:
            raise ValueError("support posts must not merge or duplicate an axis")
    centre = [sum(r["axis_yz_mm"][i] for r in seats.values()) / 4 for i in (0, 1)]
    host_min = min(bounds(shapes[n])[0] for n in ("PG3_crank", "PG3_carriage_R", "PG3_carriage_L"))
    thickness, gap, width, depth = 3.0, 0.3, 48.0, 60.0
    base_high = host_min - gap
    frame = {
        "origin_world_mm": [base_high - thickness, *centre],
        "axis_map": "print (x,y,z) -> world (y,z,x); right-handed +120deg about (1,1,1)",
    }
    body = cq.Solid.makeBox(width, depth, thickness, (-width / 2, -depth / 2, 0))
    for row in seats.values():
        x, y = (row["axis_yz_mm"][i] - centre[i] for i in (0, 1))
        if abs(x) + post_radius_mm >= width / 2 or abs(y) + post_radius_mm >= depth / 2:
            raise ValueError("complete post must be inside base footprint")
        height = row["nut_back_x_mm"] - base_high
        if height <= 0:
            raise ValueError("nut seats must be ahead of the base")
        row.update(
            print_xy_mm=[x, y], post_height_mm=height, post_top_print_z_mm=thickness + height
        )
        body = body.fuse(cq.Solid.makeCylinder(post_radius_mm, height, (x, y, thickness)))
    for row in seats.values():
        x, y = row["print_xy_mm"]
        body = body.cut(
            cq.Solid.makeCylinder(tip_radius_mm, row["post_top_print_z_mm"] + 2, (x, y, -1))
        )
    if not body.isValid() or len(body.Solids()) != 1 or body.Volume() <= 0:
        raise ValueError("one valid connected support solid required")
    return {
        "print_shape": body,
        "world_shape": to_world(body, frame),
        "frame": frame,
        "seats": seats,
        "dimensions": {
            "base_width_mm": width,
            "base_depth_mm": depth,
            "base_thickness_mm": thickness,
            "base_to_host_gap_mm": gap,
            "post_outer_radius_mm": post_radius_mm,
            "tip_hole_radius_mm": tip_radius_mm,
            "post_wall_mm": post_radius_mm - tip_radius_mm,
        },
        "installation_approved": False,
        "print_release_approved": False,
    }
