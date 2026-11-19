import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from b2_test_data import branch_record, passing_snapshot_validation, state_record
from gate_b_v2.core import append_jsonl, write_json
from gate_b_v2.locks import load_b1_full_manifest, load_fixed_project_config
from gate_b_v2.snapshot import save_snapshot

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

    def current_sim_state(self):
        return np.zeros(2)

    def step(self, action, *, strict=False):
        self.steps += 1
        self.max_reward = 1.0
        return {}, 1.0, False, {}

    def success(self, threshold=None, *, strict=False):
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
    state = {"state_id": "disc_300000", "source_seed": 300000, "source_step": 0,
             "geometry": {}}
    snapshot = {
        "schema_version": 3, "episode": {"steps": 0},
        "validation_reference": {"sim_state": np.zeros(2)}, "robosuite_internal": {"done": False},
    }
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
        "source_step": 0,
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
            "peg_half_z_m": 0.05,
            "geometry_fingerprint": "fingerprint",
            "aperture_bar_geom_ids": [46, 47, 48, 49],
        },
        "snapshot_sha256": "snap",
    }
    snapshot = {
        "schema_version": 3, "episode": {"steps": 0},
        "validation_reference": {"sim_state": np.zeros(2)}, "robosuite_internal": {"done": False},
    }

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


@pytest.mark.parametrize("split", ["discovery", "confirmation"])
@pytest.mark.parametrize("artifact", [
    "run.json", "snapshot_validation.json", "episodes.jsonl", "summary.json",
    "status.json", "analysis.json",
])
@pytest.mark.parametrize("existing", [b"", b"prior output\n"])
def test_branch_collision_preserves_every_existing_file(tmp_path, split, artifact, existing):
    env = SimpleNamespace(run_dir=tmp_path)
    (tmp_path / "b2_preflight_summary.json").write_bytes(b"preflight")
    (tmp_path / "b2_{}_state_manifest.jsonl".format(split)).write_bytes(b"harvest states")
    snapshot_path = tmp_path / "snapshots" / split / "harvested.pkl.gz"
    snapshot_path.parent.mkdir(parents=True)
    snapshot_path.write_bytes(b"harvest snapshot")
    conflict = tmp_path / "b2_{}_{}".format(split, artifact)
    conflict.write_bytes(existing)

    def files():
        return {
            path.relative_to(tmp_path): (path.read_bytes(), path.stat().st_mtime_ns)
            for path in tmp_path.rglob("*") if path.is_file()
        }

    before = files()
    with pytest.raises(FileExistsError, match=conflict.name):
        GateBExperiment.run_b2(env, split)
    assert files() == before


def test_branch_cli_checks_conflict_before_environment_manifest_write(tmp_path, monkeypatch):
    from gate_b_v2 import cli

    (tmp_path / "environment_manifest.json").write_bytes(b"existing environment")
    (tmp_path / "b2_discovery_run.json").touch()

    def forbidden_build(*args, **kwargs):
        pytest.fail("environment construction reached before conflict check")

    monkeypatch.setattr(cli, "GateBExperiment", forbidden_build)
    args = cli.build_parser().parse_args(["b2", "--split", "discovery", "--run-dir", str(tmp_path)])
    with pytest.raises(FileExistsError, match="b2_discovery_run.json"):
        cli._cmd_b2(args)
    assert (tmp_path / "environment_manifest.json").read_bytes() == b"existing environment"


def _branch_harness(tmp_path, monkeypatch):
    exp = GateBExperiment.__new__(GateBExperiment)
    exp.run_dir = tmp_path
    exp.project_root = Path(__file__).resolve().parents[1]
    exp.config = load_fixed_project_config(exp.project_root)
    exp.manifest = load_b1_full_manifest(exp.project_root / "reports" / "b1_full_run.json")
    exp.env = FakeEnv()
    split = "discovery"
    states = [state_record(split, 300000 + i, 100 + i, 0.001) for i in range(30)]
    first = states[0]
    first["snapshot_sha256"] = save_snapshot(tmp_path / first["snapshot_file"], {"key": "diagnostic"})
    manifest_path = tmp_path / "b2_discovery_state_manifest.jsonl"
    for state in states:
        append_jsonl(manifest_path, state)
    write_json(tmp_path / "b2_discovery_harvest_summary.json", {
        "status": "COMPLETE", "split": split, "manifest_file": manifest_path.name,
        "selected_source_seeds": [state["source_seed"] for state in states],
    })
    write_json(tmp_path / "b2_preflight_summary.json", {"marker": "PREFLIGHT"})

    monkeypatch.setattr(runner_module, "validate_formal_authorization", lambda *args, **kwargs: None)

    def validation(states, split):
        path = tmp_path / "b2_discovery_snapshot_validation.json"
        write_json(path, passing_snapshot_validation(
            split, {state["state_id"]: state["snapshot_sha256"] for state in states},
        ))
        return path

    exp._validate_all_b2_snapshots = validation
    return exp, first


