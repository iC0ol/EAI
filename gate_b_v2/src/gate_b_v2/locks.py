"""Formal B1 environment and configuration lock.

These values are derived from the accepted B0 manifest and the pre-registered
B1 protocol. B1 Pilot and Full must match them exactly. The functions here are
pure validators so they can be tested without loading the checkpoint, starting
MuJoCo or using a GPU.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
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


# ---------------------------------------------------------------------------
# B2 v1.1 lock.  B2 reads the real B1 Full manifest rather than trusting
# abbreviated hashes copied from prose.
# ---------------------------------------------------------------------------

B2_LOCKED_CONFIG_VALUES: Dict[str, Any] = {
    "source_horizon": 8,
    "continuation_horizon": 15,
    "horizons": [1, 2, 4, 8, 15],
    "repeats_per_state_horizon": 3,
    "selected_states": 30,
    "discovery_primary_seed_start": 300000,
    "discovery_primary_seed_count": 100,
    "discovery_extension_seed_start": 300100,
    "discovery_extension_seed_count": 100,
    "discovery_selection_seed": 20261116,
    "confirmation_primary_seed_start": 310000,
    "confirmation_primary_seed_count": 100,
    "confirmation_extension_seed_start": 310100,
    "confirmation_extension_seed_count": 100,
    "confirmation_selection_seed": 20261117,
    "source_policy_seed_offset": 900000,
    "branch_order_seed_base": 20261118,
    "branch_order_seed_stride": 5,
    "repeat_seed_base": 1000000,
    "repeat_seed_stride": 17,
    "bootstrap_samples": 5000,
    "permutation_samples": 100000,
    "practical_effect_threshold": 0.08,
    "snapshot_state_atol": 1.0e-7,
    "snapshot_observation_mean_abs_tol": 1.0e-3,
    "snapshot_geometry_atol": 1.0e-6,
    "prediction_horizon": 16,
    "n_obs_steps": 2,
    "max_steps": 500,
    "device": "cuda:0",
}

B2_CONFIG_FINGERPRINT = _fingerprint(B2_LOCKED_CONFIG_VALUES)

B2_LOCKED_ENVIRONMENT_KEYS: Tuple[str, ...] = (
    "checkpoint_sha256",
    "dataset_sha256",
    "dp_source_tree_sha256",
    "max_steps",
    "prediction_horizon",
    "n_obs_steps",
    "device",
    "gpu_name",
    "cuda_available",
    "torch",
    "torch_cuda",
    "robomimic",
    "robosuite",
    "mujoco_py",
    "abs_action",
    "action_dim",
    "env_action_dim",
    "rotation_rep",
    "checkpoint_use_ema",
    "n_action_steps_checkpoint",
    "available_future_actions",
    "env_name",
)

B1_FULL_MANIFEST_REQUIRED_KEYS: Tuple[str, ...] = B2_LOCKED_ENVIRONMENT_KEYS + (
    "b1_phase",
    "episodes",
    "seed_start",
    "seed_end",
    "horizons",
    "checkpoint_bytes",
    "dataset_bytes",
)

B2_RECORD_ENVIRONMENT_KEYS: Tuple[str, ...] = B2_LOCKED_ENVIRONMENT_KEYS + (
    "config_fingerprint",
    "b1_full_manifest_sha256",
)


def load_b1_full_manifest(path: Path) -> Dict[str, Any]:
    """Load and structurally validate the real B1 Full manifest.

    B2 must not copy abbreviated hashes from documentation.  The manifest is
    read from disk and every required fingerprint is checked for presence and
    for the accepted B1 Full identity.
    """
    manifest_path = Path(path)
    if not manifest_path.is_file():
        raise FileNotFoundError("B1 Full manifest not found: {}".format(manifest_path))
    payload = manifest_path.read_bytes()
    manifest = json.loads(payload.decode("utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("B1 Full manifest must contain a JSON object")
    missing = [key for key in B1_FULL_MANIFEST_REQUIRED_KEYS if key not in manifest]
    if missing:
        raise ValueError("B1 Full manifest is missing required keys: {}".format(missing))
    if manifest.get("b1_phase") != "full":
        raise ValueError("B2 lock requires the B1 Full manifest, got phase {!r}".format(manifest.get("b1_phase")))
    if int(manifest.get("episodes", -1)) != 100:
        raise ValueError("B1 Full manifest episodes must be 100, got {!r}".format(manifest.get("episodes")))
    if int(manifest.get("seed_start", -1)) != 200020 or int(manifest.get("seed_end", -1)) != 200119:
        raise ValueError(
            "B1 Full manifest seed interval must be 200020-200119, got {}-{}".format(
                manifest.get("seed_start"), manifest.get("seed_end")
            )
        )
    if sorted(int(x) for x in manifest.get("horizons", [])) != [1, 2, 4, 8, 15]:
        raise ValueError("B1 Full manifest horizons are not [1,2,4,8,15]")
    # Do not merely compare a runtime manifest to whatever file was read.
    # The accepted B1 Full manifest itself must match the frozen B0/B1 lock.
    validate_b1_environment(
        manifest,
        phase="full",
        seed_start=200020,
        seed_end=200119,
        episodes=100,
    )
    manifest["_manifest_path"] = str(manifest_path)
    manifest["_manifest_sha256"] = hashlib.sha256(payload).hexdigest()
    return manifest


def critical_b2_config(config: Mapping[str, Any]) -> Dict[str, Any]:
    """Extract the exact B2 v1.1 protocol constants from the YAML config."""
    b2 = config.get("b2")
    if not isinstance(b2, Mapping):
        raise RuntimeError("B2 config section is missing")
    try:
        discovery = b2["discovery"]
        confirmation = b2["confirmation"]
        validation = b2["snapshot_validation"]
        values = {
            "source_horizon": int(b2["source_horizon"]),
            "continuation_horizon": int(b2["continuation_horizon"]),
            "horizons": [int(x) for x in b2["horizons"]],
            "repeats_per_state_horizon": int(b2["repeats_per_state_horizon"]),
            "selected_states": int(b2["selected_states"]),
            "discovery_primary_seed_start": int(discovery["primary_seed_start"]),
            "discovery_primary_seed_count": int(discovery["primary_seed_count"]),
            "discovery_extension_seed_start": int(discovery["extension_seed_start"]),
            "discovery_extension_seed_count": int(discovery["extension_seed_count"]),
            "discovery_selection_seed": int(discovery["selection_seed"]),
            "confirmation_primary_seed_start": int(confirmation["primary_seed_start"]),
            "confirmation_primary_seed_count": int(confirmation["primary_seed_count"]),
            "confirmation_extension_seed_start": int(confirmation["extension_seed_start"]),
            "confirmation_extension_seed_count": int(confirmation["extension_seed_count"]),
            "confirmation_selection_seed": int(confirmation["selection_seed"]),
            "source_policy_seed_offset": int(b2["source_policy_seed_offset"]),
            "branch_order_seed_base": int(b2["branch_order_seed_base"]),
            "branch_order_seed_stride": int(b2["branch_order_seed_stride"]),
            "repeat_seed_base": int(b2["repeat_seed_base"]),
            "repeat_seed_stride": int(b2["repeat_seed_stride"]),
            "bootstrap_samples": int(b2["bootstrap_samples"]),
            "permutation_samples": int(b2["permutation_samples"]),
            "practical_effect_threshold": float(b2["practical_effect_threshold"]),
            "snapshot_state_atol": float(validation["state_atol"]),
            "snapshot_observation_mean_abs_tol": float(validation["observation_mean_abs_tol"]),
            "snapshot_geometry_atol": float(validation["geometry_atol"]),
            "prediction_horizon": int(config["evaluation"]["expected_prediction_horizon"]),
            "n_obs_steps": 2,
            # The official B1 Full manifest and the B2 lock both use 500; a null
            # YAML value keeps reading the official runner config, and the actual
            # runtime value is still checked against the B1 Full manifest.
            "max_steps": int(config["evaluation"].get("max_steps") or 500),
            "device": str(config["evaluation"]["device"]),
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError("B2 config is missing or has an invalid critical field: {}".format(exc))
    return values


def validate_b2_config(config: Mapping[str, Any]) -> Dict[str, Any]:
    actual = critical_b2_config(config)
    mismatches = []
    for key, expected in B2_LOCKED_CONFIG_VALUES.items():
        if actual.get(key) != expected:
            mismatches.append("{}: actual={!r} expected={!r}".format(key, actual.get(key), expected))
    if mismatches:
        raise RuntimeError("B2 config lock failed: " + "; ".join(mismatches))
    return {"values": dict(B2_LOCKED_CONFIG_VALUES), "sha256": B2_CONFIG_FINGERPRINT}


def _b2_environment_value(manifest: Mapping[str, Any], key: str) -> Any:
    if key == "device":
        return manifest.get("device", manifest.get("device_requested"))
    return manifest.get(key)


def validate_b2_environment(
    runtime_manifest: Mapping[str, Any],
    b1_full_manifest: Mapping[str, Any],
) -> None:
    """Fail closed unless B2 exactly inherits the B1 Full runtime fingerprint."""
    mismatches = []
    for key in B2_LOCKED_ENVIRONMENT_KEYS:
        actual = _b2_environment_value(runtime_manifest, key)
        expected = _b2_environment_value(b1_full_manifest, key)
        if actual != expected:
            mismatches.append("{}: actual={!r} B1Full={!r}".format(key, actual, expected))
    if mismatches:
        raise RuntimeError("B2 environment lock failed: " + "; ".join(mismatches))


def build_b2_run_manifest(
    config: Mapping[str, Any],
    runtime_manifest: Mapping[str, Any],
    b1_full_manifest: Mapping[str, Any],
    split: str,
    command: str,
) -> Dict[str, Any]:
    """Build the B2 run manifest and validate it against the B1 Full manifest."""
    if split not in ("discovery", "confirmation", "preflight"):
        raise ValueError("split must be discovery, confirmation or preflight")
    critical = validate_b2_config(config)
    validate_b2_environment(runtime_manifest, b1_full_manifest)
    manifest = dict(runtime_manifest)
    manifest["device"] = _b2_environment_value(manifest, "device")
    manifest.update({
        "phase": "B2",
        "split": split,
        "command": command,
        "protocol_version": "B2_PROTOCOL_REVISION_20261116",
        "config_fingerprint": critical["sha256"],
        "config_critical": critical["values"],
        "b1_full_manifest": b1_full_manifest.get("_manifest_path"),
        "b1_full_manifest_sha256": b1_full_manifest.get("_manifest_sha256"),
        "source_horizon": critical["values"]["source_horizon"],
        "continuation_horizon": critical["values"]["continuation_horizon"],
        "branch_horizons": critical["values"]["horizons"],
        "repeats_per_state_horizon": critical["values"]["repeats_per_state_horizon"],
    })
    validate_b2_environment(manifest, b1_full_manifest)
    return manifest


def b2_record_environment_fields(manifest: Mapping[str, Any]) -> Dict[str, Any]:
    return {key: _b2_environment_value(manifest, key) for key in B2_RECORD_ENVIRONMENT_KEYS}


B2_PROTOCOL_VERSION = "B2_PROTOCOL_REVISION_20261116"
PREFLIGHT_SEED = 299999


def _default_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_fixed_project_config(project_root: Optional[Path] = None) -> Dict[str, Any]:
    """Load the fixed project YAML config; B2 analysis never accepts overrides."""
    import yaml

    root = Path(project_root).resolve() if project_root is not None else _default_project_root()
    path = root / "configs" / "gate_b.yaml"
    if not path.is_file():
        raise FileNotFoundError("Fixed project config not found: {}".format(path))
    with path.open("r", encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    if not isinstance(config, dict):
        raise ValueError("Fixed project config root must be a mapping")
    return config


def current_git_commit(project_root: Optional[Path] = None) -> Optional[str]:
    """Return the current repository HEAD when available, else None."""
    root = Path(project_root).resolve() if project_root is not None else _default_project_root()
    candidates = [root]
    if root.parent != root:
        candidates.append(root.parent)
    for candidate in candidates:
        if not (candidate / ".git").exists():
            continue
        try:
            result = subprocess.run(
                ["git", "-C", str(candidate), "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
            )
            return result.stdout.strip() or None
        except Exception:
            continue
    return None


def validate_b2_run_manifest(
    manifest: Mapping[str, Any],
    split: str,
    b1_full_manifest: Mapping[str, Any],
) -> None:
    """Fail closed unless a B2 run manifest is complete and frozen-config-locked."""
    if split not in ("discovery", "confirmation", "preflight"):
        raise ValueError("invalid B2 split {!r}".format(split))
    required = (
        "phase", "split", "command", "protocol_version", "config_fingerprint",
        "config_critical", "b1_full_manifest_sha256", "source_horizon",
        "continuation_horizon", "branch_horizons", "repeats_per_state_horizon",
    )
    missing = [key for key in required if key not in manifest]
    if missing:
        raise RuntimeError("B2 run manifest is missing required fields: {}".format(missing))
    if manifest.get("phase") != "B2":
        raise RuntimeError("B2 run manifest phase is not 'B2'")
    if manifest.get("split") != split:
        raise RuntimeError(
            "B2 run manifest split {!r} != requested {!r}".format(manifest.get("split"), split)
        )
    if manifest.get("protocol_version") != B2_PROTOCOL_VERSION:
        raise RuntimeError(
            "B2 run manifest protocol_version {!r} != {!r}".format(
                manifest.get("protocol_version"), B2_PROTOCOL_VERSION
            )
        )
    if manifest.get("config_fingerprint") != B2_CONFIG_FINGERPRINT:
        raise RuntimeError(
            "B2 run manifest config fingerprint {!r} != frozen {!r}".format(
                manifest.get("config_fingerprint"), B2_CONFIG_FINGERPRINT
            )
        )
    if manifest.get("config_critical") != B2_LOCKED_CONFIG_VALUES:
        raise RuntimeError("B2 run manifest critical config does not equal the frozen lock")
    if manifest.get("b1_full_manifest_sha256") != b1_full_manifest.get("_manifest_sha256"):
        raise RuntimeError(
            "B2 run manifest B1 Full SHA256 {!r} != actual {!r}".format(
                manifest.get("b1_full_manifest_sha256"), b1_full_manifest.get("_manifest_sha256")
            )
        )
    if int(manifest.get("source_horizon", -1)) != 8:
        raise RuntimeError("B2 run manifest source horizon is not 8")
    if int(manifest.get("continuation_horizon", -1)) != 15:
        raise RuntimeError("B2 run manifest continuation horizon is not 15")
    if [int(x) for x in manifest.get("branch_horizons", [])] != [1, 2, 4, 8, 15]:
        raise RuntimeError("B2 run manifest branch horizons are not [1,2,4,8,15]")
    if int(manifest.get("repeats_per_state_horizon", -1)) != 3:
        raise RuntimeError("B2 run manifest repeat count is not 3")
    validate_b2_environment(manifest, b1_full_manifest)
