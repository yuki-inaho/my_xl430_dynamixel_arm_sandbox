"""ID5 overhead camera mount R5: RealSense D405 carrier on a fixed-angle base.

Derived from the R4-C2 two-part concept (motor-top four-hole base + swappable
carrier, ``camera_overhead_r4``) but re-solved for a D405:

* D405 datum from the RealSense D400 datasheet 337029-017: 42x42x23 mm body,
  rear 2x M3x0.5 at 20.00 mm pitch with 4.0 mm maximum insertion, depth origin
  3.7 mm behind the front glass, left imager 9 mm from the 1/4-20 centreline,
  depth FOV H84/V58, Min-Z 70 mm at 848x480 and 100 mm at 1280x720, 58 g.
* The rear-hole vertical position is not dimensioned in the drawing; the holes
  are slotted +/-1 mm along the image-up axis instead of guessing a value.
* Pitch is the optical-axis angle below the gripper approach axis (+Y).
  Robonine SO-ARM101 holders measure 30 deg; that angle cannot see the PG3 pads
  over the PG3 frame/cap, so R5 uses 65 deg (5-degree grid, user-selected rule).

Units mm, world frame of the supplied arm (X right, Y gripper forward, Z up).
All camera/cable/fastener bodies are nominal envelopes, not purchased parts.
"""
import math
from dataclasses import asdict, dataclass

import cadquery as cq
import numpy as np

from gripper_design.camera_overhead_r4 import (
    ANCHORS,
    INPUT,
    ORIGIN,
    ROOT,
    TOP,
    bolt_z,
    box,
    cut_many,
    cylinder,
    hexagon,
    nut_z,
    opening_mm,
    retained_at,
    ring,
    screw_stack,
)

RUN = ROOT / 'outputs/camera-mount-id5-overhead-d405-r5'

# RealSense D400 datasheet 337029-017 (Table 3-49/3-54/4-11/4-16/4-21, Fig. 10-13).
D405 = {
    'body_mm': (42.0, 42.0, 23.0),
    'rear_m3_pitch_mm': 20.0,
    'rear_m3_max_insert_mm': 4.0,
    'rear_m3_vertical_offset_mm': None,  # not dimensioned; slotted +/-1 mm
    'mass_g': 58.0,
    'mass_tolerance': 0.10,
    'baseline_mm': 18.0,
    'left_imager_from_tripod_centreline_mm': 9.0,
    'depth_origin_behind_glass_mm': 3.7,
    'depth_fov_deg': {'H': 84.0, 'V': 58.0},
    'min_z_mm': {'848x480': 70.0, '1280x720': 100.0},
    'usb_connector': 'USB 3 Micro-B on a lateral face (datasheet 3.7.6)',
    'usb_centre_from_rear_mm': 6.82,
}
ROBONINE_PITCH_DEG = 30.0  # measured from RB9.01.062.000 Gripper.STEP lens axis


@dataclass(frozen=True)
class Spec:
    revision: str = 'ID5-CAM-R5-D405-P65'
    motor: str = 'XL430-W250-T'
    parent: str = 'fixed_case_external_top_holes'
    extra_motor_count: int = 0
    camera: str = 'Intel RealSense D405 (nominal datasheet envelope)'
    pitch_deg: float = 65.0
    glass_center: tuple = (-0.2, 197.0, 257.0)
    plate_thickness: float = 4.0
    plate_half_width: float = 31.5
    plate_v_range: tuple = (-29.0, 25.0)
    cheek_inner_x: float = 22.5
    cheek_thickness: float = 8.0
    cheek_attach_v: tuple = (-27.0, -11.0)
    tie_bolt_local: tuple = (26.5, -19.0)
    d405_screw_length: float = 6.0
    d405_counterbore_depth: float = 1.0
    d405_slot_half_travel: float = 1.0
    base_seat_thickness: float = 2.0
    base_screw_length: float = 5.0
    hole_depth: float = 4.0
    usb_plug_side: int = -1  # upright D405: connector on world -X
    structural_mass_rating_kg: object = None


