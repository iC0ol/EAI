from types import SimpleNamespace

import numpy as np
import pytest

import gate_b_v2.runner as runner_module
from gate_b_v2.runner import GateBExperiment


class FakeEnv:
    def __init__(self, max_steps=40):
        self.max_steps = max_steps
        self.steps = 0
        self.restore_calls = 0
        self.max_reward = 0.0
        self.success_seen = False
        self.success_error = None

    def restore(self, snapshot):
        self.restore_calls += 1
        self.steps = int(snapshot["episode"]["steps"])

    def policy_observation(self):
        return {"obs": np.zeros((1, 1))}

    def step(self, action):
        self.steps += 1
        self.max_reward = 1.0
        return {}, 1.0, False, {}

    def success(self, threshold=None):
        return True


class FakePolicy:
    def __init__(self):
        self.reset_calls = 0

    def reset(self):
        self.reset_calls += 1


def _fake_self(max_steps=40):
    return SimpleNamespace(
        config={
            "b2": {"continuation_horizon": 15},
            "evaluation": {"success_threshold": 0.99},
        },
        env=FakeEnv(max_steps=max_steps),
        policy=FakePolicy(),
        torch=object(),
        device="cpu",
        n_obs_steps=2,
        prediction_horizon=16,
        max_steps=max_steps,
        max_steps_value=max_steps,
        _env_action=lambda action: np.asarray(action),
    )


class FailingPolicy:
    def reset(self):
        raise RuntimeError("controller reset unavailable")


class NoResetPolicy:
    pass


def test_branch_policy_reset_failure_is_blocked(monkeypatch):
    monkeypatch.setattr(runner_module, "seed_policy_rng", lambda torch, seed: None)
    monkeypatch.setattr(
        runner_module, "predict_full_future_chunk",
        lambda *args, **kwargs: np.zeros((15, 10), dtype=np.float32),
    )
    state = {"state_id": "disc_300000", "source_seed": 300000, "source_step": 1,
             "geometry": {}}
    snapshot = {"schema_version": 2, "episode": {"steps": 0}}
    for policy in (FailingPolicy(), NoResetPolicy()):
        fake = _fake_self(max_steps=10)
        fake.policy = policy
        with pytest.raises(RuntimeError, match="policy reset"):
            GateBExperiment._run_b2_branch(
                fake,
                snapshot=snapshot,
                state_record=state,
                first_horizon=1,
                repeat_seed_value=123,
                split="discovery",
                repeat_index=0,
                randomized_order_index=0,
                order_seed=999,
                horizon_order=[1, 2, 4, 8, 15],
            )


def test_branch_executes_first_h_then_continuation_15(monkeypatch):
    monkeypatch.setattr(runner_module, "seed_policy_rng", lambda torch, seed: None)
    monkeypatch.setattr(
        runner_module, "predict_full_future_chunk",
        lambda *args, **kwargs: np.zeros((15, 10), dtype=np.float32),
    )
    state = {
        "state_id": "disc_300000",
        "source_seed": 300000,
        "source_step": 124,
        "clearance_m": 0.0,
        "clearance_x_positive_m": 0.0,
        "clearance_x_negative_m": 0.0,
        "clearance_y_positive_m": 0.0,
        "clearance_y_negative_m": 0.0,
        "dx_m": 0.0,
        "dy_m": 0.0,
        "d_xy_m": 0.01,
        "relative_yaw_rad": 0.0,
        "z_gap_m": 0.01,
        "t_nut_m": 0.02,
        "r_hole_m": 0.032,
        "r_peg_m": 0.022,
        "geometry": {
            "clearance_m": 0.0,
            "clearance_x_positive_m": 0.0,
            "clearance_x_negative_m": 0.0,
            "clearance_y_positive_m": 0.0,
            "clearance_y_negative_m": 0.0,
            "dx_m": 0.0,
            "dy_m": 0.0,
            "d_xy_m": 0.01,
            "relative_yaw_rad": 0.0,
            "z_gap_m": 0.01,
            "nut_bottom_local_z_m": -0.01,
            "peg_top_local_z_m": -0.02,
            "t_nut_m": 0.02,
            "nut_collision_thickness_m": 0.02,
            "r_hole_m": 0.032,
            "r_peg_m": 0.022,
            "hole_half_x_m": 0.02275,
            "hole_half_y_m": 0.02275,
            "peg_half_x_m": 0.016,
            "peg_half_y_m": 0.016,
            "geometry_fingerprint": "fingerprint",
            "aperture_bar_geom_ids": [46, 47, 48, 49],
        },
        "snapshot_sha256": "snap",
    }
    snapshot = {"schema_version": 2, "episode": {"steps": 0}}

    fake = _fake_self(max_steps=40)
    record = GateBExperiment._run_b2_branch(
        fake,
        snapshot=snapshot,
        state_record=state,
        first_horizon=1,
        repeat_seed_value=123,
        split="discovery",
        repeat_index=0,
        randomized_order_index=0,
        order_seed=999,
        horizon_order=[1, 2, 4, 8, 15],
    )
    # h=1, then h=15 -> 1 + 15 + 15 + 9 = 40.
    assert record["steps_after_branch"] == 40
    assert record["policy_calls_after_branch"] == 4
    assert record["continuation_horizon"] == 15
    assert record["success"] is True
    assert record["repeat_seed"] == 123
    assert record["branch_order_seed"] == 999
    assert len(record["policy_noise_seed_schedule"]) == 4
    assert fake.env.restore_calls == 1
    assert fake.policy.reset_calls == 1

    fake = _fake_self(max_steps=40)
    record = GateBExperiment._run_b2_branch(
        fake,
        snapshot=snapshot,
        state_record=state,
        first_horizon=15,
        repeat_seed_value=123,
        split="discovery",
        repeat_index=0,
        randomized_order_index=4,
        order_seed=999,
        horizon_order=[1, 2, 4, 8, 15],
    )
    # h=15 branch is the fixed-h=15 continuation baseline: 15 + 15 + 10 = 40.
    assert record["policy_calls_after_branch"] == 3
    assert record["steps_after_branch"] == 40
