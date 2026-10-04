"""D19 held-gripper release only after actual external weight support is confirmed."""
import json
from pathlib import Path

from cap_grasp_probe import ProbeController
from cap_grasp_stages import WideRecoveryController

from arm_observer.motion_guard import MotionViolation
from arm_observer.photo_session import holding_goals, load_previous_plan
from arm_observer.photo_supported_release import main


class SupportedGripperReleaseController(ProbeController):
    # Match the recorded held family's fresh-read window, including the observed ID4
    # sag; the reused release routine parks present counts only after all-five OFF.
    window_offsets = WideRecoveryController.window_offsets

    def write(self, mid, name, value):
        if name == "torque" and value != 0:
            raise MotionViolation("Supported release cannot enable torque")
        if self.enabled and (name != "torque" or value != 0):
            raise MotionViolation("All-five OFF required before goal parking or RAM restoration")
        return super().write(mid, name, value)


def load_supported_plan(path, *, held=False):
    events = [json.loads(line) for line in Path(path).read_text().splitlines()]
    last = events[-1]
    # The recorded failed395 return restores ID2 PWM350 after the five park writes.
    # Accept only this explicit trailing restore; keep the strict five-park validator
    # and all later fresh hardware/profile/goal checks. Never rewrite the failed log.
    if held and all(last.get(k) == v for k, v in {
        "kind": "write", "motor_id": 2, "name": "pwm", "value": 350
    }.items()):
        plan = next(e for e in events if e["kind"] == "plan")
        return {**plan, "holding_goals": holding_goals(events[:-1])}
    return load_previous_plan(path, held=held)


if __name__ == "__main__":
    main(controller_type=SupportedGripperReleaseController, resume_loader=load_supported_plan)
