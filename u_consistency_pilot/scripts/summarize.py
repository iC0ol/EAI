#!/usr/bin/env python3
"""Validate and summarize a blocked resource audit; no scientific metrics invented."""
import argparse
import csv
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outputs", required=True)
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    out = Path(args.outputs).resolve()
    if project not in out.parents:
        parser.error("outputs must be inside u_consistency_pilot")
    target = out / "summary.json"
    if target.exists():
        parser.error("refusing to overwrite existing summary")
    manifest = json.loads((out / "resource_manifest.json").read_text())
    versions = json.loads((out / "versions.json").read_text())
    execution = json.loads((out / "audit_execution.json").read_text())
    config_hash = hashlib.sha256((project / "configs/protocol_v2.json").read_bytes()).hexdigest()
    if config_hash != versions["protocol_sha256"]:
        raise ValueError("Protocol changed after audit")
    if manifest["status"] != "TECHNICAL-BLOCK" or execution["status"] != "TECHNICAL-BLOCK":
        raise ValueError("This summarizer only supports the blocked resource-audit path")
    if (manifest["candidate_name_hits"] or manifest["candidate_size_hits"] or
            any(manifest["direct_hf_cache_directory_checks"].values())):
        raise ValueError("Unreviewed resource candidates exist; do not report them absent")
    rows = {}
    for filename in ["replay_check.csv", "root_manifest.csv", "per_root_metrics.csv"]:
        with (out / filename).open(newline="") as handle:
            rows[filename] = sum(1 for _ in csv.DictReader(handle))
        if rows[filename]:
            raise ValueError("Unexpected scientific rows in a resource-blocked run")
    stages = {name: "NOT_RUN" for name in [
        "strict_checkpoint_load", "original_scaler_reconstruction", "runtime_action_semantics",
        "engineering_replay", "0B_splitting", "0B_flow_training", "0B_MLP_fitting_check",
        "0B_strengthened_G", "32_calibration", "16_dev", "64_test", "U1"]}
    summary = {
        "schema_version": 1, "final_status": "TECHNICAL-BLOCK", "stop_stage": "0A",
        "resource_audit": "COMPLETED_WITH_EXPLICIT_COVERAGE_LIMITS",
        "blockers": ["Specified LeWM weights not located in completed searched scopes",
                     "Matching PushT training data/trusted scaler provenance not located",
                     "No compatible LeWM/PushT environment validated; no installation authorized when resources absent"],
        "stages": stages,
        "dev_to_test_triggers": {str(i): "NOT_EVALUATED_RESOURCE_BLOCK" for i in range(1, 7)},
        "test_authorized_by_gate": False, "U_selected": None,
        "scientific_root_count": None, "independent_source_count": None,
        "scientific_root_count_status": "NOT_RUN_NO_ROOTS_CREATED",
        "scientific_metrics": {"mean_R": None, "mean_J": None, "block_only": None,
                               "success": None, "harmful_flips": None, "confidence_interval": None},
        "engineering_max_repeat_J_difference": None, "delta_J": None,
        "header_only_csv_data_rows": rows,
        "protocol_sha256": config_hash,
        "scientific_interpretation": "No evidence for or against U; no inference or simulator execution",
        "omitted_unexecuted_outputs": ["split_manifest.csv", "training_curves.csv",
            "calibration_pairs.jsonl", "calibration_shuffle.json", "frozen_predictions_dev.jsonl",
            "real_transitions_dev.jsonl", "all test outputs"],
        "next_action": "STOP_AND_AWAIT_RESEARCHER_REVIEW",
        "delivery_state": "REPORTS_AND_PUBLIC_BRANCH_SYNC_PENDING"}
    target.write_text(json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    print(json.dumps({"final_status": summary["final_status"], "stages": stages,
                      "header_only_csv_data_rows": rows}))


if __name__ == "__main__":
    main()
