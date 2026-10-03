"""Local, source-preserving changes for the PG3 installation workstream.

No fabrication approval is implied. Coordinates use the frozen R3 arm frame, mm.
The distal finger has no fastening holes. Bottom mounting hole centres/seats
are retained; only their diameter changes to clear the case tapping screws.
Upstream horn axes/diameters and the motor seat are unchanged. One rear
counterbore opens an originally blind lower hole and provides a full screw seat.
"""

import math

import cadquery as cq
from cadre.probes import cylinder_surface_sense
from OCP.BRepAdaptor import BRepAdaptor_Surface

from camera_jig.build import CAMERA_LOC, box, build_parts, donor_parts, drill_y, envelope_hardware
from camera_jig.serviceability import tools
from camera_jig.spec import SPEC
from gripper_design.build import _source_rows
from gripper_design.pg3 import arm_assembly, to_arm
from gripper_design.pg3_crank_representation import build_candidate as build_crank
from scripts.assembly_io import bounds

DISTAL_END_Y = 240.9
OUTBOARD_EDGE_X = 16.3
SIDE_CAMERA_ORIGIN = (52.0, 53.0, 164.6)
SIDE_CAMERA_LOC = cq.Location(SIDE_CAMERA_ORIGIN, (1, 0, 0), -90)
SIDE_OPTICAL_PROXY_MM = (SIDE_CAMERA_ORIGIN[0], SIDE_CAMERA_ORIGIN[1] + 32, SIDE_CAMERA_ORIGIN[2])
CASE_HOLES = tuple((x, y) for x in (-6.2, 5.8) for y in (206.9, 230.9))
CASE_CLEARANCE_DIAMETER = 2.8
HORN_HOLES = ((-8.2, 164.6), (-0.2, 156.6), (-0.2, 172.6), (7.8, 164.6))


def frame_change_mask():
    """Four guide end-land strips, in PG3 construction coordinates (mm)."""
    return cq.Compound.makeCompound(
        [cq.Solid.makeBox(2, 0.3, 4.6, (x, y, 19.5)) for x in (-46, 44) for y in (-18.8, 18.5)]
    )


def frame_candidate(original):
    """Relieve end-land running contact without altering bores or main rails."""
    shape = original.cut(frame_change_mask())
    if not shape.isValid() or len(shape.Solids()) != 1 or shape.Volume() <= 0:
        raise ValueError("frame relief disconnected or invalid")
    return shape


def original_support():
    return next(r.world for r in _source_rows() if r.name == "P06_fixed_gripper_XL430")


def support_change_mask():
    distal = cq.Solid.makeBox(100, 100, 100, (-50, DISTAL_END_Y, 120))
    edge = cq.Solid.makeBox(100, 150, 100, (OUTBOARD_EDGE_X, 180, 120))
    bores = [
        cq.Solid.makeCylinder(CASE_CLEARANCE_DIAMETER / 2, 4, (x, y, 146.35)) for x, y in CASE_HOLES
    ]
    lower_horn_seat = cq.Solid.makeCylinder(2.4, 4.1, (-0.2, 187.9, 156.6), (0, 1, 0))
    return distal.fuse(edge, lower_horn_seat, *bores)


def support_candidate():
    shape = original_support().cut(support_change_mask()).clean()
    if not shape.isValid() or len(shape.Solids()) != 1 or shape.Volume() <= 0:
        raise ValueError("local support change disconnected or invalid")
    return shape


def move_camera_part(shape):
    return shape.moved(CAMERA_LOC.inverse).rotate((0, 0, 0), (0, 0, 1), 180).moved(SIDE_CAMERA_LOC)


