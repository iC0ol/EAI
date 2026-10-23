"""Read-only checks of measured engineering results; no environment creation."""
import unittest

import numpy as np

from common import ROOT, OUT, REPORT, CODE, BASE, read_json, protected, sha256, git
from report_recovery import rows


class DeliveryTests(unittest.TestCase):
    def test_exact_budget_and_gated_suffixes(self):
        s = read_json(OUT/"final_summary.json")
        self.assertEqual(s["decision"], "R-Fail / Engineering blocked")
        c = s["costs"]
        self.assertEqual((c["prefix_attempts"], c["expert_control_steps"], c["integration_steps"]), (2,104,2600))
        self.assertEqual((c["complete_zero_suffixes"], c["gpu_inference_calls"], c["new_training"]), (0,0,0))
        ledger = rows(OUT/"complete_budget_ledger.csv")
        self.assertEqual(len(ledger), 10)
        self.assertEqual(sum(r["attempted"] == "True" for r in ledger), 2)
        self.assertTrue(all(r["Y_ever"] == r["Y_final"] == "" for r in ledger))
        self.assertFalse((OUT/"R2_gate.json").exists())
        self.assertFalse(any(OUT.glob("Z*.json")))

    def test_old_record_and_protocol_integrity(self):
        self.assertEqual(len(protected()), 56)
        r = read_json(OUT/"registration.json")
        for p,h in r["frozen_files"].items(): self.assertEqual(sha256(ROOT/p), h, p)
        for b,h in read_json(OUT/"R0_audit.json")["old_branch_heads"].items():
            self.assertEqual(git("rev-parse",b), h, b)
        for name in ["D1_P1_S00", "D2_P2_S00"]:
            for p,h in read_json(OUT/f"{name}.json")["code_sha256"].items(): self.assertEqual(sha256(ROOT/p),h,p)

    def test_path_comparison_cannot_be_called_source_fidelity(self):
        r = read_json(OUT/"paired_path_comparison.json")
        for name in ["P0_P1_states", "P0_P1_native_obs", "P0_P1_received_actions", "P1_P2_states"]:
            self.assertTrue(r[name]["byte_identical"])
            self.assertEqual(r[name]["max_abs"],0)
        self.assertGreater(r["physical_metrics"]["max_position_m"],.001)
        self.assertGreater(r["physical_metrics"]["max_geodesic_rad"],.01)
        self.assertFalse(read_json(OUT/"R1_gate.json")["technical_pass"])

    def test_all_local_telemetry_hashes_and_sample_lags(self):
        index=read_json(OUT/"local_trace_index.json")
        self.assertEqual(len(index),8)
        for item in index: self.assertEqual(sha256(ROOT/item["path"]),item["sha256"])
        for r in read_json(OUT/"paired_path_comparison.json")["lag_examples"]:
            self.assertEqual(r["native_qpos_value_max_abs"],0)
            self.assertEqual(r["forced_qpos_value_max_abs"],0)
            self.assertAlmostEqual(r["boundary_time_s"]-r["native_nut_value_matches_preintegration_qpos_time"],.004)
            self.assertAlmostEqual(r["boundary_time_s"]-r["forced_nut_value_matches_preintegration_qpos_time"],.002)

    def test_contact_normals_and_substeps_have_real_records(self):
        for name in ["D1_P1_S00", "D2_P2_S00"]:
            r=rows(OUT/f"{name}_contact_by_substep.csv")
            self.assertEqual(len(r),1300)
            self.assertEqual([int(x["integration_index"]) for x in r],list(range(1,1301)))
        import json
        for r in rows(OUT/"contact_peaks38_52.csv"):
            self.assertAlmostEqual(np.linalg.norm(json.loads(r["normal_geom0_to_geom1_world"])),1.,places=8)
        self.assertEqual(len(rows(OUT/"controller_cache_window38_52.csv")),15)
        self.assertTrue(all(r["P1_P2_controller_same"] == "True" for r in rows(OUT/"controller_cache_window38_52.csv")))


if __name__ == "__main__": unittest.main(verbosity=2)
