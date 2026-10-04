"""D19 one return-only ID2 output revision; other scoped limits remain unchanged."""
import argparse
from dataclasses import replace
from functools import partial
from pathlib import Path

from cap_grasp_probe import capture_pair
from cap_grasp_stages import WideRecoveryController

from arm_observer.photo_session import (
    ARM_CONFIG,
    load_previous_plan,
    photo_device,
    stop_handler,
    write_event,
)
from arm_observer.standby_motion import open_standby_bus


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resume-log", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    with (args.output / "events.jsonl").open("x") as log:
        with open_standby_bus(photo_device(ARM_CONFIG, None)) as (port, packet):
            c = WideRecoveryController(port, packet, partial(write_event, log),
                                       stop_requested=stop_handler())
            c.prepare_photo(resume=load_previous_plan(args.resume_log, held=True))
            if not args.execute:
                return 0
            try:
                c.stage = "observed_stopped_hold"
                c.hold()
                capture_pair(args.output, "before-output-revision", c)
                port.envelopes[2] = replace(port.envelopes[2],
                                            goal_pwm=frozenset({350, 395, 885}))
                c.write(2, "pwm", 395)
                if c.read(2, ("goal_pwm",))["goal_pwm"] != 395:
                    raise RuntimeError("Revised output readback failed")
                c.return_and_release()
                capture_pair(args.output, "returned-off", c)
                return 0
            except Exception as error:
                c.freeze(f"{type(error).__name__}: {error}")
                if 2 in c.enabled:
                    c.write(2, "pwm", 350)
                    if c.read(2, ("goal_pwm",))["goal_pwm"] != 350:
                        c.event("output_restoration_fault", motor_id=2)
                return 2


if __name__ == "__main__":
    raise SystemExit(main())