def side_camera_parts():
    """Rear-set bracket, unmodified P05 clamp interfaces and 28 mm camera pitch."""
    old = build_parts()
    saddle_spec, stop_spec = SPEC.clamp["saddle"], SPEC.clamp["top_stop"]
    saddle = box(*saddle_spec["size_mm"], *saddle_spec["origin_mm"])
    stop = box(*stop_spec["size_mm"], *stop_spec["origin_mm"])
    back_y = SIDE_CAMERA_ORIGIN[1] - 4
    bridge = box(32, 140.4 - back_y, 6, 26, back_y, 193.6)
    tab = box(12, 4, 12, 46, back_y, 183.6)
    # Tie the side arm into the full clamp top instead of only its thin corner.
    # This broadens the load path; it is not a PLA strength/creep qualification.
    root_roof = box(81.2, 13.75, 6, -23.2, 130.4, 196.6)
    saddle = saddle.fuse(stop, bridge, tab, root_roof)
    for x in SPEC.clamp["clamp_bores"]["center_x_mm"]:
        saddle = drill_y(saddle, 3.4, x, 188.6)
    for x in (48, 56):
        saddle = saddle.cut(cq.Solid.makeCylinder(1.2, 12, (x, back_y - 4, 188.6), (0, 1, 0)))
    carrier = move_camera_part(old["camera_carrier"])
    # The left tie ear would occupy the existing right-hand M3 clamp screw.
    # Retain the entire camera frame/tab and the right tie anchor instead.
    carrier = carrier.cut(box(50, 60, 80, -17, SIDE_CAMERA_ORIGIN[1] - 18, 130))
    parts = {
        "saddle": saddle.clean(),
        "front_jaw": old["front_jaw"],
        "camera_carrier": carrier.clean(),
        "camera_spacer": move_camera_part(old["camera_spacer"]),
    }
    for name, shape in parts.items():
        if not shape.isValid() or len(shape.Solids()) != 1:
            raise ValueError(f"invalid side-camera part: {name}")
    return parts


def side_camera_assembly():
    shapes = {f"CAMERA_{name}": shape for name, shape in side_camera_parts().items()}
    for name, shape in envelope_hardware().items():
        shapes[f"CAMERA_HW_{name}"] = shape if name.startswith("M3") else move_camera_part(shape)
    _, raw_camera = donor_parts()
    local = raw_camera.rotate((0, 0, 0), (1, 0, 0), -90).translate((0, 0, 5))
    shapes["CAMERA_REFERENCE_UNCONFIRMED"] = local.rotate((0, 0, 0), (0, 0, 1), 180).moved(
        SIDE_CAMERA_LOC
    )
    return shapes


def camera_tools(*, short_clamp_driver=True):
    """Nominal procurement envelopes; no claim of a measured purchased tool.

    Camera M2 screws are tightened on the bench. The M3 clamp can be released
    on-arm using a 25 mm exposed shaft plus a 25 mm, diameter 20 mm handle.
    """
    result = {
        name: shape if name.startswith("M3") else move_camera_part(shape)
        for name, shape in tools().items()
    }
    if short_clamp_driver:
        for i, x in enumerate(SPEC.clamp["clamp_bores"]["center_x_mm"]):
            shaft = cq.Solid.makeCylinder(2.5, 25, (x, 149.9, 188.6), (0, 1, 0))
            handle = cq.Solid.makeCylinder(10, 25, (x, 174.9, 188.6), (0, 1, 0))
            result[f"M3_{i}_head"] = shaft.fuse(handle)
        # The rear-set camera bridge occupies the old nut-driver handle region.
        # Keep the narrow socket shaft under it and put the handle behind it.
        x = SPEC.clamp["clamp_bores"]["center_x_mm"][1]
        socket = cq.Solid.makeCylinder(4.5, 100, (x, 134.5, 188.6), (0, -1, 0)).cut(
            cq.Solid.makeCylinder(1.7, 6, (x, 134.5, 188.6), (0, -1, 0))
        )
        handle = cq.Solid.makeCylinder(10, 30, (x, 34.5, 188.6), (0, -1, 0))
        result["M3_1_nut"] = socket.fuse(handle)
    return result


