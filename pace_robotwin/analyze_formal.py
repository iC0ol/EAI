"""Reproduce the registered paired results and attempt-level costs from an audited run."""

from collections import Counter, defaultdict
from itertools import combinations
from statistics import mean

import numpy as np
from scipy.stats import binomtest

from design import RUNS, STAGES, TASKS, file_hash, read_json, write_json


FORMAL = RUNS / "formal"
TIMES = ("setup_s", "observation_s", "action_s", "rollout_s", "attempt_s")
QUERY_TIMES = ("policy_s", "server_s", "rpc_s", "selection_s", "component_s")


def averages(rows):
    if not rows:
        return None
    return {name: mean(row[name] for row in rows) for name in rows[0]}


def trial(path, record):
    logs = record["query_log"]
    timing = read_json(path / "timing.json")
    costs = {name: record[name] for name in ("steps", "queries", *TIMES)}
    costs.update({name: sum(log[name] for log in logs) for name in QUERY_TIMES})
    costs["wall_with_io_s"] = timing["wall_with_io_s"]
    costs["planned_steps"] = sum(log["h"] for log in logs)
    return {"success": record["success"], "costs": costs}


def component_activity(path, record, counters, peaks, changed_scenes):
    """Count an intervention only when a changed command actually reached the environment."""
    touched = set()
    with np.load(path / "chunks.npz", allow_pickle=False) as source:
        raw, issued = source["raw"], source["issued"]
        for i, log in enumerate(record["query_log"]):
            offset = log["step"]
            count = min(log["h"], len(issued) - offset)
            for side, joints in (("left", slice(0, 6)), ("right", slice(7, 13))):
                arm = log["decision"]["arms"][side]
                tally = counters[side]
                tally["arm_queries"] += 1
                tally["eligible"] += int(arm["eligible"])
                tally["applied_to_plan"] += int(arm["applied"])
                reason = arm["release_reason"]
                if reason:
                    tally["reason_" + reason] += 1
                if reason and reason.startswith("ik_"):
                    tally["ik_fallback"] += 1
                changed = np.any(issued[offset:offset+count, joints] != raw[i, :count, joints], axis=1)
                if changed.any():
                    if not arm["applied"]:
                        raise ValueError(f"Unlogged changed command at {path}, query {i}, {side}")
                    tally["issued_windows"] += 1
                    tally["changed_control_steps"] += int(changed.sum())
                    actual = np.abs(arm["actual_axial_m"][:count])
                    peak_mm = float(1000 * actual.max())
                    peaks[side].append(peak_mm)
                    if peak_mm >= 1:
                        tally["issued_windows_at_least_1mm"] += 1
                    touched.add(side)
    for side in touched:
        changed_scenes[side].add(record["index"])
    return bool(touched)


def paired_success(left, right):
    counts = Counter((a["success"], b["success"]) for a, b in zip(left, right))
    delta = np.array([int(a["success"]) - int(b["success"]) for a, b in zip(left, right)])
    rng = np.random.default_rng(20261125)
    draws = rng.integers(0, len(delta), size=(20000, len(delta)))
    bootstrap_pp = delta[draws].sum(axis=1) * (100.0 / len(delta))
    only_left, only_right = counts[True, False], counts[False, True]
    discordant = only_left + only_right
    return {
        "both_success": counts[True, True], "only_component": only_left, "only_pace": only_right,
        "both_failure": counts[False, False], "difference_pp": (only_left - only_right) * 100 / len(delta),
        "percentile_95_pp": np.percentile(bootstrap_pp, [2.5, 97.5]).tolist(),
        "mcnemar_exact_two_sided_p": float(binomtest(only_left, discordant, .5).pvalue) if discordant else 1.0,
    }


def matched_costs(left, right):
    pairs = [(a["costs"], b["costs"]) for a, b in zip(left, right) if a["success"] and b["success"]]
    return {"n": len(pairs), "left_average": averages([a for a, _ in pairs]),
            "right_average": averages([b for _, b in pairs]),
            "mean_difference": averages([{k: a[k]-b[k] for k in a} for a, b in pairs])}


def summarize():
    audit = read_json(FORMAL / "AUDIT.json")
    status = read_json(FORMAL / "STATUS.json")
    manifest = file_hash(FORMAL / "MANIFEST.json")
    if (status["state"], audit["verified_records"], audit["verified_pairs"]) != ("AUDITED", 1600, 400):
        raise ValueError("The complete formal audit is required")
    if not manifest == audit["manifest_sha256"] == read_json(RUNS / "ACCEPTED.json")["manifest_sha256"]:
        raise ValueError("Manifest differs from engineering acceptance")
    result = {"manifest_sha256": manifest, "audit_sha256": file_hash(FORMAL / "AUDIT.json"),
              "cells": {}, "paired": {}, "joint_success_costs": {}, "component_activity": {},
              "sessions": {p.parent.name: read_json(p) for p in sorted((FORMAL / "sessions").glob("*/startup.json"))}}
    steps = queries = 0
    for stage in ("reproduction", "heldout"):
        for task in TASKS:
            groups = {}
            counters, peaks, changed = defaultdict(Counter), defaultdict(list), defaultdict(set)
            touched = set()
            for method in STAGES[stage][1]:
                rows = []
                for i in range(100):
                    path = FORMAL / stage / task / f"scene_{i:03d}" / method
                    key = path.relative_to(FORMAL).as_posix()
                    if file_hash(path / "sha256.json") != audit["record_manifests"][key]:
                        raise ValueError(f"Changed evidence manifest at {key}")
                    hashes = read_json(path / "sha256.json")
                    inputs = ["record.json", "timing.json"] + (["chunks.npz"] if method == "component" else [])
                    if any(file_hash(path / name) != hashes[name] for name in inputs):
                        raise ValueError(f"Analysis input differs from evidence at {key}")
                    rec = read_json(path / "record.json")
                    rows.append(trial(path, rec))
                    steps += rec["steps"]
                    queries += rec["queries"]
                    if method == "component" and component_activity(path, rec, counters, peaks, changed):
                        touched.add(i)
                groups[method] = rows
                successes = [r["costs"] for r in rows if r["success"]]
                result["cells"][f"{stage}/{task}/{method}"] = {
                    "n": len(rows), "success": len(successes), "all": averages([r["costs"] for r in rows]),
                    "success_only": averages(successes)}
            for a, b in combinations(groups, 2):
                result["joint_success_costs"][f"{stage}/{task}/{a}-{b}"] = matched_costs(groups[a], groups[b])
            if stage == "heldout":
                result["paired"][task] = paired_success(groups["component"], groups["pace"])
                for side in ("left", "right"):
                    counters[side]["scenes_changed"] = len(changed[side])
                result["component_activity"][task] = {
                    "per_side": dict(counters), "scenes_changed": len(touched),
                    "changed_wins": sum(groups["component"][i]["success"] and not groups["pace"][i]["success"] for i in touched),
                    "changed_losses": sum(groups["pace"][i]["success"] and not groups["component"][i]["success"] for i in touched),
                    "issued_peak_mm_by_side": {s: {"median": float(np.median(v)), "max": max(v)}
                                               for s, v in peaks.items() if v}}
    if (steps, queries) != (audit["verified_control_steps"], audit["verified_single_candidate_queries"]):
        raise ValueError("Analysis totals differ from audit")
    return result


if __name__ == "__main__":
    data = summarize()
    target = FORMAL / "ANALYSIS.json"
    if target.exists():
        if read_json(target) != data:
            raise ValueError("Independent recomputation disagrees with the previously stored analysis")
    else:
        write_json(target, data)
    print(target)
