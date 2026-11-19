from __future__ import annotations

import copy
import gzip
import hashlib
import math
import pickle
import random
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

from .core import sha256_array


SNAPSHOT_SCHEMA_VERSION = 3
B2_REFERENCE_SOURCE = "source_rollout_at_capture"
STATE_HASH_FORMAT = "SHA256(dtype, shape, C-order little-endian float64 bytes; zero signs normalized)"
REQUIRED_SNAPSHOT_CHECKS = (
    "state_restore", "snapshot_payload_matches_source", "observation_restore",
    "fresh_observation_restore", "geometry_restore", "model_xml_restore",
    "controller_gripper_restore", "mujoco_dynamics_inputs_restore",
    "deterministic_state", "deterministic_observation", "deterministic_geometry",
)

_MUJOCO_DATA_FIELDS = (
    "ctrl", "qacc_warmstart", "qfrc_applied", "xfrc_applied", "mocap_pos", "mocap_quat", "userdata",
)
_OBSERVABLE_STATE_FIELDS = (
    "_time_since_last_sample", "_current_delay", "_sampled", "_current_observed_value",
)

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

GEOMETRY_LENGTH_FIELDS: Tuple[str, ...] = (
    "clearance_m",
    "clearance_x_positive_m",
    "clearance_x_negative_m",
    "clearance_y_positive_m",
    "clearance_y_negative_m",
    "dx_m",
    "dy_m",
    "d_xy_m",
    "z_gap_m",
    "nut_bottom_local_z_m",
    "peg_top_local_z_m",
    "t_nut_m",
    "nut_collision_thickness_m",
    "r_hole_m",
    "r_peg_m",
    "hole_half_x_m",
    "hole_half_y_m",
    "peg_half_x_m",
    "peg_half_y_m",
    "peg_half_z_m",
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


def sim_state_sha256(state: np.ndarray) -> str:
    normalized = np.array(state, dtype="<f8", order="C", copy=True)
    normalized[normalized == 0] = 0.0
    # Explicitly encode byte order even on a native little-endian host.
    header = "<f8" + str(normalized.shape)
    return hashlib.sha256(header.encode("ascii") + normalized.tobytes()).hexdigest()


def observation_hashes(observation: Mapping[str, np.ndarray]) -> Dict[str, str]:
    return {key: sha256_array(value) for key, value in observation.items()}


def _capture_robot_states(robosuite_env: Any) -> List[Dict[str, Any]]:
    robots = []
    for robot in getattr(robosuite_env, "robots", []):
        record = {}
        for attr in ("controller", "gripper"):
            obj = getattr(robot, attr, None)
            if obj is not None:
                state, audit = _capture_object_state(obj, attr)
                record[attr] = {"class": audit["class"], "state": state, "audit": audit}
        robots.append(record)
    return robots


def _robot_state_summary(robosuite_env: Any) -> Dict[str, Any]:
    return {
        "{}.{}".format(index, name): {
            "audit": item["audit"],
            "field_sha256": {
                field: hashlib.sha256(pickle.dumps(value, protocol=4)).hexdigest()
                for field, value in item["state"].items()
            },
        }
        for index, robot in enumerate(_capture_robot_states(robosuite_env))
        for name, item in robot.items()
    }


def _capture_mujoco_data(sim: Any) -> Dict[str, np.ndarray]:
    values = {key: getattr(sim.data, key) for key in _MUJOCO_DATA_FIELDS}
    # mujoco_py exposes unused, zero-length channels (such as mocap) as None.
    return {key: np.array(value, copy=True) for key, value in values.items() if value is not None}


def capture_episode_snapshot(
    episode_env: Any,
    metadata: Optional[Mapping[str, Any]] = None,
    observation_qpos: Optional[np.ndarray] = None,
) -> Dict[str, Any]:
    robomimic_env = episode_env.robomimic_env
    robosuite_env = episode_env.robosuite_env
    if not hasattr(robomimic_env, "get_state"):
        raise RuntimeError("robomimic EnvRobosuite.get_state is unavailable")
    env_state = robomimic_env.get_state()
    if "states" not in env_state or "model" not in env_state:
        raise RuntimeError("Environment snapshot must include both MuJoCo states and model XML")

    robot_states = _capture_robot_states(robosuite_env)
    robot_audits = [item["audit"] for robot in robot_states for item in robot.values()]

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

    snapshot = {
        "schema_version": 2,
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
    if observation_qpos is not None:
        snapshot.update({
            "schema_version": SNAPSHOT_SCHEMA_VERSION,
            "sim_state_sha256": sim_state_sha256(env_state["states"]),
            "observation_qpos": np.array(observation_qpos, copy=True),
            "mujoco_data": _capture_mujoco_data(robosuite_env.sim),
            "observable_state": {
                name: {key: copy.deepcopy(getattr(observable, key)) for key in _OBSERVABLE_STATE_FIELDS}
                for name, observable in robosuite_env._observables.items()
            },
            "observable_cache": copy.deepcopy(robosuite_env._obs_cache),
        })
    return snapshot


def restore_episode_snapshot(episode_env: Any, snapshot: Mapping[str, Any]):
    schema = int(snapshot.get("schema_version", -1))
    if schema not in (1, 2, SNAPSHOT_SCHEMA_VERSION):
        raise ValueError("Unsupported snapshot schema version {}".format(schema))
    robomimic_env = episode_env.robomimic_env
    if schema == SNAPSHOT_SCHEMA_VERSION:
        robomimic_env.reset_to({"model": snapshot["env_state"]["model"]})
    else:
        robomimic_env.reset_to(copy.deepcopy(snapshot["env_state"]))
    robosuite_env = episode_env.robosuite_env
    if schema == SNAPSHOT_SCHEMA_VERSION:
        sim = robosuite_env.sim
        # Euler integrates qpos after computing the transforms used for the
        # control-step observation and gate. Recompute those transforms at
        # their original pose, then restore the exact integration endpoint.
        sim.set_state_from_flattened(snapshot["env_state"]["states"])
        sim.data.qpos[:] = snapshot["observation_qpos"]
        for key, value in snapshot["mujoco_data"].items():
            getattr(sim.data, key)[:] = value
        sim.forward()
        sim.set_state_from_flattened(snapshot["env_state"]["states"])
        sim.data.qacc_warmstart[:] = snapshot["mujoco_data"]["qacc_warmstart"]
        if set(robosuite_env._observables) != set(snapshot["observable_state"]):
            raise RuntimeError("Observable set changed during B2 snapshot restore")
        for name, values in snapshot["observable_state"].items():
            for key, value in values.items():
                setattr(robosuite_env._observables[name], key, copy.deepcopy(value))
        robosuite_env._obs_cache = copy.deepcopy(snapshot["observable_cache"])
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

    episode = snapshot["episode"]
    if schema == SNAPSHOT_SCHEMA_VERSION:
        obs = copy.deepcopy(episode["current_observation"])
    else:
        if hasattr(robosuite_env, "_update_observables"):
            robosuite_env._update_observables(force=True)
        obs = episode_env.wrapper.get_observation(robomimic_env.get_observation())
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


def load_snapshot(path: Path, expected_sha256: Optional[str] = None) -> Dict[str, Any]:
    # Hash the same bytes that will be deserialized.
    compressed = Path(path).read_bytes()
    if expected_sha256 is not None:
        actual = hashlib.sha256(compressed).hexdigest()
        if actual != expected_sha256:
            raise RuntimeError("Snapshot SHA256 mismatch for {}: {} != {}".format(path, actual, expected_sha256))
    value = pickle.loads(gzip.decompress(compressed))
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


def _array_errors(original: np.ndarray, restored: np.ndarray) -> Dict[str, Any]:
    a, b = np.asarray(original), np.asarray(restored)
    mean_error, max_error = None, None
    if a.shape == b.shape and np.isfinite(a).all() and np.isfinite(b).all():
        errors = np.abs(a.astype(np.float64) - b.astype(np.float64))
        mean_error = float(errors.mean()) if errors.size else 0.0
        max_error = float(errors.max(initial=0))
        if not math.isfinite(max_error):
            mean_error, max_error = None, None
    return {
        "original_shape": list(a.shape),
        "restored_shape": list(b.shape),
        "original_dtype": str(a.dtype),
        "restored_dtype": str(b.dtype),
        "mean_abs_error": mean_error,
        "max_abs_error": max_error,
    }


def compare_sim_state(original: np.ndarray, restored: np.ndarray) -> Dict[str, Any]:
    result = _array_errors(original, restored)
    result.update({
        "original_state_sha256": sim_state_sha256(original),
        "restored_state_sha256": sim_state_sha256(restored),
        "normalization": STATE_HASH_FORMAT,
        "original_legacy_sha256": sha256_array(original),
        "restored_legacy_sha256": sha256_array(restored),
        "original_dtype_with_byte_order": original.dtype.str,
        "restored_dtype_with_byte_order": restored.dtype.str,
        "original_strides": list(original.strides),
        "restored_strides": list(restored.strides),
    })
    if result["max_abs_error"] is not None:
        changed = np.flatnonzero(original.ravel() != restored.ravel())
        result["changed_value_count"] = int(changed.size)
        result["changed_flat_indices_first_16"] = changed[:16].tolist()
    return result


def _compare_observations(original, restored, modalities, tolerance):
    by_key = {}
    for key in sorted(set(modalities) | set(original) | set(restored)):
        a, b = original.get(key), restored.get(key)
        item = {"observation_key": key, "modality": modalities.get(key)}
        if a is None or b is None:
            item.update({
                "original_shape": list(a.shape) if a is not None else None,
                "restored_shape": list(b.shape) if b is not None else None,
                "original_dtype": str(a.dtype) if a is not None else None,
                "restored_dtype": str(b.dtype) if b is not None else None,
                "mean_abs_error": None,
                "max_abs_error": None,
            })
        else:
            item.update(_array_errors(a, b))
            item["original_sha256"] = sha256_array(a)
            item["restored_sha256"] = sha256_array(b)
        error = item["mean_abs_error"]
        item["passed"] = (
            key in modalities and error is not None and error <= tolerance
            and item["original_dtype"] == item["restored_dtype"]
        )
        by_key[key] = item
    return {
        "by_key": by_key,
        "passed": bool(by_key) and all(row["passed"] for row in by_key.values()),
        "max_mean_abs_error": max(
            (row["mean_abs_error"] for row in by_key.values() if row["mean_abs_error"] is not None),
            default=None,
        ),
    }


def _compare_geometry(original, restored, metric_tolerance):
    length_errors = {
        key: abs(float(original[key]) - float(restored[key])) for key in GEOMETRY_LENGTH_FIELDS
    }
    angle_tolerance_rad = 1e-6
    yaw_error_rad = abs(math.remainder(
        float(restored["relative_yaw_rad"]) - float(original["relative_yaw_rad"]), 2 * math.pi
    ))
    max_length_error = max(length_errors.values())
    return {
        "abs_error_by_metric_m": length_errors,
        "max_abs_error_m": max_length_error,
        "relative_yaw_abs_error_rad": yaw_error_rad,
        "relative_yaw_tolerance_rad": angle_tolerance_rad,
        "metric_tolerance_m": metric_tolerance,
        "geometry_fingerprint_matches": original["geometry_fingerprint"] == restored["geometry_fingerprint"],
        "passed": (
            all(math.isfinite(error) and error <= metric_tolerance for error in length_errors.values())
            and yaw_error_rad <= angle_tolerance_rad
            and original["geometry_fingerprint"] == restored["geometry_fingerprint"]
        ),
    }


def _read_fresh_observation(episode_env: Any) -> Tuple[Dict[str, np.ndarray], Optional[str]]:
    try:
        return episode_env.fresh_observation(), None
    except Exception as exc:
        return {}, "{}: {}".format(type(exc).__name__, exc)


def capture_validation_reference(episode_env: Any, geometry: Mapping[str, Any]) -> Dict[str, Any]:
    """Read the live source at the gate, independently of the snapshot payload."""
    state = episode_env.robomimic_env.get_state()
    history = episode_env.policy_observation()
    current = {key: np.array(value, copy=True) for key, value in episode_env.history[-1].items()}
    raw_history_hashes = [observation_hashes(item) for item in episode_env.history]
    controller_gripper = _robot_state_summary(episode_env.robosuite_env)
    mujoco_data = _capture_mujoco_data(episode_env.robosuite_env.sim)
    fresh, fresh_error = _read_fresh_observation(episode_env)
    return {
        "source": B2_REFERENCE_SOURCE,
        "source_step": episode_env.steps,
        "sim_state": np.array(state["states"], copy=True),
        "policy_observation": history,
        "step_observation": current,
        "fresh_observation": fresh,
        "fresh_observation_error": fresh_error,
        "observation_history_sha256": raw_history_hashes,
        "geometry": copy.deepcopy(geometry),
        "model_xml_sha256": hashlib.sha256(state["model"].encode("utf-8")).hexdigest(),
        "controller_gripper": controller_gripper,
        "mujoco_data": mujoco_data,
    }


def validation_reference_hashes(reference: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "sim_state_sha256": sim_state_sha256(reference["sim_state"]),
        "model_xml_sha256": reference["model_xml_sha256"],
        "observation_key_sha256": observation_hashes(reference["step_observation"]),
        "policy_observation_key_sha256": observation_hashes(reference["policy_observation"]),
        "fresh_observation_key_sha256": observation_hashes(reference["fresh_observation"]),
        "observation_history_sha256": reference["observation_history_sha256"],
    }


def validate_snapshot_reference(snapshot: Mapping[str, Any], state_record: Mapping[str, Any]) -> None:
    """Bind the live-capture reference and restore payload to the harvested state."""
    if (snapshot.get("schema_version") != SNAPSHOT_SCHEMA_VERSION
            or state_record.get("snapshot_schema_version") != SNAPSHOT_SCHEMA_VERSION):
        raise RuntimeError("B2 requires snapshot schema 3 with a source-rollout validation reference")
    reference = snapshot.get("validation_reference", {})
    if reference.get("source") != B2_REFERENCE_SOURCE:
        raise RuntimeError("Missing independent source-rollout validation reference")
    metadata = snapshot["snapshot_metadata"]
    for key in ("split", "source_seed", "source_step", "stage_gate_version", "preflight"):
        if metadata.get(key) != state_record[key]:
            raise RuntimeError("Snapshot metadata disagrees with the state manifest for {}".format(key))
    if not reference["source_step"] == snapshot["episode"]["steps"] == state_record["source_step"]:
        raise RuntimeError("Snapshot capture step disagrees with the state manifest")
    for key, value in validation_reference_hashes(reference).items():
        if state_record.get(key) != value:
            raise RuntimeError("Source-rollout validation reference hash mismatch for {}".format(key))
    if reference["geometry"] != state_record["geometry"]:
        raise RuntimeError("Source-rollout validation geometry disagrees with the state manifest")


def require_passed_snapshot_validation(
    report: Mapping[str, Any], split: str, expected_snapshots: Mapping[str, str],
) -> None:
    formal = split != "preflight"
    states = report.get("per_state")
    if (
        report.get("split") != split or report.get("marker") != ("B2" if formal else "PREFLIGHT")
        or report.get("scientific_data") is not formal or report.get("all_passed") is not True
        or report.get("status") != "PASS" or report.get("n_states") != len(expected_snapshots)
        or not isinstance(states, dict) or set(states) != set(expected_snapshots)
    ):
        raise RuntimeError("B2 {} snapshot validation is incomplete or blocked".format(split))
    for state_id, snapshot_sha in expected_snapshots.items():
        state = states[state_id]
        if (
            state.get("status") != "PASS" or state.get("passed") is not True
            or state.get("reference_source") != B2_REFERENCE_SOURCE
            or state.get("snapshot_schema_version") != SNAPSHOT_SCHEMA_VERSION
            or state.get("snapshot_sha256") != snapshot_sha
            or any(state.get("checks", {}).get(check) is not True for check in REQUIRED_SNAPSHOT_CHECKS)
        ):
            raise RuntimeError("B2 {} snapshot validation evidence does not pass for {}".format(split, state_id))


def _compare_robot_states(original, restored):
    changed = {}
    for name in sorted(set(original) | set(restored)):
        a, b = original.get(name, {}), restored.get(name, {})
        fields_a, fields_b = a.get("field_sha256", {}), b.get("field_sha256", {})
        mismatch = sorted(
            field for field in set(fields_a) | set(fields_b)
            if fields_a.get(field) != fields_b.get(field)
        )
        changed[name] = {
            "original_audit": a.get("audit"),
            "restored_audit": b.get("audit"),
            "original_field_sha256": fields_a,
            "restored_field_sha256": fields_b,
            "mismatched_fields": mismatch,
            "passed": a.get("audit") == b.get("audit") and not mismatch,
        }
    return changed


def validate_snapshot_restore(
    episode_env: Any,
    snapshot: Mapping[str, Any],
    probe_action: np.ndarray,
    state_atol: float = 1e-7,
    observation_mean_abs_tol: float = 1e-3,
    geometry_atol: float = 1e-6,
) -> Dict[str, Any]:
    """Compare against the original source, then check deterministic double replay."""
    from .geometry import compute_square_geometry

    reference = snapshot["validation_reference"]
    if reference.get("source") != B2_REFERENCE_SOURCE:
        raise RuntimeError("B2 snapshot validation requires an original source-rollout reference")
    modalities = {
        key: attrs.get("type", "low_dim") for key, attrs in episode_env.shape_meta["obs"].items()
    }
    episode_env.restore(snapshot)
    after = episode_env.robomimic_env.get_state()
    state = compare_sim_state(reference["sim_state"], after["states"])
    state_error = state["max_abs_error"]
    payload = compare_sim_state(reference["sim_state"], snapshot["env_state"]["states"])
    history = _compare_observations(
        reference["policy_observation"], episode_env.policy_observation(), modalities,
        observation_mean_abs_tol,
    )
    history["original_frame_sha256"] = reference["observation_history_sha256"]
    history["restored_frame_sha256"] = [observation_hashes(item) for item in episode_env.history]
    history["raw_frames_match"] = history["original_frame_sha256"] == history["restored_frame_sha256"]
    geometry = _compare_geometry(
        reference["geometry"], compute_square_geometry(episode_env.robosuite_env), geometry_atol,
    )
    model_after = hashlib.sha256(after["model"].encode("utf-8")).hexdigest()
    controller_gripper = _compare_robot_states(
        reference["controller_gripper"], _robot_state_summary(episode_env.robosuite_env),
    )
    inputs_after = _capture_mujoco_data(episode_env.robosuite_env.sim)
    dynamics_inputs = {
        key: _array_errors(reference["mujoco_data"][key], value) for key, value in inputs_after.items()
    }
    fresh, render_error = _read_fresh_observation(episode_env)
    fresh_comparison = _compare_observations(
        reference["fresh_observation"], fresh, modalities, observation_mean_abs_tol,
    )
    step_comparison = _compare_observations(
        reference["step_observation"], fresh, modalities, observation_mean_abs_tol,
    )

    # Both replays start from the snapshot's RNG and controller state.
    replay = []
    replay_error = None
    try:
        for _ in range(2):
            episode_env.restore(snapshot)
            episode_env.step(np.asarray(probe_action, dtype=np.float32), strict=True)
            replay.append((
                episode_env.current_sim_state(),
                episode_env.policy_observation(),
                compute_square_geometry(episode_env.robosuite_env),
            ))
        episode_env.restore(snapshot)
    except Exception as exc:
        replay_error = "{}: {}".format(type(exc).__name__, exc)
    replay_state = replay_obs = replay_geometry = {}
    if len(replay) == 2:
        replay_state = compare_sim_state(replay[0][0], replay[1][0])
        replay_obs = _compare_observations(replay[0][1], replay[1][1], modalities, observation_mean_abs_tol)
        replay_geometry = _compare_geometry(replay[0][2], replay[1][2], geometry_atol)
    replay_state_error = replay_state.get("max_abs_error")
    checks = {
        "state_restore": state_error is not None and state_error <= state_atol,
        "snapshot_payload_matches_source": payload["max_abs_error"] == 0.0,
        "observation_restore": history["passed"] and history["raw_frames_match"],
        "fresh_observation_restore": (
            not reference["fresh_observation_error"] and not render_error
            and fresh_comparison["passed"] and step_comparison["passed"]
        ),
        "geometry_restore": geometry["passed"],
        "model_xml_restore": model_after == reference["model_xml_sha256"] == snapshot["model_xml_sha256"],
        "controller_gripper_restore": bool(controller_gripper) and set(controller_gripper) == {
            "{}.{}".format(index, name)
            for index, _ in enumerate(episode_env.robosuite_env.robots)
            for name in ("controller", "gripper")
        } and all(item["passed"] for item in controller_gripper.values()),
        "mujoco_dynamics_inputs_restore": all(
            item["max_abs_error"] == 0.0 for item in dynamics_inputs.values()
        ),
        "deterministic_state": (
            replay_error is None and replay_state_error is not None and replay_state_error <= state_atol
        ),
        "deterministic_observation": replay_obs.get("passed", False),
        "deterministic_geometry": replay_geometry.get("passed", False),
    }
    passed = all(checks.values())

    return {
        "status": "PASS" if passed else "BLOCKED",
        "passed": passed,
        "checks": checks,
        "reference_source": reference["source"],
        "source_step": reference["source_step"],
        "snapshot_schema_version": snapshot["schema_version"],
        "original_state_sha256": state["original_state_sha256"],
        "restored_state_sha256": state["restored_state_sha256"],
        "original_vs_restored_max_abs_error": state_error,
        "state_max_abs": state_error,
        "state_comparison": state,
        "state_source_vs_payload": payload,
        "snapshot_sim_state_sha256": snapshot["sim_state_sha256"],
        "original_model_xml_sha256": reference["model_xml_sha256"],
        "restored_model_xml_sha256": model_after,
        "observation_history_comparison": history,
        "fresh_observation_comparison": fresh_comparison,
        "source_step_observation_vs_restored_fresh": step_comparison,
        "fresh_observation_status": "PASS" if checks["fresh_observation_restore"] else "BLOCKED",
        "source_fresh_observation_error": reference["fresh_observation_error"],
        "restore_fresh_observation_error": render_error,
        "observation_mean_abs_max": max(
            (item["max_mean_abs_error"] for item in (history, fresh_comparison, step_comparison)
             if item["max_mean_abs_error"] is not None), default=None,
        ),
        "geometry_comparison": geometry,
        "geometry_abs_max": geometry["max_abs_error_m"],
        "controller_gripper": controller_gripper,
        "mujoco_dynamics_inputs_comparison": dynamics_inputs,
        "replay": {
            "state_comparison": replay_state,
            "observation_comparison": replay_obs,
            "geometry_comparison": replay_geometry,
            "error": replay_error,
        },
    }
