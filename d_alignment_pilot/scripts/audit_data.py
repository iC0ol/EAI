"""Inspect raw bytes, transition continuity and actual official simulation."""
import importlib.metadata
import json
import platform
import time

import h5py
import numpy as np
import torch

from d_alignment.environment import create_env
from d_alignment.io import ROOT, read_json, sha256, write_json

cfg = read_json(ROOT / "configs/gate1.json")
source = ROOT / cfg["source_path"]
result = {"source_sha256": sha256(source), "python": platform.python_version(),
          "torch": torch.__version__, "torch_cuda": torch.version.cuda,
          "cuda_available": torch.cuda.is_available(), "gpu": torch.cuda.get_device_name(0)}
with h5py.File(source, "r") as f:
    meta = json.loads(f["data"].attrs["env_args"])
    result["env_args"] = meta
    result["root_keys"] = list(f.keys())
    result["data_attrs"] = {k: (v.item() if hasattr(v, "item") else str(v)) for k, v in f["data"].attrs.items() if k != "env_args"}
    names = sorted(f["data"], key=lambda n: int(n.split("_")[-1]))
    ep = f["data"][names[0]]
    result["demo"] = names[0]
    result["episode_keys"] = list(ep.keys())
    result["episode_shapes"] = {}
    ep.visititems(lambda name, obj: result["episode_shapes"].update({name: {"shape": list(obj.shape), "dtype": str(obj.dtype)}}) if isinstance(obj, h5py.Dataset) else None)
    result["demo_count"] = len(names)
    result["length_range"] = [min(len(f["data"][n]["actions"]) for n in names), max(len(f["data"][n]["actions"]) for n in names)]
    result["total_transitions"] = sum(len(f["data"][n]["actions"]) for n in names)
    result["mask_counts"] = {k: len(f["mask"][k]) for k in f["mask"]}
    result["next_obs_to_following_obs_max_abs"] = {k: max(float(np.max(np.abs(f["data"][n]["next_obs"][k][:-1] - f["data"][n]["obs"][k][1:]))) for n in names) for k in ep["obs"]}
    result["states_time_differences_demo0"] = np.unique(np.round(np.diff(ep["states"][:, 0]), 10)).tolist()
    result["transition_example_t10"] = {"obs": {k: ep["obs"][k][10].tolist() for k in cfg["obs_keys"]}, "action": ep["actions"][10].tolist(), "next_obs": {k: ep["next_obs"][k][10].tolist() for k in cfg["obs_keys"]}}
    write_json(ROOT / "reports/gate1/data_audit.json", result)

    # Compare state-restored observations and a normal full-action replay. These
    # checks supplement the extraction code; equal lengths alone are insufficient.
    start = time.monotonic()
    env, _ = create_env()
    initial = {"model": ep.attrs["model_file"], "states": ep["states"][0], "ep_meta": ep.attrs.get("ep_meta", None)}
    env.reset()
    obs = env.reset_to(initial)
    result["state_restore_max_abs"] = {}
    for t in [0, 10, len(ep["actions"])//2]:
        restored = env.reset_to({"states": ep["states"][t]})
        result["state_restore_max_abs"][str(t)] = {k: float(np.max(np.abs(restored[k] - ep["obs"][k][t]))) for k in cfg["obs_keys"]}
    obs = env.reset_to(initial)
    eef_errors, successes = [], []
    for t, a in enumerate(ep["actions"][:]):
        obs, reward, done, info = env.step(a)
        eef_errors.append(float(np.linalg.norm(obs["robot0_eef_pos"] - ep["next_obs/robot0_eef_pos"][t])))
        successes.append(bool(env.is_success()["task"]))
    result["raw_action_replay"] = {"steps": len(eef_errors), "success": any(successes), "first_success_step": next((i+1 for i, s in enumerate(successes) if s), None), "eef_error_median_m": float(np.median(eef_errors)), "eef_error_max_m": float(max(eef_errors)), "wall_seconds": time.monotonic()-start}
    result["runtime_control_freq"] = env.env.control_freq
    result["runtime_model_timestep"] = env.env.model_timestep
    result["runtime_control_timestep"] = env.env.control_timestep
    result["runtime_action_dim"] = env.env.action_dim
    write_json(ROOT / "reports/gate1/data_audit.json", result)
    print(json.dumps({k: result[k] for k in ("demo_count", "total_transitions", "runtime_control_freq", "runtime_action_dim", "state_restore_max_abs", "raw_action_replay")}, indent=2))
    env.env.close()
