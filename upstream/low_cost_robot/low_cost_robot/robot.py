from __future__ import annotations
from enum import Enum, auto
from typing import Union

import numpy as np
from dynamixel_sdk import (
    GroupSyncRead,
    GroupSyncWrite,
    DXL_LOBYTE,
    DXL_HIBYTE,
    DXL_LOWORD,
    DXL_HIWORD,
)

from low_cost_robot.robot_base import RobotBase
from low_cost_robot.dynamixel import Dynamixel, OperatingMode, ReadAttribute, to_signed32


class MotorControlType(Enum):
    PWM = auto()
    POSITION_CONTROL = auto()
    DISABLED = auto()
    UNKNOWN = auto()


class Robot(RobotBase):
    def __init__(self, dynamixel: Dynamixel, servo_ids: list[int] | None = None):
        if servo_ids is None:
            servo_ids = [1, 2, 3, 4, 5]
        self.servo_ids = servo_ids
        self.dynamixel = dynamixel

        self.position_reader = GroupSyncRead(
            self.dynamixel.portHandler,
            self.dynamixel.packetHandler,
            ReadAttribute.POSITION.value,
            4,
        )
        for sid in self.servo_ids:
            self.position_reader.addParam(sid)

        self.velocity_reader = GroupSyncRead(
            self.dynamixel.portHandler,
            self.dynamixel.packetHandler,
            ReadAttribute.VELOCITY.value,
            4,
        )
        for sid in self.servo_ids:
            self.velocity_reader.addParam(sid)

        self.pos_writer = GroupSyncWrite(
            self.dynamixel.portHandler,
            self.dynamixel.packetHandler,
            Dynamixel.ADDR_GOAL_POSITION,
            4,
        )
        for sid in self.servo_ids:
            self.pos_writer.addParam(sid, [2048])

        self.pwm_writer = GroupSyncWrite(
            self.dynamixel.portHandler,
            self.dynamixel.packetHandler,
            Dynamixel.ADDR_GOAL_PWM,
            2,
        )
        for sid in self.servo_ids:
            self.pwm_writer.addParam(sid, [2048])

        self._disable_torque()
        self.motor_control_state = MotorControlType.DISABLED

    def read_position(self, tries: int = 2) -> list[float]:
        result = self.position_reader.txRxPacket()
        if result != 0:
            if tries > 0:
                return self.read_position(tries=tries - 1)
            print("failed to read position")
        return [
            to_signed32(self.position_reader.getData(sid, ReadAttribute.POSITION.value, 4))
            for sid in self.servo_ids
        ]

    def read_velocity(self) -> list[float]:
        self.velocity_reader.txRxPacket()
        return [
            to_signed32(self.velocity_reader.getData(sid, ReadAttribute.VELOCITY.value, 4))
            for sid in self.servo_ids
        ]

    def set_goal_pos(self, action) -> None:
        if self.motor_control_state is not MotorControlType.POSITION_CONTROL:
            self._set_position_control()
        for i, motor_id in enumerate(self.servo_ids):
            data_write = [
                DXL_LOBYTE(DXL_LOWORD(action[i])),
                DXL_HIBYTE(DXL_LOWORD(action[i])),
                DXL_LOBYTE(DXL_HIWORD(action[i])),
                DXL_HIBYTE(DXL_HIWORD(action[i])),
            ]
            self.pos_writer.changeParam(motor_id, data_write)
        self.pos_writer.txPacket()

    def set_pwm(self, action) -> None:
        if self.motor_control_state is not MotorControlType.PWM:
            self._set_pwm_control()
        for i, motor_id in enumerate(self.servo_ids):
            data_write = [
                DXL_LOBYTE(DXL_LOWORD(action[i])),
                DXL_HIBYTE(DXL_LOWORD(action[i])),
            ]
            self.pwm_writer.changeParam(motor_id, data_write)
        self.pwm_writer.txPacket()

    def set_trigger_torque(self) -> None:
        self.dynamixel._enable_torque(self.servo_ids[-1])
        self.dynamixel.set_pwm_value(self.servo_ids[-1], 200)

    def limit_pwm(self, limit: Union[int, list, np.ndarray]) -> None:
        if isinstance(limit, int):
            limits = [limit] * len(self.servo_ids)
        else:
            limits = limit
        self._disable_torque()
        for motor_id, lim in zip(self.servo_ids, limits):
            self.dynamixel.set_pwm_limit(motor_id, lim)
        self._enable_torque()

    def _disable_torque(self):
        for motor_id in self.servo_ids:
            self.dynamixel._disable_torque(motor_id)

    def _enable_torque(self):
        for motor_id in self.servo_ids:
            self.dynamixel._enable_torque(motor_id)

    def _set_pwm_control(self):
        self._disable_torque()
        for motor_id in self.servo_ids:
            self.dynamixel.set_operating_mode(motor_id, OperatingMode.PWM)
        self._enable_torque()
        self.motor_control_state = MotorControlType.PWM

    def _set_position_control(self):
        self._disable_torque()
        for motor_id in self.servo_ids:
            self.dynamixel.set_operating_mode(motor_id, OperatingMode.POSITION)
        self._enable_torque()
        self.motor_control_state = MotorControlType.POSITION_CONTROL
