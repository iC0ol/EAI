import numpy as np

from gate_b_v2.env import EpisodeEnv


class _RobomimicEnv:
    def __init__(self, value=None, error=None):
        self.value = value
        self.error = error

    def is_success(self):
        if self.error is not None:
            raise self.error
        return {"task": self.value}


class _Wrapper:
    def __init__(self, robomimic_env):
        self.env = robomimic_env


def _episode_env(robomimic_env):
    return EpisodeEnv(
        wrapper=_Wrapper(robomimic_env),
        shape_meta={"obs": {}},
        n_obs_steps=1,
        max_steps=10,
    )


def test_success_uses_final_task_predicate_not_sticky_flag():
    env = _episode_env(_RobomimicEnv(value=False))
    env.success_seen = True
    assert env.success() is False

    env = _episode_env(_RobomimicEnv(value=True))
    assert env.success() is True
    assert env.success_error is None


def test_success_fails_closed_and_records_predicate_error():
    env = _episode_env(_RobomimicEnv(error=RuntimeError("bad state")))
    assert env.success() is False
    assert env.success_error is not None
