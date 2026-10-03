"""Pure inspection rules; they never change settings."""

from collections.abc import Iterable

from arm_observer.models import (
    Finding,
    FrameEvent,
    MetadataEvent,
    MotorMetadata,
    MotorTelemetry,
    TelemetryFrame,
)


def configuration_findings(motor: MotorMetadata) -> tuple[Finding, ...]:
    notes = []
    drive_mode = motor.value("drive_mode")
    velocity_profile = drive_mode is not None and drive_mode & 4 == 0
    if motor.faults:
        notes.append(
            Finding(
                motor.motor_id,
                "error",
                "metadata_incomplete",
                "Metadata contains communication or model errors",
            )
        )
    rules = (
        (
            motor.value("min_position_limit") == 0 and motor.value("max_position_limit") == 4095,
            "full_turn_limits",
            "Position limits span a full turn; joint limits are unverified",
        ),
        (motor.value("bus_watchdog") == 0, "watchdog_disabled", "Bus Watchdog is disabled"),
        (
            velocity_profile and motor.value("profile_velocity") == 0,
            "unbounded_velocity_profile",
            "Profile Velocity=0 provides no finite profile limit",
        ),
        (
            velocity_profile and motor.value("profile_acceleration") == 0,
            "unbounded_acceleration_profile",
            "Profile Acceleration=0 provides no finite limit",
        ),
    )
    notes.extend(
        Finding(motor.motor_id, "info", code, message)
        for matched, code, message in rules
        if matched
    )
    return tuple(notes)


def telemetry_findings(motor: MotorTelemetry) -> tuple[Finding, ...]:
    rules = (
        (not motor.complete, "error", "telemetry_incomplete", "Some telemetry values are unknown"),
        (motor.torque_enabled is True, "warning", "torque_on", "Torque is ON; no change was sent"),
        (motor.hardware_error not in (None, 0), "error", "hardware_error", "Hardware fault is set"),
        (motor.device_alert, "warning", "device_alert", "Device status packet contains Alert"),
    )
    return tuple(
        Finding(motor.motor_id, level, code, message)
        for matched, level, code, message in rules
        if matched
    )


def position_findings(frames: tuple[TelemetryFrame, ...]) -> tuple[Finding, ...]:
    if not frames:
        return ()
    notes = []
    for motor in frames[0].motors:
        positions = tuple(
            item.position_counts
            for frame in frames
            for item in frame.motors
            if item.motor_id == motor.motor_id and item.position_counts is not None
        )
        if positions and max(positions) != min(positions):
            notes.append(
                Finding(
                    motor.motor_id,
                    "info",
                    "position_changed",
                    f"Observed position span: {max(positions) - min(positions)} counts",
                )
            )
    return tuple(notes)


def unique_findings(findings: Iterable[Finding]) -> tuple[Finding, ...]:
    unique: list[Finding] = []
    for finding in findings:
        if finding not in unique:
            unique.append(finding)
    return tuple(unique)


def inspect_findings(
    metadata: MetadataEvent, frames: tuple[TelemetryFrame, ...]
) -> tuple[Finding, ...]:
    config_notes = tuple(
        note for motor in metadata.metadata for note in configuration_findings(motor)
    )
    telemetry_notes = tuple(
        note for frame in frames for motor in frame.motors for note in telemetry_findings(motor)
    )
    return unique_findings((*config_notes, *telemetry_notes, *position_findings(frames)))


def frame_lines(event: FrameEvent) -> tuple[str, ...]:
    frame = event.frame
    lines = [
        f"frame={frame.sequence} {frame.finished_at} "
        f"read_ms={frame.duration_ms:.2f} late={frame.deadline_missed}"
    ]
    for motor in frame.motors:
        lines.append(
            f"  id={motor.motor_id} torque={motor.torque_enabled} "
            f"position={motor.position_counts} rpm={motor.velocity_rpm} "
            f"voltage={motor.voltage_v} temp={motor.temperature_c} "
            f"error={motor.hardware_error} valid={motor.complete}"
        )
    return tuple(lines)