def validate_spec(s):
    if s.motor != 'XL430-W250-T' or s.parent != 'fixed_case_external_top_holes':
        raise ValueError('wrong motor or rotating/case-tie anchor')
    if s.extra_motor_count != 0:
        raise ValueError('single-ID5 contract')
    if not math.isfinite(s.pitch_deg) or s.pitch_deg % 5 or not 30 <= s.pitch_deg <= 80:
        raise ValueError('pitch must be a 5-degree multiple, looking forward/down')
    if not all(math.isfinite(x) for x in s.glass_center):
        raise ValueError('non-finite camera position')
    if s.cheek_inner_x - D405['body_mm'][0] / 2 < 1.0:
        raise ValueError('cheeks must clear the D405 side faces')
    if s.cheek_attach_v[1] > -10.0:
        raise ValueError('cheek attachment must stay below the lateral USB plug band')
    insertion = s.d405_screw_length - (s.plate_thickness - s.d405_counterbore_depth)
    if not 2.0 <= insertion <= D405['rear_m3_max_insert_mm'] - 0.5:
        raise ValueError('D405 M3 insertion outside 2.0..3.5 mm (datasheet max 4.0)')
    screw_stack(s.base_screw_length, s.base_seat_thickness, .5, s.hole_depth)


def basis(pitch_deg):
    """u = image right (X), v = image up, n = plate normal (away from camera)."""
    t = math.radians(pitch_deg)
    return (np.array((1., 0, 0)), np.array((0, math.sin(t), math.cos(t))),
            np.array((0, -math.cos(t), math.sin(t))))


def optical_direction(s):
    return -basis(s.pitch_deg)[2]


def plate_center(s):
    """Plate camera-side face (local z=0) touches the D405 rear face."""
    _, _, n = basis(s.pitch_deg)
    return np.array(s.glass_center) + D405['body_mm'][2] * n


def local_point(p, s):
    u, v, n = basis(s.pitch_deg)
    return plate_center(s) + u * p[0] + v * p[1] + n * p[2]


def local_to_world(shape, s):
    return shape.rotate((0, 0, 0), (1, 0, 0), 90 - s.pitch_deg).translate(tuple(plate_center(s)))


def world_to_local(p, s):
    u, v, n = basis(s.pitch_deg)
    r = np.asarray(p, float) - plate_center(s)
    return np.array((r @ u, r @ v, r @ n))


def foot_bounds(s):
    half = s.cheek_inner_x + s.cheek_thickness + 0.2
    return (-0.2 - half, -0.2 + half, 152.9, 176.9, TOP, TOP + 3)


def cheek_profile(s):
    """YZ polygon: foot top rear/front to the plate attachment band."""
    a = local_point((0, s.cheek_attach_v[0], 0), s)
    b = local_point((0, s.cheek_attach_v[1], 0), s)
    return [(154.9, TOP + 2.5), (176.9, TOP + 2.5), (float(b[1]), float(b[2])),
            (float(a[1]), float(a[2]))]


def base(s):
    """Foot on the four motor-top holes and two cheeks outside the D405 width."""
    x0, x1, y0, y1, z0, z1 = foot_bounds(s)
    b = cq.Workplane(obj=box(x0, x1, y0, y1, z0, z1)).edges('|Z').fillet(2).val()
    profile = cheek_profile(s)
    for sign in (-1, 1):
        inner = -0.2 + sign * s.cheek_inner_x
        start = inner if sign > 0 else inner - s.cheek_thickness
        pl = cq.Plane(origin=(start, 0, 0), xDir=(0, 1, 0), normal=(1, 0, 0))
        b = b.fuse(cq.Workplane(pl).polyline(profile).close().extrude(s.cheek_thickness).val())
    cutters = []
    for x, y, _ in ANCHORS:
        cutters += [cylinder(1.45, 6, (x, y, TOP - 1)),
                    cylinder(3.25, 4, (x, y, TOP + s.base_seat_thickness))]
    tx, tv = s.tie_bolt_local
    for sign in (-1, 1):
        x = -0.2 + sign * tx
        cutters.append(local_to_world(cylinder(1.65, 22, (x + 0.2, tv, -17)), s))
        cutters.append(local_to_world(hexagon(3.4, 2.7, (x + 0.2, tv, -6.8)), s))
        # Nut loading slot opens to the outer cheek face.
        a, bx = sorted((x + 0.2, x + 0.2 + sign * 6.0))
        cutters.append(local_to_world(box(a, bx, tv - 3.05, tv + 3.05, -6.8, -4.1), s))
    return cut_many(b, cutters)


