import mujoco
import numpy as np

from physics_step import finish_forward, integrate


def test_split_pipeline_matches_standard_implicitfast_step():
    model = mujoco.MjModel.from_xml_string("""<mujoco><option integrator="implicitfast"/><worldbody>
    <geom type="plane" size="1 1 .1"/><body pos="0 0 .07"><freejoint/><geom type="sphere" size=".05" mass=".01"/></body>
    <body pos=".2 0 .15"><joint name="hinge" type="hinge" axis="0 1 0" damping=".01"/><geom type="capsule" fromto="0 0 0 0 0 -.1" size=".02"/></body>
    </worldbody><actuator><motor joint="hinge"/></actuator></mujoco>""")
    standard, split = mujoco.MjData(model), mujoco.MjData(model)
    for _ in range(200):
        standard.ctrl[:] = 0.01
        mujoco.mj_step(model, standard)
        mujoco.mj_step1(model, split)
        split.ctrl[:] = 0.01
        finish_forward(model, split)
        integrate(model, split)
        assert np.array_equal(standard.qpos, split.qpos)
        assert np.array_equal(standard.qvel, split.qvel)
