"""Freeze 50 normal initial simulator states before any policy training."""
import hashlib
import json

import h5py
import numpy as np

from d_alignment.environment import create_env, flatten_obs
from d_alignment.io import ROOT, read_json, sha256, write_json

env, meta = create_env()
cfg = read_json(ROOT / "configs/gate1.json")
path = ROOT / "data/derived/eval_initial_states.hdf5"
assert not path.exists(), "Do not overwrite frozen initial conditions"
path.parent.mkdir(parents=True, exist_ok=True)
manifest = []
with h5py.File(path, "w") as f:
    for seed in read_json(ROOT / "data/manifests/eval_seeds.json")["seeds"]:
        np.random.seed(seed)
        env.reset()
        state = env.get_state()
        obs = env.reset_to(state)
        # This is the exact reset_to procedure used in every policy evaluation.
        state = env.get_state()
        g = f.create_group(str(seed))
        g.create_dataset("states", data=state["states"])
        g.attrs["model"] = state["model"]
        g.attrs["ep_meta"] = state.get("ep_meta", "{}")
        g.create_dataset("obs", data=flatten_obs(obs))
        manifest.append({"seed": seed, "state_sha256": hashlib.sha256(state["states"].tobytes()).hexdigest(), "obs_sha256": hashlib.sha256(flatten_obs(obs).tobytes()).hexdigest(), "xml_sha256": hashlib.sha256(state["model"].encode()).hexdigest()})
write_json(ROOT / "data/manifests/eval_initial_conditions.json", {"path": str(path.relative_to(ROOT)), "sha256": sha256(path), "count": len(manifest), "initial_conditions": manifest})
env.env.close()
print(f"Froze {len(manifest)} initial conditions")
