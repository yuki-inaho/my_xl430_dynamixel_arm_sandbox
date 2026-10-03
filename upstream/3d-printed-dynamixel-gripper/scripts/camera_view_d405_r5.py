"""D405 view diagnostics on the saved R5 assembly, plus same-FOV reference viewpoints.

Both depth imagers are rendered (depth needs both). HFOV 84 deg at 1280x720 gives
VFOV 53.7 deg, narrower than the datasheet 58 deg, so vertical margins are
conservative. Distances are measured along the optical axis from the datasheet
depth origin (3.7 mm behind the front glass). This is a CAD diagnostic, not a
calibrated camera test.
"""
import json
import math

import numpy as np
from scipy.optimize import brentq

from gripper_design.camera_overhead_d405_r5 import (
    D405,
    RUN,
    Spec,
    imagers,
    opening_mm,
    optical,
    retained_at,
)
from gripper_design.camera_overhead_r4 import box
from scripts.assembly_io import read_step
from scripts.camera_view_r4 import View, category
from scripts.validate_camera_overhead_r4 import digest

SIZE = (1280, 720)
HFOV = D405['depth_fov_deg']['H']
CUBE_CENTER = (-0.2, 214.6, 164.6)


def pose_basis(pitch_deg):
    t = math.radians(pitch_deg)
    return np.array((0, math.cos(t), -math.sin(t))), np.array((0, math.sin(t), math.cos(t)))


def reference_viewpoints():
    """Other candidates' camera poses re-evaluated with the same D405 FOV.

    Their own mount parts are NOT in the scene (optimistic for them).
    R7: reports/camera.json origins of ID5_D405_30deg_R7 (front-cover origin).
    R4-C2: optical() eye of camera_overhead_r4.Spec (UVC lens front, 63 deg).
    """
    return {
        'R7_30deg': {'pitch': 30.0, 'left': (-9.2, 154.04848809760975, 246.425),
                     'right': (8.8, 154.04848809760975, 246.425)},
        'R4C2_63deg_if_D405': {'pitch': 63.0, 'left': (-9.2, 186.33, 221.43),
                               'right': (8.8, 186.33, 221.43)},
    }


def frustum_stats(shape, eye, d, up, hfov, size):
    vs, _ = shape.tessellate(.2, .3)
    pts = np.array([v.toTuple() for v in vs])
    right = np.cross(d, up)
    r = pts - np.asarray(eye)
    dep = r @ d
    th = math.tan(math.radians(hfov) / 2)
    tv = th * size[1] / size[0]
    inside = (dep > 0) & (np.abs(r @ right) <= dep * th) & (np.abs(r @ up) <= dep * tv)
    return float(inside.mean()), float(dep.min())


def cases():
    out = [('open_empty', 25.0, None), ('mid_empty', 90.0, None), ('closed_empty', 135.0, None)]
    for edge in (10, 20, 30):
        out.append((f'cube_{edge}_grasp', brentq(lambda a, e=edge: opening_mm(a) - e, 25, 135), edge))
    return out


def evaluate(scene, eye, d, up, image=None):
    view = View(scene, tuple(eye), tuple(d), tuple(up), HFOV, SIZE)
    if image:
        view.capture(image)
    visible = view.capture(seg=True)
    inv = {i: n for n, i in view.ids.items()}
    targets = {'jaw_L': {'PG3_finger_L', 'PG3_pad_L'}, 'jaw_R': {'PG3_finger_R', 'PG3_pad_R'},
               'pad_L': {'PG3_pad_L'}, 'pad_R': {'PG3_pad_R'}}
    if 'DIAGNOSTIC_CUBE' in scene:
        targets['cube'] = {'DIAGNOSTIC_CUBE'}
    result = {}
    for key, names in targets.items():
        ref = view.capture(seg=True, only=names)
        codes = [view.ids[n] for n in names]
        mask = np.isin(ref, codes)
        hit = mask & np.isin(visible, codes)
        occ = {}
        for i, c in zip(*np.unique(visible[mask & ~np.isin(visible, codes)], return_counts=True)):
            cat = category(inv.get(int(i), 'outside_background')).replace('CAM4', 'CAM5')
            occ[cat] = occ.get(cat, 0) + int(c)
        in_frame, min_depth = [], []
        for n in names:
            f, dm = frustum_stats(scene[n], eye, d, up, HFOV, SIZE)
            in_frame.append(f)
            min_depth.append(dm)
        rows, cols = np.where(mask)
        result[key] = {
            'reference_pixels': int(mask.sum()), 'visible_pixels': int(hit.sum()),
            'visible_fraction_of_in_frame': float(hit.sum() / mask.sum()) if mask.sum() else 0.0,
            'vertex_fraction_in_frustum': float(min(in_frame)),
            'min_axial_depth_mm': float(min(min_depth)),
            'touches_image_edge': bool(mask[0].any() or mask[-1].any() or mask[:, 0].any() or mask[:, -1].any()),
            'margin_pixels': int(min(cols.min(), SIZE[0] - 1 - cols.max(), rows.min(), SIZE[1] - 1 - rows.max())) if len(rows) else None,
            'occluded_by_pixel_count': occ}
    view.close()
    return result


