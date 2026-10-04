"""Release the interrupted photo session only after external weight support is confirmed."""

import argparse
import signal
from functools import partial
from pathlib import Path

from arm_observer.photo_session import ARM_CONFIG, load_previous_plan, photo_device, write_event
from arm_observer.pose_capture_motion import PhotoController
from arm_observer.standby_motion import IDS, open_standby_bus


def release_supported(controller, *, support_confirmed):
    if not support_confirmed or controller.plan is None or controller.enabled != set(IDS):
        raise RuntimeError("External weight support and verified held session required")
    controller.stage = "externally_supported_release"
    controller.sample()
    for mid in reversed(IDS):
        off_motor(controller, mid)
    # Verify all five again before restoring settings that include unlimited profiles.
    if any(controller.read(mid, ("torque_enable",))["torque_enable"] for mid in IDS):
        raise RuntimeError("All-five OFF unconfirmed; RAM restoration skipped")
    for mid in IDS:
        count = controller.read(mid, ("present_position",))["present_position"]
        controller.write(mid, "goal", count)
    controller.restore_ram(IDS)
    controller.event("external_supported_release", all_torque_off=True, ram_restored=True)


def off_motor(controller, mid):
    for _ in range(3):
        controller.port.is_using = False
        try:
            controller.write(mid, "torque", 0)
        except Exception as exc:
            controller.safe_event("off_write_error", motor_id=mid, error=str(exc))
        if controller.read(mid, ("torque_enable",))["torque_enable"] == 0:
            controller.enabled.remove(mid)
            return
    raise RuntimeError(f"ID{mid} OFF unconfirmed; RAM restoration skipped")


def main(controller_type=PhotoController, resume_loader=load_previous_plan):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resume-log", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--support-confirmed", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--config", type=Path, default=ARM_CONFIG)
    parser.add_argument("--device")
    args = parser.parse_args()
    if args.execute and not args.support_confirmed:
        parser.error("External weight support must be confirmed before release")
    interrupted = [False]

    def record_signal(_signum, _frame):
        interrupted[0] = True

    for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(signum, record_signal)
    resume = resume_loader(args.resume_log, held=True)
    args.output.mkdir(parents=True, exist_ok=False)
    with (args.output / "events.jsonl").open("x") as log:
        with open_standby_bus(photo_device(args.config, args.device)) as (
            port,
            packet,
        ):
            controller = controller_type(port, packet, partial(write_event, log))
            controller.prepare_photo(resume)
            if args.execute:
                release_supported(controller, support_confirmed=args.support_confirmed)
                if interrupted[0]:
                    controller.safe_event("signal_recorded_during_supported_release")


if __name__ == "__main__":
    main()
