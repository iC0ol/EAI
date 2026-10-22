"""Reconcile an abandoned started run without restarting any optimizer.

Preserve the original metadata and last confirmed timing. Missing final weights
cannot be reconstructed from loss logs, and unobserved work is never imputed.
"""
import datetime
import json
import os
from pathlib import Path

from d_alignment.io import ROOT, read_json, sha256, write_json

name = "larger_lag_seed43"
run = ROOT / "outputs/gate1" / name
evidence_path = ROOT / "reports/gate1/interruption.json"
assert not evidence_path.exists(), "Interruption is already recorded"
metadata = read_json(run / "run.json")
assert metadata["status"] == "started"
assert not (ROOT / "outputs/gate1/checkpoints" / f"{name}.pt").exists()
assert not (run / "evaluation.jsonl").exists()
active = []
for proc in Path("/proc").iterdir():
    if not proc.name.isdigit():
        continue
    try:
        if proc.stat().st_uid != os.getuid():
            continue
        args = (proc / "cmdline").read_bytes().decode(errors="replace").split("\0")
    except (FileNotFoundError, PermissionError, ProcessLookupError):
        continue
    if any(arg in ("d_alignment.train", "d_alignment.evaluate") or arg.endswith("/run_remaining.py") or arg == "scripts/run_remaining.py" for arg in args):
        active.append({"pid": int(proc.name), "args": args})
assert not active, f"Policy pipeline still active: {active}"
metrics_path = run / "metrics.jsonl"
metrics = [json.loads(line) for line in metrics_path.read_text().splitlines()]
last = metrics[-1]
assert last["update"] == metadata["updates_completed"] == 42400
pipeline_path = ROOT / "outputs/gate1/pipeline_status.json"
evidence = {
    "observed_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "run": name,
    "classification": "execution_interruption_unknown_termination_cause",
    "original_run_metadata": metadata,
    "original_run_metadata_sha256": sha256(run / "run.json"),
    "original_pipeline_status": read_json(pipeline_path),
    "metrics_sha256": sha256(metrics_path),
    "metrics_last_modified_utc": datetime.datetime.fromtimestamp(metrics_path.stat().st_mtime, datetime.timezone.utc).isoformat(),
    "last_confirmed_metric": last,
    "active_policy_pipeline_processes_at_observation": active,
    "final_checkpoint_present": False,
    "evaluation_present": False,
    "termination_traceback_present": False,
    "exit_status": None,
    "unobserved_updates": "Unknown; do not extrapolate beyond the last confirmed update.",
    "decision": "No restart: six training attempts already consumed; no resumable optimizer/EMA/RNG checkpoint exists.",
    "additional_optimizer_updates": 0,
}
write_json(evidence_path, evidence)
metadata.update(
    status="interrupted",
    termination_cause="unknown; process absent, final checkpoint absent, no captured traceback or exit status",
    interruption_evidence="reports/gate1/interruption.json",
    gpu_allocated_wall_hours_lower_bound=last["optimization_seconds"] / 3600,
    wall_seconds_lower_bound=last["wall_seconds"],
)
write_json(run / "run.json", metadata)
pipeline = evidence["original_pipeline_status"]
pipeline.update(state="stopped_after_interruption", phase="done", interrupted_run=name,
                last_confirmed_update=last["update"], termination_cause="unknown",
                note="Six training attempts started, five completed; no retraining or partial-policy evaluation.")
write_json(pipeline_path, pipeline)
print(json.dumps({"interrupted_run": name, "last_confirmed_update": last["update"],
                  "gpu_hours_lower_bound": metadata["gpu_allocated_wall_hours_lower_bound"],
                  "additional_optimizer_updates": 0}, indent=2))
