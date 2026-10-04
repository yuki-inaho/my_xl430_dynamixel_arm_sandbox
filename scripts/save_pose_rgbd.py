"""Save a settled pose from the existing live camera; never access the serial bus."""
import argparse
import hashlib
import json
import shutil
import time
import urllib.request
from datetime import datetime
from pathlib import Path


def latest_sample(dataset):
    with (dataset / "events.jsonl").open("rb") as log:
        log.seek(0, 2)
        log.seek(max(0, log.tell() - 16384))
        lines = log.read().splitlines()[1:]
    for line in reversed(lines):
        event = json.loads(line)
        if event["kind"] == "sample":
            if time.time() - datetime.fromisoformat(event["at"]).timestamp() > 2:
                raise RuntimeError("No fresh robot telemetry")
            return event
    raise RuntimeError("Missing robot sample")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--pose", required=True)
    parser.add_argument("--camera-url", default="http://127.0.0.1:18107")
    args = parser.parse_args()
    deadline = time.monotonic() + 25
    while True:
        events = args.dataset / "events.jsonl"
        if events.exists():
            with events.open("rb") as log:
                log.seek(0, 2)
                log.seek(max(0, log.tell() - 8192))
                tail = log.read()
            if b'"kind": "stop"' in tail or b'"kind": "stop_hold_fault"' in tail:
                raise RuntimeError("Motion stopped; capture not accepted")
        ready = args.dataset / "ready.json"
        if ready.exists():
            record = json.loads(ready.read_text())
            if record["name"] == args.pose:
                break
        if time.monotonic() > deadline:
            raise RuntimeError("Pose not ready before capture deadline")
        time.sleep(0.2)
    before = latest_sample(args.dataset)
    with urllib.request.urlopen(urllib.request.Request(
        args.camera_url + "/capture", method="POST"), timeout=5) as response:
        result = json.load(response)
    after = latest_sample(args.dataset)
    if any(abs(a-b) > 3 for a, b in zip(before["positions"], after["positions"])):
        raise RuntimeError("Robot shifted during image capture")
    dest = args.dataset / args.pose
    shutil.copytree(result["path"], dest)
    record.update(camera_capture=result["metadata"]["captured_at"],
                  telemetry_before=before, telemetry_after=after,
                  hardware_synchronized=False, accepted=False,
                  review="Pending actual image review before next motion")
    (dest / "pose.json").write_text(json.dumps(record, ensure_ascii=False, indent=2))
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
              for p in dest.glob("*.png")}
    (dest / "sha256.json").write_text(json.dumps(hashes, indent=2))
    print(json.dumps(dict(pose=args.pose, path=str(dest), positions=after["positions"],
                          captured_at=record["camera_capture"]), ensure_ascii=False))


if __name__ == "__main__":
    main()
