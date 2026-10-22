"""Unmodified official DP network, objective, EMA and action-slice convention."""
import copy

import numpy as np
import torch
from diffusers.schedulers.scheduling_ddim import DDIMScheduler
from diffusion_policy.model.common.normalizer import LinearNormalizer, SingleFieldLinearNormalizer
from diffusion_policy.model.diffusion.conditional_unet1d import ConditionalUnet1D
from diffusion_policy.model.diffusion.ema_model import EMAModel
from diffusion_policy.policy.diffusion_unet_lowdim_policy import DiffusionUnetLowdimPolicy

from d_alignment.io import ROOT, read_json


def make_policy():
    cfg = read_json(ROOT / "configs/gate1.json")
    net = ConditionalUnet1D(input_dim=7, global_cond_dim=cfg["obs_dim"]*cfg["n_obs_steps"], **cfg["model"])
    sched = cfg["scheduler"]
    # DDIM uses the same forward noising objective as DDPM. eta=0 is its default.
    scheduler = DDIMScheduler(num_train_timesteps=sched["num_train_timesteps"],
                              beta_schedule=sched["beta_schedule"], clip_sample=sched["clip_sample"],
                              prediction_type=sched["prediction_type"], set_alpha_to_one=True,
                              steps_offset=0)
    policy = DiffusionUnetLowdimPolicy(model=net, noise_scheduler=scheduler,
        horizon=cfg["horizon"], obs_dim=cfg["obs_dim"], action_dim=7,
        n_obs_steps=cfg["n_obs_steps"], n_action_steps=cfg["n_action_steps"],
        num_inference_steps=sched["num_inference_steps"], obs_as_global_cond=True,
        oa_step_convention=True)
    stats = read_json(ROOT / "data/manifests/normalization.json")
    normalizer = LinearNormalizer()
    for k, v in stats.items():
        normalizer[k] = SingleFieldLinearNormalizer.create_manual(
            scale=np.asarray(v["scale"], dtype=np.float32), offset=np.asarray(v["offset"], dtype=np.float32),
            input_stats_dict={n: np.asarray(v[n], dtype=np.float32) for n in ("min", "max", "mean", "std")})
    policy.set_normalizer(normalizer)
    return policy


def make_ema(policy):
    cfg = read_json(ROOT / "configs/gate1.json")
    return EMAModel(copy.deepcopy(policy), **cfg["ema"])
