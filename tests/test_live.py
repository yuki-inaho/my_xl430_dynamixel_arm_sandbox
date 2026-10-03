"""Offline lifecycle tests; acquisition is injected and never opens serial."""
import json
import threading
from contextlib import contextmanager
from dataclasses import FrozenInstanceError

import pytest
from test_readonly import OfflinePacket

from arm_observer import live
from arm_observer.models import ArmConfig, BusConfig
from arm_observer.observer import PollOptions, observe
from arm_observer.reader import SdkReader, decode_telemetry
from arm_observer.registers import TELEMETRY

CONFIG = ArmConfig(BusConfig("offline", 1000000, 2.0, (1, 2, 3, 4, 5)))


def run_fake(config, options, emit, stop):
    return live.run_acquisition(config, options, emit, stop)


@pytest.fixture
def transport(monkeypatch):
    events = []
    @contextmanager
    def fake_open(device, baud):
        events.append("open")
        try:
            yield None, OfflinePacket()
        finally:
            events.append("closed")
    monkeypatch.setattr(live, "open_bus", fake_open)
    def fake_reader(port, packet):
        reader = SdkReader(port, packet)
        monkeypatch.setattr(reader, "telemetry", lambda ids, mode: tuple(
            decode_telemetry(mid, reader.registers(mid, TELEMETRY)) for mid in ids
        ))
        return reader
    monkeypatch.setattr(live, "SdkReader", fake_reader)
    return events


def test_constructor_and_status_do_not_open_port(tmp_path, transport):
    monitor = live.LiveMonitor(CONFIG, tmp_path)
    assert monitor.snapshot().state == "idle"
    assert monitor.snapshot().port_closed is True
    assert transport == []
    with pytest.raises(FrozenInstanceError):
        monitor.snapshot().state = "running"

def test_http_origin_and_unknown_actions_do_not_acquire(tmp_path, transport):
    from http.client import HTTPConnection
    from http.server import ThreadingHTTPServer

    from arm_observer.live_http import handler_for
    monitor = live.LiveMonitor(CONFIG, tmp_path)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(monitor, 8085))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        conn = HTTPConnection("127.0.0.1", server.server_port, timeout=2)
        conn.request("GET", "/api/status")
        response = conn.getresponse()
        assert response.status == 200
        assert json.loads(response.read())["state"] == "idle"
        conn.request("POST", "/api/start", '{"duration_seconds":0}',
                     {"Origin": "https://elsewhere.invalid", "Content-Type": "application/json"})
        response = conn.getresponse()
        assert response.status == 403
        response.read()
        for path, body in [("/api/write", "{}"), ("/api/start", '{"torque":true}')]:
            conn.request("POST", path, body)
            response = conn.getresponse()
            assert response.status == 400
            response.read()
        assert transport == []
    finally:
        conn.close()
        server.shutdown()
        server.server_close()
        thread.join(2)

def test_finite_run_closes_and_writes_v2_end(tmp_path, transport):
    monitor = live.LiveMonitor(CONFIG, tmp_path)
    monitor.start(0.1)
    assert monitor.join(3)
    status = monitor.snapshot()
    assert status.state == "stopped" and status.port_closed is True, status.error
    assert status.metadata and status.frame
    assert status.summary.frames >= 1
    assert transport == ["open", "closed"]
    records = [json.loads(line) for line in status.log_path.read_text().splitlines()]
    assert records[0]["kind"] == "metadata"
    assert records[-1]["kind"] == "end"
    assert records[-1]["summary"]["port_closed"]
    assert all(record["schema_version"] == 2 for record in records)


def test_stop_cancels_continuous_run_and_new_session(tmp_path, transport):
    monitor = live.LiveMonitor(CONFIG, tmp_path)
    first = monitor.start(0.0).session_id
    with pytest.raises(ValueError, match="running"):
        monitor.start(0.0)
    monitor.stop()
    assert monitor.join(3)
    assert monitor.snapshot().port_closed is True
    second = monitor.start(0.1).session_id
    assert monitor.join(3)
    assert second != first
    assert transport.count("open") == transport.count("closed")


def test_stop_pending_is_not_reported_closed(tmp_path):
    entered, release = threading.Event(), threading.Event()
    def held(config, options, emit, stop):
        entered.set()
        release.wait(3)
        return live.empty_summary(port_closed=True)
    monitor = live.LiveMonitor(CONFIG, tmp_path, acquire=held)
    monitor.start(0.0)
    assert entered.wait(1)
    monitor.stop()
    assert monitor.snapshot().state == "stopping"
    assert monitor.snapshot().port_closed is False
    release.set()
    assert monitor.join(3)
    assert monitor.snapshot().port_closed is True


def test_busy_error_has_no_frame_and_no_retry(tmp_path, monkeypatch):
    calls = []
    @contextmanager
    def busy(*args):
        calls.append(1)
        raise RuntimeError("Port owned by 123")
        yield
    monkeypatch.setattr(live, "open_bus", busy)
    monitor = live.LiveMonitor(CONFIG, tmp_path)
    monitor.start(0.1)
    assert monitor.join(3)
    status = monitor.snapshot()
    assert status.state == "error"
    assert "owned by 123" in status.error
    assert status.frame is None
    assert calls == [1]


def test_cancel_before_first_frame(monkeypatch):
    stop = threading.Event()
    stop.set()
    frames = []
    summary = observe(SdkReader(None, OfflinePacket()), CONFIG, PollOptions(),
                      frames.append, stop_event=stop)
    assert summary.frames == 0
    assert summary.interrupted


@pytest.mark.parametrize("duration", [-1.0, float("nan"), True])
def test_invalid_start_has_no_hardware(tmp_path, transport, duration):
    monitor = live.LiveMonitor(CONFIG, tmp_path)
    with pytest.raises((ValueError, TypeError)):
        monitor.start(duration)
    assert transport == []
