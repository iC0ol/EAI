"""Reconstruct ignored artifacts from committed manifests; never resample truth.

This is a data-generation program. It may read injection truth. It is not an
estimator or policy input. Existing artifacts are only verified, not overwritten.
"""
import argparse
import hashlib
import sys

import h5py
import numpy as np

from d_alignment.data import shifted_labels
from d_alignment.environment import create_env, flatten_obs
from d_alignment.io import ROOT, read_json, sha256, write_json

p = argparse.ArgumentParser()
p.add_argument("--verify-reconstruction", action="store_true", help="Write a separate ignored copy and verify bytes")
p.add_argument("--actions-only", action="store_true", help="Do not create a simulator while another evaluation is running")
args = p.parse_args()
cfg = read_json(ROOT / "configs/gate1.json")
split = read_json(ROOT / "data/manifests/splits.json")
truth = read_json(ROOT / "data/manifests/injection_truth.json")
assert sha256(ROOT / cfg["source_path"]) == split["source_sha256"]
scratch = ROOT / ".cache/reconstruction_check"
if args.verify_reconstruction:
    scratch.mkdir(parents=True, exist_ok=True)
records = []
with h5py.File(ROOT / cfg["source_path"], "r") as source:
    for name, condition in truth["conditions"].items():
        target = scratch / f"{name}.hdf5" if args.verify_reconstruction else ROOT / condition["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            with h5py.File(target, "w") as out:
                for episode in split["train"]:
                    labels = shifted_labels(source["data"][episode]["actions"][:], condition["episode_delta"][episode])
                    out.create_dataset(f"data/{episode}/actions", data=labels, compression="gzip")
        actual = sha256(target)
        assert actual == condition["sha256"], (str(target), actual, condition["sha256"])
        records.append({"artifact": name, "sha256": actual, "matches": True})

if args.actions_only:
    if args.verify_reconstruction:
        write_json(ROOT / "reports/gate1/reconstruction_actions_integrity.json", {"resampling": False, "records": records})
    print("Verified all frozen action files without starting a simulator")
    sys.exit(0)

initial = read_json(ROOT / "data/manifests/eval_initial_conditions.json")
target = scratch / "eval_initial_states.hdf5" if args.verify_reconstruction else ROOT / initial["path"]
target.parent.mkdir(parents=True, exist_ok=True)
if not target.exists():
    env, _ = create_env()
    try:
        with h5py.File(target, "w") as out:
            for item in initial["initial_conditions"]:
                seed = item["seed"]
                np.random.seed(seed)
                env.reset()
                state = env.get_state()
                obs = env.reset_to(state)
                state = env.get_state()
                assert hashlib.sha256(state["states"].tobytes()).hexdigest() == item["state_sha256"]
                assert hashlib.sha256(flatten_obs(obs).tobytes()).hexdigest() == item["obs_sha256"]
                assert hashlib.sha256(state["model"].encode()).hexdigest() == item["xml_sha256"], "XML assets use absolute paths: reproduce under the recorded /home/asus/EAI workspace with the pinned source layout"
                group = out.create_group(str(seed))
                group.create_dataset("states", data=state["states"])
                group.attrs["model"] = state["model"]
                group.attrs["ep_meta"] = state.get("ep_meta", "{}")
                group.create_dataset("obs", data=flatten_obs(obs))
    finally:
        env.env.close()
assert sha256(target) == initial["sha256"]
records.append({"artifact": "eval_initial_states", "sha256": sha256(target), "matches": True})
if args.verify_reconstruction:
    write_json(ROOT / "reports/gate1/reconstruction_integrity.json", {"resampling": False, "policy_training_updates": 0, "records": records})
print("Verified frozen action conditions and all 50 initial states; no resampling")
