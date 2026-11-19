import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

import run_b2_continuation_h4 as diagnostic
from gate_b_v2.b2_protocol import branch_order, branch_order_seed, repeat_seed
from gate_b_v2.core import policy_noise_seed, sha256_file
from gate_b_v2.locks import load_fixed_project_config, validate_b2_config
from gate_b_v2.snapshot import verify_snapshot_sha256


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BASE_CONFIG = load_fixed_project_config(PROJECT_ROOT)
CONFIG_SHA = "a" * 64


def baseline_row(seed, index, horizon, source_step=469):
    order = branch_order(BASE_CONFIG, seed, index)
    return {
        **dict.fromkeys(diagnostic.PAIRED_FIELDS, 0),
        "state_id": f"conf_{seed}",
        "source_seed": seed,
        "source_step": source_step,
        "repeat_index": index,
        "repeat_seed": repeat_seed(BASE_CONFIG, seed, index),
        "branch_order_seed": branch_order_seed(BASE_CONFIG, seed, index),
        "horizon_order": order,
        "randomized_order_index": order.index(horizon),
        "horizon": horizon,
        "snapshot_schema_version": 3,
        "snapshot_sha256": f"{seed:064x}",
        "clearance_m": -0.015,
    }


def measurement_for(baseline):
    executed = diagnostic.MAX_STEPS - baseline["source_step"]
    calls = diagnostic.policy_calls_for_steps(executed, baseline["horizon"])
    return {
        **diagnostic.paired_fields(baseline, CONFIG_SHA),
        "policy_noise_seed_schedule": [policy_noise_seed(baseline["repeat_seed"], i) for i in range(calls)],
        "policy_reset_verified": True,
        "restored_snapshot_verified": True,
        "success": False,
        "success_seen": True,
        "success_error": None,
        "max_reward": 0.25,
        "steps_from_episode_start": diagnostic.MAX_STEPS,
        "steps_after_branch": executed,
        "policy_calls_after_branch": calls,
        "wall_time_s": 12.0,
        "termination": "max_steps",
    }


class FakeEpisode:
    def __init__(self, done_at):
        self.done_at = done_at
        self.restores = 0
        self.actions = []
        self.success_seen = True
        self.success_error = None
        self.max_reward = 0.9

    def restore(self, snapshot):
        self.steps = snapshot["source_step"]
        self.sim_state = snapshot["validation_reference"]["sim_state"].copy()
        self.actions.clear()
        self.restores += 1

    def current_sim_state(self):
        return self.sim_state

    def policy_observation(self):
        return self.steps

    def step(self, action, strict):
        assert strict is True
        self.actions.append(action)
        self.steps += 1
        return None, 0.0, self.steps == self.done_at, {}

    def success(self, threshold, strict):
        assert threshold == BASE_CONFIG["evaluation"]["success_threshold"]
        assert strict is True
        return False


def fake_rollout(monkeypatch, source_step, done_at=None):
    observations, noise_seeds, resets = [], [], []
    env = FakeEpisode(done_at)
    experiment = SimpleNamespace(
        env=env, torch=object(), policy=SimpleNamespace(reset=lambda: resets.append(env.steps)),
        config=BASE_CONFIG, device="cuda:0", max_steps=500, n_obs_steps=2, prediction_horizon=16,
        _env_action=lambda action: int(action[0]),
    )
    snapshot = {
        "source_step": source_step,
        "validation_reference": {"sim_state": np.array([0.8, -0.1])},
        "robosuite_internal": {"done": False},
    }

    def predict(policy, torch, observation, device, obs_steps, prediction_horizon):
        assert policy is experiment.policy and torch is experiment.torch
        assert (device, obs_steps, prediction_horizon) == ("cuda:0", 2, 16)
        observations.append(observation)
        return np.arange(15)[:, None] + (len(observations) - 1) * 100

    monkeypatch.setattr(diagnostic, "predict_full_future_chunk", predict)
    monkeypatch.setattr(diagnostic, "seed_policy_rng", lambda torch, seed: noise_seeds.append(seed))
    return experiment, snapshot, observations, noise_seeds, resets


