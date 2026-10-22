"""Official robomimic wrapper; no renderers or language model imports."""
import json

import h5py
import numpy as np

from d_alignment.io import ROOT, read_json


def create_env():
    import robomimic.utils.obs_utils as ObsUtils
    from robomimic.envs.env_robosuite import EnvRobosuite

    cfg = read_json(ROOT / "configs/gate1.json")
    ObsUtils.initialize_obs_utils_with_obs_specs({"obs": {"low_dim": cfg["obs_keys"]}})
    with h5py.File(ROOT / cfg["source_path"], "r") as f:
        meta = json.loads(f["data"].attrs["env_args"])
    env = EnvRobosuite(env_name=meta["env_name"], render=False, render_offscreen=False,
                       use_image_obs=False, **meta["env_kwargs"])
    return env, meta


def flatten_obs(obs):
    cfg = read_json(ROOT / "configs/gate1.json")
    lo, hi = cfg["object_slice"]
    return np.concatenate([obs[k][lo:hi] if k == "object" else obs[k] for k in cfg["obs_keys"]]).astype(np.float32)
