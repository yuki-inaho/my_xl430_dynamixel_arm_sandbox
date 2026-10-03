"""Independent saved-file checks for the R5 D405 mount (fail closed).

Reuses the R4-C2 material-first pair checker. Declared contacts are explicit
per fastener family; the D405 M3 thread engagement is accepted only inside a
named receiver ROI on the datasheet hole axis. Inherited arm statuses are kept.
"""
import json
import math
from itertools import combinations, product

import numpy as np
import trimesh
from OCP.BRepAdaptor import BRepAdaptor_Surface

from gripper_design.camera_overhead_d405_r5 import (
    D405,
    INPUT,
    RUN,
    Spec,
    local_to_world,
    opening_mm,
    retained_at,
)
from gripper_design.camera_overhead_r4 import ANCHORS, TOP, cylinder
from scripts.assembly_io import bounds, read_step
from scripts.validate_camera_overhead_r4 import box_distance, controls, counter, digest, pair

MIN_GAP = .3


def declared_contact(a, b):
    pair_ = {a, b}
    for i in range(4):
        if pair_ <= {f'CAM5_BASE_WASHER_{i}', f'CAM5_BASE_TAP_{i}', 'CAM5_BASE'}:
            return True
    for i in range(2):
        fam = {f'CAM5_TIE_WASHER_{i}', f'CAM5_TIE_BOLT_{i}', f'CAM5_TIE_NUT_{i}'}
        if (a in fam and b in fam | {'CAM5_BASE', 'CAM5_D405_CARRIER'}) or \
           (b in fam and a in fam | {'CAM5_BASE', 'CAM5_D405_CARRIER'}):
            return True
        if pair_ == {f'CAM5_D405_SCREW_{i}', 'CAM5_D405_CARRIER'}:
            return True
    return pair_ in [{'CAM5_D405_CARRIER', 'CAM5_BASE'}, {'CAM5_D405_CARRIER', 'CAM5_D405_BODY'},
                     {'CAM5_D405_BODY', 'CAM5_D405_USB_PLUG'},
                     {'CAM5_D405_USB_PLUG', 'CAM5_D405_USB_CABLE_STUB'}]


def thread_roi(i, s):
    """Datasheet receiver: M3 hole axis, 4.0 mm max insertion from the rear face."""
    x = (-1 if i == 0 else 1) * D405['rear_m3_pitch_mm'] / 2
    depth = D405['rear_m3_max_insert_mm']
    return local_to_world(cylinder(1.501, depth + .001, (x, 0, -depth)), s)


def internal_pair(a, sa, b, sb, s):
    for i in range(2):
        if {a, b} == {f'CAM5_D405_SCREW_{i}', 'CAM5_D405_BODY'}:
            screw = sa if a.startswith('CAM5_D405_SCREW') else sb
            body = sb if screw is sa else sa
            res = pair(screw, body, contact=True, roi=thread_roi(i, s))
            res['receiver'] = 'D405 rear M3x0.5, datasheet max insert 4.0 mm'
            return res
    return pair(sa, sb, contact=declared_contact(a, b))


def external_pair(n, a, m, b):
    if m == 'PG3_XL430_fixed' and n == 'CAM5_BASE':
        gap = bounds(a)[2] - bounds(b)[5]
        return {'status': 'PASS' if gap >= -1e-6 else 'FAIL', 'method': 'shared_top_plane_separation',
                'signed_gap_mm': gap, 'contact_is_intended': True}
    if m == 'PG3_XL430_fixed' and n.startswith('CAM5_BASE_TAP_'):
        i = int(n.rsplit('_', 1)[1])
        x, y, _ = ANCHORS[i]
        outside = a.cut(cylinder(1.301, 4.001, (x, y, TOP - 4)))
        diff = bounds(outside)[2] - bounds(b)[5]
        return {'status': 'PASS' if diff >= -1e-5 else 'FAIL', 'method': 'receiver_ROI_and_top_plane',
                'outside_roi_signed_gap_mm': diff, 'thread_forming_contact_is_intended': True}
    return pair(a, b, min_gap=MIN_GAP)