def support_hardware():
    """S14 tapper + 0.5 mm washer candidate; thread envelope is not a thread solid."""
    shapes = {}
    for i, (x, y) in enumerate(CASE_HOLES):
        # Four mm PLA plus 0.5 mm washer: 8 - 4 - 0.5 = 3.5 mm into case.
        shank = cq.Solid.makeCylinder(1.3, 8, (x, y, 145.85), (0, 0, 1))
        head = cq.Solid.makeCylinder(2.75, 2.5, (x, y, 143.35), (0, 0, 1))
        washer = cq.Solid.makeCylinder(3.5, 0.5, (x, y, 145.85)).cut(
            cq.Solid.makeCylinder(1.4, 0.5, (x, y, 145.85))
        )
        shapes[f"ARM_P06_case_tapper_{i}_ENVELOPE"] = shank.fuse(head)
        shapes[f"ARM_P06_case_washer_{i}_ENVELOPE"] = washer
    return shapes


def _outer_planar_seat(shape, axis, sign, transverse_points):
    """Select an outward plane spanning the mount pattern, not a bore's end."""
    other = [i for i in range(3) if i != axis]
    candidates = []
    for index, face in enumerate(shape.Faces()):
        if face.geomType() != "PLANE" or face.normalAt().toTuple()[axis] * sign < 1 - 1e-8:
            continue
        bb = bounds(face)
        if all(
            all(bb[j] - 1e-6 <= point[k] <= bb[j + 3] + 1e-6 for k, j in enumerate(other))
            for point in transverse_points
        ):
            candidates.append(
                {
                    "face": index,
                    "coordinate_mm": face.Center().toTuple()[axis],
                    "area_mm2": face.Area(),
                }
            )
    if not candidates:
        raise ValueError("no outward planar seat spanning the mounting pattern")
    return max(candidates, key=lambda p: sign * p["coordinate_mm"])


def case_attachment_report(motor, *, screw_length=8.0, washer_thickness=0.5):
    """Nominal M06/P06 fit, with actual concave pilot-hole faces as evidence.

    The selected 3 mm minimum engagement is a design target, not a pull-out
    strength claim. Drawing limit: 4 mm from the case seating plane at Z150.35.
    """
    pilot_faces = []
    for index, face in enumerate(motor.Faces()):
        if face.geomType() != "CYLINDER" or cylinder_surface_sense(face) != "concave":
            continue
        cylinder = BRepAdaptor_Surface(face.wrapped).Cylinder()
        axis, p = cylinder.Axis().Direction(), cylinder.Location()
        bb = bounds(face)
        if abs(axis.Z()) > 1 - 1e-8 and abs(cylinder.Radius() - 1.05) < 1e-6 and bb[5] < 160:
            pilot_faces.append(
                {
                    "face": index,
                    "axis_xy_mm": [p.X(), p.Y()],
                    "cylindrical_span_z_mm": [bb[2], bb[5]],
                }
            )
    rows = []
    tip_z = 146.35 - washer_thickness + screw_length
    for x, y in CASE_HOLES:
        if not pilot_faces:
            raise ValueError("no actual case pilot bores found")
        matched = min(pilot_faces, key=lambda f: math.dist((x, y), f["axis_xy_mm"]))
        rows.append(
            {
                "support_axis_xy_mm": [x, y],
                **matched,
                "axis_error_mm": math.dist((x, y), matched["axis_xy_mm"]),
                "tip_to_bottom_mm": matched["cylindrical_span_z_mm"][1] - tip_z,
            }
        )
    error = max(r["axis_error_mm"] for r in rows)
    margin = min(r["tip_to_bottom_mm"] for r in rows)
    engagement = screw_length - 4 - washer_thickness
    seat = _outer_planar_seat(motor, 2, -1, CASE_HOLES)
    seat_error = abs(seat["coordinate_mm"] - 150.35)
    passed = (
        len(pilot_faces) == 4
        and error < 1e-6
        and margin >= 0.5 - 1e-6
        and 3 <= engagement <= 3.5
        and math.isfinite(engagement)
        and seat_error < 1e-6
    )
    return {
        "nominal_geometry_pass": passed,
        "bores": rows,
        "max_axis_error_mm": error,
        "minimum_tip_to_bottom_mm": margin,
        "nominal_engagement_mm": engagement,
        "target_minimum_engagement_mm": 3,
        "case_seat_z_mm": 150.35,
        "actual_case_seat": seat,
        "seat_gap_mm": seat_error,
        "support_thickness_mm": 4,
        "screw_length_mm": screw_length,
        "washer_thickness_mm": washer_thickness,
        "thread_form_approved": False,
        "pullout_strength_verified": False,
        "actual_fasteners_verified": False,
    }


