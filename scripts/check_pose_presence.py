"""Replay the presence gate on accepted observations and a reviewed arm-absent control.

This checks gate compatibility, not a new fit or an independent angle evaluation.
The negative control always uses the original fixed-scene vision anchor, never
the erroneous background pose recorded before the fix.
"""

import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np
from articulated_filterreg.geometry import CadModel, State

from arm_observer.perception.renderer import CadRenderer
from arm_observer.perception.source import Frame
from arm_observer.perception.tracker import PoseTracker, quality, sample_points


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dataset', type=Path)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    paths = sorted(args.dataset.glob('**/pose_*/observation.npz'))
    if len(paths) != 20:
        raise ValueError('Expected twenty accepted observations')
    anchor = State.from_dict(json.loads((args.dataset/'neutral/pose.json').read_text())
                             ['vision']['pose'])
    rows = []
    with CadRenderer(CadModel.load(args.model), 480, 270) as renderer:
        tracker = PoseTracker(renderer.model, renderer, initial_state=anchor)
        for path in [*paths, args.dataset/'arm-absent-negative/observation.npz']:
            absent = path.parent.name == 'arm-absent-negative'
            with np.load(path) as saved:
                metadata = json.loads(str(saved['metadata_json']))
                frame = Frame(saved['rgb'], saved['depth_m'], saved['K'], 0,
                              time.monotonic(), metadata)
                mask = saved['mask']
                state = anchor if absent else State.from_dict(metadata['pose'])
                _, metrics = quality(renderer, frame, mask,
                                     sample_points(frame, mask, 1200), state)
                accepted = tracker.acceptable(metrics)
                if accepted == absent:
                    raise AssertionError(f'Unexpected gate decision at {path}: {metrics}')
                row = dict(path=str(path.relative_to(args.dataset)), absent=absent,
                           accepted=accepted, quality=metrics,
                           sha256=hashlib.sha256(path.read_bytes()).hexdigest())
                if absent:
                    # Continue beyond three failures, where the old implementation
                    # discarded its seed and searched for a root on the background.
                    results = [tracker.update(Frame(frame.rgb, frame.depth_m, frame.K, i,
                                                    time.monotonic(), metadata), mask)
                               for i in range(4)]
                    assert all(r.status == 'lost' and r.state is None for r in results)
                    assert tracker.seed is anchor
                    row['repeated_loss_reasons'] = [r.reason for r in results]
                rows.append(row)
    args.output.write_text(json.dumps(dict(
        model_sha256=hashlib.sha256(args.model.read_bytes()).hexdigest(),
        scope='Stored-pose gate compatibility and anchored absence rejection; no new fit',
        positive_accepted=sum(1 for r in rows if r['accepted']), negative_rejected=True,
        min_base_depth_points=tracker.config.min_base_points,
        max_base_depth_error_m=tracker.config.max_base_depth_error_m, observations=rows,
    ), indent=2)+'\n')
    print('20 positive observations accepted; arm-absent control lost on all four updates')


if __name__ == '__main__':
    main()
