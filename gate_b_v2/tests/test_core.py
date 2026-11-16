import subprocess

import numpy as np
import pytest

from gate_b_v2.core import (
    available_future_actions,
    git_commit,
    policy_noise_seed,
    stack_observation_history,
    validate_horizons,
)


def test_available_future_actions_respects_observation_alignment():
    assert available_future_actions(16, 1) == 16
    assert available_future_actions(16, 2) == 15
    assert available_future_actions(16, 3) == 14


def test_horizon_guard_does_not_silently_truncate():
    with pytest.raises(ValueError, match="Do not silently truncate"):
        validate_horizons([1, 2, 4, 8, 16], 16, 2)
    assert validate_horizons([1, 2, 4, 8, 15], 16, 2) == [1, 2, 4, 8, 15]


def test_policy_noise_seed_is_common_by_call_index():
    assert policy_noise_seed(123, 4) == policy_noise_seed(123, 4)
    assert policy_noise_seed(123, 4) != policy_noise_seed(123, 5)


def test_observation_history_pads_with_first_observation_and_converts_hwc():
    shape_meta = {
        "obs": {
            "agentview_image": {"shape": [3, 2, 2], "type": "rgb"},
            "robot0_eef_pos": {"shape": [3], "type": "low_dim"},
        }
    }
    obs = {
        "agentview_image": np.arange(12, dtype=np.uint8).reshape(2, 2, 3),
        "robot0_eef_pos": np.asarray([1, 2, 3], dtype=np.float64),
    }
    result = stack_observation_history([obs], 2, shape_meta)
    assert result["agentview_image"].shape == (2, 3, 2, 2)
    assert np.array_equal(result["agentview_image"][0], result["agentview_image"][1])
    assert result["robot0_eef_pos"].shape == (2, 3)
    assert result["robot0_eef_pos"].dtype == np.float32


def test_observation_history_converts_raw_uint8_hwc_rgb_to_float_chw():
    shape_meta = {"obs": {"agentview_image": {"shape": [3, 2, 2], "type": "rgb"}}}
    raw = np.arange(12, dtype=np.uint8).reshape(2, 2, 3)
    result = stack_observation_history([{"agentview_image": raw}], 1, shape_meta)
    expected = np.transpose(raw.astype(np.float32) / 255.0, (2, 0, 1))[None]
    assert result["agentview_image"].dtype == np.float32
    assert result["agentview_image"].shape == (1, 3, 2, 2)
    assert np.allclose(result["agentview_image"], expected)


def test_observation_history_rejects_wrong_rgb_range():
    shape_meta = {"obs": {"agentview_image": {"shape": [3, 2, 2], "type": "rgb"}}}
    raw = np.full((2, 2, 3), 255.0, dtype=np.float32)
    with pytest.raises(ValueError, match="must be in \\[0, 1\\]"):
        stack_observation_history([{"agentview_image": raw}], 1, shape_meta)


def test_git_commit_does_not_inherit_parent_repository(tmp_path):
    repo = tmp_path / "repo"
    nested = repo / "nested"
    nested.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@example.com",
         "-C", str(repo), "commit", "-q", "--allow-empty", "-m", "init"],
        check=True,
    )
    head = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    assert git_commit(repo) == head
    assert git_commit(nested) is None


def test_sha256_tree_is_deterministic_and_content_sensitive(tmp_path):
    from gate_b_v2.core import sha256_tree

    root = tmp_path / "src"
    (root / "pkg").mkdir(parents=True)
    (root / "pkg" / "a.py").write_text("A\n", encoding="utf-8")
    (root / "b.py").write_text("B\n", encoding="utf-8")
    first = sha256_tree(root)
    assert first == sha256_tree(root)
    (root / "pkg" / "a.py").write_text("A2\n", encoding="utf-8")
    assert sha256_tree(root) != first
