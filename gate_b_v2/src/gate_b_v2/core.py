from __future__ import annotations

import hashlib
import json
import os
import platform
import random
import subprocess
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Deque, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np


def utc_run_id(prefix: str = "gateb") -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return "{}_{}".format(prefix, stamp)


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def sha256_array(array: np.ndarray) -> str:
    arr = np.ascontiguousarray(array)
    digest = hashlib.sha256()
    digest.update(str(arr.dtype).encode("utf-8"))
    digest.update(str(arr.shape).encode("utf-8"))
    digest.update(arr.tobytes())
    return digest.hexdigest()


def git_commit(path: Path) -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True,
        )
        return result.stdout.strip()
    except Exception:
        return None


def seed_everything(seed: int) -> None:
    random.seed(int(seed))
    np.random.seed(int(seed))
    try:
        import torch
        torch.manual_seed(int(seed))
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(int(seed))
    except ImportError:
        pass


def seed_policy_rng(torch_module: Any, seed: int) -> None:
    """Seed only policy sampling, leaving the simulator RNG untouched."""
    value = int(seed) % (2 ** 31 - 1)
    torch_module.manual_seed(value)
    if torch_module.cuda.is_available():
        torch_module.cuda.manual_seed_all(value)


def policy_noise_seed(base_seed: int, call_index: int) -> int:
    # Identical seed schedule across horizons gives common random numbers by
    # policy-call index, without pretending environment trajectories are equal.
    return int((int(base_seed) + 1000003 * int(call_index)) % (2 ** 31 - 1))


def available_future_actions(prediction_horizon: int, n_obs_steps: int) -> int:
    """DP aligns action index 0 with the first observation; future starts at To-1."""
    if prediction_horizon < 1 or n_obs_steps < 1:
        raise ValueError("prediction_horizon and n_obs_steps must be positive")
    return int(prediction_horizon) - (int(n_obs_steps) - 1)


def validate_horizons(
    requested: Sequence[int], prediction_horizon: int, n_obs_steps: int
) -> List[int]:
    available = available_future_actions(prediction_horizon, n_obs_steps)
    values = [int(x) for x in requested]
    if not values or any(x < 1 for x in values):
        raise ValueError("At least one positive execution horizon is required")
    if len(set(values)) != len(values):
        raise ValueError("Execution horizons must be unique")
    too_long = [x for x in values if x > available]
    if too_long:
        raise ValueError(
            "Requested h={} exceeds the {} executable future actions available "
            "from checkpoint H={} with n_obs_steps={}. Do not silently truncate. "
            "Inspect the checkpoint config and obtain approval for a protocol "
            "amendment (likely replace h=16 with h={}).".format(
                too_long, available, prediction_horizon, n_obs_steps, available
            )
        )
    return values


def stack_observation_history(
    history: Sequence[Mapping[str, np.ndarray]],
    n_obs_steps: int,
    shape_meta: Mapping[str, Any],
) -> Dict[str, np.ndarray]:
    """Match Diffusion Policy's stack_last_n_obs padding and C,H,W convention."""
    if not history:
        raise ValueError("Observation history is empty")
    result: Dict[str, np.ndarray] = {}
    selected = list(history[-n_obs_steps:])
    if len(selected) < n_obs_steps:
        selected = [selected[0]] * (n_obs_steps - len(selected)) + selected
    for key, attr in shape_meta["obs"].items():
        expected = tuple(int(x) for x in attr["shape"])
        values = []
        for obs in selected:
            if key not in obs:
                raise KeyError("Observation missing checkpoint key {!r}".format(key))
            arr = np.asarray(obs[key])
            if arr.shape != expected and len(expected) == 3:
                # Robosuite/robomimic versions differ in whether images are HWC or CHW.
                chw_from_hwc = (expected[1], expected[2], expected[0])
                if arr.shape == chw_from_hwc:
                    arr = np.transpose(arr, (2, 0, 1))
            if arr.shape != expected:
                raise ValueError(
                    "Observation {!r} shape {} does not match checkpoint shape {}".format(
                        key, arr.shape, expected
                    )
                )
            if attr.get("type", "low_dim") != "rgb":
                arr = arr.astype(np.float32, copy=False)
            values.append(np.ascontiguousarray(arr))
        result[key] = np.stack(values, axis=0)
    return result


def jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return repr(value)


def append_jsonl(path: Path, record: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(jsonable(dict(record)), ensure_ascii=False, sort_keys=True) + "\n")


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as stream:
        json.dump(jsonable(dict(value)), stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
    os.replace(str(tmp), str(path))


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    records = []
    with path.open("r", encoding="utf-8") as stream:
        for line_no, line in enumerate(stream, 1):
            if line.strip():
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise ValueError("Invalid JSONL at {}:{}: {}".format(path, line_no, exc))
    return records


def environment_fingerprint(dp_root: Path, checkpoint: Path, dataset: Path, device: str) -> Dict[str, Any]:
    info: Dict[str, Any] = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "dp_root": str(dp_root),
        "dp_git_commit": git_commit(dp_root),
        "checkpoint": str(checkpoint),
        "checkpoint_bytes": checkpoint.stat().st_size,
        "checkpoint_sha256": sha256_file(checkpoint),
        "dataset": str(dataset),
        "dataset_bytes": dataset.stat().st_size,
        "dataset_sha256": sha256_file(dataset),
        "device_requested": device,
    }
    try:
        import torch
        info.update({
            "torch": torch.__version__,
            "cuda_available": bool(torch.cuda.is_available()),
            "torch_cuda": torch.version.cuda,
            "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        })
    except Exception as exc:
        info["torch_import_error"] = repr(exc)
    try:
        import robomimic
        info["robomimic"] = getattr(robomimic, "__version__", "unknown")
    except Exception as exc:
        info["robomimic_import_error"] = repr(exc)
    try:
        import robosuite
        info["robosuite"] = getattr(robosuite, "__version__", "unknown")
    except Exception as exc:
        info["robosuite_import_error"] = repr(exc)
    try:
        import mujoco
        info["mujoco"] = getattr(mujoco, "__version__", "unknown")
    except Exception:
        try:
            import mujoco_py
            info["mujoco_py"] = getattr(mujoco_py, "__version__", "installed")
        except Exception as exc:
            info["mujoco_import_error"] = repr(exc)
    return info
