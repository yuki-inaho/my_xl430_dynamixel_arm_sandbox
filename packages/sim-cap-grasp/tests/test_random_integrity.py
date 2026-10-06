from types import SimpleNamespace

import pytest

from random_run import run


def test_random_invalid_parameters_leave_no_trial(tmp_path):
    output = tmp_path / "trial"
    args = SimpleNamespace(
        output=output, friction=float("nan"), mass=0.0015, timestep=0.001, seed=81020261005
    )
    with pytest.raises(ValueError, match="friction"):
        run(args)
    assert not output.exists()
