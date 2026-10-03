"""XL430-W250 control table; model number 1060 only."""

from dataclasses import dataclass

SOURCE = "https://emanual.robotis.com/docs/en/dxl/x/xl430-w250/"
BAUDRATES = {
    0: 9600,
    1: 57600,
    2: 115200,
    3: 1000000,
    4: 2000000,
    5: 3000000,
    6: 4000000,
    7: 4500000,
}
ERROR_BITS = {
    0: "input_voltage",
    2: "overheating",
    3: "motor_encoder",
    4: "electrical_shock",
    5: "overload",
}


@dataclass(frozen=True)
class Register:
    name: str
    address: int
    size: int
    signed: bool = False
    minimum_firmware: int = 0

    def decode(self, raw: int) -> int:
        bits = self.size * 8
        return raw - (1 << bits) if self.signed and raw & (1 << (bits - 1)) else raw

    @property
    def memory(self) -> str:
        return "EEPROM" if self.address < 64 else "RAM"


REGISTERS = (
    Register("model_number", 0, 2),
    Register("model_information", 2, 4),
    Register("firmware_version", 6, 1),
    Register("id", 7, 1),
    Register("baud_rate", 8, 1),
    Register("return_delay_time", 9, 1),
    Register("drive_mode", 10, 1),
    Register("operating_mode", 11, 1),
    Register("secondary_id", 12, 1),
    Register("protocol_type", 13, 1),
    Register("homing_offset", 20, 4, True),
    Register("moving_threshold", 24, 4),
    Register("temperature_limit", 31, 1),
    Register("max_voltage_limit", 32, 2),
    Register("min_voltage_limit", 34, 2),
    Register("pwm_limit", 36, 2),
    Register("velocity_limit", 44, 4),
    Register("max_position_limit", 48, 4),
    Register("min_position_limit", 52, 4),
    Register("startup_configuration", 60, 1, minimum_firmware=45),
    Register("shutdown", 63, 1),
    Register("torque_enable", 64, 1),
    Register("led", 65, 1),
    Register("status_return_level", 68, 1),
    Register("registered_instruction", 69, 1),
    Register("hardware_error_status", 70, 1),
    Register("velocity_i_gain", 76, 2),
    Register("velocity_p_gain", 78, 2),
    Register("position_d_gain", 80, 2),
    Register("position_i_gain", 82, 2),
    Register("position_p_gain", 84, 2),
    Register("feedforward_2nd_gain", 88, 2),
    Register("feedforward_1st_gain", 90, 2),
    Register("bus_watchdog", 98, 1, True),
    Register("goal_pwm", 100, 2, True),
    Register("goal_velocity", 104, 4, True),
    Register("profile_acceleration", 108, 4),
    Register("profile_velocity", 112, 4),
    Register("goal_position", 116, 4, True),
    Register("realtime_tick", 120, 2),
    Register("moving", 122, 1),
    Register("moving_status", 123, 1),
    Register("present_pwm", 124, 2, True),
    Register("present_load", 126, 2, True),
    Register("present_velocity", 128, 4, True),
    Register("present_position", 132, 4, True),
    Register("velocity_trajectory", 136, 4, True),
    Register("position_trajectory", 140, 4, True),
    Register("present_input_voltage", 144, 2),
    Register("present_temperature", 146, 1),
    Register("backup_ready", 147, 1, minimum_firmware=45),
)
BY_NAME = {register.name: register for register in REGISTERS}
TELEMETRY_NAMES = (
    "torque_enable",
    "hardware_error_status",
    "moving",
    "moving_status",
    "present_pwm",
    "present_load",
    "present_velocity",
    "present_position",
    "present_input_voltage",
    "present_temperature",
)
TELEMETRY = tuple(BY_NAME[name] for name in TELEMETRY_NAMES)
