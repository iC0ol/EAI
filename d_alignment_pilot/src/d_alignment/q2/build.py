"""Trusted data constructor. This module is never mounted in the estimator."""
import argparse
import hashlib
import secrets
from pathlib import Path

import h5py
import numpy as np

from .common import deadline, read_json, save_view, sha256, write_json

ROOT = Path(__file__).resolve().parents[3]
LOCAL = ROOT / "data/derived/q2_blind"
CONFIG = ROOT / "configs/q2_blind/experiment.json"


def view_from_group(group, sample_id, trajectory_id, delta, crop=4):
    length = len(group["actions"])
    idx = np.arange(crop, length-crop)
    assert (idx+delta).min() >= 0 and (idx+delta).max() < length
    view = {"sample_id": np.asarray(sample_id), "trajectory_id": np.asarray(trajectory_id),
            "command": group["actions"][:][idx+delta].astype(np.float64)}
    for prefix, h5name in [("", "obs"), ("next_", "next_obs")]:
        for target, source in [("position", "robot0_eef_pos"), ("quaternion", "robot0_eef_quat"), ("gripper", "robot0_gripper_qpos")]:
            view[prefix+target] = group[h5name][source][:][idx].astype(np.float64)
    return view


def build_anchors():
    cfg = read_json(CONFIG)
    deadline(cfg)
    assert sha256(ROOT / cfg["source_path"]) == cfg["source_sha256"]
    out = LOCAL / "anchors"
    out.mkdir(parents=True, exist_ok=False)
    hashes = {}
    with h5py.File(ROOT / cfg["source_path"], "r") as source:
        for j, name in enumerate(cfg["anchors"]):
            identity = f"anchor_{j:04d}"
            path = out / f"{identity}.npz"
            save_view(path, view_from_group(source["data"][name], identity, identity, 0))
            hashes[name] = {"view_name": path.name, "sha256": sha256(path)}
    write_json(ROOT / "outputs/q2_blind/anchor_view_hashes.json", hashes)
    print("Built eight authorized clean anchor views; no lag-test actions read")


def build_queries():
    cfg = read_json(CONFIG)
    deadline(cfg)
    assert sha256(ROOT / cfg["source_path"]) == cfg["source_sha256"]
    # Model is selected and frozen before the independent test packets exist.
    receipt = read_json(ROOT / "outputs/q2_blind/anchor_model_frozen.json")
    assert sha256(LOCAL / "model/model.json") == receipt["model_sha256"]
    out, private = LOCAL / "queries", LOCAL / "private"
    out.mkdir(parents=True, exist_ok=False)
    private.mkdir(parents=True, exist_ok=False)
    seed = secrets.randbits(128)
    rng = np.random.default_rng(seed)
    cases, dispatch, hashes, lengths = {}, [], {}, {}
    with h5py.File(ROOT / cfg["source_path"], "r") as source:
        for name in cfg["lag_test"]:
            trajectory = rng.bytes(16).hex()
            group = source["data"][name]
            clean = group["actions"][:].astype(np.float64)
            oracle = private / f"{trajectory}.npz"
            with oracle.open("xb") as handle:
                np.savez_compressed(handle, clean_action=clean)
            for delta in cfg["injected_lags"]:
                sample = rng.bytes(16).hex()
                path = out / f"{sample}.npz"
                view = view_from_group(group, sample, trajectory, delta)
                save_view(path, view)
                cases[sample] = {"episode": name, "trajectory_id": trajectory, "delta": delta,
                                 "oracle_path": oracle.name, "source_length": len(clean), "outer_crop": 4}
                hashes[sample] = sha256(path)
                lengths[sample] = len(view["command"])
                dispatch.append(sample)
    rng.shuffle(dispatch)
    write_json(private / "truth.json", {"anonymization_entropy_seed": str(seed), "cases": cases})
    # Only opaque names, input hashes and shapes; no injection/source mapping.
    write_json(ROOT / "outputs/q2_blind/blind_input_hashes.json", {"files": hashes, "lengths": lengths, "dispatch_order": dispatch,
               "test_samples": len(cases), "independent_sources": len(cfg["lag_test"]),
               "private_truth_sha256": sha256(private / "truth.json")})
    print("Built 112 finite anonymous packets from 16 sources; private mapping not printed")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=["anchors", "queries"])
    args = p.parse_args()
    build_anchors() if args.mode == "anchors" else build_queries()
