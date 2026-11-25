"""Regression tests for native-prefix logging and committing exactly one paired record."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from audit import audit_trial
from design import ROOT, file_hash, read_json
from trial import run_cell


class FakeRobot:
    def __init__(self):
        art = SimpleNamespace(get_qpos=lambda: np.zeros(14), get_qvel=lambda: np.zeros(14))
        self.left_entity = self.right_entity = art
        self.get_left_gripper_val = self.get_right_gripper_val = lambda: 1.


class FakePhoneTask:
    def setup_demo(self, **unused):
        self.take_action_cnt, self.step_lim, self.eval_success = 0, 400, False
        self.robot = FakeRobot()
        pose = SimpleNamespace(p=np.array([0., 0., .8]), q=np.array([1., 0., 0., 0.]))
        self.phone = SimpleNamespace(get_pose=lambda: pose, get_functional_point=lambda idx: [0., 0., .8])
        self.stand = SimpleNamespace(get_pose=lambda: pose,
                                     get_functional_point=lambda idx: [0., float(not self.eval_success), .8])
        self.phone_id = self.stand_id = 1

    def get_obs(self):
        frame = np.full((240, 320, 3), self.take_action_cnt, dtype=np.uint8)
        return {"observation": {k: {"rgb": frame} for k in ("head_camera", "left_camera", "right_camera")},
                "joint_action": {"vector": np.zeros(14)}}

    def set_instruction(self, value):
        self.instruction = value

    def get_instruction(self):
        return self.instruction

    def take_action(self, action):
        self.take_action_cnt += 1
        self.eval_success = self.take_action_cnt == 12

    def check_success(self):
        return self.eval_success

    def close_env(self, **unused):
        pass


class DeterministicClient:
    def __init__(self):
        self.indices = []

    def infer(self, request):
        i = request["query_index"]
        self.indices.append(i)
        raw = np.random.default_rng(request["episode_seed"] + i).normal(size=(50, 14)).astype(np.float32)
        return {"episode_seed": request["episode_seed"], "query_index": i, "actions": raw,
                "policy_timing": {"infer_ms": 1}, "server_timing": {"infer_ms": 1}}


class RolloutTest(unittest.TestCase):
    def test_paired_native_prefix_partial_last_chunk_and_resume(self):
        base = ROOT / "runtime/runner-test"
        base.mkdir(exist_ok=True, parents=True)
        with tempfile.TemporaryDirectory(dir=base) as temporary:
            output = Path(temporary)
            task = "place_phone_stand"
            args = SimpleNamespace(output=output, stage="reproduction", task=task, manifest="unit")
            meta = {"task": task, "config": "pi05_robotwin_place_phone_stand", "action_horizon": 50,
                    "action_dim": 14, "candidate_count": 1, "denoising_steps": 10, "action_space": "absolute_joint"}
            client = DeterministicClient()
            common = (args, client, meta, FakePhoneTask(), {"clear_cache_freq": 5},
                      {"scene_seed": 9, "episode_info": {}}, .09, 0)
            with patch("trial.sample_instruction", return_value="Put the phone on the stand."):
                for method in ("fixed5", "fixed25", "fixed5"):
                    run_cell(*common, method)
            self.assertEqual(client.indices, [0, 1, 2, 0])
            parent = output / "reproduction/place_phone_stand/scene_000"
            fingerprints = []
            for method in ("fixed5", "fixed25"):
                path = parent / method
                identity = dict(stage="reproduction", task=task, index=0, method=method, scene_seed=9,
                                manifest_sha256="unit")
                _, first, _, steps, _ = audit_trial(path, identity, None, .09, file_hash(parent / "initial.npz"))
                fingerprints.append(first)
                self.assertEqual(steps, 12)
            self.assertEqual(*fingerprints)
            record = parent / "fixed5/record.json"
            record.write_text(record.read_text().replace('"steps": 12', '"steps": 11'))
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                run_cell(*common, "fixed5")


if __name__ == "__main__":
    unittest.main()
