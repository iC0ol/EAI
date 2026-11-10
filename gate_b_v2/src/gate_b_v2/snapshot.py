from __future__ import annotations

import copy
import gzip
import pickle
import random
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Tuple

import numpy as np


def _copy_safe(value: Any):
    if isinstance(value, np.ndarray):
        return value.copy()
    if isinstance(value, (str, int, float, bool, type(None), np.integer, np.floating, np.bool_)):
        return value.item() if isinstance(value, (np.integer, np.floating, np.bool_)) else value
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            copied = _copy_safe(item)
            if copied is not _UNSAFE:
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


def _capture_object_state(obj: Any) -> Dict[str, Any]:
    state: Dict[str, Any] = {}
    for key, value in vars(obj).items():
        if key in {"sim", "robot", "robot_model", "gripper", "_model", "_sim", "env"}:
            continue
        copied = _copy_safe(value)
        if copied is not _UNSAFE:
            state[key] = copied
    return state


def _restore_object_state(obj: Any, state: Mapping[str, Any]) -> None:
    for key, value in state.items():
        try:
            setattr(obj, key, copy.deepcopy(value))
        except Exception as exc:
            raise RuntimeError("Could not restore controller/gripper field {}: {}".format(key, exc))


def _capture_rng(rng: Any):
    if rng is None:
        return {"kind": "none", "state": None}
    if hasattr(rng, "get_state") and callable(rng.get_state):
        return {"kind": "legacy", "state": copy.deepcopy(rng.get_state())}
    if hasattr(rng, "bit_generator"):
        return {"kind": "generator", "state": copy.deepcopy(rng.bit_generator.state)}
    if rng is np.random:
        return {"kind": "global_numpy", "state": copy.deepcopy(np.random.get_state())}
    return {"kind": "unsupported", "state": None}


def _restore_rng(rng: Any, snapshot: Mapping[str, Any]) -> None:
    kind = snapshot.get("kind")
    if kind == "none":
        return
    if kind == "legacy" and hasattr(rng, "set_state"):
        rng.set_state(copy.deepcopy(snapshot["state"]))
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


def capture_episode_snapshot(episode_env: Any) -> Dict[str, Any]:
    robomimic_env = episode_env.robomimic_env
    robosuite_env = episode_env.robosuite_env
    if not hasattr(robomimic_env, "get_state"):
        raise RuntimeError("robomimic EnvRobosuite.get_state is unavailable")
    env_state = robomimic_env.get_state()
    if "states" not in env_state or "model" not in env_state:
        raise RuntimeError("Environment snapshot must include both MuJoCo states and model XML")

    robot_states = []
    for robot in getattr(robosuite_env, "robots", []):
        robot_record: Dict[str, Any] = {}
        for attr in ("controller", "gripper"):
            obj = getattr(robot, attr, None)
            if obj is not None:
                robot_record[attr] = {
                    "class": obj.__class__.__module__ + "." + obj.__class__.__name__,
                    "state": _capture_object_state(obj),
                }
        robot_states.append(robot_record)

    task_state = {}
    if hasattr(robosuite_env, "objects_on_pegs"):
        task_state["objects_on_pegs"] = np.asarray(robosuite_env.objects_on_pegs).copy()

    torch_state = None
    cuda_states = None
    try:
        import torch
        torch_state = torch.get_rng_state().clone()
        if torch.cuda.is_available():
            cuda_states = [item.clone() for item in torch.cuda.get_rng_state_all()]
    except Exception:
        pass

    env_rng = _capture_rng(getattr(robosuite_env, "rng", None))
    if env_rng["kind"] == "unsupported":
        raise RuntimeError("Robosuite RNG is not serializable; B2 snapshot/restore is blocked")

    return {
        "schema_version": 1,
        "env_state": copy.deepcopy(env_state),
        "robosuite_internal": {
            "timestep": int(getattr(robosuite_env, "timestep", 0)),
            "cur_time": float(getattr(robosuite_env, "cur_time", 0.0)),
            "done": bool(getattr(robosuite_env, "done", False)),
            "task_state": task_state,
            "rng": env_rng,
        },
        "robot_states": robot_states,
        "global_rng": {
            "numpy": copy.deepcopy(np.random.get_state()),
            "python": random.getstate(),
            "torch_cpu": torch_state,
            "torch_cuda": cuda_states,
        },
        "episode": {
            "history": [{k: np.array(v, copy=True) for k, v in obs.items()} for obs in episode_env.history],
            "steps": int(episode_env.steps),
            "max_reward": float(episode_env.max_reward),
            "success_seen": bool(episode_env.success_seen),
            "last_info": copy.deepcopy(episode_env.last_info),
        },
        "snapshot_capabilities": {
            "model_xml": True,
            "sim_state": True,
            "robosuite_counters": True,
            "env_rng": env_rng["kind"],
            "robot_controller_objects": len(robot_states),
            "controller_state_fields": [
                {key: sorted(value["state"].keys()) for key, value in record.items()}
                for record in robot_states
            ],
        },
    }


