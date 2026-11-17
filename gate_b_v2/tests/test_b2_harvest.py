import json
from pathlib import Path

import numpy as np

import pytest

import gate_b_v2.harvest as harvest_module
from gate_b_v2.harvest import (
    _check_no_partial_harvest_artifacts,
    harvest_split,
    run_source_episode,
)


def _config():
    return {
        "b2": {
            "source_horizon": 8,
            "selected_states": 30,
            "source_policy_seed_offset": 900000,
            "horizons": [1, 2, 4, 8, 15],
            "continuation_horizon": 15,
            "repeats_per_state_horizon": 3,
            "branch_order_seed_base": 20261118,
            "branch_order_seed_stride": 5,
            "repeat_seed_base": 1000000,
            "repeat_seed_stride": 17,
            "discovery": {
                "primary_seed_start": 300000, "primary_seed_count": 100,
                "extension_seed_start": 300100, "extension_seed_count": 100,
                "selection_seed": 20261116,
            },
            "confirmation": {
                "primary_seed_start": 310000, "primary_seed_count": 100,
                "extension_seed_start": 310100, "extension_seed_count": 100,
                "selection_seed": 20261117,
            },
        }
    }


def _geometry(step):
    z_gap = {0: 0.10, 1: 0.03, 2: 0.015, 3: 0.010}.get(step, 0.010)
    return {
        "stage_gate_version": "B2_GEOMETRY_GATE_V1_20261116",
        "clearance_m": 0.0,
        "clearance_x_positive_m": 0.0,
        "clearance_x_negative_m": 0.0,
        "clearance_y_positive_m": 0.0,
        "clearance_y_negative_m": 0.0,
        "dx_m": 0.0,
        "dy_m": 0.0,
        "d_xy_m": 0.01,
        "relative_yaw_rad": 0.0,
        "z_gap_m": z_gap,
        "t_nut_m": 0.02,
        "r_hole_m": 0.032,
        "r_peg_m": 0.022,
        "hole_half_x_m": 0.02275,
        "hole_half_y_m": 0.02275,
        "peg_half_x_m": 0.016,
        "peg_half_y_m": 0.016,
    }


class FakeEnv:
    def __init__(self):
        self.max_steps = 10
        self.steps = 0
        self.history = []
        self.snapshot_calls = 0
        self.robosuite_env = object()

    def reset(self, seed):
        self.steps = 0
        self.history = [{"obs": np.asarray([seed], dtype=float)}]

    def step(self, action):
        self.steps += 1
        self.history.append({"obs": np.asarray([self.steps], dtype=float)})
        return self.history[-1], 0.0, False, {}

    def policy_observation(self):
        return {"obs": np.asarray([[0.0]])}

    def snapshot(self, metadata=None):
        self.snapshot_calls += 1
        return {
            "schema_version": 2,
            "sim_state_sha256": "sim-{}".format(self.steps),
            "model_xml_sha256": "model",
            "controller_gripper_audit": [],
            "snapshot_capabilities": {},
            "episode": {"steps": self.steps},
            "snapshot_metadata": metadata or {},
        }


class FakeExperiment:
    def __init__(self):
        self.config = _config()
        self.env = FakeEnv()
        self.policy = self
        self.torch = object()
        self.device = "cpu"
        self.n_obs_steps = 2
        self.prediction_horizon = 16
        self.manifest = {}
        self.project_root = Path(__file__).resolve().parents[1]
        self.policy_reset_calls = 0

    def reset(self):
        self.policy_reset_calls += 1

    def _env_action(self, action):
        return np.asarray(action, dtype=np.float32)


