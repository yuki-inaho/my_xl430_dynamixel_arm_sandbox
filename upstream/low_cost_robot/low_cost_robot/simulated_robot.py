from __future__ import annotations

import mujoco
import numpy as np

from low_cost_robot.robot_base import RobotBase


class SimulatedRobot(RobotBase):
    def __init__(self, m, d) -> None:
        self.m = m
        self.d = d

    def read_position(self) -> list[float]:
        return self.d.qpos[:5]

    def read_velocity(self) -> list[float]:
        return self.d.qvel

    def set_goal_pos(self, action) -> None:
        self.d.ctrl = action

    def read_ee_pos(self, joint_name: str = "end_effector") -> np.ndarray:
        joint_id = self.m.body(joint_name).id
        return self.d.geom_xpos[joint_id]

    def inverse_kinematics(
        self, ee_target_pos: np.ndarray, joint_name: str = "end_effector"
    ) -> np.ndarray:
        joint_id = self.m.body(joint_name).id
        ee_pos = self.d.geom_xpos[joint_id]
        jac = np.zeros((3, self.m.nv))
        mujoco.mj_jacBodyCom(self.m, self.d, jac, None, joint_id)
        qpos = self.read_position()
        qdot = np.dot(np.linalg.pinv(jac[:, :5]), ee_target_pos - ee_pos)
        return qpos + qdot * 0.2

    @staticmethod
    def pwm_to_radians(pwm: np.ndarray) -> np.ndarray:
        return (pwm / 2048 - 1) * 3.14

    @staticmethod
    def radians_to_pwm(pos: np.ndarray) -> np.ndarray:
        return (pos / 3.14 + 1.0) * 2048
