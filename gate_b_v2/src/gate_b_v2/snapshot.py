from __future__ import annotations

import copy
import gzip
import hashlib
import pickle
import random
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

from .core import sha256_array


SNAPSHOT_SCHEMA_VERSION = 2

# Fields that are references to the live simulator or owner objects.  They must
# not be serialized; the restored object is expected to keep the current
# environment's references.
_OBJECT_REFERENCE_FIELDS = {
    "sim", "robot", "robot_model", "gripper", "_model", "_sim", "env",
}

# Model XML ElementTree objects and their containers are immutable during an
# episode.  They are recorded in the capture audit but not serialized.
_IMMUTABLE_MODEL_FIELDS = {
    "tree", "root", "worldbody", "actuator", "sensor", "asset", "tendon",
    "equality", "contact", "_elements",
}

_GEOMETRY_METRIC_FIELDS: Tuple[str, ...] = (
    "clearance_m",
    "clearance_x_positive_m",
    "clearance_x_negative_m",
    "clearance_y_positive_m",
    "clearance_y_negative_m",
    "dx_m",
    "dy_m",
    "d_xy_m",
    "relative_yaw_rad",
    "z_gap_m",
    "nut_bottom_local_z_m",
    "peg_top_local_z_m",
    "t_nut_m",
    "r_hole_m",
    "r_peg_m",
    "hole_half_x_m",
    "hole_half_y_m",
    "peg_half_x_m",
    "peg_half_y_m",
)


def _copy_safe(value: Any):
    if isinstance(value, np.ndarray):
        return value.copy()
    if isinstance(value, (str, int, float, bool, type(None), np.integer, np.floating, np.bool_)):
        return value.item() if isinstance(value, (np.integer, np.floating, np.bool_)) else value
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            copied = _copy_safe(item)
            if copied is _UNSAFE:
                return _UNSAFE
            out[key] = copied
        return out
    if isinstance(value, list):
        out = [_copy_safe(item) for item in value]
        return out if all(item is not _UNSAFE for item in out) else _UNSAFE
    if isinstance(value, tuple):
        out = tuple(_copy_safe(item) for item in value)
        return out if all(item is not _UNSAFE for item in out) else _UNSAFE
    return _UNSAFE


_UNSAFE = object()


def _classify_skipped(field: str, value: Any) -> Tuple[str, bool]:
    """Return (classification, blocking) for a field that cannot be copied."""
    if field in _OBJECT_REFERENCE_FIELDS:
        return "object_reference_not_serialized", False
    if field in _IMMUTABLE_MODEL_FIELDS:
        return "immutable_model_metadata", False
    if isinstance(value, (ET.Element, ET.ElementTree)):
        return "immutable_model_metadata", False
    if callable(value):
        return "callable_immutable", False
    if field in ("interpolator_pos", "interpolator_ori") and value is None:
        return "none", False
    return "mutable_unknown", True


def _capture_object_state(obj: Any, object_name: str, strict: bool = True) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    state: Dict[str, Any] = {}
    captured: List[str] = []
    skipped: List[Dict[str, Any]] = []
    blockers: List[str] = []
    for key, value in vars(obj).items():
        copied = _copy_safe(value)
        if copied is not _UNSAFE:
            state[key] = copied
            captured.append(key)
            continue
        classification, blocking = _classify_skipped(key, value)
        skipped.append({
            "field": key,
            "type": type(value).__module__ + "." + type(value).__name__,
            "classification": classification,
            "blocking": bool(blocking),
        })
        if blocking:
            blockers.append(key)
    audit = {
        "object": object_name,
        "class": obj.__class__.__module__ + "." + obj.__class__.__name__,
        "captured_fields": sorted(captured),
        "skipped_fields": skipped,
        "capture_complete": not blockers,
    }
    if blockers and strict:
        raise RuntimeError(
            "Snapshot capture would silently omit mutable {} fields: {}. "
            "Extend the snapshot schema or explicitly classify each field.".format(
                object_name, blockers
            )
        )
    return state, audit