def test_source_episode_stops_at_first_gate_and_captures_one_state(monkeypatch, tmp_path):
    experiment = FakeExperiment()
    monkeypatch.setattr(harvest_module, "seed_everything", lambda seed: None)
    monkeypatch.setattr(harvest_module, "seed_policy_rng", lambda torch, seed: None)
    monkeypatch.setattr(
        harvest_module, "predict_full_future_chunk",
        lambda *args, **kwargs: np.zeros((15, 10), dtype=np.float32),
    )
    monkeypatch.setattr(
        harvest_module, "compute_square_geometry",
        lambda rs_env: _geometry(experiment.env.steps),
    )

    record = run_source_episode(
        experiment, "discovery", 300000, tmp_path / "snapshots", preflight=False
    )
    assert record is not None
    assert record["source_step"] == 2
    assert experiment.env.steps == 2  # stopped at first eligible step
    assert experiment.env.snapshot_calls == 1  # exactly one state per source episode
    snapshot_path = Path(record["snapshot_file"])
    assert snapshot_path.is_file()
    assert record["stage_gate_version"] == "B2_GEOMETRY_GATE_V1_20261116"
    assert record["stage_gate"]["eligible"] is True
    assert record["scientific_data"] is True
    assert record["preflight"] is False


def test_source_episode_returns_none_without_gate(monkeypatch, tmp_path):
    experiment = FakeExperiment()
    monkeypatch.setattr(harvest_module, "seed_everything", lambda seed: None)
    monkeypatch.setattr(harvest_module, "seed_policy_rng", lambda torch, seed: None)
    monkeypatch.setattr(
        harvest_module, "predict_full_future_chunk",
        lambda *args, **kwargs: np.zeros((15, 10), dtype=np.float32),
    )
    monkeypatch.setattr(
        harvest_module, "compute_square_geometry",
        lambda rs_env: _geometry(0),
    )
    record = run_source_episode(
        experiment, "discovery", 300001, tmp_path / "snapshots", preflight=False
    )
    assert record is None
    assert experiment.env.snapshot_calls == 0


def test_source_episode_policy_reset_failure_is_blocked(monkeypatch, tmp_path):
    experiment = FakeExperiment()

    def fail_reset():
        raise RuntimeError("reset unavailable")

    experiment.reset = fail_reset
    monkeypatch.setattr(harvest_module, "seed_everything", lambda seed: None)
    monkeypatch.setattr(harvest_module, "seed_policy_rng", lambda torch, seed: None)
    monkeypatch.setattr(
        harvest_module, "predict_full_future_chunk",
        lambda *args, **kwargs: np.zeros((15, 10), dtype=np.float32),
    )
    with pytest.raises(RuntimeError, match="policy reset"):
        run_source_episode(
            experiment, "discovery", 300000, tmp_path / "snapshots", preflight=False
        )


@pytest.mark.parametrize(
    "artifact",
    [
        "b2_discovery_harvest_manifest.json",
        "b2_discovery_candidates.json",
        "b2_discovery_state_manifest.jsonl",
        "b2_discovery_harvest_summary.json",
        "b2_discovery_status.json",
        "b2_discovery_episodes.jsonl",
        "b2_discovery_run.json",
        "snapshots/discovery",
    ],
)
def test_partial_harvest_artifacts_block_overwrite(tmp_path, artifact):
    path = tmp_path / artifact
    if artifact.endswith("discovery"):
        path.mkdir(parents=True)
        (path / "partial.pkl.gz").write_bytes(b"partial")
    else:
        path.write_text("partial", encoding="utf-8")
    with pytest.raises(RuntimeError, match="Refusing to overwrite prior B2 discovery"):
        _check_no_partial_harvest_artifacts(tmp_path, "discovery")
    assert path.exists()


def test_harvest_split_refuses_partial_run_before_rollout(monkeypatch, tmp_path):
    experiment = FakeExperiment()
    experiment.run_dir = tmp_path
    (tmp_path / "b2_discovery_harvest_manifest.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(harvest_module, "validate_formal_authorization", lambda *a, **k: {})
    with pytest.raises(RuntimeError, match="Refusing to overwrite prior B2 discovery"):
        harvest_split(experiment, "discovery")
