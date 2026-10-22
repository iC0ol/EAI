"""Required safety properties against independent raw-array indexing."""
import itertools

import h5py
import numpy as np
import pytest

from d_alignment.data import CONDITIONS, SequenceData, shifted_labels, window_starts
from d_alignment.io import ROOT, read_json, sha256


@pytest.mark.parametrize("delta", [-4, -2, -1, 0, 1, 2, 4])
def test_known_ramp_no_wrap_and_exact_inverse(delta):
    raw = np.arange(37 * 7, dtype=np.float32).reshape(37, 7)
    cor = shifted_labels(raw, delta)
    for t in range(37):
        if 0 <= t + delta < 37:
            np.testing.assert_array_equal(cor[t], raw[t+delta])
        else:
            assert np.isnan(cor[t]).all()
    t = np.arange(4, 33)
    np.testing.assert_array_equal(cor[t-delta], raw[t])
    if delta == 0:
        np.testing.assert_array_equal(cor, raw)


def test_official_source_and_split_isolation():
    cfg = read_json(ROOT / "configs/gate1.json")
    split = read_json(ROOT / "data/manifests/splits.json")
    assert sha256(ROOT / cfg["source_path"]) == split["source_sha256"]
    sets = [set(split[p]) for p in ("train", "validation", "anchors", "lag_test")]
    for a, b in itertools.combinations(sets, 2):
        assert a.isdisjoint(b)
    with h5py.File(ROOT / cfg["source_path"], "r") as f:
        assert set.union(*sets) == set(f["data"])
        assert sets[1] == {v.decode() for v in f["mask/valid"][:]}
    assert list(map(len, sets)) == [156, 20, 8, 16]


def test_frozen_conditions_and_raw_inverse():
    cfg = read_json(ROOT / "configs/gate1.json")
    truth = read_json(ROOT / "data/manifests/injection_truth.json")
    split = read_json(ROOT / "data/manifests/splits.json")
    assert sha256(ROOT / "configs/gate1.json") == split["config_sha256"]
    counts, corrupt_sets = [], []
    with h5py.File(ROOT / cfg["source_path"], "r") as f:
        for cond in CONDITIONS:
            meta = truth["conditions"][cond]
            assert sha256(ROOT / meta["path"]) == meta["sha256"]
            assert meta["corrupted_episode_count"] == (0 if cond == "clean" else 78)
            counts.append((meta["valid_timesteps"], meta["valid_sequence_count"]))
            corrupt_sets.append({n for n, d in meta["episode_delta"].items() if d})
            with h5py.File(ROOT / meta["path"], "r") as cf:
                assert set(cf["data"]) == set(split["train"])
                for n, d in meta["episode_delta"].items():
                    raw = f["data"][n]["actions"][:]
                    cor = cf["data"][n]["actions"][:]
                    t = np.arange(4, len(raw)-4)
                    np.testing.assert_array_equal(cor[t], raw[t+d])
                    np.testing.assert_array_equal(cor[t-d], raw[t])
    assert len(set(counts)) == 1
    assert corrupt_sets[1] == corrupt_sets[2]
    assert truth["conditions"]["mixed_small_lag"]["delta_counts"] == {"0": 78, "-1": 13, "1": 13, "-2": 13, "2": 13, "-4": 13, "4": 13}
    assert truth["conditions"]["larger_lag"]["delta_counts"] == {"0": 78, "-4": 39, "4": 39}


def test_actual_sampler_every_boundary_and_observations():
    cfg = read_json(ROOT / "configs/gate1.json")
    datasets = [SequenceData(c) for c in CONDITIONS]
    assert len({len(ds) for ds in datasets}) == 1
    assert datasets[0].index == datasets[1].index == datasets[2].index
    for ei, obs in enumerate(datasets[0].obs):
        for ds in datasets[1:]:
            np.testing.assert_array_equal(ds.obs[ei], obs)
    for ds in datasets:
        for i, (ep, start) in enumerate(ds.index):
            assert 4 <= start and start + 16 <= len(ds.obs[ep])-4
            # Sample actual loader at both ends of each episode, including labels.
            if i == 0 or i == len(ds)-1 or ds.index[i-1][0] != ep or ds.index[i+1][0] != ep:
                sample = ds[i]
                assert sample["action"].shape == (16, 7)
                assert sample["obs"].shape == (16, cfg["obs_dim"])
                np.testing.assert_array_equal(sample["action"], ds.actions[ep][start:start+16])
    validations = [SequenceData(c, "validation") for c in CONDITIONS]
    for i in range(len(validations[0])):
        for ds in validations[1:]:
            for key in ("obs", "action"):
                np.testing.assert_array_equal(ds[i][key], validations[0][i][key])


def test_sampler_short_episode_has_no_synthetic_samples():
    assert len(window_starts(23, 4, 16)) == 0
    assert window_starts(24, 4, 16).tolist() == [4]


def test_selected_observations_are_unmodified_raw_coordinates():
    cfg = read_json(ROOT / "configs/gate1.json")
    ds = SequenceData()
    with h5py.File(ROOT / cfg["source_path"], "r") as f:
        for i, n in enumerate(ds.split["train"]):
            ep = f["data"][n]
            expected = np.concatenate([ep["obs/object"][:,7:14], ep["obs/robot0_eef_pos"][:], ep["obs/robot0_eef_quat"][:], ep["obs/robot0_gripper_qpos"][:]], axis=1).astype(np.float32)
            np.testing.assert_array_equal(ds.obs[i], expected)
