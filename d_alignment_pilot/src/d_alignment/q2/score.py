"""Independent one-time scorer. Prediction receipt is checked before truth I/O."""
import datetime
import json
from pathlib import Path

import numpy as np

from .common import deadline, load_view, read_json, sha256, write_json
from .metrics import cluster_summary, midrank, repair_metrics
from .signals import times

ROOT = Path(__file__).resolve().parents[3]
LOCAL = ROOT / "data/derived/q2_blind"
PUBLIC = ROOT / "outputs/q2_blind"


def validate_frozen_predictions(public, local):
    frozen = read_json(public / "predictions_frozen.json")
    assert sha256(public / "predictions.jsonl") == frozen["predictions_sha256"]
    assert sha256(public / "preblind_tests.json") == frozen["preblind_tests_sha256"]
    tests = read_json(public / "preblind_tests.json")
    assert tests["passed"] and tests["failures"] == 0
    assert sha256(ROOT / tests["junit_xml_path"]) == tests["junit_xml_sha256"]
    assert sha256(public / "blind_input_hashes.json") == frozen["blind_inputs_sha256"]
    assert sha256(public / "blind_packet_audit.json") == frozen["blind_packet_audit_sha256"]
    assert read_json(public / "blind_packet_audit.json")["passed"]
    assert sha256(public / "query_access_probe.json") == frozen["query_access_probe_sha256"]
    assert read_json(public / "query_access_probe.json")["all_forbidden_reads_denied"]
    assert sha256(local / "model/model.json") == frozen["model_sha256"]
    assert not (public / "scoring_started.json").exists(), "Do not repeat test-truth scoring"
    return frozen


def make_decision(rows, summary, config, selection):
    candidates_A = []
    for method in ("xcorr", "arx"):
        selected = [r for r in rows if r["method"] == method]
        episodes = sorted({r["episode"] for r in selected})
        all_negligible = sum(all(r["negligible_label_consequence"] for r in selected if r["episode"] == e) for e in episodes)
        switch_sources = sum(any(r["meaningful_switch_error"] for r in selected if r["episode"] == e) for e in episodes)
        if (np.mean([r["negligible_label_consequence"] for r in selected]) >= config["decision_A"]["minimum_negligible_sample_fraction"] and
            all_negligible >= config["decision_A"]["minimum_sources_all_seven_negligible"] and
            switch_sources <= config["decision_A"]["maximum_sources_with_meaningful_switch_error"]):
            candidates_A.append(method)
    if candidates_A:
        return {"category": "A", "decision": "No-Go for D posterior-supervision necessity in this setting", "sufficient_methods": candidates_A}
    by_sample = {}
    for row in rows:
        by_sample.setdefault(row["sample_id"], {})[row["method"]] = row
    quality = {"arx": selection["arx_oof_R2"] >= config["decision_C"]["arx_min_anchor_oof_R2"],
               "xcorr": selection["xcorr_oof_correlation"] >= config["decision_C"]["xcorr_min_anchor_oof_correlation"]}
    informative = {}
    for method in ("xcorr", "arx"):
        ci = summary[method]["top3_advantage_over_fixed"]["cluster_bootstrap_95ci"]
        informative[method] = quality[method] and summary[method]["top3_support"]["mean"] >= .75 and ci[0] > 0
    supported_sources, supported_cases = set(), []
    for sample, methods in by_sample.items():
        if not all(not methods[m]["exact_lag"] and not methods[m]["negligible_label_consequence"] for m in ("xcorr", "arx")):
            continue
        for method in ("xcorr", "arx"):
            row = methods[method]
            if (informative[method] and not row["unreliable"] and not row["unidentifiable"] and row["true_in_near_set"] and
                2 <= row["near_set_size"] <= 4 and row["true_midrank"] <= 3):
                supported_sources.add(row["episode"])
                supported_cases.append({"sample_id": sample, "method": method, "episode": row["episode"]})
                break
    if len(supported_sources) >= config["decision_C"]["minimum_sources_both_methods_wrong_meaningful_supported"]:
        return {"category": "C", "decision": "Potential Go for further D diagnosis", "supported_sources": sorted(supported_sources),
                "supported_cases": supported_cases, "quality": quality, "informative": informative}
    residual = [r for r in rows if r["method"] != "zero" and not r["exact_lag"] and not r["negligible_label_consequence"]]
    uninformative_fraction = float(np.mean([not r["true_in_near_set"] or r["near_set_size"] > 4 for r in residual])) if residual else 0.
    low_change_dominance = float(np.mean([r["low_change_error_energy_fraction"] for r in residual])) if residual else 0.
    mismatch = selection["arx_oof_R2"] < 0 or selection["xcorr_oof_correlation"] < .1
    category_B = bool(residual and uninformative_fraction >= .5 and (mismatch or low_change_dominance > .5))
    return {"category": "B" if category_B else "D",
            "decision": "No-Go / Unidentifiable under current observations" if category_B else "Stop / Inconclusive",
            "supported_sources": sorted(supported_sources), "supported_cases": supported_cases,
            "quality": quality, "informative": informative, "consequential_error_cases": len(residual),
            "uninformative_residual_fraction": uninformative_fraction,
            "low_change_error_energy_mean_fraction": low_change_dominance, "anchor_model_mismatch": mismatch}


