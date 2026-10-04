"""Capture two camera owners at one monitored ID5 state; preserve actual host times."""

import argparse
import json
import time
import urllib.request
from pathlib import Path


def latest_sample(path):
    events = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    sample = next(e for e in reversed(events) if e["kind"] == "sample")
    ready_index = max((i for i, e in enumerate(events) if e["kind"] == "ready"), default=-1)
    write_index = max((i for i, e in enumerate(events) if e["kind"] == "write"), default=-1)
    if ready_index <= write_index:
        raise RuntimeError("No matching ready event after the last motor write")
    if time.time() - sample["host_unix_s"] > 2:
        raise RuntimeError("Motor observation is stale")
    motor = next(m for m in sample["motors"] if m["motor_id"] == 5)
    if not motor["torque_enabled"]:
        raise RuntimeError("ID5 is not monitored and held")
    if (
        motor["velocity_raw"] != 0
        or abs(motor["position_counts"] - events[ready_index]["actual"]) > 12
    ):
        raise RuntimeError("ID5 is no longer stationary at the accepted observed position")
    return sample


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", required=True)
    parser.add_argument("--motion", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    destination = args.output / f"{args.state}.json"
    if destination.exists():
        raise FileExistsError(destination)
    captures = {}
    evidence = dict(
        state=args.state,
        synchronization="sequential host timestamps; not hardware sync",
        captures=captures,
    )
    for camera, port in (("d435", 18108), ("d405", 18109)):
        before = latest_sample(args.motion)
        request = urllib.request.Request(
            f"http://127.0.0.1:{port}/capture",
            method="POST",
            data=json.dumps({"not_before_unix_s": time.time()}).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            receipt = json.load(response)
        after = latest_sample(args.motion)
        path = Path(receipt["path"])
        metadata = receipt["metadata"]
        metadata["robot_observation"] = dict(
            before=before, after=after, correspondence="host time brackets, no hardware sync"
        )
        (path / "metadata.json").write_text(json.dumps(metadata, indent=2))
        captures[camera] = dict(path=str(path), before=before, after=after)
    destination.write_text(json.dumps(evidence, indent=2))
    print(json.dumps(dict(state=args.state, paths={k: v["path"] for k, v in captures.items()})))


if __name__ == "__main__":
    main()
