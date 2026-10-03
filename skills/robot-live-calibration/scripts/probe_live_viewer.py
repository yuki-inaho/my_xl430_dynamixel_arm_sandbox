"""GET-only health probe for an existing local telemetry bridge and pose viewer."""
import argparse
import json
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError("Redirect rejected")


def read(origin, path):
    parts = urlsplit(origin)
    if (parts.scheme != "http" or parts.hostname not in ("localhost", "127.0.0.1")
        or parts.path not in ("", "/") or parts.username or parts.password
        or parts.query or parts.fragment or not parts.port):
        raise ValueError("Explicit local HTTP origin required")
    with build_opener(NoRedirect()).open(Request(origin.rstrip("/") + path), timeout=2) as response:
        value = response.read(262145)
    if len(value) > 262144:
        raise ValueError("Response too large")
    return json.loads(value)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--viewer-url", required=True)
    parser.add_argument("--bridge-url", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    first = read(args.viewer_url, "/api/state")
    bridge = read(args.bridge_url, "/api/status")
    time.sleep(.2)
    second = read(args.viewer_url, "/api/state")
    report = {"captured_at": datetime.now().astimezone().isoformat(),
        "actions": ["GET /api/state", "GET /api/status", "GET /api/state"],
        "first": first, "bridge": bridge, "second": second,
        "frames_progressed": second["frame_seq"] > first["frame_seq"],
        "render_error": second["error"], "physical_calibration_proven": False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in
                     ["frames_progressed", "render_error", "physical_calibration_proven"]}))
    return 0 if report["frames_progressed"] and not report["render_error"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