def run(s=None):
    s = s or Spec()
    path = RUN / 'CAD/ID5_D405_mid_ASSEMBLY.step'
    source = {r.name: r.world for r in read_step(path)[2]}
    arm = {n: v for n, v in source.items() if not n.startswith('CAM5_')}
    mount = {n: v for n, v in source.items() if n.startswith('CAM5_')}
    # The depth origin lies inside the D405 envelope box, so the camera body itself
    # is not an occluder; every other mount/cable body stays in the scene.
    # Names are mapped to CAM4_ so the R4 category() helper reports them as the mount.
    mount4 = {n.replace('CAM5_', 'CAM4_'): v for n, v in mount.items() if n != 'CAM5_D405_BODY'}
    opt = optical(s)
    d = np.array(opt['direction'])
    up = np.array(opt['up'])
    report = {'revision': s.revision, 'saved_mid_sha': digest(path), 'checker_sha': digest(__file__),
              'optical': opt, 'fov': {'H_deg': HFOV, 'render_size': SIZE,
                                      'V_deg_rendered': math.degrees(2 * math.atan(math.tan(math.radians(HFOV) / 2) * SIZE[1] / SIZE[0])),
                                      'V_deg_datasheet': D405['depth_fov_deg']['V']},
              'min_z_mm': D405['min_z_mm'], 'depth_origin': 'datasheet depth start, 3.7 mm behind glass',
              'cube_center_world_mm': CUBE_CENTER, 'cases': [], 'references': [],
              'excluded_from_occluders': ['CAM5_D405_BODY (contains the depth origin)'],
              'physical_camera_validation': False}
    folder = RUN / 'images/camera'
    folder.mkdir(parents=True, exist_ok=True)
    eyes = {k: np.array(v) for k, v in imagers(s).items()}
    refs = reference_viewpoints()
    for label, angle, edge in cases():
        scene = retained_at(arm, angle) | mount4
        bare = retained_at(arm, angle)
        if edge:
            h = edge / 2
            c = CUBE_CENTER
            cube = box(c[0] - h, c[0] + h, c[1] - h, c[1] + h, c[2] - h, c[2] + h)
            scene['DIAGNOSTIC_CUBE'] = cube
            bare['DIAGNOSTIC_CUBE'] = cube
        for side, eye in eyes.items():
            img = folder / f'{label}_{side}.png'
            res = evaluate(scene, eye, d, up, img)
            report['cases'].append({'label': label, 'angle': angle, 'cube_edge_mm': edge,
                                    'opening_mm': opening_mm(angle), 'imager': side,
                                    'eye': eye.tolist(), 'targets': res,
                                    'image': str(img.relative_to(RUN)), 'image_sha': digest(img)})
            print(label, side, {k: (round(v['visible_fraction_of_in_frame'], 3),
                                    round(v['vertex_fraction_in_frustum'], 3),
                                    round(v['min_axial_depth_mm'], 1)) for k, v in res.items()}, flush=True)
        for name, ref in refs.items():
            rd, ru = pose_basis(ref['pitch'])
            for side in ('left', 'right'):
                eye = np.array(ref[side])
                img = folder / f'REF_{name}_{label}_{side}.png'
                res = evaluate(bare, eye, rd, ru, img)
                report['references'].append({'reference': name, 'label': label, 'imager': side,
                                             'pitch_deg': ref['pitch'], 'eye': eye.tolist(),
                                             'own_mount_in_scene': False, 'targets': res,
                                             'image': str(img.relative_to(RUN))})
        (RUN / 'reports/camera_views.json').write_text(json.dumps(report, indent=2))
    return report


if __name__ == '__main__':
    run()
