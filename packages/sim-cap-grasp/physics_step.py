"""Complete the split forward pipeline and use the frozen implicitfast integrator.

Call mj_step1 before setting ctrl, then finish_forward before logging this state.
Unlike mj_step2, integration here preserves implicitfast rather than choosing Euler.
"""

import mujoco


def finish_forward(model, data):
    mujoco.mj_fwdActuation(model, data)
    mujoco.mj_fwdAcceleration(model, data)
    mujoco.mj_fwdConstraint(model, data)
    mujoco.mj_sensorAcc(model, data)
    mujoco.mj_checkAcc(model, data)


def integrate(model, data):
    if model.opt.integrator != mujoco.mjtIntegrator.mjINT_IMPLICITFAST:
        raise ValueError("This pipeline requires the frozen implicitfast integrator")
    mujoco.mj_implicit(model, data)