def horn_attachment_report(motor, support, *, length_adjustment=0.0):
    """Compare actual M05 tapped bores and the preserved P06 clearance bores."""

    def bores(shape, radius, front_minimum):
        result = []
        for index, face in enumerate(shape.Faces()):
            if face.geomType() != "CYLINDER" or cylinder_surface_sense(face) != "concave":
                continue
            cylinder = BRepAdaptor_Surface(face.wrapped).Cylinder()
            axis, p = cylinder.Axis().Direction(), cylinder.Location()
            bb = bounds(face)
            if (
                abs(axis.Y()) > 1 - 1e-8
                and abs(cylinder.Radius() - radius) < 1e-6
                and bb[4] > front_minimum
            ):
                result.append(
                    {"face": index, "axis_xz_mm": [p.X(), p.Z()], "span_y_mm": [bb[1], bb[4]]}
                )
        return result

    holes = bores(support, 1.2, 187)
    seat = _outer_planar_seat(motor, 1, 1, HORN_HOLES)
    threads = bores(motor, 1.0, seat["coordinate_mm"] - 0.9)
    if len(holes) != 4 or len(threads) != 4:
        raise ValueError("expected four actual support and horn bores")
    rows = []
    for x, z in HORN_HOLES:
        hole = min(holes, key=lambda h: math.dist((x, z), h["axis_xz_mm"]))
        thread = min(threads, key=lambda h: math.dist((x, z), h["axis_xz_mm"]))
        inner, outer = hole["span_y_mm"]
        thickness = outer - inner
        # The local lower counterbore restores a full seat at the same Y187.9.
        length = 8 + length_adjustment
        tip = outer + 1 - length
        rows.append(
            {
                "axis_xz_mm": [x, z],
                "support_face": hole["face"],
                "horn_face": thread["face"],
                "support_span_y_mm": hole["span_y_mm"],
                "horn_cylindrical_span_y_mm": thread["span_y_mm"],
                "axis_error_mm": max(
                    math.dist((x, z), hole["axis_xz_mm"]),
                    math.dist(hole["axis_xz_mm"], thread["axis_xz_mm"]),
                ),
                "support_thickness_mm": thickness,
                "seat_gap_mm": abs(inner - seat["coordinate_mm"]),
                "spacer_thickness_mm": 1,
                "spacer_outer_diameter_mm": 4.3 if z == 156.6 else 5.0,
                "screw_length_mm": length,
                "head_seat_y_mm": outer + 1,
                "nominal_engagement_mm": length - thickness - 1,
                "tip_to_bottom_mm": tip - thread["span_y_mm"][0],
            }
        )
    for row in rows:
        bolt, spacer = _horn_shapes(row)
        row["bolt_support_intersection_mm3"] = support.intersect(bolt).Volume()
        row["spacer_support_intersection_mm3"] = support.intersect(spacer).Volume()
        row["bearing_area_mm2"] = support.intersect(spacer.translate((0, -0.01, 0))).Volume() / 0.01
        row["expected_bearing_area_mm2"] = math.pi * (
            (row["spacer_outer_diameter_mm"] / 2) ** 2 - 1.2**2
        )
    passed = all(
        r["axis_error_mm"] < 1e-6
        and abs(r["nominal_engagement_mm"] - 3) < 1e-6
        and r["tip_to_bottom_mm"] >= 0.5 - 1e-6
        and r["seat_gap_mm"] < 1e-6
        and r["bolt_support_intersection_mm3"] < 1e-5
        and r["spacer_support_intersection_mm3"] < 1e-5
        and abs(r["bearing_area_mm2"] - r["expected_bearing_area_mm2"]) < 1e-4
        for r in rows
    )
    return {
        "nominal_geometry_pass": passed,
        "bores": rows,
        "actual_horn_seat": seat,
        "actual_fasteners_verified": False,
        "strength_verified": False,
    }


