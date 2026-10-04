"""Evaluate recognition changes across saved RGB-D snapshots, never encoder inputs."""

import argparse
import json
import time
from pathlib import Path

import cv2
import numpy as np
from articulated_filterreg.geometry import CadModel

from arm_observer.perception.renderer import CadRenderer
from arm_observer.perception.segmentation import BiRefNetSegmenter, registration_mask
from arm_observer.perception.source import Frame, load_frame
from arm_observer.perception.tracker import PoseTracker


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    paths = [args.dataset/'neutral'] + sorted(args.dataset.glob('pose_*'))
    paths = [path for path in paths if (path/'metadata.json').is_file()]
    if len(paths) < 2:
        raise ValueError('expected neutral and a series of RGB-D pose directories')
    args.output.mkdir(parents=True, exist_ok=True)
    cv2.setNumThreads(1)
    model = CadModel.load(args.model)
    segmenter = BiRefNetSegmenter()
    first = load_frame(paths[0])
    records = []
    with CadRenderer(model, first.rgb.shape[1], first.rgb.shape[0]) as renderer:
        tracker = PoseTracker(model, renderer)
        for sequence, path in enumerate(paths):
            frame = load_frame(path, sequence)
            mask = registration_mask(segmenter.predict(frame.rgb), 7)
            # These are distinct static snapshots, not a 30fps recorded video.
            # Several EM updates settle each jump; timings are labelled offline.
            estimate = None
            start = time.monotonic()
            for _ in range(8):
                fresh = Frame(frame.rgb, frame.depth_m, frame.K, sequence,
                              time.monotonic(), frame.metadata)
                estimate = tracker.update(fresh, mask)
            assert estimate is not None
            image = frame.rgb.copy()
            if estimate.rendering is not None:
                r = estimate.rendering
                image[r.mask] = (.5*image[r.mask]+.5*r.rgb[r.mask]).astype(np.uint8)
            cv2.imwrite(str(args.output/f'{path.name}.png'), cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
            record = {
                'source': str(path), 'status': estimate.status, 'quality': estimate.quality,
                'pose': None if estimate.state is None else estimate.state.to_dict(),
                'reason': estimate.reason, 'offline_settling_seconds': time.monotonic()-start,
                'encoder_used_for_fitting': False,
            }
            records.append(record)
            (args.output/'poses.json').write_text(json.dumps(records, indent=2, allow_nan=False))
            print(path.name, record['status'], record['quality'], flush=True)
    (args.output/'segmentation.json').write_text(json.dumps(segmenter.provenance, indent=2))


if __name__ == '__main__':
    main()
