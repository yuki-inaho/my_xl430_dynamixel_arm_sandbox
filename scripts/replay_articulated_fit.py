"""Replay the archive's winning initialization without overwriting its results."""

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import cv2
import numpy as np
from articulated_filterreg.evaluate import evaluate
from articulated_filterreg.geometry import CadModel, State
from articulated_filterreg.native import BINDING
from articulated_filterreg.observations import Observations
from articulated_filterreg.optimize import FitConfig, fit
from articulated_filterreg.render import render, shaded_image


def replay(source: Path, output: Path) -> dict:
    model = CadModel.load(source / 'model/bare_arm.npz')
    observation = Observations.load(source)
    best = json.loads((source / 'results/best.json').read_text())
    manifest = json.loads((source / 'results/run_manifest.json').read_text())
    config = FitConfig(**manifest['configuration'])
    result = fit(model, observation, State.from_dict(best['initial']), config)
    if result.status != 'completed':
        raise RuntimeError(result.status)
    original = State.from_dict(best['final'])
    difference = float(np.max(np.abs(result.state.vector() - original.vector())))
    metrics = evaluate(model, observation, result.state, include_held_out=True)
    report = {
        'binding': BINDING, 'configuration': asdict(config), 'trial_id': best['id'],
        'elapsed_seconds': result.elapsed_seconds,
        'state': result.state.to_dict(), 'metrics': metrics,
        'max_abs_state_difference': difference,
        'selection_score_difference': abs(
            metrics['selection_score'] - best['final_metrics']['selection_score']
        ),
    }
    output.mkdir(parents=True, exist_ok=True)
    _, index, vertices = render(
        model, result.state, observation.K, observation.width, observation.height,
    )
    cad = shaded_image(model, vertices, index)
    overlay = observation.rgb.copy()
    visible = (index >= 0) & ~observation.occlusion
    overlay[visible] = (.55 * overlay[visible] + .45 * cad[visible]).astype(np.uint8)
    for name, image in [('overlay', overlay), ('cad', cad), ('input', observation.rgb)]:
        if not cv2.imwrite(str(output / f'{name}.png'), cv2.cvtColor(image, cv2.COLOR_RGB2BGR)):
            raise OSError(f'cannot save {name}')
    (output / 'replay.json').write_text(json.dumps(report, indent=2) + '\n')
    (output / 'trace.json').write_text(json.dumps(result.trace, indent=2) + '\n')
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path('packages/articulated-filterreg'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = replay(args.source, args.output)
    print(json.dumps({k: report[k] for k in (
        'binding', 'elapsed_seconds', 'max_abs_state_difference', 'selection_score_difference',
    )}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
