"""Gate B, fixed order, only after every primary A zero pair passed."""
import json
import time

from m_direction.audit import verify_registration
from m_direction.fork import execute_branch
from m_direction.io import OUT, read_csv, read_json, write_json
from m_direction.policy import make_policy, setup_torch


def main():
    verify_registration()
    a = read_json(OUT/"gate_a_summary.json")
    assert a["status"] == "passed" and len(a["comparisons"]) == 12 and a["completed_suffixes"] == 24
    assert not (OUT/"gate_b_summary.json").exists()
    assert not list((OUT/"branch_results").glob("B*.json")), "Refuse B rerun"
    setup_torch()
    states = {s["state_id"]: s for s in read_csv(OUT/"frozen_state_manifest.csv")}
    plan = read_csv(OUT/"branch_plan.csv")
    start = time.monotonic()
    summary = {"status": "running", "attempted": 0, "completed_suffixes": 0}
    current_seed, policy = None, None
    for b in plan:
        if current_seed != int(b["checkpoint_seed"]):
            del policy
            current_seed = int(b["checkpoint_seed"])
            policy = make_policy(current_seed)
        r = execute_branch(b, states[b["state_id"]], policy)
        summary["attempted"] += 1
        summary["completed_suffixes"] += r["status"] == "completed"
        if r["status"] != "completed":
            summary.update({"status": "Invalid/Engineering blocked", "stop_branch": r["branch_id"], "reason": r["error"]})
            break
    if summary["status"] == "running": summary["status"] = "completed"
    summary["wall_seconds"] = time.monotonic()-start
    write_json(OUT/"gate_b_summary.json", summary)
    print(json.dumps(summary), flush=True)
    return 0 if summary["status"] == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
