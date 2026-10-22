"""Episode-level splits and action-only corruption with explicit invalid edges."""
from collections import Counter
from pathlib import Path

import h5py
import numpy as np

from d_alignment.io import ROOT, read_json, sha256, write_json

CONDITIONS = ("clean", "mixed_small_lag", "larger_lag")


def shifted_labels(actions, delta):
    """C[t]=A[t+delta]. No wrap, endpoint replication, or valid-edge invention."""
    out = np.full(actions.shape, np.nan, dtype=actions.dtype)
    t = np.arange(len(actions))
    valid = (t + delta >= 0) & (t + delta < len(actions))
    out[t[valid]] = actions[t[valid] + delta]
    return out


def window_starts(length, max_shift, horizon):
    # Every prediction target is inside [max_shift, length-max_shift).
    return np.arange(max_shift, length - max_shift - horizon + 1, dtype=np.int64)


def decode_names(values):
    return [v.decode() if isinstance(v, bytes) else str(v) for v in values]


def observation(ep, keys):
    cfg = read_json(ROOT / "configs/gate1.json")
    values = []
    for k in keys:
        value = ep["obs"][k][:]
        if k == "object":
            lo, hi = cfg["object_slice"]
            value = value[:, lo:hi]
        values.append(value)
    return np.concatenate(values, axis=-1).astype(np.float32)


