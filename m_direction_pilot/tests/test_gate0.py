import json
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import torch

from m_direction.io import ROOT, OUT, LOCAL, read_csv, array_hash, stable_seed, write_json
from m_direction.perturb import DIRECTIONS, intervention
from m_direction.geometry import quat_angle, object_direction
from m_direction.audit import Ledger, compare_zero
from m_direction.assets import demo_obs
from m_direction.policy import make_policy, predict
from m_direction.replay import prefix_replay
from m_direction.metrics import delta_loss


class Gate0Tests(unittest.TestCase):
    def test_missing_outcomes_and_signed_improvements(self):
        self.assertIsNone(delta_loss(None, False))
        self.assertIsNone(delta_loss(True, None))
        self.assertEqual(delta_loss(False, True), -1)
        self.assertEqual(delta_loss(True, False), 1)
        self.assertEqual(delta_loss(True, True), 0)
        with self.assertRaises(ValueError): delta_loss(3, True)

    def test_signed_mixed_norms_and_expert_other_coordinates(self):
        expert = np.array([.21, -.34, .13, .27, -.18, .04, 1.])
        for r in [.1, .2]:
            for d in DIRECTIONS:
                pair = [intervention(expert, d, s, r) for s in [-1, 1]]
                for action, delta in pair:
                    self.assertAlmostEqual(np.linalg.norm(delta), r, places=14)
                    np.testing.assert_array_equal(action[3:], expert[3:])
                np.testing.assert_allclose(pair[0][1], -pair[1][1], atol=0, rtol=0)
        nominal, d = intervention(expert, "nominal", 0, 0)
        np.testing.assert_array_equal(nominal, expert)
        np.testing.assert_array_equal(d, np.zeros(7))

    def test_boundary_is_rejected_not_clipped(self):
        for x in [.8, .9, 1.]:
            with self.assertRaises(ValueError): intervention([x, 0, 0, 0, 0, 0, 1], "x", 1, .2)

    def test_geodesic_angle_and_frame_rotation(self):
        q = np.array([0, 0, np.sin(np.pi/4), np.cos(np.pi/4)])
        self.assertLess(quat_angle(q, -q), 1e-7)
        self.assertAlmostEqual(quat_angle(q, [0, 0, 0, 1]), np.pi/2)
        np.testing.assert_allclose(object_direction([1, 0, 0], q), [0, -1, 0], atol=1e-14)

    def test_frozen_episode_split_and_exact_budget(self):
        states = read_csv(OUT/"frozen_state_manifest.csv")
        self.assertEqual(len(states), 12)
        dev = {s["source_episode"] for s in states if s["split"] == "development"}
        held = {s["source_episode"] for s in states if s["split"] == "held-out"}
        self.assertEqual((len(dev), len(held), len(dev & held)), (4, 2, 0))
        b = read_csv(OUT/"branch_plan.csv")
        self.assertEqual(len({r["branch_id"] for r in b}), 120)
        self.assertEqual([sum(r["block"] == block for r in b) for block in ["B1", "B2", "B3", "B4"]], [84, 18, 4, 14])
        nominal = [r for r in b if r["direction"] == "nominal"]
        self.assertEqual(len(nominal), 14)
        self.assertEqual(len({(r["state_id"], r["checkpoint_seed"]) for r in nominal}), 14)
        self.assertEqual(len(read_csv(OUT/"gate_a_plan.csv")), 24)

    def test_exclusive_outputs_and_budget_attempt_guard(self):
        LOCAL.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=LOCAL) as tmp:
            from pathlib import Path
            p = Path(tmp)
            write_json(p/"result.json", {"x": 1})
            with self.assertRaises(FileExistsError): write_json(p/"result.json", {"x": 2})
            ledger = Ledger(p)
            b = {"branch_id": "A_0", "block": "A"}
            ledger.reserve(b)
            with self.assertRaises(RuntimeError): ledger.reserve(b)
            with self.assertRaises(RuntimeError): ledger.reserve({"branch_id": "A_1", "block": "A"})
            ledger.append({"event": "finished", "branch_id": "A_0"})
            with (p/"attempt_ledger.jsonl").open("w") as f:
                for i in range(30):
                    f.write(json.dumps({"event": "started", "branch_id": f"A{i}", "block": "A"})+"\n")
                    f.write(json.dumps({"event": "finished", "branch_id": f"A{i}"})+"\n")
            with self.assertRaises(RuntimeError): ledger.reserve({"branch_id": "A_extra", "block": "A"})
            with (p/"attempt_ledger.jsonl").open("w") as f:
                for i in range(120):
                    f.write(json.dumps({"event": "started", "branch_id": f"B{i}", "block": "B1"})+"\n")
                    f.write(json.dumps({"event": "finished", "branch_id": f"B{i}"})+"\n")
            with self.assertRaises(RuntimeError): ledger.reserve({"branch_id": "B_extra", "block": "B2"})

    def test_original_policy_action_time_slice_and_rng(self):
        torch.set_num_threads(2)
        policy = make_policy(42, device="cpu")
        def sample(data, mask, **kwargs):
            return torch.arange(16, dtype=data.dtype)[None, :, None].expand(1, 16, 7)
        policy.conditional_sample = sample
        history = [np.zeros(16, dtype=np.float32), np.ones(16, dtype=np.float32)]
        actions, a, na = predict(policy, history, "S00", 0)
        actions2, b, nb = predict(policy, history, "S00", 0)
        np.testing.assert_allclose(actions[:, 0], np.arange(1, 9))
        np.testing.assert_array_equal(actions, actions2)
        np.testing.assert_array_equal(na, nb)
        self.assertEqual(a, b)
        self.assertNotEqual(stable_seed("S00", 0), stable_seed("S00", 1))
        self.assertNotEqual(stable_seed("S00", 0), stable_seed("S01", 0))

    def test_prefix_replays_real_expert_time_and_live_history(self):
        t = 3
        actions = np.arange(5*7).reshape(5, 7)*.001
        states = np.zeros((5, 45)); states[:, 0] = np.arange(5)*.05
        obs = {"object": np.zeros((5, 14)), "robot0_eef_pos": np.zeros((5, 3)),
               "robot0_eef_quat": np.tile([0., 0, 0, 1.], (5, 1)), "robot0_gripper_qpos": np.zeros((5, 2))}
        obs["object"][:, 13] = 1.
        obs["robot0_eef_pos"][:, 0] = np.arange(5)*.0001
        class Group(dict): pass
        g = Group({"states": states, "actions": actions, **{f"obs/{k}": v for k, v in obs.items()}})
        g.attrs = {"model_file": "dummy"}
        called = []
        class FakeEnv:
            def __init__(self):
                self.i = 0
                self.env = SimpleNamespace(sim=SimpleNamespace(get_state=lambda: states[self.i]))
            def reset_to(self, initial):
                np.testing.assert_array_equal(initial["states"], states[0])
                return {k: v[self.i] for k, v in obs.items()}
            def step(self, action):
                called.append(action.copy()); self.i += 1
                return {k: v[self.i] for k, v in obs.items()}, 0, False, {}
            def is_success(self): return {"task": False}
        class FakeTap:
            def __init__(self, env): pass
            def begin(self): pass
            def receipt(self, action): return {"composite_input": action.copy()}
        progress = {"prefix_steps": 0}
        with patch("m_direction.replay.create_env", return_value=FakeEnv()), patch("m_direction.replay.ControllerTap", FakeTap), patch("m_direction.replay.snapshot", return_value={}):
            env, history, tap = prefix_replay(g, {"state_id": "unit", "t": t}, progress)
        np.testing.assert_array_equal(np.stack(called), actions[:t])
        np.testing.assert_array_equal(np.stack(history), np.stack([demo_obs(g, t-1), demo_obs(g, t)]))
        self.assertEqual(progress["prefix_steps"], t)
        self.assertLess(max(progress["prefix_diagnostics"]["max_errors"].values()), 1e-7)

    def test_zero_repeat_rejects_success_flip(self):
        obs = np.zeros((3, 16)); obs[:, 6] = 1; obs[:, 13] = 1
        trace = {"suffix_observations": obs, "suffix_sim_states": np.zeros((3, 45)),
                 "suffix_received_actions": np.zeros((2, 7)), "suffix_success": np.array([False, True])}
        a = {"replans": [], "ever_success": True, "final_success": True, "prefix_diagnostics": {"fork_snapshot": {}}}
        self.assertTrue(compare_zero(a, a, trace, trace)["passed"])
        b = {**a, "ever_success": False}
        self.assertFalse(compare_zero(a, b, trace, trace)["passed"])

    def test_hash_includes_dtype_shape_and_content(self):
        a = np.zeros((2, 3), dtype=np.float64)
        self.assertNotEqual(array_hash(a), array_hash(a.astype(np.float32)))
        self.assertNotEqual(array_hash(a), array_hash(a.reshape(3, 2)))
        b = a.copy(); b[0, 0] = 1.
        self.assertNotEqual(array_hash(a), array_hash(b))


if __name__ == "__main__":
    unittest.main(verbosity=2)
