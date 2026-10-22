import numpy as np
import torch

from d_alignment.io import ROOT, read_json
from d_alignment.policy import make_policy


def test_current_action_is_prediction_index_one(monkeypatch):
    policy = make_policy()
    def deterministic_sample(condition_data, *args, **kwargs):
        return torch.arange(16, dtype=condition_data.dtype)[None, :, None].expand(1, 16, 7)
    monkeypatch.setattr(policy, "conditional_sample", deterministic_sample)
    obs = torch.zeros(1, 2, read_json(ROOT / "configs/gate1.json")["obs_dim"])
    result = policy.predict_action({"obs": obs})
    np.testing.assert_array_equal(result["action"][0, :, 0].numpy(), np.arange(1, 9))
    cfg = read_json(ROOT / "configs/gate1.json")
    assert cfg["n_latency_steps"] == 0 and cfg["pad_before"] == cfg["pad_after"] == 0


def test_normalization_roundtrip_and_identity_actions():
    policy = make_policy()
    actions = torch.linspace(-1, 1, 7)[None, :].repeat(3, 1)
    torch.testing.assert_close(policy.normalizer["action"].normalize(actions), actions)
    obs = torch.randn(8, read_json(ROOT / "configs/gate1.json")["obs_dim"])
    field = policy.normalizer["obs"]
    torch.testing.assert_close(field.unnormalize(field.normalize(obs)), obs, atol=1e-5, rtol=1e-5)
