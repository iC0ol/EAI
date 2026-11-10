import numpy as np
import pytest

from gate_b_v2.core import (
    available_future_actions,
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