@pytest.mark.parametrize("horizon", [1, 2, 4, 8, 15])
def test_first_commitment_then_fresh_four_action_chunks(monkeypatch, horizon):
    baseline = baseline_row(310000, 0, horizon)
    experiment, snapshot, observations, seeds, resets = fake_rollout(monkeypatch, baseline["source_step"])
    result = diagnostic.execute_branch(experiment, snapshot, baseline)
    groups = [horizon]
    while sum(groups) < 31:
        groups.append(min(4, 31 - sum(groups)))
    assert observations == list((469 + np.cumsum([0, *groups[:-1]])).tolist())
    assert experiment.env.actions == [
        100 * query + action for query, count in enumerate(groups) for action in range(count)
    ]
    assert seeds == [policy_noise_seed(baseline["repeat_seed"], i) for i in range(len(groups))]
    assert result["policy_calls_after_branch"] == len(groups)
    assert resets == [469] and experiment.env.restores == 1
    assert result["success"] is False and result["success_seen"] is True
    assert result["steps_from_episode_start"] == 500 and result["steps_after_branch"] == 31
    diagnostic.validate_branch({**diagnostic.paired_fields(baseline, CONFIG_SHA), **result}, baseline, CONFIG_SHA)


@pytest.mark.parametrize(
    "source_step,first_horizon,done_at,expected",
    [(489, 15, 491, [0, 1]), (489, 2, 494, [0, 1, 100, 101, 102]), (498, 15, None, [0, 1])],
)
def test_early_done_and_500_step_cap(monkeypatch, source_step, first_horizon, done_at, expected):
    baseline = baseline_row(310000, 1, first_horizon, source_step)
    experiment, snapshot, _, _, _ = fake_rollout(monkeypatch, source_step, done_at)
    result = diagnostic.execute_branch(experiment, snapshot, baseline)
    assert experiment.env.actions == expected
    assert result["steps_after_branch"] == len(expected)
    assert result["termination"] == ("environment_done" if done_at else "max_steps")
    diagnostic.validate_branch({**diagnostic.paired_fields(baseline, CONFIG_SHA), **result}, baseline, CONFIG_SHA)


def test_branches_restore_the_same_state_and_reuse_the_call_index_seed_schedule(monkeypatch):
    experiment, snapshot, _, seeds, resets = fake_rollout(monkeypatch, 469)
    first = diagnostic.execute_branch(experiment, snapshot, baseline_row(310000, 1, 1))
    second = diagnostic.execute_branch(experiment, snapshot, baseline_row(310000, 1, 15))
    assert resets == [469, 469] and experiment.env.restores == 2
    assert second["policy_noise_seed_schedule"] == first["policy_noise_seed_schedule"][:second["policy_calls_after_branch"]]
    assert seeds == first["policy_noise_seed_schedule"] + second["policy_noise_seed_schedule"]


def test_incorrect_restore_blocks_before_policy_calls(monkeypatch):
    baseline = baseline_row(310000, 0, 4)
    experiment, snapshot, observations, seeds, resets = fake_rollout(monkeypatch, 469)
    experiment.env.current_sim_state = lambda: np.array([1.0, 2.0])
    with pytest.raises(RuntimeError, match="Restored branch start"):
        diagnostic.execute_branch(experiment, snapshot, baseline)
    assert not observations and not seeds and not resets


def test_policy_reset_failure_blocks_before_first_prediction(monkeypatch):
    baseline = baseline_row(310000, 0, 4)
    experiment, snapshot, observations, seeds, _ = fake_rollout(monkeypatch, 469)
    experiment.policy.reset = None
    with pytest.raises(RuntimeError, match="policy reset"):
        diagnostic.execute_branch(experiment, snapshot, baseline)
    assert not observations and not seeds and not experiment.env.actions


