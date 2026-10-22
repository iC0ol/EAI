"""One documented pretraining amendment; never resample or change action files."""
import h5py
import numpy as np

from d_alignment.data import observation
from d_alignment.io import ROOT, read_json, sha256, write_json

assert not (ROOT / "data/manifests/frozen_protocol.json").exists()
assert not list((ROOT / "outputs/gate1").glob("*/run.json")), "No post-result amendment allowed"
out = ROOT / "data/manifests/pretraining_observation_amendment.json"
assert not out.exists()
cfg = read_json(ROOT / "configs/gate1.json")
split = read_json(ROOT / "data/manifests/splits.json")
truth = read_json(ROOT / "data/manifests/injection_truth.json")
before = split["config_sha256"]
for cond in truth["conditions"].values():
    assert sha256(ROOT / cond["path"]) == cond["sha256"]
stats = read_json(ROOT / "data/manifests/normalization.json")
with h5py.File(ROOT / cfg["source_path"], "r") as f:
    obs = np.concatenate([observation(f["data"][n], cfg["obs_keys"])[4:-4] for n in split["train"]])
low, high = obs.min(axis=0), obs.max(axis=0)
span = high - low
scale = np.where(span > 1e-6, 2./np.maximum(span, 1e-6), 1.)
offset = np.where(span > 1e-6, -(high+low)/np.maximum(span, 1e-6), 0.)
stats["obs"] = {"min": low.tolist(), "max": high.tolist(), "mean": obs.mean(axis=0).tolist(), "std": obs.std(axis=0).tolist(), "scale": scale.tolist(), "offset": offset.tolist()}
write_json(ROOT / "data/manifests/normalization.json", stats)
split["config_sha256"] = sha256(ROOT / "configs/gate1.json")
truth["original_pre_audit_config"] = truth["config"]
truth["config"] = cfg
write_json(ROOT / "data/manifests/splits.json", split)
write_json(ROOT / "data/manifests/injection_truth.json", truth)
write_json(out, {"reason": cfg["observation_selection_reason"], "optimizer_updates_before_amendment": 0,
    "previous_config_sha256": before, "final_config_sha256": split["config_sha256"],
    "unchanged_action_file_sha256": {k: v["sha256"] for k, v in truth["conditions"].items()},
    "evidence": "reports/gate1/observation_cache_summary.json"})
print("Finalized 16 raw synchronized coordinates before any training; action conditions unchanged")
