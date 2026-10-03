"""Does the R5 mount shrink the ID4 (wrist pitch) range? Sampled CAD diagnostic.

The ID4 axis is measured from the saved M04 horn geometry (largest X-axis
cylinder family on ARM_M04 leaves), not assumed. Everything downstream of ID4
(P05, M05, PG3, mount) rotates rigidly; upstream parts stay fixed.

From the saved pose (0 deg) the search walks outward in both directions and
stops at the first sampled collision, separately for (a) the existing arm
without the mount and (b) the mount parts. Pairs already in contact at 0 deg
(e.g. the coaxial ID4 horn/P05 interface) are recorded and excluded, never
blamed on the mount. Samples every 2 deg; not a continuous-sweep proof, and no
joint-limit source exists for ID4 in the supplied data.
"""
import json
from collections import Counter

import numpy as np

from gripper_design.camera_overhead_d405_r5 import RUN, Spec
from scripts.assembly_io import bounds, read_step
from scripts.validate_camera_overhead_r4 import box_distance, digest

STEP_DEG = 2.0
LIMIT_DEG = 180.0
GAP = 0.3
MOVING = ('ARM_P05', 'ARM_M05', 'PG3_', 'CAM5_')


def id4_axis(parts):
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    area = Counter()
    for n, s in parts.items():
        if not n.startswith('ARM_M04'):
            continue
        for f in s.Faces():
            if f.geomType() != 'CYLINDER':
                continue
            c = BRepAdaptor_Surface(f.wrapped).Cylinder()
            d = c.Axis().Direction()
            if abs(d.X()) > .999 and c.Radius() >= 4:
                p = c.Location()
                area[(round(p.Y(), 3), round(p.Z(), 3))] += f.Area()
    (y, z), _ = area.most_common(1)[0]
    return np.array((0.0, y, z)), np.array((1.0, 0, 0)), area.most_common(5)


def hits(group, upstream, ub, point, axis, deg, skip, near_is_hit):
    out = []
    for n, shape in group.items():
        moved = shape.rotate(tuple(point), tuple(point + axis), float(deg)) if deg else shape
        mb = bounds(moved)
        for m, b in ub.items():
            if (n, m) in skip or box_distance(mb, b) >= GAP:
                continue
            vol = abs(moved.intersect(upstream[m]).Volume())
            if vol > 1e-5:
                out.append({'moving': n, 'upstream': m, 'volume_mm3': vol})
            elif near_is_hit and moved.distance(upstream[m]) < GAP:
                out.append({'moving': n, 'upstream': m, 'gap_below_mm': GAP})
            if out:
                return out
    return out


def walk(group, upstream, ub, point, axis, skip, near_is_hit, sign):
    last = 0.0
    deg = sign * STEP_DEG
    while abs(deg) <= LIMIT_DEG:
        h = hits(group, upstream, ub, point, axis, deg, skip, near_is_hit)
        print('walk', sign, deg, len(h), flush=True)
        if h:
            return last, {'deg': deg, 'first_hit': h[0]}
        last = deg
        deg += sign * STEP_DEG
    return last, None


def run(s=None):
    s = s or Spec()
    path = RUN / 'CAD/ID5_D405_mid_ASSEMBLY.step'
    parts = {r.name: r.world for r in read_step(path)[2]}
    upstream = {n: v for n, v in parts.items() if not n.startswith(MOVING)}
    arm = {n: v for n, v in parts.items() if n.startswith(MOVING[:3])}
    mount = {n: v for n, v in parts.items() if n.startswith('CAM5_')}
    point, axis, candidates = id4_axis(parts)
    ub = {n: bounds(v) for n, v in upstream.items()}
    # Contacts already present in the saved pose are recorded, then skipped.
    existing = set()
    for n, shape in arm.items():
        sb = bounds(shape)
        for m, b in ub.items():
            if box_distance(sb, b) >= GAP:
                continue
            if abs(shape.intersect(upstream[m]).Volume()) > 1e-5 or shape.distance(upstream[m]) < 1e-3:
                existing.add((n, m))
    mount_at_zero = hits(mount, upstream, ub, point, axis, 0.0, set(), True)
    result = {}
    for label, group, skip, near in (('arm_only', arm, existing, False), ('mount', mount, set(), True)):
        lo, lo_hit = walk(group, upstream, ub, point, axis, skip, near, -1)
        hi, hi_hit = walk(group, upstream, ub, point, axis, skip, near, +1)
        result[label] = {'free_interval_deg': [lo, hi], 'negative_stop': lo_hit, 'positive_stop': hi_hit}
    a, m = result['arm_only']['free_interval_deg'], result['mount']['free_interval_deg']
    report = {'revision': s.revision, 'saved_mid_sha': digest(path), 'checker_sha': digest(__file__),
              'id4_axis_point_mm': point.tolist(), 'id4_axis_dir': axis.tolist(),
              'axis_candidates': [[list(k), v] for k, v in candidates], 'step_deg': STEP_DEG,
              'search_limit_deg': LIMIT_DEG, 'min_gap_mm_for_mount': GAP,
              'existing_contacts_at_saved_pose': sorted(existing), 'mount_hits_at_saved_pose': mount_at_zero,
              **result, 'mount_reduces_id4_range': bool(m[0] > a[0] or m[1] < a[1] or mount_at_zero),
              'sampled_not_continuous': True, 'id4_joint_limits_source': None}
    (RUN / 'reports/id4_sweep.json').write_text(json.dumps(report, indent=1, default=str))
    print('axis', point.tolist(), 'arm-only', a, 'mount', m,
          'reduces', report['mount_reduces_id4_range'], flush=True)
    return report


if __name__ == '__main__':
    run()