def _restore_object_state(obj: Any, state: Mapping[str, Any], object_name: str) -> None:
    for key, value in state.items():
        try:
            setattr(obj, key, copy.deepcopy(value))
        except Exception as exc:
            raise RuntimeError(
                "Could not restore {} field {}: {}".format(object_name, key, exc)
            )


def _capture_rng(rng: Any) -> Dict[str, Any]:
    if rng is None:
        return {"kind": "none", "state": None}
    if rng is np.random:
        return {"kind": "global_numpy", "state": copy.deepcopy(np.random.get_state())}
    if hasattr(rng, "get_state") and callable(rng.get_state):
        return {"kind": "legacy", "state": copy.deepcopy(rng.get_state())}
    if hasattr(rng, "getstate") and callable(rng.getstate):
        return {"kind": "python_legacy", "state": copy.deepcopy(rng.getstate())}
    if hasattr(rng, "bit_generator"):
        return {"kind": "generator", "state": copy.deepcopy(rng.bit_generator.state)}
    return {"kind": "unsupported", "state": None}


def _restore_rng(rng: Any, snapshot: Mapping[str, Any]) -> None:
    kind = snapshot.get("kind")
    if kind == "none":
        return
    if kind == "legacy" and hasattr(rng, "set_state"):
        rng.set_state(copy.deepcopy(snapshot["state"]))
        return
    if kind == "python_legacy" and hasattr(rng, "setstate"):
        rng.setstate(copy.deepcopy(snapshot["state"]))
        return
    if kind == "generator" and hasattr(rng, "bit_generator"):
        rng.bit_generator.state = copy.deepcopy(snapshot["state"])
        return
    if kind == "global_numpy":
        np.random.set_state(copy.deepcopy(snapshot["state"]))
        return
    if kind == "unsupported":
        raise RuntimeError("Robosuite environment RNG type cannot be snapshotted")
    raise RuntimeError("Robosuite RNG type changed between snapshot and restore: {}".format(kind))


def _capture_task_state(robosuite_env: Any) -> Dict[str, Any]:
    """Capture task-selection and mutable task state explicitly.

    These are the robosuite NutAssembly fields that can influence the task
    predicate or subsequent dynamics.  Configuration fields are immutable and
    are not copied.
    """
    state: Dict[str, Any] = {}
    for key in (
        "objects_on_pegs",
        "nut_id",
        "obj_to_use",
        "single_object_mode",
    ):
        if hasattr(robosuite_env, key):
            value = getattr(robosuite_env, key)
            copied = _copy_safe(value)
            if copied is _UNSAFE:
                raise RuntimeError("Task state field {!r} is not snapshot-safe".format(key))
            state[key] = copied
    return state


