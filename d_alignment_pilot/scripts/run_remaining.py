"""Bounded sequential continuation after Clean seed 42 passes its full test."""
import json
import subprocess
import time

from d_alignment.io import ROOT, read_json, write_json

status_path = ROOT / "outputs/gate1/pipeline_status.json"
assert not status_path.exists(), "Do not restart or duplicate the fixed run budget"
gate = read_json(ROOT / "outputs/gate1/clean_gate.json")
assert gate["pass"] and gate["clean_seeds_evaluated"] == [42]
cfg = read_json(ROOT / "configs/gate1.json")
status = {"state": "running", "phase": "initializing", "completed": [], "policy_training_budget": 6}
write_json(status_path, status)


def run(module_args, log_name, phase, run_name):
    status.update(phase=phase, run=run_name)
    write_json(status_path, status)
    print(json.dumps({"phase": phase, "run": run_name}), flush=True)
    with open(ROOT / "reports/gate1/logs" / log_name, "x") as log:
        subprocess.run(["bash", str(ROOT / "scripts/run.sh")] + module_args, cwd=ROOT,
                       stdout=log, stderr=subprocess.STDOUT, check=True)


try:
    run(["scripts/materialize_frozen_data.py", "--verify-reconstruction"], "reconstruction_all.txt", "reconstruction", "no_policy_updates")
    plan = [("clean", 43), ("mixed_small_lag", 42), ("mixed_small_lag", 43), ("larger_lag", 42), ("larger_lag", 43)]
    for condition, seed in plan:
        name = f"{condition}_seed{seed}"
        run(["-m", "d_alignment.train", "--condition", condition, "--seed", str(seed)], f"train_{name}.txt", "training", name)
        run(["-m", "d_alignment.evaluate", "--condition", condition, "--seed", str(seed)], f"eval_{name}.txt", "evaluation", name)
        status["completed"].append(name)
        write_json(status_path, status)
        if condition == "clean":
            run(["scripts/clean_gate.py"], "clean_gate_seed43.txt", "clean_gate", name)
            if not read_json(ROOT / "outputs/gate1/clean_gate.json")["pass"]:
                status.update(state="stopped_at_clean_gate", phase="done")
                write_json(status_path, status)
                break
    else:
        status.update(state="all_policy_runs_completed", phase="done")
        write_json(status_path, status)
    run(["scripts/aggregate.py"], "aggregate.txt", "analysis", "completed_runs")
    run(["scripts/plot_results.py"], "plot_results.txt", "analysis", "completed_runs")
    status["phase"] = "done"
    write_json(status_path, status)
except Exception as exc:
    status.update(state="failed", error=repr(exc))
    write_json(status_path, status)
    raise
