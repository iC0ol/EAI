"""Gate A only. A failure prevents every B suffix; never automatically retry."""
import json
import time

import numpy as np

from m_direction.audit import verify_registration, compare_zero
from m_direction.fork import execute_branch
from m_direction.io import ROOT, OUT, read_csv, write_json, read_json, sha256
from m_direction.policy import make_policy, setup_torch


def main():
    verify_registration()
    assert not (OUT/"gate_a_summary.json").exists(), "Gate A already concluded"
    assert not (OUT/"attempt_ledger.jsonl").exists(), "No automatic restart of an attempted A"
    setup_torch()
    policy = make_policy(42)
    states = {s["state_id"]: s for s in read_csv(OUT/"frozen_state_manifest.csv")}
    plan = read_csv(OUT/"gate_a_plan.csv")
    start = time.monotonic()
    summary = {"status": "running", "comparisons": [], "attempted": 0, "completed_suffixes": 0}
    for i in range(0, len(plan), 2):
        pair = []
        for b in plan[i:i+2]:
            r = execute_branch(b, states[b["state_id"]], policy)
            summary["attempted"] += 1
            summary["completed_suffixes"] += r["status"] == "completed"
            pair.append(r)
            if r["status"] != "completed":
                summary.update({"status": "Invalid/Engineering blocked", "stop_branch": r["branch_id"], "reason": r["error"]})
                break
        if summary["status"] != "running": break
        for r in pair:
            assert sha256(ROOT/r["trace_path"]) == r["trace_sha256"]
        with np.load(ROOT/pair[0]["trace_path"]) as a, np.load(ROOT/pair[1]["trace_path"]) as b:
            comparison = compare_zero(pair[0], pair[1], a, b)
        summary["comparisons"].append({"state_id": plan[i]["state_id"], **comparison})
        print(json.dumps(summary["comparisons"][-1]), flush=True)
        if not comparison["passed"]:
            summary.update({"status": "Invalid/Engineering blocked", "reason": "Zero-perturbation repeat mismatch"})
            break
    if summary["status"] == "running": summary["status"] = "passed"
    summary["wall_seconds"] = time.monotonic()-start
    write_json(OUT/"gate_a_summary.json", summary)
    print(json.dumps(summary), flush=True)
    return 0 if summary["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
