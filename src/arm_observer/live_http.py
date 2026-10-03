"""Local bridge: status is passive; only explicit start acquires the read-only bus."""
import argparse
import json
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from arm_observer.configuration import load_config
from arm_observer.live import LiveMonitor


def origin_allowed(origin: str | None, port: int) -> bool:
    return origin is None or origin in {f"http://127.0.0.1:{port}", f"http://localhost:{port}"}


def status_bytes(monitor: LiveMonitor) -> bytes:
    return json.dumps(asdict(monitor.snapshot()), default=str, allow_nan=False).encode()


def handler_for(monitor: LiveMonitor, port: int) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def respond(self, code: int, content: bytes) -> None:
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            try:
                self.wfile.write(content)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def do_GET(self) -> None:
            if self.path == "/api/status":
                self.respond(200, status_bytes(monitor))
            else:
                self.respond(404, b'{"error":"Not found"}')

        def do_POST(self) -> None:
            if not origin_allowed(self.headers.get("Origin"), port):
                self.respond(403, b'{"error":"Invalid origin"}')
                return
            try:
                size = int(self.headers.get("Content-Length", 0))
                if not 0 < size <= 1024:
                    raise ValueError("Invalid payload size")
                payload = json.loads(self.rfile.read(size))
                self.apply_request(payload)
                self.respond(200, status_bytes(monitor))
            except (ValueError, TypeError) as exc:
                self.respond(400, json.dumps({"error": str(exc)}).encode())

        def apply_request(self, payload: object) -> None:
            if not isinstance(payload, dict):
                raise ValueError("Object required")
            if self.path == "/api/start" and set(payload) == {"duration_seconds"}:
                monitor.start(payload["duration_seconds"])
            elif self.path == "/api/stop" and not payload:
                monitor.stop()
            else:
                raise ValueError("Unknown action or field; bridge has no write API")

        def log_message(self, format: str, *args: object) -> None:
            pass
    return Handler


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8085)
    parser.add_argument("--config", type=Path, default=root / "config/arm.toml")
    parser.add_argument("--reports", type=Path, default=root / "reports")
    args = parser.parse_args()
    monitor = LiveMonitor(load_config(args.config), args.reports)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler_for(monitor, args.port))
    print(f"READ bridge http://127.0.0.1:{args.port} (idle; no serial connection)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        monitor.stop()
        closed = monitor.join()
        server.server_close()
        if not closed:
            print("Acquisition still closing; closure has not been confirmed", flush=True)


if __name__ == "__main__":
    main()