def d405_carrier_local(s):
    """Flat plate: D405 rear face on z=0, fasteners inserted from z=+t."""
    t = s.plate_thickness
    v0, v1 = s.plate_v_range
    p = box(-s.plate_half_width, s.plate_half_width, v0, v1, 0, t)
    p = cq.Workplane(obj=p).edges('|Z').fillet(3).val()
    cutters = []
    half = D405['rear_m3_pitch_mm'] / 2
    for x in (-half, half):
        slot = cq.Workplane('XY').center(x, 0).slot2D(3.4 + 2 * s.d405_slot_half_travel, 3.4, 90)
        cutters.append(slot.extrude(t + 2).val().translate((0, 0, -1)))
        cb = cq.Workplane('XY').center(x, 0).slot2D(6.6 + 2 * s.d405_slot_half_travel, 6.6, 90)
        cutters.append(cb.extrude(s.d405_counterbore_depth + 1).val()
                       .translate((0, 0, t - s.d405_counterbore_depth)))
    tx, tv = s.tie_bolt_local
    for x in (-tx, tx):
        cutters.append(cylinder(1.7, t + 2, (x, tv, -1)))
    # 28x28 UVC pattern kept for a separately printed spacer (R4 compatibility).
    for x in (-14, 14):
        for y in (-14, 14):
            cutters.append(cylinder(1.2, t + 2, (x, y, -1)))
    return cut_many(p, cutters)


def d405_body_local(s):
    w, h, d = D405['body_mm']
    body = box(-w / 2, w / 2, -h / 2, h / 2, -d, 0)
    body = cq.Workplane(obj=body).edges('|Z').fillet(4).val()
    for x in (-D405['rear_m3_pitch_mm'] / 2, D405['rear_m3_pitch_mm'] / 2):
        body = body.cut(cylinder(1.25, D405['rear_m3_max_insert_mm'], (x, 0, -D405['rear_m3_max_insert_mm'])))
    return body.clean()


def usb_plug_local(s):
    side = s.usb_plug_side
    x0 = side * D405['body_mm'][0] / 2
    zc = -D405['usb_centre_from_rear_mm']
    a, b = sorted((x0, x0 + side * 26.0))
    return box(a, b, -8.5, 8.5, zc - 5.0, zc + 5.0)


def usb_cable_local(s, diameter=4.5):
    side = s.usb_plug_side
    x0 = side * (D405['body_mm'][0] / 2 + 26.0)
    zc = -D405['usb_centre_from_rear_mm']
    return cylinder(diameter / 2, 15.0, (x0, 0, zc), (side, 0, 0))