def prepare():
    cfg = read_json(ROOT / "configs/gate1.json")
    versions = read_json(ROOT / "configs/versions.json")
    source = ROOT / cfg["source_path"]
    assert sha256(source) == versions["dataset"]["sha256"], "Unexpected source bytes"
    split_path = ROOT / "data/manifests/splits.json"
    assert not split_path.exists(), "Frozen artifacts exist; refuse to regenerate"
    with h5py.File(source, "r") as f:
        names = sorted(f["data"], key=lambda n: int(n.split("_")[-1]))
        assert len(names) == 200, f"Expected official PH 200 demos, found {len(names)}"
        official_train = decode_names(f["mask/train"][:])
        validation = decode_names(f["mask/valid"][:])
        assert len(official_train) == 180 and len(validation) == 20
        rng = np.random.default_rng(cfg["split_seed"])
        ordered = rng.permutation(sorted(official_train)).tolist()
        na, nl = cfg["anchor_episodes"], cfg["lag_test_episodes"]
        anchors, lag_test, train = ordered[:na], ordered[na:na+nl], sorted(ordered[na+nl:])
        n_corrupt = int(len(train) * cfg["corruption_fraction"])
        assert n_corrupt * 2 == len(train) and n_corrupt % 6 == 0
        crng = np.random.default_rng(cfg["contamination_seed"])
        corrupt_ids = crng.permutation(train)[:n_corrupt].tolist()
        offsets = {}
        for cond, values in (("clean", [0]), ("mixed_small_lag", cfg["mixed_deltas"]), ("larger_lag", cfg["large_deltas"])):
            ds = {n: 0 for n in train}
            if cond != "clean":
                balanced = np.tile(values, n_corrupt // len(values))
                crng.shuffle(balanced)
                ds.update({n: int(d) for n, d in zip(corrupt_ids, balanced)})
            offsets[cond] = ds

        lengths = {n: len(f["data"][n]["actions"]) for n in names}
        split = {
            "source_sha256": sha256(source), "config_sha256": sha256(ROOT / "configs/gate1.json"),
            "seed": cfg["split_seed"], "train": train, "validation": sorted(validation),
            "anchors": sorted(anchors), "lag_test": sorted(lag_test),
            "lengths": lengths, "common_interval": "[4, T-4), zero-based, half-open",
            "horizon": cfg["horizon"], "max_shift": cfg["max_shift"],
        }
        all_obs = np.concatenate([observation(f["data"][n], cfg["obs_keys"])[4:-4] for n in train])
        all_actions = np.concatenate([f["data"][n]["actions"][4:-4] for n in train])
        stats = {}
        for key, data in (("obs", all_obs), ("action", all_actions)):
            low, high = data.min(axis=0), data.max(axis=0)
            span = high - low
            scale = np.where(span > 1e-6, 2.0 / np.maximum(span, 1e-6), 1.0)
            offset = np.where(span > 1e-6, -(high + low) / np.maximum(span, 1e-6), 0.0)
            if key == "action":
                scale, offset = np.ones_like(low), np.zeros_like(low)
            stats[key] = {"min": low.tolist(), "max": high.tolist(), "mean": data.mean(axis=0).tolist(), "std": data.std(axis=0).tolist(), "scale": scale.tolist(), "offset": offset.tolist()}
        write_json(ROOT / "data/manifests/normalization.json", stats)
        manifest = {"definition": cfg["definition"], "seed": cfg["contamination_seed"], "source_sha256": split["source_sha256"], "config": cfg, "conditions": {}}
        for cond in CONDITIONS:
            path = ROOT / f"data/derived/{cond}.hdf5"
            path.parent.mkdir(exist_ok=True, parents=True)
            with h5py.File(path, "w") as out:
                for n in train:
                    out.create_dataset(f"data/{n}/actions", data=shifted_labels(f["data"][n]["actions"][:], offsets[cond][n]), compression="gzip")
            manifest["conditions"][cond] = {
                "path": str(path.relative_to(ROOT)), "sha256": sha256(path),
                "episode_delta": offsets[cond], "delta_counts": dict(Counter(offsets[cond].values())),
                "train_episode_count": len(train), "corrupted_episode_count": sum(d != 0 for d in offsets[cond].values()),
                "valid_timesteps": sum(lengths[n] - 8 for n in train),
                "valid_sequence_count": sum(len(window_starts(lengths[n], 4, cfg["horizon"])) for n in train),
            }
        write_json(split_path, split)
        write_json(ROOT / "data/manifests/injection_truth.json", manifest)
        write_json(ROOT / "data/manifests/eval_seeds.json", {"seeds": list(range(cfg["eval_seeds"]["start"], cfg["eval_seeds"]["start"] + cfg["eval_seeds"]["count"])), "max_steps": cfg["eval_max_steps"]})
    print({"train": len(train), "validation": len(validation), "anchors": len(anchors), "lag_test": len(lag_test), "corrupted": n_corrupt})


class SequenceData:
    """Never reads injection_truth.json. Full-window sampling, no padding."""
    def __init__(self, condition="clean", partition="train"):
        self.cfg = read_json(ROOT / "configs/gate1.json")
        self.split = read_json(ROOT / "data/manifests/splits.json")
        self.obs, self.actions, self.index = [], [], []
        assert condition in CONDITIONS and partition in ("train", "validation")
        derived = None
        if partition == "train":
            derived = h5py.File(ROOT / f"data/derived/{condition}.hdf5", "r")
        try:
            with h5py.File(ROOT / self.cfg["source_path"], "r") as f:
                for n in self.split[partition]:
                    ep = f["data"][n]
                    self.obs.append(observation(ep, self.cfg["obs_keys"]))
                    self.actions.append((derived["data"][n]["actions"][:] if derived else ep["actions"][:]).astype(np.float32))
                    ei = len(self.obs) - 1
                    self.index.extend((ei, int(s)) for s in window_starts(len(ep["actions"]), 4, self.cfg["horizon"]))
        finally:
            if derived:
                derived.close()

    def __len__(self):
        return len(self.index)

    def __getitem__(self, idx):
        ep, start = self.index[idx]
        h = self.cfg["horizon"]
        action = self.actions[ep][start:start+h].copy()
        assert np.isfinite(action).all()
        return {"obs": self.obs[ep][start:start+h].copy(), "action": action}


if __name__ == "__main__":
    prepare()
