"""Camera-only articulated recognition; static reproduction remains a separate CLI."""

import argparse
import hashlib
import json
from pathlib import Path

from articulated_filterreg.geometry import State

from arm_observer.perception.server import LiveSession, serve
from arm_observer.perception.source import ProcessCameraSource


def load_initial_pose(path, model_path, serial):
    if path is None:
        return None
    value = json.loads(path.read_text())
    digest = hashlib.sha256(model_path.read_bytes()).hexdigest()
    if value['model_sha256'] != digest or value['metadata']['serial'] != serial:
        raise ValueError('Initial vision pose belongs to a different model/camera')
    if value['status'] != 'tracking':
        raise ValueError('Initial vision pose must be a previously successful estimate')
    state = State.from_dict(value['pose'])
    if state.scale != 1. or state.joints.shape != (4,):
        raise ValueError('Initial vision pose must use metric scale and four CAD joints')
    return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--camera-serial', required=True)
    parser.add_argument('--model', type=Path, default=Path('models/current_arm_r3_d405_r5_65.npz'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--port', type=int, default=18111)
    parser.add_argument('--segmentation-size', type=int, default=768)
    parser.add_argument('--width', type=int, choices=(320, 480, 640), default=640)
    parser.add_argument('--backend', choices=('native', 'cuda'), default='native')
    parser.add_argument('--initial-pose', type=Path,
                        help='Previous vision estimate, same fixed camera/base; quality rechecked')
    args = parser.parse_args()
    initial = load_initial_pose(args.initial_pose, args.model, args.camera_serial)
    source = ProcessCameraSource(args.camera_serial, args.width)
    try:
        session = LiveSession(source, args.model, args.output, args.segmentation_size,
                              args.backend, initial)
    except BaseException:
        source.close()
        raise
    serve(session, args.port)


if __name__ == '__main__':
    main()
