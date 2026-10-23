"""Reconstruct the existing Clean architecture from its frozen configuration."""
import numpy as np
import torch
from diffusers.schedulers.scheduling_ddim import DDIMScheduler
from diffusion_policy.model.common.normalizer import LinearNormalizer, SingleFieldLinearNormalizer
from diffusion_policy.model.diffusion.conditional_unet1d import ConditionalUnet1D
from diffusion_policy.policy.diffusion_unet_lowdim_policy import DiffusionUnetLowdimPolicy

from .io import D_ROOT, config, read_json, sha256, array_hash, stable_seed
from .assets import checkpoint_path


def setup_torch():
    torch.set_num_threads(config()["torch_threads"])
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.allow_tf32 = False
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.use_deterministic_algorithms(True)


def make_policy(seed, device="cuda"):
    cfg = read_json(D_ROOT / "configs/gate1.json")
    sched = cfg["scheduler"]
    net = ConditionalUnet1D(input_dim=7, global_cond_dim=32, **cfg["model"])
    scheduler = DDIMScheduler(num_train_timesteps=sched["num_train_timesteps"],
        beta_schedule=sched["beta_schedule"], clip_sample=sched["clip_sample"],
        prediction_type=sched["prediction_type"], set_alpha_to_one=True, steps_offset=0)
    policy = DiffusionUnetLowdimPolicy(model=net, noise_scheduler=scheduler,
        horizon=cfg["horizon"], obs_dim=16, action_dim=7, n_obs_steps=2, n_action_steps=8,
        num_inference_steps=sched["num_inference_steps"], obs_as_global_cond=True,
        oa_step_convention=True, eta=0.)
    normalizer = LinearNormalizer()
    for k, v in read_json(D_ROOT / "data/manifests/normalization.json").items():
        normalizer[k] = SingleFieldLinearNormalizer.create_manual(
            scale=np.asarray(v["scale"], dtype=np.float32), offset=np.asarray(v["offset"], dtype=np.float32),
            input_stats_dict={n: np.asarray(v[n], dtype=np.float32) for n in ("min", "max", "mean", "std")})
    policy.set_normalizer(normalizer)
    assert sha256(checkpoint_path(seed)) == config()["checkpoint_sha256"][str(seed)]
    policy.load_state_dict(torch.load(checkpoint_path(seed), map_location="cpu")["policy"], strict=True)
    policy.to(device).eval().requires_grad_(False)
    return policy


def predict(policy, history, state_id, replan_index, stream=0):
    seed = stable_seed(state_id, replan_index, stream)
    gen = torch.Generator(device=policy.device).manual_seed(seed)
    clone = torch.Generator(device=policy.device).manual_seed(seed)
    # Same initial tensor that the unmodified upstream conditional_sample draws.
    expected_noise = torch.randn((1, 16, 7), device=policy.device, dtype=policy.dtype, generator=clone)
    schedule = {"replan_index": replan_index, "seed": seed,
                "generator_before_sha256": array_hash(gen.get_state().cpu().numpy()),
                "initial_noise_sha256": array_hash(expected_noise.cpu().numpy()),
                "history_sha256": array_hash(np.stack(history))}
    policy.kwargs["generator"] = gen
    with torch.inference_mode():
        out = policy.predict_action({"obs": torch.from_numpy(np.stack(history)[None]).to(policy.device)})
    action = out["action"][0].cpu().numpy()
    schedule["generator_after_sha256"] = array_hash(gen.get_state().cpu().numpy())
    assert action.shape == (8, 7) and np.isfinite(action).all()
    return action, schedule, expected_noise.cpu().numpy()
