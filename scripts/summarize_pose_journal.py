"""Measure successful, distinct pose publications, including gaps and reacquisition."""

import argparse
import gzip
import json
from collections import Counter, deque
from datetime import datetime
from pathlib import Path

import numpy as np


def summarize(path, seconds, start_iso=None, end_iso=None):
    rows = deque()
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt') as journal:
        return summarize_records(journal, rows, seconds, path, start_iso, end_iso)


def summarize_records(journal, rows, seconds, path, start_iso=None, end_iso=None):
    start = datetime.fromisoformat(start_iso).timestamp() if start_iso else float('-inf')
    end = datetime.fromisoformat(end_iso).timestamp() if end_iso else float('inf')
    for line in journal:
        # A running producer may not have finished its final line yet.
        if not line.endswith('\n'):
            break
        row = json.loads(line)
        host = datetime.fromisoformat(row['metadata']['host_received_at']).timestamp()
        if not start <= host <= end:
            continue
        timestamp = row['frame_received_monotonic']
        rows.append(row)
        while rows and timestamp-rows[0]['frame_received_monotonic'] > seconds:
            rows.popleft()
    if len(rows) < 2:
        raise ValueError('At least two complete pose records are required')
    elapsed = rows[-1]['frame_received_monotonic']-rows[0]['frame_received_monotonic']
    if elapsed <= 0:
        raise ValueError('No positive observation interval')
    successes = {r['sequence']: r for r in rows
                 if r['status'] == 'tracking' and r['pose'] is not None}
    ages = [r['frame_age_seconds'] for r in successes.values()]
    return dict(
        source=str(path), window_requested_seconds=seconds,
        window_observed_seconds=elapsed, records=len(rows),
        status_counts=dict(Counter(r['status'] for r in rows)),
        distinct_successful_poses=len(successes),
        successful_pose_hz=len(successes)/elapsed,
        successful_record_fraction=len(successes)/len(rows),
        publication_frame_age_seconds=percentiles(r['frame_age_seconds'] for r in rows),
        publication_mask_age_seconds=percentiles(r['mask_age_seconds'] for r in rows),
        timings_seconds={name: percentiles(r.get('timings_seconds', {}).get(name) for r in rows)
                         for name in ('mask_preparation', 'registration', 'jpeg')},
        host_time_bounds=dict(start_iso=start_iso, end_iso=end_iso),
        successful_publication_age_p95_seconds=float(np.percentile(ages, 95)) if ages else None,
        note='Includes lost/reacquisition gaps; publication age excludes subsequent browser delay. '
             'A short observation window is not proof of sustained performance.',
    )


def percentiles(values):
    present = [v for v in values if isinstance(v, (int, float))]
    return (dict(p50=float(np.percentile(present, 50)), p95=float(np.percentile(present, 95)))
            if present else None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('journal', type=Path)
    parser.add_argument('--seconds', type=float, default=60)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--start-iso', help='Inclusive frame host-receipt time, timezone required')
    parser.add_argument('--end-iso', help='Inclusive frame host-receipt time, timezone required')
    args = parser.parse_args()
    if args.seconds <= 0:
        parser.error('--seconds must be positive')
    result = summarize(args.journal, args.seconds, args.start_iso, args.end_iso)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
