"""Read-only closure audit; does not refit, predict, or rescore private truth."""
import datetime
import json
from pathlib import Path
import subprocess

import numpy as np

from .common import read_json, sha256, write_json

ROOT = Path(__file__).resolve().parents[3]
REPO = ROOT.parent
PUBLIC = ROOT / "outputs/q2_blind"
REPORT = ROOT / "reports/q2_blind"


def git(*args):
    return subprocess.check_output(["git",*args],cwd=REPO,text=True).strip()


def finalize():
    protection=read_json(REPORT/"baseline_protection.json")
    for relative,expected in protection["original_tracked_files"].items():
        assert sha256(REPO/relative)==expected, f"Original file changed: {relative}"
    for branch,expected in protection["branch_tips"].items():
        assert git("rev-parse",branch)==expected,branch
    assert git("branch","--show-current")=="research/d-gate1-q2"
    initial="9e89e1c"
    for relative in ("reports/q2_blind/protocol.md","configs/q2_blind/experiment.json","configs/q2_blind/estimator.json"):
        previous=subprocess.check_output(["git","show",f"{initial}:d_alignment_pilot/{relative}"],cwd=REPO)
        assert (ROOT/relative).read_bytes()==previous,relative
    original=read_json(ROOT/"data/manifests/frozen_protocol.json")
    for relative,expected in {**original["files"],**original["data_manifests"]}.items():
        assert sha256(ROOT/relative)==expected
    cfg=read_json(ROOT/"configs/q2_blind/experiment.json")
    assert sha256(ROOT/cfg["source_path"])==cfg["source_sha256"]
    split=read_json(ROOT/"data/manifests/splits.json")
    assert cfg["anchors"]==split["anchors"] and cfg["lag_test"]==split["lag_test"]
    assert len(set(cfg["anchors"]))==8 and len(set(cfg["lag_test"]))==16
    assert not set(cfg["anchors"]) & set(cfg["lag_test"])
    old_runs=read_json(ROOT/"outputs/gate1/comparison.json")["runs"]
    assert len(old_runs)==6
    for run in old_runs.values():
        assert sha256(run["training"]["checkpoint"])==run["training"]["checkpoint_sha256"]
    frozen=read_json(PUBLIC/"predictions_frozen.json")
    assert sha256(PUBLIC/"predictions.jsonl")==frozen["predictions_sha256"]
    assert not (PUBLIC/"predictions.jsonl").stat().st_mode & 0o222
    for filename,expected in frozen["safe_code_sha256"].items():
        assert sha256(ROOT/"src/d_alignment/q2"/filename)==expected
    assert sha256(ROOT/"data/derived/q2_blind/model/model.json")==frozen["model_sha256"]
    assert sha256(PUBLIC/"preblind_tests.json")==frozen["preblind_tests_sha256"]
    tests=read_json(PUBLIC/"preblind_tests.json")
    assert tests["tests"]==43 and tests["passed"] and tests["failures"]==0
    assert sha256(ROOT/tests["junit_xml_path"])==tests["junit_xml_sha256"]
    assert sha256(ROOT/"tests/test_q2_blind.py")==tests["test_source_sha256"]
    blind=read_json(PUBLIC/"blind_input_hashes.json")
    assert sha256(PUBLIC/"blind_input_hashes.json")==frozen["blind_inputs_sha256"]
    for sample,expected in blind["files"].items():
        assert sha256(ROOT/"data/derived/q2_blind/queries"/f"{sample}.npz")==expected
    assert sha256(ROOT/"data/derived/q2_blind/private/truth.json")==blind["private_truth_sha256"]
    for name in ("anchor_access_probe.json","query_access_probe.json"):
        assert read_json(PUBLIC/name)["all_forbidden_reads_denied"]
    assert read_json(PUBLIC/"blind_packet_audit.json")["passed"]
    preds=[json.loads(line) for line in (PUBLIC/"predictions.jsonl").read_text().splitlines()]
    assert len(preds)==224 and len({r["sample_id"] for r in preds})==112
    assert len({r["trajectory_id"] for r in preds})==16
    for row in preds:
        assert row["candidate_lags"]==list(range(-4,5))
        assert len(row["scores"])==9 and np.isfinite(row["scores"]).all()
        assert row["score_timesteps"]==blind["lengths"][row["sample_id"]]-12
        assert row["estimated_lag"] in row["candidate_lags"]
    rows=[json.loads(line) for line in (PUBLIC/"scored_cases.jsonl").read_text().splitlines()]
    assert len(rows)==336 and len({r["episode"] for r in rows})==16
    assert {r["episode"] for r in rows}==set(cfg["lag_test"])
    for method in ("xcorr","arx","zero"):
        chosen=[r for r in rows if r["method"]==method]
        assert len(chosen)==112
        for episode in cfg["lag_test"]:
            seven=[r for r in chosen if r["episode"]==episode]
            assert sorted(r["true_lag"] for r in seven)==sorted(cfg["injected_lags"])
        for row in chosen:
            assert row["timesteps"]==blind["lengths"][row["sample_id"]]-12
        if method=="arx":
            assert all(r["exact_lag"] and r["action_exact"] and r["negligible_label_consequence"] for r in chosen)
    data=read_json(PUBLIC/"summary.json")
    assert data["decision"]["category"]=="A" and data["decision"]["sufficient_methods"]==["arx"]
    pred_commit=git("rev-parse","6c9b83c")
    pred_time=datetime.datetime.fromisoformat(git("show","-s","--format=%cI",pred_commit))
    score_time=datetime.datetime.fromisoformat(read_json(PUBLIC/"scoring_started.json")["started_at_utc"])
    assert pred_time<=score_time
    assert subprocess.check_output(["git","show",f"{pred_commit}:d_alignment_pilot/outputs/q2_blind/predictions.jsonl"],cwd=REPO)==(PUBLIC/"predictions.jsonl").read_bytes()
    now=datetime.datetime.now(datetime.timezone.utc)
    elapsed=(now-datetime.datetime.fromisoformat(cfg["budget_start_utc"])).total_seconds()
    assert elapsed<=28800
    for required in ("protocol.md","leakage_audit.md","anchor_model_selection.md","lag_recovery_results.md","action_repair_results.md","ambiguity_diagnostic.md","q2_go_no_go.md","environment_and_commands.md"):
        assert (REPORT/required).is_file()
    summary={"status":"passed","checked_at_utc":now.isoformat(),"conservative_elapsed_seconds":elapsed,
             "within_eight_hours":True,"original_tracked_files_unchanged":len(protection["original_tracked_files"]),
             "gate1_frozen_files_unchanged":len(original["files"])+len(original["data_manifests"]),
             "original_six_policy_checkpoint_hashes_unchanged":True,"original_branch_tips_unchanged":protection["branch_tips"],
             "protocol_and_config_unchanged_since_preregistration":True,"safe_estimator_code_unchanged_since_model_freeze":True,
             "prediction_commit":pred_commit,"prediction_commit_precedes_truth_scoring":True,
             "raw_prediction_records":224,"derived_conditions":112,"independent_sources":16,
             "same_times_per_candidate_and_method":True,"all_112_blind_packet_hashes_verified":True,
             "arx_oracle_action_exact_conditions":112,"new_policy_trainings":0,"new_simulation_episodes":0,
             "scope":"Artifact/hash/order audit only. No refit, estimator rerun, or second private-truth scoring."}
    write_json(PUBLIC/"final_integrity.json",summary,exclusive=False)
    # Self-hash is intentionally excluded; logs generated after this call excluded.
    files=[]
    for directory in (ROOT/"configs/q2_blind",ROOT/"src/d_alignment/q2",ROOT/"scripts/q2",REPORT,PUBLIC):
        files.extend(p for p in directory.rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.name!="artifact_sha256.json" and p.suffix!=".pyc" and p != REPORT/"logs/final_audit.txt")
    files.append(ROOT/"tests/test_q2_blind.py")
    manifest={str(p.relative_to(ROOT)):sha256(p) for p in sorted(set(files))}
    write_json(PUBLIC/"artifact_sha256.json",{"files":manifest,"self_hash_excluded":True,
               "log_note":"Finalizer stdout file is excluded because the invoking shell writes it after manifest creation."},exclusive=False)
    print(json.dumps(summary,indent=2))
