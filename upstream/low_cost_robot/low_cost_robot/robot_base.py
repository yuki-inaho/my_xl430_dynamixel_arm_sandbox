from __future__ import annotations
from abc import ABC, abstractmethod


class RobotBase(ABC):
    @abstractmethod
    def read_position(self) -> list[float]:
        ...

    @abstractmethod
    def read_velocity(self) -> list[float]:
        ...

    @abstractmethod
    def set_goal_pos(self, action) -> None:
        ...
