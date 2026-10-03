"""Read-only live acquisition. No port is opened by construction or status queries."""
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from threading import Event, Lock, Thread
from uuid import uuid4

from arm_observer.bus import open_bus
from arm_observer.models import ArmConfig, EndEvent, FrameEvent, MetadataEvent, StreamSummary
from arm_observer.observer import PollOptions, observe
from arm_observer.output import JsonlSink, report_stem
from arm_observer.reader import SdkReader

StreamEvent = MetadataEvent | FrameEvent
Acquire = Callable[[ArmConfig, PollOptions, Callable[[StreamEvent], None], Event], StreamSummary]


def empty_summary(port_closed: bool = False) -> StreamSummary:
    return StreamSummary(0, 0, 0, 0.0, 0.0, False, port_closed)


def run_acquisition(
    config: ArmConfig, options: PollOptions, emit: Callable[[StreamEvent], None], stop: Event
) -> StreamSummary:
    with open_bus(config.bus.device, config.bus.baudrate) as (port, packet):
        summary = observe(SdkReader(port, packet), config, options, emit, stop_event=stop)
    return replace(summary, port_closed=True)


@dataclass(frozen=True, slots=True)
class LiveSnapshot:
    state: str = "idle"
    session_id: str | None = None
    port_closed: bool | None = True
    metadata: MetadataEvent | None = None
    frame: FrameEvent | None = None
    summary: StreamSummary | None = None
    log_path: Path | None = None
    error: str | None = None


class LiveMonitor:
    def __init__(self, config: ArmConfig, reports: Path, acquire: Acquire = run_acquisition):
        self.config, self.reports, self.acquire = config, reports, acquire
        self._lock = Lock()
        self._stop = Event()
        self._thread: Thread | None = None
        self._snapshot = LiveSnapshot()

    def snapshot(self) -> LiveSnapshot:
        with self._lock:
            return self._snapshot

    def start(self, duration_seconds: float = 10.0) -> LiveSnapshot:
        if type(duration_seconds) not in (int, float):
            raise ValueError("Duration must be numeric")
        options = PollOptions(duration_seconds=float(duration_seconds))
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                raise ValueError("Already running; wait for port closure")
            self.reports.mkdir(parents=True, exist_ok=True)
            self._snapshot = LiveSnapshot(
                state="starting", session_id=str(uuid4()), port_closed=False,
                log_path=self.reports / (report_stem("live") + ".jsonl"),
            )
            self._stop = Event()
            self._thread = Thread(target=self._run, args=(options,), daemon=True)
            self._thread.start()
            return self._snapshot

    def stop(self) -> LiveSnapshot:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                self._stop.set()
                self._snapshot = replace(self._snapshot, state="stopping")
            return self._snapshot

    def join(self, timeout: float = 10.0) -> bool:
        thread = self._thread
        if thread is not None:
            thread.join(timeout)
        return thread is None or not thread.is_alive()

    def _receive(self, event: StreamEvent) -> None:
        with self._lock:
            fields = {"metadata": event} if isinstance(event, MetadataEvent) else {"frame": event}
            # A stop requested during a read stays visible until the finally block completes.
            state = "stopping" if self._stop.is_set() else "running"
            self._snapshot = replace(self._snapshot, state=state, **fields)

    def _record(self, options: PollOptions, sink: JsonlSink) -> StreamSummary:
        def emit(event: StreamEvent) -> None:
            sink.emit(event)
            self._receive(event)
        return self.acquire(self.config, options, emit, self._stop)

    def _run(self, options: PollOptions) -> None:
        path = self.snapshot().log_path
        summary, error = empty_summary(), None
        try:
            assert path is not None
            with path.open("x", encoding="utf-8") as file:
                sink = JsonlSink(file)
                try:
                    summary = self._record(options, sink)
                except Exception as exc:
                    # No stale success or guessed closure after an exceptional SDK/close failure.
                    error = f"{type(exc).__name__}: {exc}"
                sink.emit(EndEvent(summary))
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        with self._lock:
            self._snapshot = replace(
                self._snapshot, state="error" if error else "stopped",
                summary=summary, port_closed=None if error else summary.port_closed, error=error,
            )

