"""No real integration in these tests. Budget and observation preflight checks."""
import functools
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import h5py
import numpy as np

from common import ROOT, OUT, LOCAL, Ledger, plan, protected, write_json
from diagnostics import SyncObserver, StepGuard, fingerprint
from m_direction.assets import create_env, data_path, demo_obs


class RecoveryTests(unittest.TestCase):
    def test_registered_budget_counts_suffix_prefixes(self):
        p = plan()
        self.assertEqual(len(p["prefix_plan"]), 6)
        self.assertEqual(sum(r["t"] for r in p["prefix_plan"]), 486)
        self.assertEqual(sum(400-next(x["t"] for x in p["prefix_plan"] if x["attempt_id"] == s["prefix_id"]) for s in p["suffix_plan"]), 1218)
        self.assertEqual(len(set(r["attempt_id"] for r in p["prefix_plan"])), 6)
        self.assertFalse(p["Gate_B"])

    def test_ledger_budget_duplicate_and_exclusive_results(self):
        LOCAL.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=LOCAL) as temp:
            ledger = Ledger(Path(temp))
            for i in range(6): ledger.reserve({"attempt_id": f"P{i}"}, "prefix")
            with self.assertRaises(RuntimeError): ledger.reserve({"attempt_id": "P6"}, "prefix")
            with self.assertRaises(RuntimeError): ledger.reserve({"attempt_id": "P0"}, "prefix")
            for i in range(4): ledger.reserve({"attempt_id": f"Z{i}"}, "suffix")
            with self.assertRaises(RuntimeError): ledger.reserve({"attempt_id": "Z4"}, "suffix")
            p = Path(temp)/"result.json"; write_json(p, {"x": 0})
            with self.assertRaises(FileExistsError): write_json(p, {"x": 1})

    def test_step_guard_disallows_unregistered_initialization(self):
        class FakeSim:
            def step(self): pass
            def step1(self): pass
            def step2(self): pass
        fake = SimpleNamespace(MjSim=FakeSim)
        with patch.dict(sys.modules, {"robosuite.utils.binding_utils": fake}):
            with StepGuard(None) as guard:
                with self.assertRaises(RuntimeError): FakeSim().step()
                with self.assertRaises(RuntimeError): FakeSim().step1()
                self.assertEqual(guard.steps, 0)

    def test_sensor_wrapper_preserves_modality_and_values(self):
        def original(cache): return np.array([1., 2.])
        original.__modality__ = "object"
        @functools.wraps(original)
        def wrapper(cache): return original(cache)
        self.assertEqual(wrapper.__modality__, "object")
        np.testing.assert_array_equal(wrapper({}), original({}))

    def test_historical_M_all_files_readonly(self):
        self.assertEqual(len(protected()), 56)

    def test_real_kinematic_observer_preflight_zero_steps(self):
        with StepGuard(None) as guard:
            env = create_env()
            try:
                with h5py.File(data_path(), "r") as f:
                    g = f["data/demo_191"]
                    env.reset()
                    env.reset_to({"model": g.attrs["model_file"], "states": g["states"][0], "ep_meta": g.attrs.get("ep_meta", None)})
                    observer = SyncObserver(env)
                    before = fingerprint(env.env)
                    np.testing.assert_allclose(observer.live(), demo_obs(g, 0), atol=1e-5, rtol=0)
                    error = max(np.max(abs(observer.from_state(g["states"][t])-demo_obs(g, t))) for t in range(53))
                    self.assertLessEqual(error, 1e-5)
                    self.assertEqual(fingerprint(env.env), before)
                    self.assertEqual(guard.steps, 0)
            finally: env.env.close()


if __name__ == "__main__": unittest.main(verbosity=2)
