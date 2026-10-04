"""Attach the nominal D405 R5 mesh set to the immutable bare-arm reference."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import trimesh


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bare', type=Path, required=True)
    parser.add_argument('--camera-meshes', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    with np.load(args.bare, allow_pickle=False) as data:
        model = {key: data[key].copy() for key in data.files}
    inputs = []
    paths = sorted(args.camera_meshes.glob('r5_65_*.obj'))
    if len(paths) != 21:
        raise ValueError('expected the complete nominal R5_65 set of 21 meshes')
    units = model['units'].tolist()
    for path in paths:
        mesh = trimesh.load_mesh(path, process=False)
        offset = len(model['vertices'])
        # The viewer exports wrist-local metres. Restore the STEP reference frame.
        vertices = np.asarray(mesh.vertices) + model['pivots'][3]
        faces = np.asarray(mesh.faces) + offset
        unit_index = len(units)
        units.append(path.stem)
        for key, value in (
            ('vertices', vertices), ('faces', faces),
            ('vertex_level', np.full(len(vertices), 4, np.int32)),
            ('face_level', np.full(len(faces), 4, np.int32)),
            ('face_kind', np.full(len(faces), int('BODY' not in path.stem), np.int32)),
            ('face_unit', np.full(len(faces), unit_index, np.int32)),
        ):
            model[key] = np.concatenate((model[key], value))
        inputs.append({'file': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    model['units'] = np.asarray(units)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(args.output, **model)
    manifest = {
        'configuration': 'R3 arm + nominal D405 long R5_65; no jaws',
        'physical_match': 'R5 family inferred from photos; 65/75-degree distinction unresolved',
        'units': 'metres', 'attachment_body_level': 4,
        'mesh_local_origin_reference_m': model['pivots'][3].tolist(),
        'bare_sha256': hashlib.sha256(args.bare.read_bytes()).hexdigest(),
        'output_sha256': hashlib.sha256(args.output.read_bytes()).hexdigest(),
        'inputs': inputs,
    }
    args.output.with_suffix('.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({key: value for key, value in manifest.items() if key != 'inputs'}))


if __name__ == '__main__':
    main()
