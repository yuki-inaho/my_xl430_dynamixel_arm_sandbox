import time

import mujoco
import mujoco.viewer

from low_cost_robot.simulated_robot import SimulatedRobot

m = mujoco.MjModel.from_xml_path("simulation/low_cost_robot/scene.xml")
d = mujoco.MjData(m)
r = SimulatedRobot(m, d)

with mujoco.viewer.launch_passive(m, d) as viewer:
    while viewer.is_running():
        step_start = time.time()
        mujoco.mj_step(m, d)
        viewer.sync()
        time_until_next_step = m.opt.timestep - (time.time() - step_start)
        if time_until_next_step > 0:
            time.sleep(time_until_next_step)
