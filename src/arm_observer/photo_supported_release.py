"""Release the interrupted photo session only after external weight support is confirmed."""

import argparse
import json
import signal
from pathlib import Path

from arm_observer.pose_capture_motion import PhotoController
from arm_observer.standby_motion import IDS, open_standby_bus


def release_supported(controller, *, support_confirmed):
    if not support_confirmed or controller.plan is None or controller.enabled != set(IDS):
        raise RuntimeError("External weight support and verified held session required")
    controller.stage = "externally_supported_release"
    controller.sample()
    for mid in reversed(IDS):
        confirmed = False
        for _ in range(3):
            controller.port.is_using = False
            try:
                controller.write(mid, "torque", 0)
            except Exception as exc:
                controller.safe_event("off_write_error", motor_id=mid, error=str(exc))
            if controller.read(mid, ("torque_enable",))["torque_enable"] == 0:
                controller.enabled.remove(mid)
                confirmed = True
                break
        if not confirmed:
            raise RuntimeError(f"ID{mid} OFF unconfirmed; RAM restoration skipped")
    # Verify all five again before restoring settings that include unlimited profiles.
    if any(controller.read(mid, ("torque_enable",))["torque_enable"] for mid in IDS):
        raise RuntimeError("All-five OFF unconfirmed; RAM restoration skipped")
    for mid in IDS:
        count = controller.read(mid, ("present_position",))["present_position"]
        controller.write(mid, "goal", count)
        for name, register in (
            ("pwm", "goal_pwm"),
            ("velocity", "profile_velocity"),
            ("acceleration", "profile_acceleration"),
        ):
            controller.write(mid, name, controller.saved[mid][register])
            if controller.read(mid, (register,))[register] != controller.saved[mid][register]:
                raise RuntimeError(f"ID{mid} {register} RAM restore mismatch")
    controller.event("external_supported_release", all_torque_off=True, ram_restored=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resume-log", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--support-confirmed", action="store_true")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if args.execute and not args.support_confirmed:
        parser.error("External weight support must be confirmed before release")
    interrupted = [False]
    def record_signal(_signum, _frame):
        interrupted[0] = True
    for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(signum, record_signal)
    events = [json.loads(line) for line in args.resume_log.read_text().splitlines()]
    resume = next(e for e in events if e["kind"] == "plan")
    last = max(i for i, e in enumerate(events) if e["kind"] == "stop")
    writes = events[last + 1:]
    if events[last]["enabled"] != list(IDS) or len(writes) != 5 or any(
        e["kind"] != "write" or e["name"] != "goal" for e in writes
    ) or {e["motor_id"] for e in writes} != set(IDS):
        raise RuntimeError("Interrupted five-motor holding evidence is incomplete")
    resume["holding_goals"] = {e["motor_id"]: e["value"] for e in writes}
    args.output.mkdir(parents=True, exist_ok=False)
    with (args.output / "events.jsonl").open("x") as log:
        def emit(event):
            log.write(json.dumps(event, ensure_ascii=False) + "\n")
            log.flush()
            if event["kind"] != "sample":
                print(json.dumps(event, ensure_ascii=False), flush=True)
        with open_standby_bus(
            "/dev/serial/by-id/usb-BestTechnology_E148_E148-if00-port0"
        ) as (port, packet):
            controller = PhotoController(port, packet, emit)
            controller.prepare_photo(resume)
            if args.execute:
                release_supported(controller, support_confirmed=args.support_confirmed)
                if interrupted[0]:
                    controller.safe_event("signal_recorded_during_supported_release")


if __name__ == "__main__":
    main()
