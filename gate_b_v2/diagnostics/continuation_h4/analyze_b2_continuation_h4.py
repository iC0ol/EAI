"""Reproduce the post-hoc paired analysis from the archived Branch records."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np

from gate_b_v2.analysis import (
    _bootstrap_slope_effect, _bootstrap_state_mean_ci, _clearance_permutation_test, _holm_adjust,
)
from gate_b_v2.core import load_jsonl, sha256_file
from gate_b_v2.snapshot import require_passed_snapshot_validation
from run_b2_continuation_h4 import (
    CONTINUATION_HORIZON, FIRST_HORIZONS, N_BRANCHES, N_STATES, PHASE, PREFIX, REPEATS,
    SOURCE_CHECKSUM_LIST_SHA256, SOURCE_SPLIT, validate_complete,
)


BASELINE_SHA256 = "fad12b5bb84dc66f9b8c05024227fd82d0f8911b65aaf09e8c38e0cfa9d9c557"
BOOTSTRAP_SAMPLES = 5000
PERMUTATION_SAMPLES = 100000
ANALYSIS_SEED = 20261110
EXACT_NONZERO_LIMIT = 16
SETTINGS_KEYS = (
    "base_b2_config_fingerprint", "continuation_horizon", "first_horizons", "max_steps", "n_states",
    "repeats_per_state_horizon", "phase", "success_threshold", "snapshot_validation",
)


def sign_flip_test(scores: np.ndarray) -> dict:
    """Flip one sign per state, keeping every component of that state together."""
    scores = np.asarray(scores, dtype=np.int64)
    if scores.ndim == 1:
        scores = scores[:, None]
    informative = scores[np.any(scores != 0, axis=1)]
    n_informative = len(informative)
    summed = informative.sum(axis=0)
    observed = int(summed @ summed)

    if n_informative <= EXACT_NONZERO_LIMIT:
        n_draws = 1 << n_informative
        bits = (np.arange(n_draws, dtype=np.uint64)[:, None]
                >> np.arange(n_informative, dtype=np.uint64)) & 1
        signed_totals = (2 * bits.astype(np.int64) - 1) @ informative
        extreme = int(np.count_nonzero(np.sum(signed_totals ** 2, axis=1) >= observed))
        p_value = extreme / n_draws
        method = "exact state-level sign flip"
    else:
        n_draws = PERMUTATION_SAMPLES
        rng = np.random.default_rng(ANALYSIS_SEED)
        extreme = 0
        for offset in range(0, n_draws, 10000):
            draws = min(10000, n_draws - offset)
            signs = 2 * rng.integers(0, 2, size=(draws, n_informative)) - 1
            signed_totals = signs @ informative
            extreme += int(np.count_nonzero(np.sum(signed_totals ** 2, axis=1) >= observed))
        p_value = (extreme + 1) / (n_draws + 1)
        method = "Monte Carlo state-level sign flip"
    return {
        "method": method, "p_value": p_value, "draws": n_draws, "n_nonzero_states": n_informative,
        "squared_sum_statistic_integer_units": observed,
    }


def interval(scores: np.ndarray, divisor: int) -> dict:
    result = _bootstrap_state_mean_ci(scores / divisor, BOOTSTRAP_SAMPLES, ANALYSIS_SEED)
    return {"estimate": result["mean"], "ci95": [result["ci95_low"], result["ci95_high"]]}


def paired_effect(scores: np.ndarray, divisor: int) -> dict:
    return {**interval(scores, divisor), "test": sign_flip_test(scores)}


def rate(scores: np.ndarray, branches_per_state: int) -> dict:
    return {
        "successes": int(scores.sum()), "branches": len(scores) * branches_per_state,
        **interval(scores, branches_per_state),
    }


def short_contrast(counts: np.ndarray) -> np.ndarray:
    """Integer numerator for the state contrast on the probability scale of 1/6."""
    return counts[:, 0] + counts[:, 1] - 2 * counts[:, -1]


def efficiency(rows: list) -> dict:
    calls = sum(row["policy_calls_after_branch"] for row in rows)
    seconds = sum(row["wall_time_s"] for row in rows)
    successes = sum(row["success"] for row in rows)
    return {
        "branches": len(rows), "successes": successes,
        "total_policy_calls": calls, "total_branch_wall_time_s": seconds,
        "mean_policy_calls": calls / len(rows), "mean_branch_wall_time_s": seconds / len(rows),
        "policy_calls_per_success": calls / successes if successes else None,
        "branch_wall_time_s_per_success": seconds / successes if successes else None,
    }


def states_matching(states: list, mask: np.ndarray) -> list:
    return [state for state, matched in zip(states, mask) if matched]


def analyze_pairs(baseline: list, diagnostic: list) -> dict:
    states = sorted({row["state_id"] for row in baseline})
    state_indices = {state: index for index, state in enumerate(states)}
    horizon_indices = {horizon: index for index, horizon in enumerate(FIRST_HORIZONS)}
    shape = (len(states), len(FIRST_HORIZONS), REPEATS)
    before, after = np.zeros(shape, dtype=bool), np.zeros(shape, dtype=bool)
    state_rows = {}
    for old, new in zip(baseline, diagnostic):
        index = state_indices[old["state_id"]], horizon_indices[old["horizon"]], old["repeat_index"]
        before[index], after[index] = old["success"], new["success"]
        state_rows[old["state_id"]] = old

    old_counts, new_counts = before.sum(axis=2), after.sum(axis=2)
    difference = new_counts - old_counts
    state_delta_old, state_delta_new = short_contrast(old_counts), short_contrast(new_counts)
    contrasts = state_delta_new - state_delta_old
    branches_per_state = len(FIRST_HORIZONS) * REPEATS
    overall = {
        "h15": rate(old_counts.sum(axis=1), branches_per_state),
        "h4": rate(new_counts.sum(axis=1), branches_per_state),
        "h4_minus_h15": paired_effect(difference.sum(axis=1), branches_per_state),
    }

    per_horizon = {}
    for index, horizon in enumerate(FIRST_HORIZONS):
        per_horizon[str(horizon)] = {
            "h15": rate(old_counts[:, index], REPEATS),
            "h4": rate(new_counts[:, index], REPEATS),
            "h4_minus_h15": paired_effect(difference[:, index], REPEATS),
            "paired_failure_to_success": int(np.count_nonzero(~before[:, index] & after[:, index])),
            "paired_success_to_failure": int(np.count_nonzero(before[:, index] & ~after[:, index])),
        }
    adjusted = _holm_adjust([item["h4_minus_h15"]["test"]["p_value"] for item in per_horizon.values()])
    for item, p_value in zip(per_horizon.values(), adjusted):
        item["h4_minus_h15"]["holm_p_value"] = p_value

    old_perfect, new_perfect = before.all(axis=(1, 2)), after.all(axis=(1, 2))
    old_separated, new_separated = np.ptp(old_counts, axis=1) > 0, np.ptp(new_counts, axis=1) > 0
    q4_failures = branches_per_state - new_counts.sum(axis=1)
    ceiling = {
        "all_fifteen_successes_h15": states_matching(states, old_perfect),
        "all_fifteen_successes_h4": states_matching(states, new_perfect),
        "differentiated_first_horizons_h15": states_matching(states, old_separated),
        "differentiated_first_horizons_h4": states_matching(states, new_separated),
        "newly_differentiated_first_horizons": states_matching(states, ~old_separated & new_separated),
        "previously_perfect_now_imperfect": states_matching(states, old_perfect & ~new_perfect),
        "previously_imperfect_now_perfect": states_matching(states, ~old_perfect & new_perfect),
        "h4_failures_by_state": {
            state: int(count) for state, count in zip(states, q4_failures) if count
        },
        "h4_failures_by_first_horizon": {
            str(h): REPEATS * len(states) - int(new_counts[:, index].sum())
            for index, h in enumerate(FIRST_HORIZONS)
        },
    }

    # Center continuation differences within each state to remove the horizon-invariant effect.
    # Keep integer scores so the exact sign-flip test can compare ties without a tolerance.
    centered = len(FIRST_HORIZONS) * difference - difference.sum(axis=1, keepdims=True)
    short = {
        "delta_h15": paired_effect(state_delta_old, 2 * REPEATS),
        "delta_h4": paired_effect(state_delta_new, 2 * REPEATS),
        "delta_h4_minus_delta_h15": paired_effect(contrasts, 2 * REPEATS),
        "states_with_nonzero_delta_h15": states_matching(states, state_delta_old != 0),
        "states_with_nonzero_delta_h4": states_matching(states, state_delta_new != 0),
    }
    clearances = np.array([state_rows[state]["clearance_m"] for state in states], dtype=float)
    c10, c90 = np.quantile(clearances, [0.1, 0.9]).tolist()
    response = state_delta_new / (2 * REPEATS)
    geom = _bootstrap_slope_effect(clearances, response, c10, c90, BOOTSTRAP_SAMPLES, ANALYSIS_SEED)
    geometry = {
        **geom, "post_hoc_exploratory": True, "clearance_c10_m": c10, "clearance_c90_m": c90,
        "clearance_range_m": [float(clearances.min()), float(clearances.max())],
        "clearance_negative_states": int(np.count_nonzero(clearances < 0)),
        "slope_permutation": _clearance_permutation_test(
            clearances, response, PERMUTATION_SAMPLES, ANALYSIS_SEED + 400,
        ),
    }
    per_state = []
    for index, state in enumerate(states):
        per_state.append({
            "state_id": state, "source_seed": state_rows[state]["source_seed"],
            "snapshot_sha256": state_rows[state]["snapshot_sha256"], "clearance_m": float(clearances[index]),
            "successes_h15_by_first_horizon": old_counts[index].tolist(),
            "successes_h4_by_first_horizon": new_counts[index].tolist(),
            "p_h15_by_first_horizon": (old_counts[index] / REPEATS).tolist(),
            "p_h4_by_first_horizon": (new_counts[index] / REPEATS).tolist(),
            "p_h4_minus_h15_by_first_horizon": (difference[index] / REPEATS).tolist(),
            "delta_h15": float(state_delta_old[index] / (2 * REPEATS)),
            "delta_h4": float(state_delta_new[index] / (2 * REPEATS)),
            "delta_h4_minus_delta_h15": float(contrasts[index] / (2 * REPEATS)),
        })

    return {
        "overall_success": overall, "per_first_horizon": per_horizon, "short_vs_h15": short,
        "omnibus_interaction": {
            "state_scores": "5 times per-horizon success count differences minus their within-state sum",
            "statistic": "squared length of the summed vector of centered horizon differences",
            "test": sign_flip_test(centered),
        },
        "ceiling": ceiling, "geometry": geometry, "per_state": per_state,
        "efficiency": {
            "overall": {"h15": efficiency(baseline), "h4": efficiency(diagnostic)},
            "per_first_horizon": {
                str(horizon): {
                    "h15": efficiency([row for row in baseline if row["horizon"] == horizon]),
                    "h4": efficiency([row for row in diagnostic if row["first_horizon"] == horizon]),
                }
                for horizon in FIRST_HORIZONS
            },
        },
    }


def gpu_summary(path: Path) -> dict:
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream, skipinitialspace=True))
    if not rows:
        raise ValueError("Diagnostic GPU telemetry has no samples")
    metrics = {}
    for output, field in (
        ("temperature_c", "temperature.gpu"), ("utilization_percent", "utilization.gpu [%]"),
        ("memory_used_mib", "memory.used [MiB]"), ("power_w", "power.draw [W]"),
        ("sm_clock_mhz", "clocks.current.sm [MHz]"),
    ):
        values = np.array([float(row[field].split()[0]) for row in rows])
        if not np.isfinite(values).all():
            raise ValueError(f"Invalid GPU telemetry in {field}")
        metrics[output] = {
            "min": float(values.min()), "median": float(np.median(values)), "max": float(values.max()),
        }
    return {
        "samples": len(rows), "configured_period_s": 30, "first_timestamp": rows[0]["timestamp"],
        "last_timestamp": rows[-1]["timestamp"], "timezone": "Asia/Shanghai",
        "gpu_names": sorted({row["name"] for row in rows}),
        "driver_versions": sorted({row["driver_version"] for row in rows}), **metrics,
    }


def analyze_run(run_dir: Path, baseline_path: Path) -> dict:
    def load(suffix):
        return json.loads((run_dir / (PREFIX + suffix)).read_text(encoding="utf-8"))

    manifest, integrity, status = load("run.json"), load("integrity.json"), load("status.json")
    for record in (status, integrity):
        if (record["status"] != "COMPLETE" or record["phase"] != PHASE
                or record["continuation_horizon"] != CONTINUATION_HORIZON
                or record["n_branch_records"] != N_BRANCHES or record["expected_branch_records"] != N_BRANCHES
                or record["n_states"] != N_STATES or record["completeness_verified"] is not True
                or record["snapshot_validation_all_passed"] is not True or record["original_checksums_verified"] is not True):
            raise ValueError("Diagnostic integrity evidence must show a complete 450-row run")

    settings = {key: manifest[key] for key in SETTINGS_KEYS}
    config_sha = hashlib.sha256(json.dumps(settings, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if not (
        config_sha == manifest["diagnostic_config_fingerprint"] == integrity["diagnostic_config_fingerprint"]
        and manifest["source_raw_checksum_list_sha256"] == integrity["source_raw_checksum_list_sha256"]
        == SOURCE_CHECKSUM_LIST_SHA256
        and manifest["source_records_sha256"] == integrity["source_records_sha256"]
        == sha256_file(baseline_path) == BASELINE_SHA256
    ):
        raise ValueError("Archived diagnostic configuration or baseline fingerprint differs")

    records_path = run_dir / (PREFIX + "episodes.jsonl")
    manifest_path = run_dir / (PREFIX + "run.json")
    validation_path = (run_dir / manifest["snapshot_recheck_file"]).resolve()
    if not validation_path.is_relative_to(run_dir.resolve()):
        raise ValueError("Snapshot recheck must be stored inside the diagnostic run")
    hashes = {
        "episodes_sha256": sha256_file(records_path),
        "run_manifest_sha256": sha256_file(manifest_path),
        "snapshot_recheck_sha256": sha256_file(validation_path),
    }
    if any(value != integrity[key] for key, value in hashes.items()):
        raise ValueError("Archived diagnostic artifact differs from the runtime integrity receipt")

    baseline, diagnostic = load_jsonl(baseline_path), load_jsonl(records_path)
    validate_complete(diagnostic, baseline, config_sha)
    expected_snapshots = {row["state_id"]: row["snapshot_sha256"] for row in baseline}
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    require_passed_snapshot_validation(validation, SOURCE_SPLIT, expected_snapshots)
    completed_at = integrity["completed_at"]
    if status["completed_at"] != completed_at or status["started_at"] != manifest["started_at"]:
        raise ValueError("Diagnostic run and terminal status timestamps differ")

    return {
        "phase": PHASE, "run_id": manifest["run_id"], "source_run_id": manifest["source_run_id"],
        "started_at": manifest["started_at"], "completed_at": completed_at,
        "post_hoc_exploratory": True, "n_states": N_STATES, "n_branches_per_run": N_BRANCHES,
        "repeats_per_state_and_first_horizon": REPEATS, "first_horizons": list(FIRST_HORIZONS),
        "continuation_horizons_compared": [15, CONTINUATION_HORIZON],
        "independent_unit": "matched physical state",
        "bootstrap": {"draws": BOOTSTRAP_SAMPLES, "seed": ANALYSIS_SEED, "interval": "95% percentile",
                      "unit": "whole matched state"},
        "sign_flip": {"exact_if_nonzero_states_at_most": EXACT_NONZERO_LIMIT,
                      "monte_carlo_draws": PERMUTATION_SAMPLES, "seed": ANALYSIS_SEED},
        "baseline_episodes_sha256": BASELINE_SHA256, **hashes,
        "gpu_telemetry": gpu_summary(run_dir / (PREFIX + "gpu.csv")),
        **analyze_pairs(baseline, diagnostic),
    }


def main() -> None:
    project = Path(__file__).resolve().parents[2]
    default_baseline = project / "reports" / "b2_confirmation_20261118" / "b2_confirmation_episodes.jsonl"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--baseline-episodes", default=default_baseline, type=Path)
    parser.add_argument("--output", type=Path, help="Create this output file, or emit JSON on stdout")
    args = parser.parse_args()
    result = analyze_run(args.run_dir, args.baseline_episodes)
    content = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.output is None:
        print(content, end="")
    else:
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(content)


if __name__ == "__main__":
    main()
