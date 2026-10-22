"""Read-only evidence audit of finished and interrupted runs; no policy steps."""
import csv
import datetime
import json
import subprocess

import numpy as np

from d_alignment.io import ROOT, read_json, sha256, write_json

cfg = read_json(ROOT / "configs/gate1.json")
frozen = read_json(ROOT / "data/manifests/frozen_protocol.json")
frozen_inputs = {**frozen["files"], **frozen["data_manifests"]}
for name, expected in frozen_inputs.items():
    assert sha256(ROOT / name) == expected, name
versions = read_json(ROOT / "configs/versions.json")
assert sha256(ROOT / cfg["source_path"]) == versions["dataset"]["sha256"]
# This is a post-hoc file integrity check, not estimator input or lag inference.
injection = read_json(ROOT / "data/manifests/injection_truth.json")
for info in injection["conditions"].values():
    assert sha256(ROOT / info["path"]) == info["sha256"]
initial = read_json(ROOT / "data/manifests/eval_initial_conditions.json")
assert sha256(ROOT / initial["path"]) == initial["sha256"]
expected_trials = read_json(ROOT / "data/manifests/eval_seeds.json")["seeds"]
initial_by_seed = {v["seed"]: v for v in initial["initial_conditions"]}
comparison = read_json(ROOT / "outputs/gate1/comparison.json")
preservation = read_json(ROOT / "reports/gate1/preservation_check.json")
assert preservation["original_tracked_files"] == 903 and preservation["changed"] == []
assert subprocess.check_output(["git", "rev-parse", "main"], cwd=ROOT, text=True).strip() == frozen["git_parent"]
old_tree = subprocess.check_output(["git", "rev-parse", "HEAD:spatial_intervention_pilot"], cwd=ROOT, text=True).strip()
assert old_tree == "3caa29cb1f2435aa9d3f27f45789f2f41b86953a"
with open(ROOT / "outputs/gate1/paired_outcomes.csv") as handle:
    paired = {int(row["test_seed"]): row for row in csv.DictReader(handle)}
assert sorted(paired) == expected_trials
records = {}
for name, value in comparison["runs"].items():
    path = ROOT / "outputs/gate1" / name
    tr = read_json(path / "run.json")
    assert tr == value["training"]
    assert tr["config"] == cfg and tr["versions"] == versions
    metrics = [json.loads(line) for line in (path / "metrics.jsonl").read_text().splitlines()]
    assert metrics[-1]["update"] == tr["updates_completed"]
    assert [m["update"] for m in metrics] == [1] + list(range(100, tr["updates_completed"] + 1, 100))
    assert all(np.isfinite(m["train_noise_mse"]) for m in metrics)
    rec = {"training_status": tr["status"], "last_confirmed_updates": tr["updates_completed"],
           "metrics_sha256": sha256(path / "metrics.jsonl"), "evaluated_episodes": 0}
    if tr["status"] == "completed":
        assert tr["updates_completed"] == cfg["updates"]
        assert sha256(tr["checkpoint"]) == tr["checkpoint_sha256"]
        ev = read_json(path / "evaluation_summary.json")
        assert ev == value["evaluation"]
        assert ev["initial_conditions_sha256"] == initial["sha256"]
        rows = [json.loads(line) for line in (path / "evaluation.jsonl").read_text().splitlines()]
        assert sorted(r["test_seed"] for r in rows) == expected_trials
        assert ev["episodes"] == len(rows) == 50
        assert ev["successes"] == sum(r["success"] for r in rows)
        assert ev["success_rate"] == ev["successes"] / len(rows)
        for row in rows:
            trial = row["test_seed"]
            assert row["initial_state_sha256"] == initial_by_seed[trial]["state_sha256"]
            assert row["initial_obs_max_error"] < 1e-5
            assert row["steps"] == cfg["eval_max_steps"] == 400
            assert row["condition"] == tr["condition"] and row["train_seed"] == tr["seed"]
            assert int(paired[trial][name]) == int(row["success"])
            assert sha256(row["local_trace_path"]) == row["local_trace_sha256"]
            with np.load(row["local_trace_path"], allow_pickle=False) as trace:
                assert trace["actions"].shape == (400, 7)
                assert trace["observations"].shape == (400, cfg["obs_dim"])
                assert np.isfinite(trace["actions"]).all() and np.isfinite(trace["observations"]).all()
                success_steps = trace["success_steps"].tolist()
                assert bool(success_steps) == row["success"]
                assert len(success_steps) == row["success_steps_count"]
                assert (success_steps[0] if success_steps else None) == row["first_success_step"]
                assert all(1 <= t <= 400 for t in success_steps)
        assert np.isclose(ev["simulation_cpu_wall_seconds"], sum(r["simulation_wall_seconds"] + r["reset_wall_seconds"] for r in rows))
        assert np.isclose(ev["inference_wall_seconds"], sum(r["inference_wall_seconds"] for r in rows))
        rec.update(evaluated_episodes=50, evaluation_sha256=sha256(path / "evaluation.jsonl"),
                   checkpoint_sha256=tr["checkpoint_sha256"], local_trace_hashes_verified=50)
    else:
        assert tr["status"] == "interrupted" and name == "larger_lag_seed43"
        assert not (path / "evaluation.jsonl").exists()
        assert not (ROOT / "outputs/gate1/checkpoints" / f"{name}.pt").exists()
        evidence = read_json(ROOT / tr["interruption_evidence"])
        assert evidence["metrics_sha256"] == rec["metrics_sha256"]
        assert evidence["additional_optimizer_updates"] == 0
    records[name] = rec
assert len(records) == cfg["max_policy_trainings"] == 6
assert sum(r["training_status"] == "completed" for r in records.values()) == 5
assert sum(r["evaluated_episodes"] for r in records.values()) == 250
assert comparison["step_d_eligible_conditions"] == []
assert not (ROOT / "reports/gate1/lag_identification.md").exists()
report = {"observed_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
          "status": "passed_with_explicitly_incomplete_sixth_training",
          "frozen_files_and_manifests_verified": len(frozen_inputs),
          "original_tracked_files_unchanged": 903,
          "spatial_intervention_pilot_tree": old_tree,
          "source_hdf5_sha256": versions["dataset"]["sha256"],
          "derived_action_files_verified": len(injection["conditions"]),
          "eval_initial_conditions_sha256": initial["sha256"],
          "runs": records, "formal_policy_episodes": 250, "formal_control_steps": 100000,
          "additional_optimizer_updates": 0, "additional_environment_steps": 0,
          "step_d_executed": False,
          "scope": "Artifact consistency and local hash audit; not new training, rollouts, or lag estimation."}
write_json(ROOT / "reports/gate1/final_audit.json", report)
print(json.dumps(report, indent=2))
