from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, Mapping

import numpy as np


def load_diffusion_policy_checkpoint(dp_root: Path, checkpoint_path: Path, device: str):
    """Load a native Diffusion Policy checkpoint using the upstream eval.py path."""
    dp_root = Path(dp_root).resolve()
    checkpoint_path = Path(checkpoint_path).resolve()
    if not (dp_root / "diffusion_policy").is_dir():
        raise FileNotFoundError("DP source root does not contain diffusion_policy/: {}".format(dp_root))
    if not checkpoint_path.is_file():
        raise FileNotFoundError("Checkpoint not found: {}".format(checkpoint_path))
    if str(dp_root) not in sys.path:
        sys.path.insert(0, str(dp_root))

    import dill
    import hydra
    import torch
    from omegaconf import OmegaConf

    # The official training workspace registers this resolver. Registering it here
    # mirrors upstream eval behavior when the pickled config still has interpolations.
    try:
        OmegaConf.register_new_resolver("eval", eval, replace=True)
    except Exception:
        pass

    load_kwargs = {"pickle_module": dill, "map_location": "cpu"}
    try:
        payload = torch.load(str(checkpoint_path), weights_only=False, **load_kwargs)
    except TypeError:
        payload = torch.load(str(checkpoint_path), **load_kwargs)
    if "cfg" not in payload:
        raise KeyError("Checkpoint payload has no 'cfg'; not a native Diffusion Policy checkpoint")
    cfg = payload["cfg"]
    try:
        OmegaConf.resolve(cfg)
    except Exception as exc:
        raise RuntimeError("Could not resolve checkpoint Hydra config: {}".format(exc))

    target = getattr(cfg, "_target_", None)
    if not target:
        raise ValueError("Checkpoint config is missing workspace _target_")
    workspace_cls = hydra.utils.get_class(target)
    workspace = workspace_cls(cfg, output_dir=str(checkpoint_path.parent))
    workspace.load_payload(payload, exclude_keys=None, include_keys=None)

    use_ema = bool(getattr(getattr(cfg, "training", {}), "use_ema", False))
    policy = workspace.ema_model if use_ema else workspace.model
    policy.to(torch.device(device))
    policy.eval()

    shape_meta = OmegaConf.to_container(cfg.task.shape_meta, resolve=True)
    n_obs_steps = int(cfg.n_obs_steps)
    prediction_horizon = int(getattr(policy, "horizon", cfg.horizon))
    action_dim = int(shape_meta["action"]["shape"][0])
    if int(getattr(policy, "action_dim", action_dim)) != action_dim:
        raise ValueError("Policy action_dim disagrees with checkpoint shape_meta")
    if not hasattr(policy, "predict_action"):
        raise TypeError("Loaded checkpoint policy has no predict_action method")

    return {
        "torch": torch,
        "workspace": workspace,
        "policy": policy,
        "cfg": cfg,
        "shape_meta": shape_meta,
        "n_obs_steps": n_obs_steps,
        "prediction_horizon": prediction_horizon,
        "action_dim": action_dim,
        "use_ema": use_ema,
    }


def predict_full_future_chunk(
    policy: Any,
    torch_module: Any,
    obs_batch: Mapping[str, np.ndarray],
    device: str,
    n_obs_steps: int,
    prediction_horizon: int,
) -> np.ndarray:
    """Return all future actions, not only policy.n_action_steps returned in 'action'.

    DiffusionUnetHybridImagePolicy.predict_action returns action_pred (the full
    unnormalised trajectory) and action (only the configured n_action_steps slice).
    Gate B must read action_pred to sweep execution horizons without changing weights.
    """
    tensors = {
        key: torch_module.from_numpy(np.ascontiguousarray(value)).unsqueeze(0).to(device)
        for key, value in obs_batch.items()
    }
    with torch_module.no_grad():
        result = policy.predict_action(tensors)
    if "action_pred" not in result:
        raise RuntimeError(
            "Policy output has no action_pred. Refusing to use the truncated 'action' "
            "field because it may contain only the checkpoint's default n_action_steps."
        )
    pred = result["action_pred"]
    if pred.ndim != 3 or pred.shape[0] != 1:
        raise ValueError("Expected action_pred [1,T,A], got {}".format(tuple(pred.shape)))
    start = int(n_obs_steps) - 1
    if int(pred.shape[1]) != int(prediction_horizon):
        raise ValueError(
            "Checkpoint action_pred length {} does not match configured H={}.".format(
                pred.shape[1], prediction_horizon
            )
        )
    future = pred[:, start:, :]
    expected_future = int(prediction_horizon) - start
    if future.shape[1] != expected_future or expected_future < 1:
        raise ValueError(
            "Checkpoint returned {} total slots but only {} executable future actions "
            "remain after n_obs_steps={}. Do not pad or reuse stale actions.".format(
                pred.shape[1], future.shape[1], n_obs_steps
            )
        )
    actions = future[0].detach().to("cpu").numpy().astype(np.float32, copy=False)
    if not np.all(np.isfinite(actions)):
        raise FloatingPointError("Policy produced NaN/Inf actions")
    return actions
