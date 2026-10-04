"""Save a settled pose from the existing live camera; never access the serial bus."""

import argparse
import hashlib
import json
import shutil
import time
import urllib.request
from datetime import datetime
from pathlib import Path

from arm_observer.photo_evidence import held_sample, sample_time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--pose", required=True)
    parser.add_argument("--camera-url", default="http://127.0.0.1:18107")
    args = parser.parse_args()
    deadline = time.monotonic() + 25
    while True:
        ready = args.dataset / "ready.json"
        if ready.exists():
            record = json.loads(ready.read_text())
            if record["name"] == args.pose:
                break
        if time.monotonic() > deadline:
            raise RuntimeError("Pose not ready before capture deadline")
        time.sleep(0.2)
    before = held_sample(args.dataset, record)
    with urllib.request.urlopen(
        urllib.request.Request(
            args.camera_url + "/capture",
            method="POST",
            data=json.dumps({"not_before_unix_s": sample_time(before)}).encode(),
            headers={"Content-Type": "application/json"},
        ),
        timeout=5,
    ) as response:
        result = json.load(response)
    acquired = datetime.fromisoformat(result["metadata"]["host_frame_received_at"]).timestamp()
    if acquired < sample_time(before):
        raise RuntimeError("Camera returned a frame from before the robot sample")
    # A cached sample from before the camera request does not bracket the capture.
    captured = time.time()
    until = time.monotonic() + 2
    while True:
        after = held_sample(args.dataset, record)
        if sample_time(after) >= captured and sample_time(after) > sample_time(before):
            break
        if time.monotonic() >= until:
            raise RuntimeError("No fresh telemetry after camera capture")
        time.sleep(0.05)
    if any(abs(a - b) > 3 for a, b in zip(before["positions"], after["positions"])):
        raise RuntimeError("Robot shifted during image capture")
    dest = args.dataset / args.pose
    shutil.copytree(result["path"], dest)
    record.update(
        camera_capture=result["metadata"]["captured_at"],
        telemetry_before=before,
        telemetry_after=after,
        hardware_synchronized=False,
        accepted=False,
        review="Pending actual image review before next motion",
    )
    (dest / "pose.json").write_text(json.dumps(record, ensure_ascii=False, indent=2))
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in dest.glob("*.png")}
    (dest / "sha256.json").write_text(json.dumps(hashes, indent=2))
    print(
        json.dumps(
            dict(
                pose=args.pose,
                path=str(dest),
                positions=after["positions"],
                captured_at=record["camera_capture"],
            ),
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