def capture_episode_snapshot(
    episode_env: Any,
    metadata: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    robomimic_env = episode_env.robomimic_env
    robosuite_env = episode_env.robosuite_env
    if not hasattr(robomimic_env, "get_state"):
        raise RuntimeError("robomimic EnvRobosuite.get_state is unavailable")
    env_state = robomimic_env.get_state()
    if "states" not in env_state or "model" not in env_state:
        raise RuntimeError("Environment snapshot must include both MuJoCo states and model XML")

    robot_states = []
    robot_audits = []
    for robot in getattr(robosuite_env, "robots", []):
        robot_record: Dict[str, Any] = {}
        for attr in ("controller", "gripper"):
            obj = getattr(robot, attr, None)
            if obj is not None:
                state, audit = _capture_object_state(obj, attr, strict=True)
                robot_record[attr] = {
                    "class": obj.__class__.__module__ + "." + obj.__class__.__name__,
                    "state": state,
                    "audit": audit,
                }
                robot_audits.append(audit)
        robot_states.append(robot_record)

    task_state = _capture_task_state(robosuite_env)

    torch_state = None
    cuda_states = None
    try:
        import torch
        # Store RNG state as NumPy bytes: torch tensor pickling can embed
        # process-specific storage metadata, which would make the snapshot file
        # hash non-reproducible for identical simulator/RNG content.
        torch_state = torch.get_rng_state().cpu().numpy().copy()
        if torch.cuda.is_available():
            cuda_states = [
                item.cpu().numpy().copy() for item in torch.cuda.get_rng_state_all()
            ]
    except ImportError:
        torch_state = None

    env_rng = _capture_rng(getattr(robosuite_env, "rng", None))
    if env_rng["kind"] == "unsupported":
        raise RuntimeError("Robosuite RNG is not serializable; B2 snapshot/restore is blocked")

    model_xml = str(env_state["model"])
    current_observation = None
    if episode_env.history:
        current_observation = {
            key: np.array(value, copy=True) for key, value in episode_env.history[-1].items()
        }

    return {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "env_state": copy.deepcopy(env_state),
        "model_xml_sha256": hashlib.sha256(model_xml.encode("utf-8")).hexdigest(),
        "sim_state_sha256": sha256_array(np.asarray(env_state["states"])),
        "robosuite_internal": {
            "timestep": int(getattr(robosuite_env, "timestep", 0)),
            "cur_time": float(getattr(robosuite_env, "cur_time", 0.0)),
            "done": bool(getattr(robosuite_env, "done", False)),
            "task_state": task_state,
            "rng": env_rng,
        },
        "robot_states": robot_states,
        "controller_gripper_audit": robot_audits,
        "global_rng": {
            "numpy": copy.deepcopy(np.random.get_state()),
            "python": random.getstate(),
            "torch_cpu": torch_state,
            "torch_cuda": cuda_states,
        },
        "episode": {
            "history": [
                {key: np.array(value, copy=True) for key, value in obs.items()}
                for obs in episode_env.history
            ],
            "current_observation": current_observation,
            "steps": int(episode_env.steps),
            "max_reward": float(episode_env.max_reward),
            "success_seen": bool(episode_env.success_seen),
            "success_error": episode_env.success_error,
            "last_info": copy.deepcopy(episode_env.last_info),
        },
        "snapshot_metadata": dict(metadata or {}),
        "snapshot_capabilities": {
            "model_xml": True,
            "sim_state": True,
            "robosuite_counters": True,
            "task_state_fields": sorted(task_state),
            "env_rng": env_rng["kind"],
            "robot_controller_objects": len(robot_states),
            "controller_gripper_capture_complete": all(
                item["capture_complete"] for item in robot_audits
            ),
        },
    }


def restore_episode_snapshot(episode_env: Any, snapshot: Mapping[str, Any]):
    schema = int(snapshot.get("schema_version", -1))
    if schema not in (1, SNAPSHOT_SCHEMA_VERSION):
        raise ValueError("Unsupported snapshot schema version {}".format(schema))
    robomimic_env = episode_env.robomimic_env
    robomimic_env.reset_to(copy.deepcopy(snapshot["env_state"]))
    robosuite_env = episode_env.robosuite_env
    internal = snapshot["robosuite_internal"]
    robosuite_env.timestep = int(internal["timestep"])
    robosuite_env.cur_time = float(internal["cur_time"])
    robosuite_env.done = bool(internal["done"])
    for key, value in internal.get("task_state", {}).items():
        setattr(robosuite_env, key, copy.deepcopy(value))

    current_robots = list(getattr(robosuite_env, "robots", []))
    saved_robots = list(snapshot.get("robot_states", []))
    if len(current_robots) != len(saved_robots):
        raise RuntimeError("Robot count changed during restore")
    for robot, robot_record in zip(current_robots, saved_robots):
        for attr, record in robot_record.items():
            obj = getattr(robot, attr, None)
            if obj is None:
                raise RuntimeError("Robot no longer exposes {} during restore".format(attr))
            current_class = obj.__class__.__module__ + "." + obj.__class__.__name__
            if current_class != record["class"]:
                raise RuntimeError(
                    "Controller/gripper class changed: {} != {}".format(current_class, record["class"])
                )
            _restore_object_state(obj, record["state"], attr)

    # reset_to updates observations once; force a fresh observation after
    # restoring controller state and environment counters.
    if hasattr(robosuite_env, "_update_observables"):
        robosuite_env._update_observables(force=True)
    raw_obs = robomimic_env.get_observation()
    obs = episode_env.wrapper.get_observation(raw_obs)

    episode = snapshot["episode"]
    episode_env.history.clear()
    for item in episode["history"]:
        episode_env.history.append({key: np.array(value, copy=True) for key, value in item.items()})
    episode_env.steps = int(episode["steps"])
    episode_env.max_reward = float(episode["max_reward"])
    episode_env.success_seen = bool(episode["success_seen"])
    episode_env.success_error = episode.get("success_error")
    episode_env.last_info = copy.deepcopy(episode["last_info"])

    _restore_rng(getattr(robosuite_env, "rng", None), internal["rng"])
    global_rng = snapshot["global_rng"]
    np.random.set_state(copy.deepcopy(global_rng["numpy"]))
    random.setstate(global_rng["python"])
    if global_rng.get("torch_cpu") is not None:
        try:
            import torch
            cpu_state = np.asarray(global_rng["torch_cpu"], dtype=np.uint8)
            torch.set_rng_state(torch.from_numpy(cpu_state.copy()))
            if global_rng.get("torch_cuda") is not None and torch.cuda.is_available():
                cuda_states = [
                    torch.from_numpy(np.asarray(item, dtype=np.uint8).copy())
                    for item in global_rng["torch_cuda"]
                ]
                torch.cuda.set_rng_state_all(cuda_states)
        except ImportError:
            pass
        except Exception as exc:
            raise RuntimeError("Could not restore Torch RNG state: {}".format(exc))
    return obs


def save_snapshot(path: Path, snapshot: Mapping[str, Any]) -> str:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    # mtime=0 and an anonymous file object make the compressed snapshot bytes a
    # deterministic content identity, not a wall-clock-dependent artifact.
    with tmp.open("wb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", compresslevel=3, mtime=0) as stream:
            pickle.dump(dict(snapshot), stream, protocol=pickle.HIGHEST_PROTOCOL)
    tmp.replace(path)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_snapshot(path: Path) -> Dict[str, Any]:
    with gzip.open(str(path), "rb") as stream:
        value = pickle.load(stream)
    if not isinstance(value, dict):
        raise TypeError("Snapshot file did not contain a dictionary")
    return value


def verify_snapshot_sha256(path: Path, expected: str) -> None:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    actual = digest.hexdigest()
    if actual != str(expected):
        raise RuntimeError(
            "Snapshot SHA256 mismatch for {}: {} != {}".format(path, actual, expected)
        )


def _observation_errors(reference: Mapping[str, np.ndarray], restored: Mapping[str, np.ndarray]) -> Dict[str, float]:
    errors: Dict[str, float] = {}
    if set(reference) != set(restored):
        missing = sorted(set(reference) - set(restored))
        extra = sorted(set(restored) - set(reference))
        raise ValueError("Observation keys changed during restore: missing={} extra={}".format(missing, extra))
    for key in reference:
        a = np.asarray(reference[key]).astype(np.float64)
        b = np.asarray(restored[key]).astype(np.float64)
        if a.shape != b.shape:
            raise ValueError(
                "Observation {!r} shape changed during restore: {} != {}".format(key, a.shape, b.shape)
            )
        errors[key] = float(np.mean(np.abs(a - b)))
    return errors


def _geometry_errors(reference: Mapping[str, Any], restored: Mapping[str, Any]) -> Dict[str, float]:
    errors: Dict[str, float] = {}
    for key in _GEOMETRY_METRIC_FIELDS:
        a = float(reference[key])
        b = float(restored[key])
        errors[key] = float(abs(a - b))
    return errors


def capture_validation_reference(episode_env: Any) -> Dict[str, Any]:
    from .geometry import compute_square_geometry

    return {
        "sim_state": episode_env.current_sim_state(),
        "policy_observation": episode_env.policy_observation(),
        "geometry": compute_square_geometry(episode_env.robosuite_env),
        "model_xml_sha256": hashlib.sha256(
            str(episode_env.robomimic_env.get_state()["model"]).encode("utf-8")
        ).hexdigest(),
    }


def validate_snapshot_restore(
    episode_env: Any,
    snapshot: Mapping[str, Any],
    probe_action: np.ndarray,
    state_atol: float = 1e-7,
    observation_mean_abs_tol: float = 1e-3,
    geometry_atol: float = 1e-6,
) -> Dict[str, Any]:
    """Validate one snapshot as required by B2 v1.1 sections 3 and 5.

    Checks (1) pre-restore simulator state, policy observation and geometry,
    (2) two identical restore/probe-action replays, and (3) RNG determinism.
    """
    from .geometry import compute_square_geometry

    reference = capture_validation_reference(episode_env)
    restored_obs = episode_env.restore(snapshot)
    state_after = episode_env.current_sim_state()
    obs_after = episode_env.policy_observation()
    geometry_after = compute_square_geometry(episode_env.robosuite_env)
    model_xml_after = hashlib.sha256(
        str(episode_env.robomimic_env.get_state()["model"]).encode("utf-8")
    ).hexdigest()

    state_error = float(np.max(np.abs(reference["sim_state"] - state_after)))
    obs_errors = _observation_errors(reference["policy_observation"], obs_after)
    obs_error = max(obs_errors.values()) if obs_errors else 0.0
    geometry_errors = _geometry_errors(reference["geometry"], geometry_after)
    geometry_error = max(geometry_errors.values()) if geometry_errors else 0.0

    # Deterministic replay: restore twice, execute exactly the same probe action
    # from the same restored RNG state.
    replay = []
    for _ in range(2):
        episode_env.restore(snapshot)
        obs, _, _, _ = episode_env.step(np.asarray(probe_action, dtype=np.float32))
        replay.append({
            "sim_state": episode_env.current_sim_state(),
            "policy_observation": episode_env.policy_observation(),
            "geometry": compute_square_geometry(episode_env.robosuite_env),
        })
    replay_state_error = float(
        np.max(np.abs(replay[0]["sim_state"] - replay[1]["sim_state"]))
    )
    replay_obs_errors = _observation_errors(
        replay[0]["policy_observation"], replay[1]["policy_observation"]
    )
    replay_obs_error = max(replay_obs_errors.values()) if replay_obs_errors else 0.0
    replay_geometry_errors = _geometry_errors(replay[0]["geometry"], replay[1]["geometry"])
    replay_geometry_error = max(replay_geometry_errors.values()) if replay_geometry_errors else 0.0

    checks = {
        "state_restore": state_error <= float(state_atol),
        "observation_restore": obs_error <= float(observation_mean_abs_tol),
        "geometry_restore": geometry_error <= float(geometry_atol),
        "model_xml_restore": model_xml_after == reference["model_xml_sha256"],
        "deterministic_state": replay_state_error <= float(state_atol),
        "deterministic_observation": replay_obs_error <= float(observation_mean_abs_tol),
        "deterministic_geometry": replay_geometry_error <= float(geometry_atol),
    }
    passed = bool(all(checks.values()))

    # Leave the environment restored to the snapshot, not to the probe result.
    episode_env.restore(snapshot)
    return {
        "passed": passed,
        "checks": {key: bool(value) for key, value in checks.items()},
        "state_max_abs": state_error,
        "observation_mean_abs_by_key": obs_errors,
        "observation_mean_abs_max": obs_error,
        "geometry_abs_by_metric": geometry_errors,
        "geometry_abs_max": geometry_error,
        "replay_state_max_abs": replay_state_error,
        "replay_observation_mean_abs_by_key": replay_obs_errors,
        "replay_observation_mean_abs_max": replay_obs_error,
        "replay_geometry_abs_by_metric": replay_geometry_errors,
        "replay_geometry_abs_max": replay_geometry_error,
        "state_hash_a": sha256_array(reference["sim_state"]),
        "state_hash_after_restore": sha256_array(state_after),
        "state_hash_replay_a": sha256_array(replay[0]["sim_state"]),
        "state_hash_replay_b": sha256_array(replay[1]["sim_state"]),
        "state_atol": float(state_atol),
        "observation_mean_abs_tol": float(observation_mean_abs_tol),
        "geometry_atol": float(geometry_atol),
        "snapshot_schema_version": int(snapshot.get("schema_version", -1)),
        "snapshot_sim_state_sha256": snapshot.get("sim_state_sha256"),
        "snapshot_model_xml_sha256": snapshot.get("model_xml_sha256"),
    }