@pytest.mark.parametrize("kind", ["success_error", "environment_exception"])
def test_formal_branch_attempt_blocks_and_keeps_only_prior_valid_rows(tmp_path, monkeypatch, kind):
    exp, first = _branch_harness(tmp_path, monkeypatch)
    attempted = []

    def run_branch(**kwargs):
        row = branch_record(exp.config, first, kwargs["repeat_index"], kwargs["first_horizon"])
        attempted.append(row)
        if len(attempted) == 2:
            if kind == "environment_exception":
                raise RuntimeError("simulator execution failed")
            row["success_error"] = "task predicate failed"
        return row

    exp._run_b2_branch = run_branch
    manifest = tmp_path / "b2_discovery_state_manifest.jsonl"
    original = manifest.read_bytes()
    with pytest.raises((ValueError, RuntimeError), match="success_error|simulator execution"):
        exp.run_b2("discovery")
    status = json.loads((tmp_path / "b2_discovery_status.json").read_text())
    assert status["status"] == "BLOCKED"
    assert status["state_id"] == first["state_id"]
    assert status["horizon"] == attempted[-1]["horizon"]
    assert status["valid_records_before_failure"] == 1
    written = (tmp_path / "b2_discovery_episodes.jsonl").read_text().splitlines()
    assert [json.loads(line) for line in written] == attempted[:1]
    assert not (tmp_path / "b2_discovery_summary.json").exists()
    assert manifest.read_bytes() == original


def test_failed_snapshot_validation_blocks_split_before_any_branch(tmp_path, monkeypatch):
    exp, first = _branch_harness(tmp_path, monkeypatch)

    def validation(states, split):
        assert len(states) == 30
        path = tmp_path / "b2_discovery_snapshot_validation.json"
        report = passing_snapshot_validation(
            split, {state["state_id"]: state["snapshot_sha256"] for state in states},
        )
        write_json(path, dict(report, all_passed=False, failed_states=[first["state_id"]]))
        return path

    exp._validate_all_b2_snapshots = validation
    exp._run_b2_branch = lambda **kwargs: pytest.fail("branch started with a failed snapshot")
    with pytest.raises(RuntimeError, match="Independent snapshot validation failed"):
        exp.run_b2("discovery")
    assert not (tmp_path / "b2_discovery_episodes.jsonl").exists()
    status = json.loads((tmp_path / "b2_discovery_status.json").read_text())
    assert status["status"] == "BLOCKED"
    assert status["failed_states"] == [first["state_id"]]


def test_restored_branch_state_is_checked_before_policy(tmp_path, monkeypatch):
    exp = _fake_self()
    exp.env.current_sim_state = lambda: np.array([1.0, 0.0])
    state = state_record("discovery", 300000, 100, 0.0)
    snapshot = {
        "schema_version": 3, "episode": {"steps": 100},
        "validation_reference": {"sim_state": np.zeros(2)}, "robosuite_internal": {"done": False},
    }
    with pytest.raises(RuntimeError, match="restored branch start"):
        GateBExperiment._run_b2_branch(exp, snapshot, state, 1, 123, "discovery", 0, 0, 999, [1, 2, 4, 8, 15])
    assert exp.policy.reset_calls == 0


@pytest.mark.parametrize("split,start_seed", [("discovery", 300000), ("confirmation", 310000)])
def test_validation_checks_every_snapshot_even_if_the_first_is_blocked(tmp_path, monkeypatch, split, start_seed):
    exp = GateBExperiment.__new__(GateBExperiment)
    exp.run_dir = tmp_path
    exp.config = load_fixed_project_config()
    exp.env = SimpleNamespace(reset=lambda seed: None)
    exp.policy = FakePolicy()
    exp.torch = object()
    exp.device = "cpu"
    exp.n_obs_steps = 2
    exp.prediction_horizon = 16
    exp._env_action = np.asarray
    states = [state_record(split, start_seed + i, 100 + i, 0.001) for i in range(30)]
    inspected = []

    def load(path, *, expected_sha256):
        return {"id": path.name.split(".")[0], "validation_reference": {"policy_observation": {}}}

    def validate(env, snapshot, *args, **kwargs):
        inspected.append(snapshot["id"])
        if len(inspected) == 1:
            raise RuntimeError("invalid simulator state")
        return {"passed": True, "status": "PASS"}

    monkeypatch.setattr(runner_module, "load_snapshot", load)
    monkeypatch.setattr(runner_module, "validate_snapshot_reference", lambda *args: None)
    monkeypatch.setattr(runner_module, "seed_policy_rng", lambda *args: None)
    monkeypatch.setattr(runner_module, "predict_full_future_chunk", lambda *args: np.zeros((15, 7)))
    monkeypatch.setattr(runner_module, "validate_snapshot_restore", validate)

    path = exp._validate_all_b2_snapshots(states, split)
    report = json.loads(path.read_text())
    assert inspected == [state["state_id"] for state in states]
    assert report["all_passed"] is False
    assert report["status"] == "BLOCKED"
    assert report["n_states"] == 30
    assert report["failed_states"] == inspected[:1]
    assert report["per_state"][inspected[0]]["error"] == "RuntimeError: invalid simulator state"
