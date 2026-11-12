"""Formal B1 environment and configuration lock.

These values are derived from the accepted B0 manifest and the pre-registered
B1 protocol. B1 Pilot and Full must match them exactly. The functions here are
pure validators so they can be tested without loading the checkpoint, starting
MuJoCo or using a GPU.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

B1_LOCKED_CONFIG_VALUES: Dict[str, Any] = {
    "horizons": [1, 2, 4, 8, 15],
    "b0_seed_start": 100000,
    "b0_baseline_episodes": 100,
    "b1_pilot_seed_start": 200000,
    "b1_pilot_episodes": 20,
    "b1_full_seed_start": 200020,
    "b1_full_episodes": 100,
    "b1_reference_horizon": 8,
    "b1_alpha": 0.05,
    "b1_practical_diff": 0.08,
    "b1_ceiling_threshold": 0.95,
    "b1_floor_threshold": 0.05,
    "policy_seed_offset": 700000,
    "device": "cuda:0",
    "expected_task_name": "square",
    "expected_dataset_type": "mh",
    "expected_prediction_horizon": 16,
    "max_steps": 500,
}


def _fingerprint(values: Mapping[str, Any]) -> str:
    payload = json.dumps(values, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


B1_CONFIG_FINGERPRINT = _fingerprint(B1_LOCKED_CONFIG_VALUES)

B1_LOCKED_ENVIRONMENT: Dict[str, Any] = {
    "checkpoint_sha256": "adaf17854fb8ff8acaccc56adbf6af321c7bec7fecb22de5257772ec81927c6d",
    "dataset_sha256": "7e58906366d79996f13785ff2dd0fe346230373532addc2afc7c92611ae42887",
    "dp_source_tree_sha256": "aec43e20abb0902b606e61fc4a391605ab755e59233ecb5f6bdbfbe8df372f21",
    "max_steps": 500,
    "prediction_horizon": 16,
    "n_obs_steps": 2,
    "horizons": [1, 2, 4, 8, 15],
    "device": "cuda:0",
    "gpu_name": "NVIDIA GeForce RTX 3090",
    "cuda_available": True,
    "torch": "1.12.1+cu116",
    "torch_cuda": "11.6",
    "robomimic": "0.2.0",
    "robosuite": "1.2.0",
    "mujoco_py": "2.0.2.13",
    "abs_action": True,
    "action_dim": 10,
    "env_action_dim": 7,
    "rotation_rep": "rotation_6d",
    "checkpoint_use_ema": True,
    "n_action_steps_checkpoint": 8,
    "available_future_actions": 15,
    "env_name": "NutAssemblySquare",
    "policy_seed_offset": 700000,
    "config_fingerprint": B1_CONFIG_FINGERPRINT,
}

RECORD_ENVIRONMENT_KEYS: Tuple[str, ...] = (
    "checkpoint_sha256",
    "dataset_sha256",
    "dp_source_tree_sha256",
    "max_steps",
    "prediction_horizon",
    "n_obs_steps",
    "config_fingerprint",
    "policy_seed_offset",
    "env_name",
    "gpu_name",
    "torch",
    "torch_cuda",
    "device",
)


def critical_b1_config(config: Mapping[str, Any], max_steps: int) -> Dict[str, Any]:
    """Extract the locked critical parameters from a YAML config."""
    evaluation = config["evaluation"]
    try:
        values = {
            "horizons": [int(x) for x in evaluation["horizons"]],
            "b0_seed_start": int(evaluation["seed_start"]),
            "b0_baseline_episodes": int(evaluation["b0_baseline_episodes"]),
            "b1_pilot_seed_start": int(evaluation["b1_pilot_seed_start"]),
            "b1_pilot_episodes": int(evaluation["b1_pilot_episodes"]),
            "b1_full_seed_start": int(evaluation["b1_full_seed_start"]),
            "b1_full_episodes": int(evaluation["b1_full_episodes"]),
            "b1_reference_horizon": int(evaluation["b1_reference_horizon"]),
            "b1_alpha": float(evaluation["b1_alpha"]),
            "b1_practical_diff": float(evaluation["b1_practical_diff"]),
            "b1_ceiling_threshold": float(evaluation["b1_ceiling_threshold"]),
            "b1_floor_threshold": float(evaluation["b1_floor_threshold"]),
            "policy_seed_offset": int(evaluation["policy_seed_offset"]),
            "device": str(evaluation["device"]),
            "expected_task_name": str(evaluation["expected_task_name"]),
            "expected_dataset_type": str(evaluation["expected_dataset_type"]),
            "expected_prediction_horizon": int(evaluation["expected_prediction_horizon"]),
            "max_steps": int(max_steps),
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError("B1 config is missing or has an invalid critical field: {}".format(exc))
    return values


def validate_b1_config(config: Mapping[str, Any], max_steps: int) -> Dict[str, Any]:
    """Fail closed unless every critical B1 parameter matches the lock."""
    actual = critical_b1_config(config, max_steps)
    mismatches = []
    for key, expected in B1_LOCKED_CONFIG_VALUES.items():
        if actual.get(key) != expected:
            mismatches.append("{}: actual={!r} expected={!r}".format(key, actual.get(key), expected))
    if mismatches:
        raise RuntimeError("B1 config lock failed: " + "; ".join(mismatches))
    return {"values": dict(B1_LOCKED_CONFIG_VALUES), "sha256": B1_CONFIG_FINGERPRINT}


def _environment_value(manifest: Mapping[str, Any], key: str) -> Any:
    if key == "device":
        return manifest.get("device", manifest.get("device_requested"))
    return manifest.get(key)


def validate_b1_environment(
    manifest: Mapping[str, Any],
    phase: Optional[str] = None,
    seed_start: Optional[int] = None,
    seed_end: Optional[int] = None,
    episodes: Optional[int] = None,
) -> None:
    """Fail closed unless the actual runtime manifest matches the B0-based lock."""
    mismatches = []
    for key, expected in B1_LOCKED_ENVIRONMENT.items():
        actual = _environment_value(manifest, key)
        if actual != expected:
            mismatches.append("{}: actual={!r} expected={!r}".format(key, actual, expected))
    if phase is not None:
        if manifest.get("b1_phase") != phase:
            mismatches.append(
                "b1_phase: actual={!r} expected={!r}".format(manifest.get("b1_phase"), phase)
            )
    if seed_start is not None and int(manifest.get("seed_start", -1)) != int(seed_start):
        mismatches.append("seed_start: actual={!r} expected={!r}".format(
            manifest.get("seed_start"), seed_start))
    if seed_end is not None and int(manifest.get("seed_end", -1)) != int(seed_end):
        mismatches.append("seed_end: actual={!r} expected={!r}".format(
            manifest.get("seed_end"), seed_end))
    if episodes is not None and int(manifest.get("episodes", -1)) != int(episodes):
        mismatches.append("episodes: actual={!r} expected={!r}".format(
            manifest.get("episodes"), episodes))
    if seed_start is not None and seed_end is not None and episodes is not None:
        if int(seed_end) != int(seed_start) + int(episodes) - 1:
            mismatches.append("seed interval is inconsistent with episode count")
    if mismatches:
        raise RuntimeError("B1 environment lock failed: " + "; ".join(mismatches))


def build_b1_run_manifest(
    config: Mapping[str, Any],
    max_steps: int,
    runtime_manifest: Mapping[str, Any],
    device: str,
    phase: str,
    seed_start: int,
    seed_end: int,
    horizons: Sequence[int],
    records_file: str,
) -> Dict[str, Any]:
    """Build and validate the actual B1 run manifest before any episode."""
    critical = validate_b1_config(config, max_steps)
    manifest = dict(runtime_manifest)
    manifest["device"] = str(device)
    manifest["policy_seed_offset"] = int(critical["values"]["policy_seed_offset"])
    manifest["horizons"] = [int(x) for x in horizons]
    manifest["config_fingerprint"] = critical["sha256"]
    manifest["config_critical"] = critical["values"]
    manifest["b1_phase"] = phase
    manifest["episodes"] = int(seed_end) - int(seed_start) + 1
    manifest["seed_start"] = int(seed_start)
    manifest["seed_end"] = int(seed_end)
    manifest["records_file"] = records_file
    validate_b1_environment(
        manifest,
        phase=phase,
        seed_start=int(seed_start),
        seed_end=int(seed_end),
        episodes=int(manifest["episodes"]),
    )
    return manifest


def record_environment_fields(manifest: Mapping[str, Any]) -> Dict[str, Any]:
    """Environment fields written into every B1 episode row."""
    return {key: _environment_value(manifest, key) for key in RECORD_ENVIRONMENT_KEYS}
