"""Post-stop contract checks against actual immutable evidence, no simulator."""
import unittest

import numpy as np

from m_direction.io import ROOT, OUT, REPORT, read_csv, read_json, sha256, git


class DeliveryTests(unittest.TestCase):
    def test_no_inference_after_fidelity_stop(self):
        s = read_json(OUT/"summary.json")
        self.assertEqual(s["decision"], "Invalid / Engineering blocked")
        self.assertEqual(s["costs"]["expert_prefix_control_steps"], 52)
        self.assertEqual(s["costs"]["B_attempts"], 0)
        self.assertEqual(s["costs"]["all_complete_suffixes"], 0)
        r = read_json(OUT/"branch_results/A_S00_repeat0.json")
        self.assertEqual(r["replans"], [])
        self.assertEqual(r["suffix_steps"], 0)
        self.assertEqual(sha256(ROOT/r["trace_path"]), r["trace_sha256"])
        with np.load(ROOT/r["trace_path"]) as trace:
            self.assertEqual(trace["prefix_received_actions"].shape, (52, 7))
            self.assertFalse(any(key.startswith("suffix_") for key in trace.files))

    def test_all_denominators_and_missing_labels(self):
        rows = read_csv(OUT/"all_branch_ledger.csv")
        self.assertEqual(len(rows), 144)
        self.assertEqual(len({r["branch_id"] for r in rows}), 144)
        self.assertEqual(sum(r["attempted"] == "True" for r in rows), 1)
        states = read_csv(OUT/"frozen_state_status.csv")
        self.assertEqual(len(states), 12)
        self.assertEqual(len(read_csv(OUT/"by_source.csv")), 6)
        pairs = read_csv(OUT/"paired_outcomes.csv")
        self.assertEqual(len(pairs), 120)
        self.assertTrue(all(r["Y_nominal"] == r["Y_perturbed"] == r["delta_loss"] == "" for r in pairs))
        self.assertTrue(all(r["in_prespecified_denominator"] == "True" for r in states))

    def test_registration_and_protected_trees(self):
        registration = read_json(OUT/"registration.json")
        for p, h in registration["frozen_sha256"].items():
            self.assertEqual(sha256(ROOT/p), h, p)
        self.assertTrue(all(p.startswith("m_direction_pilot/") for p in git("diff", "--name-only", "cea2502eee1dd6504035f4fcde47af1833a90b93").splitlines()))
        r = read_json(OUT/"branch_results/A_S00_repeat0.json")
        for p, h in r["execution_source_sha256"].items():
            self.assertEqual(sha256(ROOT/p), h, p)
        self.assertTrue(read_json(OUT/"read_only_diagnosis.json")["no_new_environment_or_policy_steps"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
