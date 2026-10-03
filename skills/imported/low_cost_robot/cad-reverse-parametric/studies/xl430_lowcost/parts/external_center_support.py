"""Nominal external support candidate, not approved hardware or print geometry.

The metal tube carries the nominal bolt compression. The PLA guide is outside
that axial stack. This changes the old internal thrust-flange arrangement;
load capacity, stock parts, threads, torque and tolerances remain unresolved.
"""
import math

import cadquery as cq


def _positive(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError("candidate dimensions must be finite and positive")
    return float(value)


def make_parts(config):
    return _build(config, 0.)


def make_insertion_sweeps(config, travel_mm):
    """Exact union of each candidate translated through [0, travel] along +X.

    Each constituent is an X extrusion of a fixed circular/annular section.
    Translation sweep distributes over their union and extends each interval.
    This does not support reverse directions, rotations or arbitrary CAD.
    """
    return _build(config, _positive(travel_mm))[0]


def _build(config, sweep_mm):
    y, z = config["axis_yz_mm"]
    seat = config["motor_seat_x_mm"]
    tube, guide, washer, bolt = (config[k] for k in ("tube", "guide", "washer", "bolt"))

    def ring(x, length, od, bore):
        length, od, bore = map(_positive, (length, od, bore))
        if bore >= od:
            raise ValueError("ring bore must be smaller than its outside diameter")
        return (cq.Workplane("YZ").circle(od/2).circle(bore/2).extrude(length+sweep_mm)
                .val().translate((x, y, z)))

    end = seat + _positive(tube["length_mm"])
    guide_flange_x = guide["inner_x_mm"] + _positive(guide["pilot_length_mm"])
    head_x = end + _positive(washer["thickness_mm"])
    tip_x = head_x - _positive(bolt["length_mm"])
    shaft = cq.Solid.makeCylinder(_positive(bolt["nominal_diameter_mm"])/2,
                                 bolt["length_mm"]+sweep_mm, cq.Vector(tip_x, y, z), cq.Vector(1,0,0))
    head = cq.Solid.makeCylinder(_positive(bolt["head_diameter_mm"])/2,
                                _positive(bolt["head_height_mm"])+sweep_mm,
                                cq.Vector(head_x, y, z), cq.Vector(1,0,0))
    parts = {
        "tube": ring(seat, tube["length_mm"], tube["outer_diameter_mm"], tube["inner_diameter_mm"]),
        "guide": ring(guide["inner_x_mm"], guide["pilot_length_mm"], guide["pilot_diameter_mm"],
                      guide["bore_diameter_mm"]).fuse(
                      ring(guide_flange_x, guide["flange_thickness_mm"], guide["flange_diameter_mm"],
                           guide["bore_diameter_mm"])),
        "washer": ring(end, washer["thickness_mm"], washer["outer_diameter_mm"], washer["inner_diameter_mm"]),
        "bolt": shaft.fuse(head),
    }
    stack = {
        "status": "nominal_geometry_only",
        "washer_to_guide_axial_gap_mm": end-guide_flange_x-guide["flange_thickness_mm"],
        "tube_to_guide_radial_gap_mm": (guide["bore_diameter_mm"]-tube["outer_diameter_mm"])/2,
        "bolt_tip_x_mm": tip_x,
        "modeled_bore_overlap_NOT_thread_engagement_mm": seat-tip_x,
        "modeled_bottom_gap_mm": tip_x-config["motor_modeled_bore_bottom_x_mm"],
        "thread_engagement_verified": False,
        "preload_and_tolerances_verified": False,
        "bolt_drive_modeled": False,
    }
    return parts, stack