def _horn_shapes(row):
    x, z = row["axis_xz_mm"]
    seat, length = row["head_seat_y_mm"], row["screw_length_mm"]
    shank = cq.Solid.makeCylinder(1, length, (x, seat, z), (0, -1, 0))
    head = cq.Solid.makeCylinder(1.9, 2, (x, seat, z), (0, 1, 0))
    spacer = cq.Solid.makeCylinder(
        row["spacer_outer_diameter_mm"] / 2, 1, (x, seat - 1, z), (0, 1, 0)
    ).cut(cq.Solid.makeCylinder(1.1, 1, (x, seat - 1, z), (0, 1, 0)))
    return shank.fuse(head), spacer


def horn_hardware():
    motor = next(r.world for r in _source_rows() if r.name == "M05_ref00")
    report = horn_attachment_report(motor, support_candidate())
    if not report["nominal_geometry_pass"]:
        raise ValueError("horn fastening geometry is not consistent")
    shapes = {}
    for i, row in enumerate(report["bores"]):
        bolt, spacer = _horn_shapes(row)
        shapes[f"ARM_P06_horn_bolt_{i}_ENVELOPE"] = bolt
        shapes[f"ARM_P06_horn_spacer_{i}_ENVELOPE"] = spacer
    return shapes


def support_tools():
    """Straight driver envelopes, case screws on-arm and horn screws before M06."""
    motor = next(r.world for r in _source_rows() if r.name == "M05_ref00")
    result = {}
    for i, row in enumerate(horn_attachment_report(motor, support_candidate())["bores"]):
        x, z = row["axis_xz_mm"]
        y = row["head_seat_y_mm"] + 2.1
        shaft = cq.Solid.makeCylinder(1.5, 75, (x, y, z), (0, 1, 0))
        handle = cq.Solid.makeCylinder(10, 30, (x, y + 75, z), (0, 1, 0))
        result[f"HORN_{i}"] = shaft.fuse(handle)
    for i, (x, y) in enumerate(CASE_HOLES):
        shaft = cq.Solid.makeCylinder(2.5, 75, (x, y, 143.25), (0, 0, -1))
        handle = cq.Solid.makeCylinder(10, 30, (x, y, 68.25), (0, 0, -1))
        result[f"CASE_{i}"] = shaft.fuse(handle)
    return result


def installed_assembly(model, angle):
    shapes = {
        n: s
        for n, s in arm_assembly(model, angle).items()
        if not n.startswith("CAMERA_") and n != "ARM_P06_fixed_gripper_XL430"
    }
    shapes["ARM_P06_PG3_support"] = support_candidate()
    shapes["PG3_frame"] = to_arm(frame_candidate(model.neutral["frame"]))
    shapes["PG3_crank"] = to_arm(build_crank().rotate((0, 0, 0), (0, 0, 1), angle))
    shapes.update(support_hardware())
    shapes.update(horn_hardware())
    shapes.update(side_camera_assembly())
    return shapes
