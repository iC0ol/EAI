"""Verify frozen resets without taking actions or evaluating a policy."""
import time

import h5py
import numpy as np

from d_alignment.environment import create_env, flatten_obs
from d_alignment.io import ROOT, read_json, write_json

initial = read_json(ROOT / "data/manifests/eval_initial_conditions.json")
assert len({r["state_sha256"] for r in initial["initial_conditions"]}) == 50
env, _ = create_env()
rows = []
start = time.monotonic()
with h5py.File(ROOT / initial["path"], "r") as f:
    for item in initial["initial_conditions"]:
        seed = item["seed"]
        np.random.seed(seed)
        env.reset()
        group = f[str(seed)]
        obs = env.reset_to({"states": group["states"][:], "model": group.attrs["model"], "ep_meta": group.attrs["ep_meta"]})
        error = float(np.max(np.abs(flatten_obs(obs) - group["obs"][:])))
        assert error < 1e-5, (seed, error)
        rows.append({"seed": seed, "max_abs_selected_obs_error": error})
env.env.close()
write_json(ROOT / "reports/gate1/eval_reset_integrity.json", {"states_checked": len(rows), "policy_episodes": 0, "action_steps": 0, "wall_seconds": time.monotonic()-start, "results": rows})
print(f"Validated {len(rows)} distinct frozen resets; 0 policy episodes / 0 action steps")
