"""Inspect an official Diffusion Policy checkpoint config without loading DP.

This tool intentionally imports only torch, dill and omegaconf. It is the first
workstation gate: verify H, To, n_action_steps, shape_meta, task and EMA before
starting any simulator or committing an execution horizon.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import dill
import torch
from omegaconf import OmegaConf


def _plain(value):
    if not OmegaConf.is_config(value):
        return value
    return OmegaConf.to_container(value, resolve=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args()

    path = args.checkpoint.expanduser().resolve()
    kwargs = {"pickle_module": dill, "map_location": "cpu"}
    try:
        payload = torch.load(str(path), weights_only=False, **kwargs)
    except TypeError:
        payload = torch.load(str(path), **kwargs)

    cfg = payload["cfg"]
    try:
        OmegaConf.resolve(cfg)
    except Exception:
        pass

    shape_meta = _plain(cfg.task.shape_meta)
    horizon = int(cfg.horizon)
    n_obs_steps = int(cfg.n_obs_steps)
    n_action_steps = int(cfg.n_action_steps)
    available = horizon - (n_obs_steps - 1)
    result = {
        "checkpoint": str(path),
        "checkpoint_bytes": path.stat().st_size,
        "workspace_target": str(cfg.get("_target_", "")),
        "horizon": horizon,
        "n_obs_steps": n_obs_steps,
        "n_action_steps": n_action_steps,
        "available_future_actions": available,
        "h16_executable": bool(16 <= available),
        "dataset_obs_steps": _plain(cfg.get("dataset_obs_steps")),
        "use_ema": bool(_plain(cfg.training.use_ema)),
        "task_name": _plain(cfg.task.task_name),
        "dataset_type": _plain(cfg.task.dataset_type),
        "dataset_path": _plain(cfg.task.dataset_path),
        "abs_action": _plain(cfg.task.get("abs_action")),
        "rotation_rep": _plain(cfg.task.get("dataset", {}).get("rotation_rep"))
        if OmegaConf.is_config(cfg.task.get("dataset")) else None,
        "action_dim": int(shape_meta["action"]["shape"][0]),
        "shape_meta": shape_meta,
        "state_dict_keys": sorted(payload.get("state_dicts", {}).keys()),
        "pickle_keys": sorted(payload.get("pickles", {}).keys()),
        "normalizer_state_keys": {
            name: len([key for key in state_dict if "normalizer" in key])
            for name, state_dict in payload.get("state_dicts", {}).items()
        },
        "normalizer_present": any(
            "normalizer" in key
            for state_dict in payload.get("state_dicts", {}).values()
            for key in state_dict
        ),
        "ema_state_present": "ema_model" in payload.get("state_dicts", {}),
    }
    text = json.dumps(result, indent=2, sort_keys=True, default=str)
    print(text)
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
