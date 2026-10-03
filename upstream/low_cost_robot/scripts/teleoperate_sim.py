import threading
import time

import mujoco
import mujoco.viewer
import numpy as np

from low_cost_robot import Dynamixel, Robot
from low_cost_robot.simulated_robot import SimulatedRobot


def read_leader_position():
    global target_pos
    while True:
        raw = np.array(leader.read_position())
        pos = SimulatedRobot.pwm_to_radians(raw)
        pos[1] = -pos[1]
        pos[3] = -pos[3]
        pos[4] = -pos[4]
        target_pos = pos


leader_dynamixel = Dynamixel.Config(baudrate=1_000_000, device_name="/dev/tty.usbmodem57380045631").instantiate()
leader = Robot(leader_dynamixel, servo_ids=[1, 2, 3, 6, 7])
leader.set_trigger_torque()

m = mujoco.MjModel.from_xml_path("simulation/low_cost_robot/scene.xml")
d = mujoco.MjData(m)
r = SimulatedRobot(m, d)

target_pos = np.zeros(5)

leader_thread = threading.Thread(target=read_leader_position, daemon=True)
leader_thread.start()

with mujoco.viewer.launch_passive(m, d) as viewer:
    while viewer.is_running():
        step_start = time.time()
        r.set_goal_pos(target_pos.copy())
        mujoco.mj_step(m, d)
        viewer.sync()
        time_until_next_step = m.opt.timestep - (time.time() - step_start)
        if time_until_next_step > 0:
            time.sleep(time_until_next_step)
