"""R0 registration -> R1 -> conditional R2 -> conditional four zero suffixes."""
import json
import time

import numpy as np

from common import ROOT, OUT, plan, verify, write_json, read_json, now
from diagnostics import run_prefix


def trace(r):
    p = next(x for x in r["local_files"] if x["path"].endswith("trace.npz"))
    return np.load(ROOT/p["path"])


def main():
    verify()
    assert not (OUT/"attempt_ledger.jsonl").exists(), "No automatic restart after any attempted replay"
    p = plan(); start, cpu = time.monotonic(), time.process_time()
    summary = {"status": "running", "utc_start": now(), "prefix_results": [], "suffix_results": [], "zero_comparisons": []}
    open_contexts = []
    def prefix(index):
        r, c = run_prefix(p["prefix_plan"][index]); summary["prefix_results"].append(r["attempt_id"])
        if c: open_contexts.append(c)
        return r, c
    try:
        a, ca = prefix(0)
        if a["status"] != "completed":
            summary.update({"status": "R-Inconclusive", "reason": "P1 instrumentation or initialization failed; no automatic retry"}); return 2
        trigger = (not a["old_gate_A_would_pass"]) or (not a["technical_pass"])
        physics_difference = 0.
        if trigger:
            b, cb = prefix(1)
            if b["status"] != "completed":
                summary.update({"status": "R-Inconclusive", "reason": "P2 diagnostic invalid; R2 gated off"}); return 2
            with trace(a) as x, trace(b) as y:
                physics_difference = float(np.max(abs(x["states"]-y["states"])))
            write_json(OUT/"P1_P2_comparison.json", {"max_flat_state_difference": physics_difference,
                "threshold": p["passive_physics_repeat_max_abs"], "identical": physics_difference == 0.,
                "scope": "P2 forced sensor calls, same registered initialization/expert commands; not a control rollout"})
            if physics_difference > p["passive_physics_repeat_max_abs"]:
                summary.update({"status": "R-Inconclusive", "reason": "P2 sensor refresh affects physical replay; no identified passive repair"}); return 2
        r1_pass = a["technical_pass"] and physics_difference <= p["passive_physics_repeat_max_abs"]
        write_json(OUT/"R1_gate.json", {"technical_pass": r1_pass, "P1_technical_pass": a["technical_pass"],
            "P2_executed": trigger, "physical_thresholds_unchanged": True, "new_failures": a["new_failures"]})
        if not r1_pass:
            physical_fail = {k: v for k, v in a["new_failures"].items() if k != "state_aligned_obs_max_abs"}
            summary.update({"status": "R-Fail / Engineering blocked" if physical_fail else "R-Partial",
                            "reason": "Fixed official initialization leaves genuine physical reconstruction errors" if physical_fail else "State-aligned observation semantics failed"}); return 2
        ca["env"].env.close()
        if trigger: cb["env"].env.close()
        c, cc = prefix(2)
        if not c.get("technical_pass"):
            summary.update({"status": "R-Fail / Engineering blocked", "reason": "Cross-source grasp prefix failed"}); return 2
        d, cd = prefix(3)
        r2_pass = d.get("technical_pass", False)
        write_json(OUT/"R2_gate.json", {"technical_pass": r2_pass, "states": ["S02", "S09"],
            "sources": ["demo_21", "demo_105"], "phases": ["grasp", "insertion"]})
        if not r2_pass:
            summary.update({"status": "R-Fail / Engineering blocked", "reason": "Cross-source insertion prefix failed"}); return 2
        from m_direction.policy import setup_torch, make_policy
        from zero import run_zero, compare
        setup_torch(); policy = make_policy(42)
        for first, context, repeat_index, offset in [(c, cc, 4, 0), (d, cd, 5, 2)]:
            za = run_zero(p["suffix_plan"][offset], first, context, policy)
            summary["suffix_results"].append(za["attempt_id"])
            if za["status"] != "completed":
                summary.update({"status": "R-Inconclusive", "reason": "Zero suffix invalid"}); return 2
            repeat, cr = prefix(repeat_index)
            if not repeat.get("technical_pass"):
                summary.update({"status": "R-Fail / Engineering blocked", "reason": "Repeated prefix failed"}); return 2
            zb = run_zero(p["suffix_plan"][offset+1], repeat, cr, policy)
            summary["suffix_results"].append(zb["attempt_id"])
            if zb["status"] != "completed":
                summary.update({"status": "R-Inconclusive", "reason": "Repeated zero suffix invalid"}); return 2
            comparison = compare(za, zb)
            summary["zero_comparisons"].append({"state_id": first["state_id"], **comparison})
            if not comparison["passed"]:
                summary.update({"status": "R-Fail / Engineering blocked", "reason": "Zero-zero trajectory or official success unstable"}); return 2
        summary.update({"status": "R-Pass (technical candidate only)", "reason": "R1, cross-source/stage reconstruction and both zero pairs pass"})
        return 0
    except Exception as exc:
        import traceback
        summary.update({"status": "R-Inconclusive", "reason": str(exc), "traceback": traceback.format_exc()})
        return 2
    finally:
        for c in open_contexts:
            try: c["env"].env.close()
            except Exception: pass
        summary.update({"utc_finish": now(), "wall_seconds": time.monotonic()-start, "cpu_seconds": time.process_time()-cpu,
                        "new_training": 0, "directional_interventions": 0, "Gate_B_executed": False})
        write_json(OUT/"run_summary.json", summary)
        print(json.dumps(summary), flush=True)


if __name__ == "__main__": raise SystemExit(main())
