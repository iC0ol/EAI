import copy
from pathlib import Path

import pytest
import yaml

from gate_b_v2.cli import build_parser
from gate_b_v2.core import sha256_tree
from gate_b_v2.locks import (
    B1_CONFIG_FINGERPRINT,
    B1_LOCKED_ENVIRONMENT,
    build_b1_run_manifest,
    validate_b1_config,
    validate_b1_environment,
)

ROOT = Path(__file__).resolve().parents[1]


def _config():
    return yaml.safe_load((ROOT / "configs" / "gate_b.yaml").read_text(encoding="utf-8"))


def _manifest(**overrides):
    manifest = dict(B1_LOCKED_ENVIRONMENT)
    manifest.update({
        "b1_phase": "pilot",
        "episodes": 20,
        "seed_start": 200000,
        "seed_end": 200019,
        "reference_horizon": 8,
        "records_file": "b1_pilot_episodes.jsonl",
    })
    manifest.update(overrides)
    return manifest


def test_real_config_matches_lock():
    assert validate_b1_config(_config(), 500)["sha256"] == B1_CONFIG_FINGERPRINT


@pytest.mark.parametrize("key,value", [
    ("horizons", [1, 2, 4, 8, 16]),
    ("seed_start", 100001),
    ("b0_baseline_episodes", 99),
    ("b1_pilot_seed_start", 200001),
    ("b1_pilot_episodes", 21),
    ("b1_full_seed_start", 200019),
    ("b1_full_episodes", 99),
    ("b1_reference_horizon", 4),
    ("b1_alpha", 0.10),
    ("b1_practical_diff", 0.10),
    ("b1_ceiling_threshold", 0.99),
    ("b1_floor_threshold", 0.01),
    ("policy_seed_offset", 700001),
    ("device", "cpu"),
    ("expected_task_name", "can"),
    ("expected_dataset_type", "ph"),
    ("expected_prediction_horizon", 15),
])
def test_config_lock_rejects_changed_critical_value(key, value):
    config = _config()
    config["evaluation"][key] = value
    with pytest.raises(RuntimeError, match="config lock failed"):
        validate_b1_config(config, 500)


@pytest.mark.parametrize("max_steps", [100, 400, 1000])
def test_config_lock_rejects_wrong_max_steps(max_steps):
    with pytest.raises(RuntimeError, match="config lock failed"):
        validate_b1_config(_config(), max_steps)


def test_environment_lock_accepts_correct_fingerprint():
    validate_b1_environment(_manifest())


@pytest.mark.parametrize("key,value", [
    ("checkpoint_sha256", "0" * 64),
    ("dataset_sha256", "1" * 64),
    ("dp_source_tree_sha256", "2" * 64),
    ("max_steps", 100),
    ("max_steps", 1000),
    ("prediction_horizon", 15),
    ("n_obs_steps", 1),
    ("horizons", [1, 2, 4, 8, 16]),
    ("device", "cpu"),
    ("gpu_name", "NVIDIA GeForce RTX 4090"),
    ("cuda_available", False),
    ("torch", "2.2.2+cu121"),
    ("torch_cuda", "12.1"),
    ("robomimic", "0.4.0"),
    ("robosuite", "1.5.1"),
    ("mujoco_py", "3.2.3"),
    ("abs_action", False),
    ("action_dim", 7),
    ("env_action_dim", 10),
    ("rotation_rep", "euler_angles"),
    ("checkpoint_use_ema", False),
    ("n_action_steps_checkpoint", 16),
    ("available_future_actions", 16),
    ("env_name", "Lift"),
    ("policy_seed_offset", 800000),
    ("config_fingerprint", "bad"),
])
def test_environment_lock_rejects_changed_fingerprint(key, value):
    manifest = _manifest()
    manifest[key] = value
    with pytest.raises(RuntimeError, match="environment lock failed"):
        validate_b1_environment(manifest)


def test_environment_lock_rejects_phase_or_seed_mismatch():
    manifest = _manifest()
    with pytest.raises(RuntimeError, match="environment lock failed"):
        validate_b1_environment(manifest, phase="full", seed_start=200020,
                                seed_end=200119, episodes=100)
    with pytest.raises(RuntimeError, match="environment lock failed"):
        validate_b1_environment(manifest, phase="pilot", seed_start=200001,
                                seed_end=200020, episodes=20)


def test_build_manifest_normal_pilot_and_full():
    config = _config()
    runtime = dict(B1_LOCKED_ENVIRONMENT)
    pilot = build_b1_run_manifest(
        config, 500, runtime, "cuda:0", "pilot", 200000, 200019,
        [1, 2, 4, 8, 15], "b1_pilot_episodes.jsonl",
    )
    assert pilot["b1_phase"] == "pilot"
    assert pilot["episodes"] == 20
    assert pilot["config_fingerprint"] == B1_CONFIG_FINGERPRINT
    full = build_b1_run_manifest(
        config, 500, runtime, "cuda:0", "full", 200020, 200119,
        [1, 2, 4, 8, 15], "b1_full_episodes.jsonl",
    )
    assert full["b1_phase"] == "full"
    assert full["episodes"] == 100


def test_build_manifest_rejects_modified_config_or_runtime():
    config = _config()
    runtime = dict(B1_LOCKED_ENVIRONMENT)
    changed = copy.deepcopy(config)
    changed["evaluation"]["policy_seed_offset"] = 700001
    with pytest.raises(RuntimeError, match="config lock failed"):
        build_b1_run_manifest(
            changed, 500, runtime, "cuda:0", "pilot", 200000, 200019,
            [1, 2, 4, 8, 15], "b1_pilot_episodes.jsonl",
        )
    bad_runtime = dict(runtime)
    bad_runtime["checkpoint_sha256"] = "0" * 64
    with pytest.raises(RuntimeError, match="environment lock failed"):
        build_b1_run_manifest(
            config, 500, bad_runtime, "cuda:0", "pilot", 200000, 200019,
            [1, 2, 4, 8, 15], "b1_pilot_episodes.jsonl",
        )


@pytest.mark.parametrize("flag,value", [
    ("--dp-root", "/tmp/dp"),
    ("--checkpoint", "/tmp/model.ckpt"),
    ("--dataset", "/tmp/data.hdf5"),
    ("--max-steps", "100"),
    ("--config", "/tmp/other.yaml"),
])
def test_b1_cli_rejects_experiment_overrides(flag, value):
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["b1", flag, value])


def test_b1_cli_accepts_only_phase_and_run_dir():
    parser = build_parser()
    args = parser.parse_args(["b1", "--b1-phase", "full", "--run-dir", "runs/example"])
    assert args.b1_phase == "full"
    assert args.run_dir == "runs/example"


def test_real_dp_source_tree_matches_b0_definition():
    tree = ROOT / "third_party" / "diffusion_policy" / "diffusion_policy"
    if not tree.is_dir():
        pytest.skip("vendored DP source is not available in this checkout")
    assert sha256_tree(tree) == B1_LOCKED_ENVIRONMENT["dp_source_tree_sha256"]
