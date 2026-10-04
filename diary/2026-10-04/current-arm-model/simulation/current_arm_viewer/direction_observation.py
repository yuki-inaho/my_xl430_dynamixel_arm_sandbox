"""Paired observations of an explicitly reported manual change. No motor commands."""
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime

try:
    from . import live_input
except ImportError:
    import live_input

# Smaller changes are encoder jitter-sized (ID1 spanned 3 counts at rest on 2026-10-03);
# a quarter turn or more risks sign aliasing in mode 3. Both are reported as undetermined.
MIN_DIRECTION_COUNTS = 20
MAX_DIRECTION_COUNTS = 1024


@dataclass(frozen=True, slots=True)
class DirectionSample:
    motor_id: int
    position_counts: int
    finished_at: str
    sequence: int
    mode: int
    session_id: str
    context_fingerprint: str
    simulated: bool
    physical_confirmed: bool


@dataclass(frozen=True, slots=True)
class DirectionEvidence:
    before: DirectionSample
    after: DirectionSample
    delta_counts: int
    degrees_signed: float
    opening_count_sign: int
    physical_change_confirmed: bool
    physical_change_reported: str = "opening"
    scope_note: str = ("opening_count_sign is the encoder count direction during the "
                       "user-reported opening; it is not a CAD calibration sign")


def capture(snapshot, motor_id, physical_confirmed, model_dir):
    if physical_confirmed is not True:
        raise ValueError("現物の位置・関節を先に確認してください")
    return sample(snapshot, motor_id, physical_confirmed, model_dir)


def sample(snapshot, motor_id, physical_confirmed, model_dir):
    if snapshot is None:
        raise ValueError("READ未接続・停止中（方向は未確定）")
    motor_id = live_input.integer(motor_id, 0, 252)
    frame, motors, metadata = live_input.validated_snapshot(snapshot)
    if motor_id not in motors:
        raise ValueError("Motor ID not in fresh READ")
    if motors[motor_id]["torque_enabled"] is not False:
        raise ValueError("手動観察はTorque OFFの読値だけを記録します")
    context = live_input.current_context(snapshot, model_dir)
    selected = next(m for m in context["motors"] if m["motor_id"] == motor_id)
    fingerprint = hashlib.sha256(json.dumps(
        {"motor": selected, "model": context["model_signature"]}, sort_keys=True
    ).encode()).hexdigest()
    return DirectionSample(
        motor_id, motors[motor_id]["position_counts"], frame["finished_at"],
        live_input.integer(frame["sequence"], 0, 2**63-1),
        live_input.metadata_values(metadata[motor_id])["operating_mode"],
        snapshot["session_id"], fingerprint, snapshot.get("simulated") is True,
        physical_confirmed,
    )


def compare(before, snapshot, physical_change_confirmed, model_dir):
    if before is None or before.physical_confirmed is not True:
        raise ValueError("先に畳んだ位置を記録してください")
    if physical_change_confirmed is not True:
        raise ValueError("肘を開いた変化の現物確認がありません（方向は未確定）")
    after = sample(snapshot, before.motor_id, physical_change_confirmed, model_dir)
    if (before.session_id != after.session_id
        or before.context_fingerprint != after.context_fingerprint
        or before.simulated != after.simulated):
        raise ValueError("観察中にsession/設定/入力元が変わりました。最初から記録してください")
    if (after.sequence <= before.sequence
        or datetime.fromisoformat(after.finished_at) <= datetime.fromisoformat(before.finished_at)):
        raise ValueError("変化後の新しいREADが必要です")
    delta = after.position_counts - before.position_counts
    if before.mode == 3:
        delta = (delta + 2048) % 4096 - 2048
    if not MIN_DIRECTION_COUNTS <= abs(delta) < MAX_DIRECTION_COUNTS:
        raise ValueError(f"差分{delta} countでは増減の方向は未確定です"
                         f"（{MIN_DIRECTION_COUNTS}以上{MAX_DIRECTION_COUNTS}未満が必要）")
    return DirectionEvidence(before, after, delta, delta*360/4096, 1 if delta > 0 else -1,
                             after.physical_confirmed)
