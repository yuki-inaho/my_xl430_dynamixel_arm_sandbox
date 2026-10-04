"""Measure HTTP-observed estimate freshness, independently from inference throughput."""

import argparse
import json
import time
import urllib.request
from pathlib import Path

from summarize_pose_journal import percentiles


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:18111')
    parser.add_argument('--seconds', type=float, default=20)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not 0 < args.seconds <= 60:
        raise ValueError('Use a finite 0..60 second observation')
    samples = []
    start = time.monotonic()
    while time.monotonic()-start < args.seconds:
        with urllib.request.urlopen(args.url.rstrip('/')+'/state.json', timeout=2) as response:
            samples.append(json.load(response))
        time.sleep(.1)
    tracking = [s for s in samples if s['status'] == 'tracking' and s['pose'] is not None]
    summary = dict(
        sample_count=len(samples), tracking_count=len(tracking),
        duration_seconds=time.monotonic()-start, url=args.url,
        all_frame_age_seconds=percentiles(s.get('frame_age_seconds') for s in samples),
        all_mask_age_seconds=percentiles(s.get('mask_age_seconds') for s in samples),
        note='Includes lost/stale observations. Polling rate is not successful pose throughput.')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(dict(summary=summary, samples=samples), indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
