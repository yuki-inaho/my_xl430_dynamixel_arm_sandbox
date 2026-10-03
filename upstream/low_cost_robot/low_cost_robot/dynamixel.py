from __future__ import annotations
import math
import os
import time
from dataclasses import dataclass
import enum

from dynamixel_sdk import *


def to_signed32(value: int) -> int:
    if value > 2**31:
        value -= 2**32
    return value


class ReadAttribute(enum.Enum):
    TEMPERATURE = 146
    VOLTAGE = 145
    VELOCITY = 128
    POSITION = 132
    CURRENT = 126
    PWM = 124
    HARDWARE_ERROR_STATUS = 70
    HOMING_OFFSET = 20
    BAUDRATE = 8


class OperatingMode(enum.Enum):
    VELOCITY = 1
    POSITION = 3
    CURRENT_CONTROLLED_POSITION = 5
    PWM = 16
    UNKNOWN = -1


_BAUDRATE_MAP = {
    57600: 1,
    1_000_000: 3,
    2_000_000: 4,
    3_000_000: 5,
    4_000_000: 6,
}


class Dynamixel:
    ADDR_TORQUE_ENABLE = 64
    ADDR_GOAL_POSITION = 116
    ADDR_VELOCITY_LIMIT = 44
    ADDR_GOAL_PWM = 100
    OPERATING_MODE_ADDR = 11
    POSITION_I = 82
    POSITION_P = 84
    ADDR_ID = 7

    @dataclass
    class Config:
        baudrate: int = 57600
        protocol_version: float = 2.0
        device_name: str = ""
        dynamixel_id: int = 1

        def instantiate(self) -> Dynamixel:
            return Dynamixel(self)

    def __init__(self, config: Config):
        self.config = config
        self.connect()

    def connect(self):
        if self.config.device_name == "":
            for port_name in os.listdir("/dev"):
                if "ttyUSB" in port_name or "ttyACM" in port_name:
                    self.config.device_name = "/dev/" + port_name
                    print(f"using device {self.config.device_name}")
        self.portHandler = PortHandler(self.config.device_name)
        self.packetHandler = PacketHandler(self.config.protocol_version)
        if not self.portHandler.openPort():
            raise Exception(f"Failed to open port {self.config.device_name}")
        if not self.portHandler.setBaudRate(self.config.baudrate):
            raise Exception(f"Failed to set baudrate to {self.config.baudrate}")
        self.operating_modes: list[OperatingMode | None] = [None] * 32
        self.torque_enabled: list[bool | None] = [None] * 32

    def disconnect(self):
        self.portHandler.closePort()

    # --- Goal commands ---

    def set_goal_position(self, motor_id: int, goal_position: int):
        self.packetHandler.write4ByteTxRx(
            self.portHandler, motor_id, self.ADDR_GOAL_POSITION, goal_position
        )

    def set_pwm_value(self, motor_id: int, pwm_value: int, tries: int = 3):
        if self.operating_modes[motor_id] is not OperatingMode.PWM:
            self._disable_torque(motor_id)
            self.set_operating_mode(motor_id, OperatingMode.PWM)
        if not self.torque_enabled[motor_id]:
            self._enable_torque(motor_id)
        dxl_comm_result, dxl_error = self.packetHandler.write2ByteTxRx(
            self.portHandler, motor_id, self.ADDR_GOAL_PWM, pwm_value
        )
        if dxl_comm_result != COMM_SUCCESS:
            if tries <= 1:
                raise ConnectionError(
                    f"dxl_comm_result: {self.packetHandler.getTxRxResult(dxl_comm_result)}"
                )
            print(f"dynamixel pwm setting failure, retrying ({tries - 1} left)")
            self.set_pwm_value(motor_id, pwm_value, tries=tries - 1)
        elif dxl_error != 0:
            raise ConnectionError(
                f"dynamixel error: {self.packetHandler.getRxPacketError(dxl_error)}"
            )

    # --- Read commands ---

    def read_temperature(self, motor_id: int):
        return self._read_value(motor_id, ReadAttribute.TEMPERATURE, 1)

    def read_velocity(self, motor_id: int):
        return to_signed32(self._read_value(motor_id, ReadAttribute.VELOCITY, 4))

    def read_position(self, motor_id: int):
        return to_signed32(self._read_value(motor_id, ReadAttribute.POSITION, 4))

    def read_position_degrees(self, motor_id: int) -> float:
        return (self.read_position(motor_id) / 4096) * 360

    def read_position_radians(self, motor_id: int) -> float:
        return (self.read_position(motor_id) / 4096) * 2 * math.pi

    def read_current(self, motor_id: int):
        current = self._read_value(motor_id, ReadAttribute.CURRENT, 2)
        if current > 2**15:
            current -= 2**16
        return current

    def read_present_pwm(self, motor_id: int):
        return self._read_value(motor_id, ReadAttribute.PWM, 2)

    def read_hardware_error_status(self, motor_id: int):
        return self._read_value(motor_id, ReadAttribute.HARDWARE_ERROR_STATUS, 1)

    # --- Configuration ---

    def set_id(self, old_id: int, new_id: int, use_broadcast_id: bool = False):
        current_id = 254 if use_broadcast_id else old_id
        dxl_comm_result, dxl_error = self.packetHandler.write1ByteTxRx(
            self.portHandler, current_id, self.ADDR_ID, new_id
        )
        self._process_response(dxl_comm_result, dxl_error, old_id)
        self.config.dynamixel_id = new_id

    def set_operating_mode(self, motor_id: int, operating_mode: OperatingMode):
        dxl_comm_result, dxl_error = self.packetHandler.write2ByteTxRx(
            self.portHandler, motor_id, self.OPERATING_MODE_ADDR, operating_mode.value
        )
        self._process_response(dxl_comm_result, dxl_error, motor_id)
        self.operating_modes[motor_id] = operating_mode

    def set_pwm_limit(self, motor_id: int, limit: int):
        dxl_comm_result, dxl_error = self.packetHandler.write2ByteTxRx(
            self.portHandler, motor_id, 36, limit
        )
        self._process_response(dxl_comm_result, dxl_error, motor_id)

    def set_velocity_limit(self, motor_id: int, velocity_limit: int):
        dxl_comm_result, dxl_error = self.packetHandler.write4ByteTxRx(
            self.portHandler, motor_id, self.ADDR_VELOCITY_LIMIT, velocity_limit
        )
        self._process_response(dxl_comm_result, dxl_error, motor_id)

    def set_P(self, motor_id: int, P: int):
        dxl_comm_result, dxl_error = self.packetHandler.write2ByteTxRx(
            self.portHandler, motor_id, self.POSITION_P, P
        )
        self._process_response(dxl_comm_result, dxl_error, motor_id)

    def set_I(self, motor_id: int, I: int):
        dxl_comm_result, dxl_error = self.packetHandler.write2ByteTxRx(
            self.portHandler, motor_id, self.POSITION_I, I
        )
        self._process_response(dxl_comm_result, dxl_error, motor_id)

    def set_baudrate(self, motor_id: int, baudrate: int):
        if baudrate not in _BAUDRATE_MAP:
            raise ValueError(f"Unsupported baudrate: {baudrate}")
        self._disable_torque(motor_id)
        dxl_comm_result, dxl_error = self.packetHandler.write1ByteTxRx(
            self.portHandler, motor_id, ReadAttribute.BAUDRATE.value, _BAUDRATE_MAP[baudrate]
        )
        self._process_response(dxl_comm_result, dxl_error, motor_id)

    # --- Homing ---

    def read_home_offset(self, motor_id: int):
        self._disable_torque(motor_id)
        home_offset = self._read_value(motor_id, ReadAttribute.HOMING_OFFSET, 4)
        self._enable_torque(motor_id)
        return home_offset

    def set_home_offset(self, motor_id: int, home_position: int):
        self._disable_torque(motor_id)
        dxl_comm_result, dxl_error = self.packetHandler.write4ByteTxRx(
            self.portHandler, motor_id, ReadAttribute.HOMING_OFFSET.value, home_position
        )
        self._process_response(dxl_comm_result, dxl_error, motor_id)
        self._enable_torque(motor_id)

    def set_home_position(self, motor_id: int):
        print(f"setting home position for motor {motor_id}")
        self.set_home_offset(motor_id, 0)
        current_position = self.read_position(motor_id)
        print(f"position before {current_position}")
        self.set_home_offset(motor_id, -current_position)
        current_position = self.read_position(motor_id)
        print(f"position after {current_position}")

    # --- Torque control ---

    def _enable_torque(self, motor_id: int):
        dxl_comm_result, dxl_error = self.packetHandler.write1ByteTxRx(
            self.portHandler, motor_id, self.ADDR_TORQUE_ENABLE, 1
        )
        self._process_response(dxl_comm_result, dxl_error, motor_id)
        self.torque_enabled[motor_id] = True

    def _disable_torque(self, motor_id: int):
        dxl_comm_result, dxl_error = self.packetHandler.write1ByteTxRx(
            self.portHandler, motor_id, self.ADDR_TORQUE_ENABLE, 0
        )
        self._process_response(dxl_comm_result, dxl_error, motor_id)
        self.torque_enabled[motor_id] = False

    # --- Internal helpers ---

    def _process_response(self, dxl_comm_result: int, dxl_error: int, motor_id: int):
        if dxl_comm_result != COMM_SUCCESS:
            raise ConnectionError(
                f"dxl_comm_result for motor {motor_id}: "
                f"{self.packetHandler.getTxRxResult(dxl_comm_result)}"
            )
        # voltage error (128) is expected when 5V motors run at 12V
        if dxl_error != 0 and dxl_error != 128:
            raise ConnectionError(
                f"dynamixel error for motor {motor_id}: "
                f"{self.packetHandler.getRxPacketError(dxl_error)}"
            )

    _READ_FN_ATTR = {1: "read1ByteTxRx", 2: "read2ByteTxRx", 4: "read4ByteTxRx"}

    def _read_value(self, motor_id: int, attribute: ReadAttribute, num_bytes: int, tries: int = 10):
        read_fn = getattr(self.packetHandler, self._READ_FN_ATTR[num_bytes])
        try:
            value, dxl_comm_result, dxl_error = read_fn(
                self.portHandler, motor_id, attribute.value
            )
        except Exception:
            if tries <= 1:
                raise
            return self._read_value(motor_id, attribute, num_bytes, tries=tries - 1)
        if dxl_comm_result != COMM_SUCCESS:
            if tries <= 1:
                raise ConnectionError(
                    f"dxl_comm_result {dxl_comm_result} for servo {motor_id}"
                )
            print(
                f"dynamixel read failure for servo {motor_id} on {self.config.device_name}, "
                f"retrying ({tries - 1} left)"
            )
            return self._read_value(motor_id, attribute, num_bytes, tries=tries - 1)
        if dxl_error != 0 and dxl_error != 128:
            if tries <= 1:
                raise ConnectionError(f"dxl_error {dxl_error} for motor {motor_id}")
            return self._read_value(motor_id, attribute, num_bytes, tries=tries - 1)
        return value


if __name__ == "__main__":
    dynamixel = Dynamixel.Config(
        baudrate=1_000_000,
        device_name="/dev/tty.usbmodem57380045631",
    ).instantiate()
    motor_id = 1
    for _ in range(10):
        s = time.monotonic()
        pos = dynamixel.read_position(motor_id)
        delta = time.monotonic() - s
        print(f"read position took {delta}")
        print(f"position {pos}")