def run(s=None):
    s = s or Spec()
    saved_path = RUN / 'CAD/ID5_D405_mid_ASSEMBLY.step'
    saved = {r.name: r.world for r in read_step(saved_path)[2]}
    source = {r.name: r.world for r in read_step(INPUT)[2]}
    p = {n: v for n, v in saved.items() if n.startswith('CAM5_')}
    retained = {n: v for n, v in saved.items() if not n.startswith('CAM5_')}
    ctl = controls()
    if not all(r['passed'] for r in ctl):
        raise ValueError(f'geometry controls failed {ctl}')
    report = {'revision': s.revision, 'input_sha': digest(INPUT), 'saved_mid_sha': digest(saved_path),
              'checker_sha': digest(__file__), 'controls': ctl, 'minimum_external_gap_mm': MIN_GAP,
              'intersection_tolerance_mm3': 1e-5,
              'inherited_checkpoint': {'PASS': 1806, 'ERROR': 1, 'UNKNOWN': 6, 'FAIL': 0,
                                       'approved': False},
              'source_preservation': [], 'anchor_holes': [], 'new_internal': [],
              'external_static': [], 'motion': {}, 'saved_files': []}
    old_camera = sorted(n for n in source if n.startswith('CAMERA_'))
    report['removed_old_camera'] = old_camera
    report['retained_inventory_pass'] = set(retained) == set(source) - set(old_camera)
    for n, b in retained.items():
        a = source[n]
        dv = abs(a.Volume() - b.Volume())
        db = max(abs(x - y) for x, y in zip(bounds(a), bounds(b)))
        ar = abs(a.Area() - b.Area())
        report['source_preservation'].append({'name': n, 'volume_error': dv, 'area_error': ar,
                                              'bbox_error': db, 'pass': dv < .01 and db < 1e-4 and ar < .01})
    motor = retained['PG3_XL430_fixed']
    found = []
    for i, f in enumerate(motor.Faces()):
        if f.geomType() != 'CYLINDER':
            continue
        c = BRepAdaptor_Surface(f.wrapped).Cylinder()
        axis = c.Axis().Direction()
        pos = c.Location()
        bb = bounds(f)
        if abs(axis.Z()) > .99 and abs(c.Radius() - 1.05) < 1e-6 and bb[5] > 199:
            found.append((pos.X(), pos.Y(), 199.85))
            report['anchor_holes'].append({'face': i, 'radius': c.Radius(), 'center': found[-1],
                                           'span': bb[2:6:3]})
    report['anchors_pass'] = len(found) == 4 and all(
        min(math.dist(a, b) for b in found) < 1e-5 for a in ANCHORS)
    holes = []
    for f in p['CAM5_BASE'].Faces():
        if f.geomType() == 'CYLINDER':
            c = BRepAdaptor_Surface(f.wrapped).Cylinder()
            d = c.Axis().Direction()
            q = c.Location()
            if abs(c.Radius() - 1.45) < 1e-5 and abs(d.Z()) > .99:
                holes.append((q.X(), q.Y(), TOP))
    report['base_holes_pass'] = len(holes) == 4 and all(
        min(math.dist(a, b) for b in holes) < 1e-5 for a in ANCHORS)
    for a, b in combinations(p, 2):
        res = internal_pair(a, p[a], b, p[b], s)
        res.update(a=a, b=b)
        report['new_internal'].append(res)
    pb = {n: bounds(v) for n, v in p.items()}
    rb = {n: bounds(v) for n, v in retained.items()}
    for a, b in product(p, retained):
        lower = box_distance(pb[a], rb[b])
        res = ({'status': 'PASS', 'method': 'AABB_lower_bound', 'gap_mm': lower}
               if lower >= MIN_GAP - 1e-6 else external_pair(a, p[a], b, retained[b]))
        res.update(a=a, b=b)
        report['external_static'].append(res)
    print('internal', counter(report['new_internal']), 'external',
          counter(report['external_static']), flush=True)
    fixed = {n for n in retained if not n.startswith('PG3_') or
             n in ['PG3_XL430_fixed', 'PG3_frame', 'PG3_cap_U', 'PG3_cap_D'] or
             n.startswith(('PG3_cap_', 'PG3_case_tapper_'))}
    summary, failures, min_gap = [], [], 1e9
    for angle in np.linspace(25, 135, 221):
        dynamic = retained_at(retained, float(angle))
        checks = []
        movers = {n: v for n, v in dynamic.items() if n not in fixed}
        db = {n: bounds(v) for n, v in movers.items()}
        for a, shape_a in p.items():
            for b, shape_b in movers.items():
                lower = box_distance(pb[a], db[b])
                res = ({'status': 'PASS', 'method': 'AABB_lower_bound', 'gap_mm': lower}
                       if lower >= MIN_GAP - 1e-6 else external_pair(a, shape_a, b, shape_b))
                if res['status'] != 'PASS':
                    failures.append({'angle': float(angle), 'a': a, 'b': b, **res})
                min_gap = min(min_gap, res.get('gap_mm', 1e9))
                checks.append(res)
        summary.append({'angle': float(angle), 'opening_mm': opening_mm(float(angle)), **counter(checks)})
    report['motion'] = {'pose_count': 221, 'range_deg': [25, 135], 'step_deg': .5,
                        'results': summary, 'failures': failures,
                        'minimum_measured_or_bounded_gap_mm': min_gap,
                        'continuous_all_arm_motion_proven': False}
    for pose in ['open', 'mid', 'closed']:
        path = RUN / f'CAD/ID5_D405_{pose}_ASSEMBLY.step'
        q = read_step(path)[2]
        report['saved_files'].append({'path': str(path.relative_to(RUN)), 'sha': digest(path),
                                      'count': len(q), 'inventory_pass': {r.name for r in q} == set(saved)})
    for path in sorted((RUN / 'STL').glob('*.stl')):
        mesh = trimesh.load(path, force='mesh')
        report['saved_files'].append({'path': str(path.relative_to(RUN)), 'sha': digest(path),
                                      'watertight': bool(mesh.is_watertight),
                                      'winding_consistent': bool(mesh.is_winding_consistent),
                                      'body_count': int(mesh.body_count),
                                      'positive_volume': bool(mesh.volume > 0),
                                      'extents_mm': mesh.extents.tolist()})
    report['counts'] = {'new_internal': counter(report['new_internal']),
                        'external_static': counter(report['external_static'])}
    stl_ok = all(r.get('watertight', True) and r.get('body_count', 1) == 1 for r in report['saved_files'])
    report['local_geometric_checks_pass'] = bool(
        report['retained_inventory_pass'] and all(r['pass'] for r in report['source_preservation'])
        and report['anchors_pass'] and report['base_holes_pass'] and not failures and stl_ok
        and all(r['status'] == 'PASS' for r in report['new_internal'] + report['external_static']))
    (RUN / 'reports/geometry.json').write_text(json.dumps(
        report, indent=2, default=lambda o: o.item() if isinstance(o, np.generic) else str(o)))
    bad = [r for r in report['new_internal'] + report['external_static'] if r['status'] != 'PASS']
    print('motion min gap', min_gap, 'failures', len(failures), 'overall_local',
          report['local_geometric_checks_pass'], flush=True)
    print(json.dumps(bad[:20], indent=1, default=str), flush=True)
    return report


if __name__ == '__main__':
    run()