def score_once():
    config = read_json(ROOT / "configs/q2_blind/experiment.json")
    deadline(config)
    frozen = validate_frozen_predictions(PUBLIC, LOCAL)
    write_json(PUBLIC / "scoring_started.json", {"started_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
               "frozen_prediction_sha256": frozen["predictions_sha256"], "truth_not_opened_before_this_receipt": True})
    # This is intentionally the first authority to open test labels after freeze.
    truth = read_json(LOCAL / "private/truth.json")
    model = read_json(LOCAL / "model/model.json")
    settings = model["settings"]
    blind = read_json(PUBLIC / "blind_input_hashes.json")
    assert sha256(LOCAL / "private/truth.json") == blind["private_truth_sha256"]
    predictions = [json.loads(line) for line in (PUBLIC / "predictions.jsonl").read_text().splitlines()]
    assert len(predictions) == 224
    indexed = {(r["sample_id"], r["method"]): r for r in predictions}
    assert len(indexed) == 224
    rows, oracles, lengths_by_delta = [], {}, {d: [] for d in config["injected_lags"]}
    for sample, case in truth["cases"].items():
        view_path = LOCAL / "queries" / f"{sample}.npz"
        assert sha256(view_path) == blind["files"][sample]
        view = load_view(view_path)
        assert str(view["sample_id"]) == sample and str(view["trajectory_id"]) == case["trajectory_id"]
        lengths_by_delta[case["delta"]].append(len(view["command"]))
        if case["oracle_path"] not in oracles:
            with np.load(LOCAL / "private" / case["oracle_path"], allow_pickle=False) as archive:
                oracles[case["oracle_path"]] = archive["clean_action"]
        clean = oracles[case["oracle_path"]]
        idx = times(len(view["command"]), settings)
        assert np.array_equal(view["command"][idx-case["delta"]], clean[case["outer_crop"]+idx])
        for method in ("xcorr", "arx", "zero"):
            pred = indexed[(sample, method)] if method != "zero" else {"estimated_lag": 0}
            estimate = pred["estimated_lag"]
            row = {"sample_id": sample, "trajectory_id": case["trajectory_id"], "episode": case["episode"],
                   "true_lag": case["delta"], "method": method, "estimated_lag": estimate,
                   "exact_lag": estimate == case["delta"], "lag_absolute_error_steps": abs(estimate-case["delta"]),
                   "lag_absolute_error_ms": 50*abs(estimate-case["delta"]), "predicted_abs3": abs(estimate) == 3,
                   **repair_metrics(view["command"], clean, case["outer_crop"], idx, estimate, settings,
                                    config["label_negligibility"], model["change_quantiles"])}
            row["lag_error_with_negligible_label_consequence"] = bool(not row["exact_lag"] and row["negligible_label_consequence"])
            if method != "zero":
                scores = np.asarray(pred["scores"])
                true_index = settings["candidate_lags"].index(case["delta"])
                tolerance = settings["tie_tolerance"] * max(1., np.abs(scores).max())
                rank = midrank(scores, true_index, tolerance)
                row.update(scores=pred["scores"], score_gap=pred["score_gap"], normalized_gap=pred["normalized_gap"],
                           true_midrank=rank, top3_support=rank <= 3, near_lags=pred["near_lags"],
                           near_set_size=len(pred["near_lags"]), true_in_near_set=case["delta"] in pred["near_lags"],
                           true_score_minus_best=float(scores[true_index]-scores.min()),
                           unidentifiable=pred["unidentifiable"], ambiguous=pred["ambiguous"], unreliable=pred["unreliable"],
                           top3_advantage_over_uniform=float(rank <= 3)-1/3,
                           top3_advantage_over_fixed=float(rank <= 3)-float(case["delta"] in (0,-1,1)),
                           near_coverage_advantage_over_uniform=float(case["delta"] in pred["near_lags"])-len(pred["near_lags"])/9)
            rows.append(row)
    # Every injected condition has exactly the same distribution of source lengths.
    assert len({tuple(sorted(lengths)) for lengths in lengths_by_delta.values()}) == 1
    assert len({r["episode"] for r in rows}) == 16
    summary = {}
    keys = ["exact_lag", "lag_absolute_error_steps", "lag_absolute_error_ms", "predicted_abs3", "action_exact",
            "negligible_label_consequence", "translation_command_rmse_m", "rotation_command_rmse_rad",
            "gripper_sign_disagreement", "gripper_switch_disagreement", "lag_error_with_negligible_label_consequence"]
    for method in ("xcorr", "arx", "zero"):
        selected = [r for r in rows if r["method"] == method]
        metrics = keys + (["true_midrank", "top3_support", "near_set_size", "true_in_near_set", "unidentifiable", "ambiguous", "unreliable",
                           "top3_advantage_over_uniform", "top3_advantage_over_fixed", "near_coverage_advantage_over_uniform"] if method != "zero" else [])
        summary[method] = {key: cluster_summary(selected, key, config["bootstrap_seed"], config["bootstrap_replicates"]) for key in metrics}
        summary[method]["by_delta"] = {str(d): {"samples": len([r for r in selected if r["true_lag"] == d]),
            "exact_lag": float(np.mean([r["exact_lag"] for r in selected if r["true_lag"] == d])),
            "lag_mae_steps": float(np.mean([r["lag_absolute_error_steps"] for r in selected if r["true_lag"] == d]))} for d in config["injected_lags"]}
        clean_cases = [r for r in selected if r["true_lag"] == 0]
        summary[method]["zero_lag_false_correction_rate"] = float(np.mean([r["estimated_lag"] != 0 for r in clean_cases]))
        summary[method]["sources_all_seven_negligible"] = sum(all(r["negligible_label_consequence"] for r in selected if r["episode"] == e) for e in config["lag_test"])
    selection = read_json(PUBLIC / "anchor_model_selection.json")
    decision = make_decision(rows, summary, config, selection)
    with (PUBLIC / "scored_cases.jsonl").open("x") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, allow_nan=False)+"\n")
    per_episode = {episode: {method: {"exact_lag": float(np.mean([r["exact_lag"] for r in rows if r["episode"] == episode and r["method"] == method])),
                    "cases": [r for r in rows if r["episode"] == episode and r["method"] == method]} for method in ("xcorr", "arx", "zero")} for episode in config["lag_test"]}
    write_json(PUBLIC / "by_episode.json", per_episode)
    write_json(PUBLIC / "summary.json", {"methods": summary, "decision": decision, "independent_sources": 16,
               "derived_conditions": 112, "score_times_common_for_all_candidates": True,
               "length_distribution_identical_across_injections": True,
               "scored_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()})
    print(json.dumps({"methods": {m: {"exact": v["exact_lag"]["mean"], "mae_steps": v["lag_absolute_error_steps"]["mean"]} for m,v in summary.items()}, "decision": decision}, indent=2))
