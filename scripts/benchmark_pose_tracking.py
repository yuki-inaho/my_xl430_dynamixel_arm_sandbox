"""Profile repeated image-only tracking of a saved frame (not a live FPS claim)."""

import argparse
import cProfile
import hashlib
import io
import json
import pstats
import time
from pathlib import Path

import cv2
import numpy as np
from articulated_filterreg.geometry import CadModel, State

from arm_observer.perception.renderer import CadRenderer
from arm_observer.perception.source import Frame
from arm_observer.perception.tracker import PoseTracker


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frame', type=Path, required=True, help='frame-XXXXXX.json')
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--iterations', type=int, default=60)
    args = parser.parse_args()
    meta = json.loads(args.frame.read_text())
    bgr = cv2.imread(str(args.frame.with_suffix('.png')))
    pixels = cv2.imread(str(args.frame.with_suffix('.mask.png')), 0)
    if bgr is None or pixels is None:
        raise ValueError('Saved frame RGB and mask are required')
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    mask = pixels > 0
    data = np.load(args.frame.with_suffix('.npz'))
    pose = meta['pose']
    seed = State.from_dict(pose)
    model = CadModel.load(args.model)
    cv2.setNumThreads(1)
    elapsed, poses = [], []
    profile = cProfile.Profile()
    with CadRenderer(model, rgb.shape[1], rgb.shape[0]) as renderer:
        tracker = PoseTracker(model, renderer, initial_state=seed)
        tracker.state = seed
        for index in range(args.iterations+5):
            frame = Frame(rgb, data['depth_m'], data['K'], index, time.monotonic(), {})
            start = time.perf_counter()
            if index >= 5:
                profile.enable()
            estimate = tracker.update(frame, mask)
            profile.disable()
            if index >= 5:
                elapsed.append(time.perf_counter()-start)
                poses.append(dict(status=estimate.status, quality=estimate.quality,
                                  pose=estimate.state.to_dict() if estimate.state else None))
        device = renderer.device
    stream = io.StringIO()
    pstats.Stats(profile, stream=stream).strip_dirs().sort_stats('cumtime').print_stats(45)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output/'profile.txt').write_text(stream.getvalue())
    result = dict(frame=str(args.frame),
                  model_sha256=hashlib.sha256(args.model.read_bytes()).hexdigest(),
                  frame_sha256=hashlib.sha256(args.frame.with_suffix('.npz').read_bytes()).hexdigest(),
                  renderer=device, iterations=args.iterations, elapsed_seconds=elapsed,
                  median_seconds=float(np.median(elapsed)),
                  p95_seconds=float(np.percentile(elapsed, 95)),
                  note='Static frame benchmark including profiler overhead, not live throughput.',
                  estimates=poses)
    (args.output/'results.json').write_text(json.dumps(result, indent=2, allow_nan=False))
    print(json.dumps({k: v for k, v in result.items()
                      if k not in ('elapsed_seconds', 'estimates')}))
    print(stream.getvalue())


if __name__ == '__main__':
    main()