def build(s=None):
    s = s or Spec()
    validate_spec(s)
    p = {'CAM5_BASE': base(s), 'CAM5_D405_CARRIER': local_to_world(d405_carrier_local(s), s)}
    for i, (x, y, _) in enumerate(ANCHORS):
        p[f'CAM5_BASE_WASHER_{i}'] = ring(3, 1.4, .5, (x, y, TOP + s.base_seat_thickness))
        p[f'CAM5_BASE_TAP_{i}'] = bolt_z(2.6, s.base_screw_length, 2, 5.2,
                                         TOP + s.base_seat_thickness + .5, (x, y))
    t = s.plate_thickness
    tx, tv = s.tie_bolt_local
    for i, x in enumerate((-tx, tx)):
        p[f'CAM5_TIE_WASHER_{i}'] = local_to_world(ring(3.5, 1.7, .5, (x, tv, t)), s)
        p[f'CAM5_TIE_BOLT_{i}'] = local_to_world(bolt_z(3, 12, 3, 5.5, t + .5, (x, tv)), s)
        p[f'CAM5_TIE_NUT_{i}'] = local_to_world(nut_z(5.5, 2.4, 1.5, (x, tv, -6.5)), s)
    seat = t - s.d405_counterbore_depth
    for i, x in enumerate((-D405['rear_m3_pitch_mm'] / 2, D405['rear_m3_pitch_mm'] / 2)):
        p[f'CAM5_D405_SCREW_{i}'] = local_to_world(bolt_z(2.9, s.d405_screw_length, 3, 5.5, seat, (x, 0)), s)
    p['CAM5_D405_BODY'] = local_to_world(d405_body_local(s), s)
    p['CAM5_D405_USB_PLUG'] = local_to_world(usb_plug_local(s), s)
    p['CAM5_D405_USB_CABLE_STUB'] = local_to_world(usb_cable_local(s), s)
    return p


def imagers(s):
    """World positions of the two depth imagers' optical centres (left first)."""
    d = optical_direction(s)
    u = basis(s.pitch_deg)[0]
    origin = np.array(s.glass_center) - D405['depth_origin_behind_glass_mm'] * d
    half = D405['baseline_mm'] / 2
    # Looking along +Y with Z up, image right is +X, so the left imager is -X.
    return {'left': origin - u * half, 'right': origin + u * half}


def optical(s):
    d = optical_direction(s)
    u, v, _ = basis(s.pitch_deg)
    return {'imagers': {k: x.tolist() for k, x in imagers(s).items()}, 'direction': d.tolist(),
            'up': v.tolist(), 'right': u.tolist(), 'pitch_below_approach_deg': s.pitch_deg,
            'robonine_reference_pitch_deg': ROBONINE_PITCH_DEG,
            'reference': 'datasheet depth start/imager offsets; not calibrated intrinsics'}


def d405_stack(s):
    seat_to_rear = s.plate_thickness - s.d405_counterbore_depth
    insertion = s.d405_screw_length - seat_to_rear
    return {'screw': f'M3x{s.d405_screw_length:g} socket head', 'plate_under_head_mm': seat_to_rear,
            'insertion_mm': insertion, 'datasheet_max_insert_mm': D405['rear_m3_max_insert_mm'],
            'margin_to_max_mm': D405['rear_m3_max_insert_mm'] - insertion,
            'thread_engagement_verified_on_hardware': False}


def mass_properties(s, pla_density=1.24e-3):
    base_v = base(s).Volume()
    plate_v = d405_carrier_local(s).Volume()
    cam = D405['mass_g']
    return {'base_volume_mm3': base_v, 'carrier_volume_mm3': plate_v,
            'solid_pla_mass_g': (base_v + plate_v) * pla_density,
            'd405_mass_g': cam, 'd405_mass_range_g': [cam * 0.9, cam * 1.1],
            'note': 'solid-model PLA mass; printed mass depends on walls/infill'}


def metadata(s):
    return {'spec': asdict(s), 'd405_datasheet': D405, 'anchors_world_mm': ANCHORS,
            'optical': optical(s), 'plate_center_world_mm': plate_center(s).tolist(),
            'base_stack': screw_stack(s.base_screw_length, s.base_seat_thickness, .5, s.hole_depth),
            'd405_stack': d405_stack(s), 'mass': mass_properties(s),
            'physical_tests_performed': [], 'fabrication_approved': False,
            'printed_parts': ['CAM5_BASE', 'CAM5_D405_CARRIER']}


__all__ = [
    'D405',
    'INPUT',
    'ORIGIN',
    'RUN',
    'Spec',
    'base',
    'build',
    'cheek_profile',
    'd405_carrier_local',
    'imagers',
    'local_point',
    'metadata',
    'opening_mm',
    'optical',
    'plate_center',
    'retained_at',
    'validate_spec',
    'world_to_local',
]
