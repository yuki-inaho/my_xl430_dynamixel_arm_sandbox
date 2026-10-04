"""Rebuild the supplied case; --start-at permits resuming an interrupted run."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import json
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
STAGES = [
    'prepare_inputs', 'calibrate_scan', 'canonical_views', 'fit_addons',
    'fit_photo', 'build_models', 'render_results', 'check_coin',
    'validate_and_scene', 'publish_figures',
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start-at', choices=STAGES, default=STAGES[0])
    args = parser.parse_args()
    results = ROOT / 'results'
    results.mkdir(exist_ok=True)
    journal = results / 'execution_journal.jsonl'
    for name in STAGES[STAGES.index(args.start_at):]:
        start = datetime.now(timezone.utc).isoformat()
        timer = time.perf_counter()
        with (results / f'rerun_{name}.log').open('w') as log:
            result = subprocess.run(
                [sys.executable, str(ROOT / 'src' / f'{name}.py')],
                cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=False,
            )
        record = {
            'stage': name, 'start_utc': start,
            'end_utc': datetime.now(timezone.utc).isoformat(),
            'elapsed_seconds': time.perf_counter() - timer,
            'exit_code': result.returncode,
        }
        with journal.open('a') as output:
            output.write(json.dumps(record) + '\n')
        print(f'{name}: exit={result.returncode}', flush=True)
        if result.returncode:
            raise RuntimeError(f'{name} failed. Inspect results/rerun_{name}.log')


if __name__ == '__main__':
    main()