def restore_episode_snapshot(episode_env: Any, snapshot: Mapping[str, Any]):
    if int(snapshot.get("schema_version", -1)) != 1:
        raise ValueError("Unsupported snapshot schema version")
    robomimic_env = episode_env.robomimic_env
    raw_obs = robomimic_env.reset_to(copy.deepcopy(snapshot["env_state"]))
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
                raise RuntimeError("Controller/gripper class changed: {} != {}".format(current_class, record["class"]))
            _restore_object_state(obj, record["state"])

    # reset_to updates observations once; force a fresh observation after restoring
    # controller state and environment counters.
    if hasattr(robosuite_env, "_update_observables"):
        robosuite_env._update_observables(force=True)
    raw_obs = robomimic_env.get_observation()
    obs = episode_env.wrapper.get_observation(raw_obs)

    episode = snapshot["episode"]
    episode_env.history.clear()
    for item in episode["history"]:
        episode_env.history.append({k: np.array(v, copy=True) for k, v in item.items()})
    episode_env.steps = int(episode["steps"])
    episode_env.max_reward = float(episode["max_reward"])
    episode_env.success_seen = bool(episode["success_seen"])
    episode_env.last_info = copy.deepcopy(episode["last_info"])

    _restore_rng(getattr(robosuite_env, "rng", None), internal["rng"])
    global_rng = snapshot["global_rng"]
    np.random.set_state(copy.deepcopy(global_rng["numpy"]))
    random.setstate(global_rng["python"])
    if global_rng.get("torch_cpu") is not None:
        try:
            import torch
            torch.set_rng_state(global_rng["torch_cpu"])
            if global_rng.get("torch_cuda") is not None and torch.cuda.is_available():
                torch.cuda.set_rng_state_all(global_rng["torch_cuda"])
        except Exception as exc:
            raise RuntimeError("Could not restore Torch RNG state: {}".format(exc))
    return obs


def save_snapshot(path: Path, snapshot: Mapping[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with gzip.open(str(tmp), "wb", compresslevel=3) as stream:
        pickle.dump(dict(snapshot), stream, protocol=pickle.HIGHEST_PROTOCOL)
    tmp.replace(path)


def load_snapshot(path: Path) -> Dict[str, Any]:
    with gzip.open(str(path), "rb") as stream:
        value = pickle.load(stream)
    if not isinstance(value, dict):
        raise TypeError("Snapshot file did not contain a dictionary")
    return value


def validate_snapshot_restore(
    episode_env: Any,
    snapshot: Mapping[str, Any],
    probe_action: np.ndarray,
    state_atol: float = 1e-7,
    observation_mean_abs_tol: float = 1e-3,
) -> Dict[str, Any]:
    """Execute the same probe action twice from one snapshot and compare outcomes."""
    from .core import sha256_array

    episode_env.restore(snapshot)
    obs_a, _, _, _ = episode_env.step(probe_action)
    state_a = episode_env.current_sim_state()
    episode_env.restore(snapshot)
    obs_b, _, _, _ = episode_env.step(probe_action)
    state_b = episode_env.current_sim_state()

    state_max_abs = float(np.max(np.abs(state_a - state_b)))
    obs_errors = {}
    for key in obs_a:
        a = np.asarray(obs_a[key]).astype(np.float64)
        b = np.asarray(obs_b[key]).astype(np.float64)
        obs_errors[key] = float(np.mean(np.abs(a - b)))
    max_obs_error = max(obs_errors.values()) if obs_errors else 0.0
    passed = state_max_abs <= float(state_atol) and max_obs_error <= float(observation_mean_abs_tol)
    episode_env.restore(snapshot)
    return {
        "passed": bool(passed),
        "state_max_abs": state_max_abs,
        "observation_mean_abs_by_key": obs_errors,
        "observation_mean_abs_max": max_obs_error,
        "state_hash_a": sha256_array(state_a),
        "state_hash_b": sha256_array(state_b),
        "state_atol": float(state_atol),
        "observation_mean_abs_tol": float(observation_mean_abs_tol),
    }
