"""Save a matched vision snapshot with independently bracketed held-motor readings."""

import argparse
import io
import json
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from arm_observer.perception.server import save_image
from arm_observer.photo_evidence import held_sample, sample_time


def observation(url, after):
    deadline = time.monotonic()+10
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url.rstrip('/')+'/observation.npz', timeout=3) as response:
                raw = response.read()
            data = np.load(io.BytesIO(raw), allow_pickle=False)
            metadata = json.loads(str(data['metadata_json']))
            timestamp = datetime.fromisoformat(metadata['metadata']['host_received_at']).timestamp()
            if timestamp >= after and time.time()-timestamp < .8:
                return data, metadata, raw
        except urllib.error.HTTPError as error:
            if error.code != 503:
                raise
        time.sleep(.05)
    raise TimeoutError('No fresh matched vision snapshot after pre-capture observation')


def after_sample(dataset, ready, timestamp):
    deadline = time.monotonic()+3
    while time.monotonic() < deadline:
        sample = held_sample(dataset, ready)
        if sample_time(sample) >= timestamp:
            return sample
        time.sleep(.05)
    raise TimeoutError('No post-frame held motor sample')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--name', required=True)
    parser.add_argument('--neutral', action='store_true', help='No held session; save vision only')
    parser.add_argument('--url', default='http://127.0.0.1:18111')
    args = parser.parse_args()
    output = args.dataset/args.name
    if output.exists() or Path(args.name).name != args.name:
        raise ValueError('Snapshot name must be a new directory basename')
    ready, before, after = None, None, None
    if not args.neutral:
        ready = json.loads((args.dataset/'ready.json').read_text())
        if ready['name'] != args.name:
            raise ValueError('Requested photo does not match current held pose')
        before = held_sample(args.dataset, ready)
    data, meta, raw = observation(args.url, sample_time(before) if before else time.time())
    timestamp = datetime.fromisoformat(meta['metadata']['host_received_at']).timestamp()
    if ready is not None:
        after = after_sample(args.dataset, ready, timestamp)
    output.mkdir(parents=True, exist_ok=False)
    (output/'observation.npz').write_bytes(raw)
    save_image(output/'color.png', cv2.cvtColor(data['rgb'], cv2.COLOR_RGB2BGR))
    save_image(output/'mask.png', data['mask'].astype(np.uint8)*255)
    save_image(output/'raw-mask.png', data['raw_mask'].astype(np.uint8)*255)
    save_image(output/'mask-source.png', cv2.cvtColor(data['mask_rgb'], cv2.COLOR_RGB2BGR))
    depth = np.clip(data['depth_m']/.8*255, 0, 255).astype(np.uint8)
    save_image(output/'depth-preview.png', cv2.applyColorMap(depth, cv2.COLORMAP_TURBO))
    (output/'overlay.jpg').write_bytes(data['overlay_jpeg'].tobytes())
    record = dict(ready=ready, before=before, after=after, vision=meta,
                  hardware_synchronized=False, encoder_used_for_fitting=False,
                  stored_data='Processed RGB and aligned metric depth; source native1280x720, '
                              'processed resolution and K stored in observation.npz',
                  recorded_at=datetime.now().astimezone().isoformat())
    (output/'pose.json').write_text(json.dumps(record, indent=2, allow_nan=False))
    print(json.dumps(dict(output=str(output), status=meta['status'], quality=meta['quality'],
                          positions=after['positions'] if after else None,
                          joints=meta['pose']['joint_angles_deg'] if meta['pose'] else None)))


if __name__ == '__main__':
    main()