def test_complete_grid_requires_all_450_unique_ordered_pairs():
    baseline = [
        baseline_row(seed, repeat, horizon)
        for seed in range(310000, 310030)
        for repeat in range(3)
        for horizon in branch_order(BASE_CONFIG, seed, repeat)
    ]
    records = [measurement_for(row) for row in baseline]
    diagnostic.validate_complete(records, baseline, CONFIG_SHA)
    with pytest.raises(ValueError, match="exactly 450"):
        diagnostic.validate_complete(records[:-1], baseline, CONFIG_SHA)
    with pytest.raises(ValueError, match="Duplicate"):
        diagnostic.validate_complete([records[1], *records[1:]], baseline, CONFIG_SHA)
    with pytest.raises(ValueError, match="differs from paired"):
        diagnostic.validate_complete([records[1], records[0], *records[2:]], baseline, CONFIG_SHA)


@pytest.mark.parametrize(
    "field,value,error",
    [
        ("continuation_horizon", 15, "continuation_horizon"),
        ("first_horizon", 16, "first_horizon"),
        ("source_step", 467, "source_step"),
        ("repeat_seed", 3, "repeat_seed"),
        ("horizon_order", [1, 2, 4, 8, 15, 16], "horizon_order"),
        ("snapshot_sha256", "bad", "snapshot_sha256"),
        ("diagnostic_config_fingerprint", "bad", "diagnostic_config_fingerprint"),
        ("steps_from_episode_start", 501, "step counts"),
        ("policy_calls_after_branch", 1, "policy-call count"),
        ("policy_noise_seed_schedule", [0], "policy-noise schedule"),
        ("restored_snapshot_verified", False, "restore evidence"),
        ("success_error", "error", "restore evidence"),
        ("wall_time_s", float("nan"), "wall_time_s"),
    ],
)
def test_branch_integrity_blocks_invalid_fields(field, value, error):
    baseline = baseline_row(310000, 0, 4)
    row = {**measurement_for(baseline), field: value}
    with pytest.raises(ValueError, match=error):
        diagnostic.validate_branch(row, baseline, CONFIG_SHA)


def test_source_snapshot_locator_and_read_only_hash(tmp_path):
    source = tmp_path.resolve()
    snapshot_path = source / "snapshots" / "confirmation" / "conf_310000.pkl.gz"
    snapshot_path.parent.mkdir(parents=True)
    snapshot_path.write_bytes(b"locked snapshot bytes")
    snapshot_sha = sha256_file(snapshot_path)
    state = {
        "state_id": "conf_310000",
        "snapshot_file": "/old/run/snapshots/confirmation/conf_310000.pkl.gz",
    }
    located = diagnostic.verified_snapshot_path(source, state)
    assert located == snapshot_path
    verify_snapshot_sha256(located, snapshot_sha)
    with pytest.raises(RuntimeError, match="locator"):
        diagnostic.verified_snapshot_path(source, {**state, "snapshot_file": "snapshots/discovery/conf_310000.pkl.gz"})
    with pytest.raises(RuntimeError, match="SHA256 mismatch"):
        verify_snapshot_sha256(located, "a" * 64)
    assert snapshot_path.read_bytes() == b"locked snapshot bytes"
    with pytest.raises(FileNotFoundError):
        diagnostic.verified_snapshot_path(source / "missing", state)


def test_missing_source_blocks_and_partial_run_cannot_be_reused(tmp_path):
    (tmp_path / "runs").mkdir()
    new_run = tmp_path / "runs" / "b2_continuation_h4_test"
    with pytest.raises(FileNotFoundError):
        diagnostic.run_diagnostic(tmp_path, tmp_path / "missing", new_run)
    status_path = new_run / "b2_continuation_h4_status.json"
    original_status = status_path.read_bytes()
    status = json.loads(original_status)
    assert (status["status"], status["stage"], status["n_branch_records"]) == ("BLOCKED", "SOURCE_VALIDATION", 0)
    assert not (new_run / "b2_continuation_h4_episodes.jsonl").exists()
    with pytest.raises(FileExistsError):
        diagnostic.run_diagnostic(tmp_path, tmp_path / "missing", new_run)
    assert status_path.read_bytes() == original_status


def test_formal_configuration_retains_the_frozen_continuation():
    assert validate_b2_config(BASE_CONFIG)["values"]["continuation_horizon"] == 15
    assert diagnostic.CONTINUATION_HORIZON == 4
