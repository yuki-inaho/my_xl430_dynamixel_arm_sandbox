"""Request exactly one existing guarded pose and save it for operator image review."""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from arm_observer.photo_evidence import tail_events


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dataset', type=Path)
    parser.add_argument('pose')
    args = parser.parse_args()
    plan = json.loads((args.dataset/'plan.json').read_text())
    if args.pose not in {p['name'] for p in plan['poses']}:
        raise ValueError('Pose must exist in the reviewed plan')
    if (args.dataset/args.pose).exists():
        raise ValueError('Retain existing capture; choose a new run for a retake')
    (args.dataset/'command.txt').write_text(args.pose)
    deadline = time.monotonic()+45
    while time.monotonic() < deadline:
        rows = tail_events(args.dataset/'events.jsonl', 65536)
        if any(r['kind'] in ('stop', 'stop_hold_fault', 'released_supported') for r in rows):
            raise RuntimeError('Motion session stopped: inspect events before proceeding')
        ready = args.dataset/'ready.json'
        if ready.exists() and json.loads(ready.read_text())['name'] == args.pose:
            subprocess.run([sys.executable,
                            str(Path(__file__).with_name('save_recognition_pose.py')),
                            '--dataset', str(args.dataset), '--name', args.pose], check=True)
            return
        time.sleep(.1)
    raise TimeoutError('Guarded motion did not announce this pose; inspect controller')


if __name__ == '__main__':
    main()
