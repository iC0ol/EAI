from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple

import numpy as np
from scipy.stats import binomtest, chi2

from .core import load_jsonl, write_json
from .locks import (
    B2_CONFIG_FINGERPRINT,
    B2_LOCKED_CONFIG_VALUES,
    B2_PROTOCOL_VERSION,
    RECORD_ENVIRONMENT_KEYS,
    load_b1_full_manifest,
    load_fixed_project_config,
    validate_b1_environment,
    validate_b2_config,
    validate_b2_run_manifest,
)


def _bootstrap_mean_ci(values: np.ndarray, n_boot: int, seed: int) -> Tuple[float, float]:
    values = np.asarray(values, dtype=np.float64)
    if values.size == 0:
        return float("nan"), float("nan")
    rng = np.random.default_rng(int(seed))
    samples = rng.choice(values, size=(int(n_boot), values.size), replace=True).mean(axis=1)
    return float(np.quantile(samples, 0.025)), float(np.quantile(samples, 0.975))


def _wilson_interval(k: int, n: int, z: float = 1.959963984540054) -> Tuple[float, float]:
    """Wilson score interval for one horizon's marginal success rate."""
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    denom = 1.0 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, float(center - half)), min(1.0, float(center + half))


def _mcnemar_exact(higher: int, lower: int) -> float:
    """Two-sided exact McNemar p-value for paired binary outcomes."""
    n = int(higher + lower)
    if n == 0:
        return 1.0
    return float(binomtest(int(higher), n, 0.5, alternative="two-sided").pvalue)


def _holm_adjust(pvalues: Sequence[float]) -> List[float]:
    """Holm step-down adjusted p-values, preserving input order."""
    values = [float(p) for p in pvalues]
    m = len(values)
    if m == 0:
        return []
    order = sorted(range(m), key=lambda index: values[index])
    adjusted = [1.0] * m
    running = 0.0
    for rank, index in enumerate(order):
        candidate = min(1.0, (m - rank) * values[index])
        running = max(running, candidate)
        adjusted[index] = running
    return adjusted


def _cochran_q(matrix: np.ndarray) -> Tuple[float, int, float]:
    """Cochran's Q for k paired binary treatments across n blocks."""
    matrix = np.asarray(matrix, dtype=np.float64)
    n, k = matrix.shape
    if n == 0 or k < 2:
        return float("nan"), max(k - 1, 0), 1.0
    column = matrix.sum(axis=0)
    row = matrix.sum(axis=1)
    denominator = k * row.sum() - float(np.sum(row * row))
    if denominator <= 0:
        return float("nan"), k - 1, 1.0
    q = (k - 1) * (k * float(np.sum(column * column)) - float(column.sum()) ** 2) / denominator
    q = max(0.0, float(q))
    return q, k - 1, float(chi2.sf(q, k - 1))


def _load_b1_manifest(run_dir: Path, phase: str) -> Tuple[Dict[str, Any], Path]:
    path = run_dir / "b1_{}_run.json".format(phase)
    if not path.is_file():
        raise FileNotFoundError(
            "B1 {} manifest not found: {}. Formal Pilot/Full analysis requires the "
            "pre-registration manifest.".format(phase, path)
        )
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("B1 manifest {} must contain a JSON object".format(path))
    return manifest, path


def _select_b1_records(run_dir: Path, phase: Any) -> Tuple[Path, Any]:
    from .core import B1_PHASES

    if phase is not None:
        if phase not in B1_PHASES:
            raise ValueError("B1 phase must be one of {}, got {!r}".format(B1_PHASES, phase))
        path = run_dir / "b1_{}_episodes.jsonl".format(phase)
        if not path.is_file():
            raise FileNotFoundError(path)
        return path, phase
    present = []
    for name, label in (
        ("b1_pilot_episodes.jsonl", "pilot"),
        ("b1_full_episodes.jsonl", "full"),
        ("b1_episodes.jsonl", None),
    ):
        path = run_dir / name
        if path.is_file():
            present.append((path, label))
    if len(present) > 1:
        raise ValueError(
            "Both Pilot and Full records exist in {}; specify --b1-phase explicitly. "
            "Automatic selection is forbidden when both phases are present.".format(run_dir)
        )
    if present:
        return present[0]
    raise FileNotFoundError("No B1 episode file in {}".format(run_dir))


def analyze_b1(
    run_dir: Path,
    n_bootstrap: int = 5000,
    seed: int = 20261110,
    phase: Any = None,
    reference: int = 8,
    alpha: float = 0.05,
    practical_diff: float = 0.08,
    ceiling_threshold: float = 0.95,
    floor_threshold: float = 0.05,
    expected_horizons: Any = None,
    expected_seed_start: Any = None,
    expected_episodes: Any = None,
    expected_phase_ranges: Any = None,
) -> Dict[str, Any]:
    run_dir = Path(run_dir)
    records_path, phase_label = _select_b1_records(run_dir, phase)
    records = load_jsonl(records_path)
    if not records:
        raise ValueError("No B1 episodes found in {}".format(records_path))
    by_seed: Dict[int, Dict[int, Mapping[str, Any]]] = defaultdict(dict)
    for row in records:
        key = (int(row["seed"]), int(row["horizon"]))
        if key[1] in by_seed[key[0]]:
            raise ValueError("Duplicate B1 record for seed/horizon {}".format(key))
        by_seed[key[0]][key[1]] = row
    horizons = sorted({int(row["horizon"]) for row in records})

    expected_start = None
    expected_count = None
    manifest_file = None
    if phase_label in ("pilot", "full"):
        manifest, manifest_path = _load_b1_manifest(run_dir, phase_label)
        manifest_file = manifest_path.name
        if expected_phase_ranges and phase_label in expected_phase_ranges:
            expected_start = int(expected_phase_ranges[phase_label][0])
            expected_count = int(expected_phase_ranges[phase_label][1])
        elif expected_seed_start is not None and expected_episodes is not None:
            expected_start, expected_count = int(expected_seed_start), int(expected_episodes)
        else:
            expected_start = int(manifest["seed_start"])
            expected_count = int(manifest["episodes"])
        if int(manifest.get("episodes", -1)) != expected_count:
            raise ValueError(
                "B1 {} manifest episodes {} != expected {}".format(
                    phase_label, manifest.get("episodes"), expected_count
                )
            )
        if int(manifest.get("seed_start", -1)) != expected_start:
            raise ValueError(
                "B1 {} manifest seed_start {} != expected {}".format(
                    phase_label, manifest.get("seed_start"), expected_start
                )
            )
        expected_end = expected_start + expected_count - 1
        if int(manifest.get("seed_end", -1)) != expected_end:
            raise ValueError(
                "B1 {} manifest seed_end {} != expected {}".format(
                    phase_label, manifest.get("seed_end"), expected_end
                )
            )
        if manifest.get("b1_phase") != phase_label:
            raise ValueError(
                "B1 manifest phase {!r} != requested {!r}".format(
                    manifest.get("b1_phase"), phase_label
                )
            )
        if manifest.get("records_file") != records_path.name:
            raise ValueError(
                "B1 manifest records_file {!r} != actual {!r}".format(
                    manifest.get("records_file"), records_path.name
                )
            )
        manifest_horizons = sorted(int(x) for x in manifest.get("horizons", []))
        if expected_horizons is None:
            expected_horizons = manifest_horizons
        elif manifest_horizons != sorted(int(x) for x in expected_horizons):
            raise ValueError(
                "B1 manifest horizons {} != protocol {}".format(
                    manifest_horizons, sorted(int(x) for x in expected_horizons)
                )
            )
        validate_b1_environment(
            manifest,
            phase=phase_label,
            seed_start=expected_start,
            seed_end=expected_end,
            episodes=expected_count,
        )
    elif expected_seed_start is not None and expected_episodes is not None:
        expected_start, expected_count = int(expected_seed_start), int(expected_episodes)

    if expected_horizons is not None:
        expected = sorted(int(x) for x in expected_horizons)
        if horizons != expected:
            raise ValueError(
                "B1 horizons {} do not match the amended protocol {}".format(horizons, expected)
            )

    if expected_start is not None and expected_count is not None:
        expected_seeds = set(range(expected_start, expected_start + expected_count))
        actual_seeds = set(by_seed)
        missing = sorted(expected_seeds - actual_seeds)
        extra = sorted(actual_seeds - expected_seeds)
        if missing or extra:
            raise ValueError(
                "B1 seed coverage mismatch for phase {!r}: missing={}, extra={}".format(
                    phase_label, missing, extra
                )
            )
        expected_records = expected_count * len(horizons)
        if len(records) != expected_records:
            raise ValueError(
                "B1 record count {} != expected {} ({} seeds x {} horizons)".format(
                    len(records), expected_records, expected_count, len(horizons)
                )
            )

    reference = int(reference)
    if reference not in horizons:
        raise ValueError("B1 protocol requires h={} reference, found {}".format(reference, horizons))

    if phase_label is not None:
        wrong_phase = sorted({row.get("b1_phase") for row in records if row.get("b1_phase") != phase_label})
        if wrong_phase:
            raise ValueError(
                "B1 records contain phase values {} but expected {!r}".format(wrong_phase, phase_label)
            )

    for seed_id, rows in by_seed.items():
        if set(rows) != set(horizons):
            raise ValueError("Seed {} does not have all horizons".format(seed_id))
        hashes = {rows[h]["initial_state_sha256"] for h in horizons}
        if len(hashes) != 1 or not all(rows[h].get("paired_initial_state_verified", False) for h in horizons):
            raise ValueError("Initial state pairing failed for seed {}".format(seed_id))

    if phase_label in ("pilot", "full"):
        offset = int(manifest["policy_seed_offset"])
        for row in records:
            for key in RECORD_ENVIRONMENT_KEYS:
                if row.get(key) != manifest.get(key):
                    raise ValueError(
                        "B1 record environment mismatch for key {!r}: record={!r} manifest={!r}".format(
                            key, row.get(key), manifest.get(key)
                        )
                    )
            expected_policy_seed = offset + int(row["seed"])
            if int(row.get("policy_seed", -1)) != expected_policy_seed:
                raise ValueError(
                    "B1 policy seed {} != policy_seed_offset + seed ({}) for seed {}".format(
                        row.get("policy_seed"), expected_policy_seed, row["seed"]
                    )
                )

    seed_ids = sorted(by_seed)
    matrix = np.asarray(
        [[float(bool(by_seed[s][h]["success"])) for h in horizons] for s in seed_ids],
        dtype=np.float64,
    )
    rates = matrix.mean(axis=0)
    result: Dict[str, Any] = {
        "phase": phase_label,
        "records_file": records_path.name,
        "manifest_file": manifest_file,
        "seed_start": expected_start if expected_start is not None else min(seed_ids),
        "seed_end": (
            expected_start + expected_count - 1
            if expected_start is not None and expected_count is not None
            else max(seed_ids)
        ),
        "episodes": expected_count if expected_count is not None else len(seed_ids),
        "completeness_verified": True,
        "n_initial_states": len(seed_ids),
        "horizons": horizons,
        "reference_horizon": reference,
        "alpha": float(alpha),
        "practical_diff": float(practical_diff),
        "success_rate": {},
        "paired_risk_difference_vs_h8": {},
        "overall_cochran_q": {},
        "statistical_unit": "initial-state seed; five horizons are paired conditions",
        "bootstrap_method": "paired cluster bootstrap resampling initial-state seeds",
        "multiple_comparison": "Holm step-down over comparisons against h={}".format(reference),
    }
    for column, horizon in enumerate(horizons):
        successes = int(matrix[:, column].sum())
        low, high = _wilson_interval(successes, len(seed_ids))
        result["success_rate"][str(horizon)] = {
            "successes": successes,
            "n": len(seed_ids),
            "rate": float(rates[column]),
            "wilson_95ci_low": low,
            "wilson_95ci_high": high,
        }

    q_value, q_df, q_p = _cochran_q(matrix)
    result["overall_cochran_q"] = {"q": q_value, "df": q_df, "p_value": q_p}

    ref_index = horizons.index(reference)
    comparisons = []
    for column, horizon in enumerate(horizons):
        if horizon == reference:
            continue
        paired_diff = matrix[:, column] - matrix[:, ref_index]
        lo, hi = _bootstrap_mean_ci(paired_diff, n_bootstrap, seed + horizon)
        higher = int(np.sum((matrix[:, column] == 1) & (matrix[:, ref_index] == 0)))
        lower = int(np.sum((matrix[:, column] == 0) & (matrix[:, ref_index] == 1)))
        comparisons.append({
            "horizon": horizon,
            "risk_difference": float(paired_diff.mean()),
            "ci95_low": lo,
            "ci95_high": hi,
            "n_pairs": int(paired_diff.size),
            "discordant_higher": higher,
            "discordant_lower": lower,
            "mcnemar_exact_p": _mcnemar_exact(higher, lower),
            "ci_excludes_zero": bool(lo > 0.0 or hi < 0.0),
        })
    holm = _holm_adjust([item["mcnemar_exact_p"] for item in comparisons])
    for item, adjusted in zip(comparisons, holm):
        item["holm_adjusted_p"] = float(adjusted)
        item["practically_significant"] = bool(abs(item["risk_difference"]) >= practical_diff)
        result["paired_risk_difference_vs_h8"][str(item["horizon"])] = {
            key: value for key, value in item.items() if key != "horizon"
        }

    pairwise = [
        abs(float(rates[i] - rates[j]))
        for i in range(len(horizons))
        for j in range(i + 1, len(horizons))
    ]
    result["max_abs_pairwise_rate_difference"] = max(pairwise) if pairwise else 0.0
    result["j1_practical_signal"] = bool(
        result["max_abs_pairwise_rate_difference"] >= float(practical_diff)
    )
    result["ceiling_effect"] = bool(float(np.min(rates)) >= float(ceiling_threshold))
    result["floor_effect"] = bool(float(np.max(rates)) <= float(floor_threshold))
    result["mean_policy_calls"] = {
        str(h): float(np.mean([by_seed[s][h]["policy_calls"] for s in seed_ids])) for h in horizons
    }
    result["mean_wall_time_s"] = {
        str(h): float(np.mean([by_seed[s][h]["wall_time_s"] for s in seed_ids])) for h in horizons
    }
    result["total_policy_calls"] = {
        str(h): int(np.sum([by_seed[s][h]["policy_calls"] for s in seed_ids])) for h in horizons
    }
    result["total_wall_time_s"] = {
        str(h): float(np.sum([by_seed[s][h]["wall_time_s"] for s in seed_ids])) for h in horizons
    }
    output_name = "b1_{}_analysis.json".format(phase_label) if phase_label else "b1_analysis.json"
    write_json(run_dir / output_name, result)
    return result


def _slope(x: np.ndarray, y: np.ndarray) -> float:
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    if x.size < 3 or np.std(x) < 1e-12:
        return float("nan")
    x_centered = x - x.mean()
    y_centered = y - y.mean()
    denom = float(np.sum(x_centered ** 2))
    return float(np.sum(x_centered * y_centered) / denom) if denom > 0 else float("nan")


def _cluster_bootstrap_slope_ci(
    x: np.ndarray, y: np.ndarray, n_bootstrap: int, seed: int
) -> Tuple[float, float, float]:
    point = _slope(x, y)
    rng = np.random.default_rng(int(seed))
    values = []
    n = len(x)
    if n < 3:
        return point, float("nan"), float("nan")
    for _ in range(int(n_bootstrap)):
        indices = rng.integers(0, n, size=n)
        value = _slope(x[indices], y[indices])
        if np.isfinite(value):
            values.append(value)
    if not values:
        return point, float("nan"), float("nan")
    return point, float(np.quantile(values, 0.025)), float(np.quantile(values, 0.975))


def _ols(x: np.ndarray, y: np.ndarray) -> Tuple[float, float]:
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    if x.size < 2 or float(np.std(x)) < 1e-15:
        return float("nan"), float("nan")
    design = np.column_stack([np.ones(x.size), x])
    coefficients = np.linalg.lstsq(design, y, rcond=None)[0]
    return float(coefficients[0]), float(coefficients[1])


def _bootstrap_slope_effect(
    x: np.ndarray,
    y: np.ndarray,
    c10: float,
    c90: float,
    n_bootstrap: int,
    seed: int,
) -> Dict[str, Any]:
    """State-cluster bootstrap of the linear contrast and E."""
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    intercept, slope = _ols(x, y)
    point_e = float((intercept + slope * c10) - (intercept + slope * c90)) if np.isfinite(slope) else float("nan")
    rng = np.random.default_rng(int(seed))
    n = x.size
    slopes: List[float] = []
    effects: List[float] = []
    for _ in range(int(n_bootstrap)):
        indices = rng.integers(0, n, size=n)
        sampled_x = x[indices]
        sampled_y = y[indices]
        if float(np.std(sampled_x)) < 1e-15:
            continue
        b0, b1 = _ols(sampled_x, sampled_y)
        if not (np.isfinite(b0) and np.isfinite(b1)):
            continue
        slopes.append(b1)
        effects.append(float((b0 + b1 * c10) - (b0 + b1 * c90)))
    slopes_array = np.asarray(slopes, dtype=np.float64)
    effects_array = np.asarray(effects, dtype=np.float64)
    if slopes_array.size == 0:
        return {
            "intercept": intercept,
            "slope_per_m": slope,
            "slope_per_mm": slope / 1000.0 if np.isfinite(slope) else float("nan"),
            "predicted_delta_at_c10": float(intercept + slope * c10) if np.isfinite(slope) else float("nan"),
            "predicted_delta_at_c90": float(intercept + slope * c90) if np.isfinite(slope) else float("nan"),
            "E": point_e,
            "E_ci95_low": float("nan"),
            "E_ci95_high": float("nan"),
            "slope_ci95_low": float("nan"),
            "slope_ci95_high": float("nan"),
            "bootstrap_seed": int(seed),
            "n_bootstrap_requested": int(n_bootstrap),
            "n_bootstrap_used": 0,
        }

    return {
        "intercept": intercept,
        "slope_per_m": slope,
        "slope_per_mm": slope / 1000.0 if np.isfinite(slope) else float("nan"),
        "predicted_delta_at_c10": float(intercept + slope * c10) if np.isfinite(slope) else float("nan"),
        "predicted_delta_at_c90": float(intercept + slope * c90) if np.isfinite(slope) else float("nan"),
        "E": point_e,
        "E_ci95_low": float(np.quantile(effects_array, 0.025)),
        "E_ci95_high": float(np.quantile(effects_array, 0.975)),
        "slope_ci95_low": float(np.quantile(slopes_array, 0.025)),
        "slope_ci95_high": float(np.quantile(slopes_array, 0.975)),
        "bootstrap_seed": int(seed),
        "n_bootstrap_requested": int(n_bootstrap),
        "n_bootstrap_used": int(slopes_array.size),
    }


def _bootstrap_state_mean_ci(values: np.ndarray, n_bootstrap: int, seed: int) -> Dict[str, Any]:
    """State-cluster bootstrap CI for a state-level mean (no invalid bootstrap p)."""
    values = np.asarray(values, dtype=np.float64)
    mean = float(values.mean())
    rng = np.random.default_rng(int(seed))
    n = values.size
    samples = rng.choice(values, size=(int(n_bootstrap), n), replace=True).mean(axis=1)
    return {
        "mean": mean,
        "ci95_low": float(np.quantile(samples, 0.025)),
        "ci95_high": float(np.quantile(samples, 0.975)),
        "bootstrap_seed": int(seed),
        "n_bootstrap_requested": int(n_bootstrap),
        "n_bootstrap": int(n_bootstrap),
    }


def _sign_flip_permutation_test(
    values: np.ndarray,
    n_permutations: int = 100000,
    seed: int = 20261110,
    chunk_size: int = 10000,
) -> Dict[str, Any]:
    """Paired state-level sign-flip permutation test for a mean difference.

    Under H0 the paired differences are symmetric about zero, so each state's
    sign is exchangeable.  This constructs an explicit null distribution instead
    of treating the bootstrap distribution as a p-value.
    """
    values = np.asarray(values, dtype=np.float64)
    observed = float(values.mean()) if values.size else float("nan")
    n = values.size
    if n == 0 or not np.isfinite(observed):
        return {
            "method": "paired state-level sign-flip permutation",
            "observed_mean": observed,
            "p_value": float("nan"),
            "seed": int(seed),
            "n_permutations": 0,
        }
    rng = np.random.default_rng(int(seed))
    extreme = 0
    used = 0
    threshold = abs(observed) - 1e-15
    remaining = int(n_permutations)
    while remaining > 0:
        size = min(int(chunk_size), remaining)
        signs = rng.integers(0, 2, size=(size, n), dtype=np.int8) * 2 - 1
        means = (signs.astype(np.float64) * values[None, :]).mean(axis=1)
        extreme += int(np.count_nonzero(np.abs(means) >= threshold))
        used += size
        remaining -= size
    p_value = float((1 + extreme) / (1 + used))
    return {
        "method": "paired state-level sign-flip permutation",
        "observed_mean": observed,
        "p_value": p_value,
        "seed": int(seed),
        "n_permutations": int(used),
    }


def _clearance_permutation_test(
    x: np.ndarray,
    y: np.ndarray,
    n_permutations: int = 100000,
    seed: int = 20261110,
    chunk_size: int = 10000,
) -> Dict[str, Any]:
    """State-level permutation test for the clearance slope.

    The null is no association between clearance and the state-level outcome
    contrast; clearance values are permuted relative to outcomes.
    """
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    _, observed_slope = _ols(x, y)
    n = x.size
    if n < 3 or not np.isfinite(observed_slope):
        return {
            "method": "state-level clearance permutation",
            "observed_slope_per_m": observed_slope,
            "p_value": float("nan"),
            "seed": int(seed),
            "n_permutations": 0,
        }
    rng = np.random.default_rng(int(seed))
    y_centered = y - y.mean()
    extreme = 0
    used = 0
    threshold = abs(observed_slope) - 1e-15
    remaining = int(n_permutations)
    while remaining > 0:
        size = min(int(chunk_size), remaining)
        # Each row is an independent permutation of clearance values.
        order = np.argsort(rng.random((size, n)), axis=1)
        permuted = x[order]
        centered = permuted - permuted.mean(axis=1, keepdims=True)
        denominator = np.sum(centered * centered, axis=1)
        slopes = np.divide(
            centered.dot(y_centered),
            denominator,
            out=np.full(size, np.nan),
            where=denominator > 0,
        )
        extreme += int(np.count_nonzero(np.abs(slopes) >= threshold))
        used += size
        remaining -= size
    p_value = float((1 + extreme) / (1 + used))
    return {
        "method": "state-level clearance permutation",
        "observed_slope_per_m": float(observed_slope),
        "p_value": p_value,
        "seed": int(seed),
        "n_permutations": int(used),
    }


def _categorical_interaction(
    x: np.ndarray,
    state_means: Mapping[str, Mapping[int, float]],
    state_ids: Sequence[str],
    horizons: Sequence[int],
    reference: int,
    n_bootstrap: int,
    seed: int,
) -> Dict[str, Any]:
    terms = [int(h) for h in horizons if int(h) != int(reference)]
    y_rows: List[float] = []
    x_rows: List[np.ndarray] = []
    for state_index, state_id in enumerate(state_ids):
        for horizon in horizons:
            row = [1.0]
            row.extend(1.0 if int(horizon) == term else 0.0 for term in terms)
            row.extend(
                (1.0 if int(horizon) == term else 0.0) * float(x[state_index])
                for term in terms
            )
            x_rows.append(np.asarray(row, dtype=np.float64))
            y_rows.append(float(state_means[state_id][int(horizon)]))
    design = np.asarray(x_rows, dtype=np.float64)
    response = np.asarray(y_rows, dtype=np.float64)
    coefficients = np.linalg.lstsq(design, response, rcond=None)[0]
    names = ["intercept_h{}".format(reference)]
    names.extend("horizon_main_h{}".format(term) for term in terms)
    names.extend("interaction_h{}_x_clearance_per_m".format(term) for term in terms)

    rng = np.random.default_rng(int(seed))
    n_states = len(state_ids)
    samples: List[np.ndarray] = []
    for _ in range(int(n_bootstrap)):
        indices = rng.integers(0, n_states, size=n_states)
        rows = []
        values = []
        for state_index in indices:
            state_id = state_ids[int(state_index)]
            for horizon in horizons:
                row = [1.0]
                row.extend(1.0 if int(horizon) == term else 0.0 for term in terms)
                row.extend(
                    (1.0 if int(horizon) == term else 0.0) * float(x[int(state_index)])
                    for term in terms
                )
                rows.append(np.asarray(row, dtype=np.float64))
                values.append(float(state_means[state_id][int(horizon)]))
        sampled = np.linalg.lstsq(np.asarray(rows), np.asarray(values), rcond=None)[0]
        samples.append(sampled)
    sample_matrix = np.asarray(samples, dtype=np.float64) if samples else np.empty((0, len(names)))
    result: Dict[str, Any] = {
        "model": "linear probability: p_s(h) ~ horizon + horizon x clearance; reference h={}".format(reference),
        "names": names,
        "coefficients": {name: float(value) for name, value in zip(names, coefficients)},
        "ci95": {},
        "method": "state-cluster bootstrap over whole state IDs; descriptive secondary analysis",
    }
    if sample_matrix.size:
        for index, name in enumerate(names):
            result["ci95"][name] = {
                "low": float(np.quantile(sample_matrix[:, index], 0.025)),
                "high": float(np.quantile(sample_matrix[:, index], 0.975)),
            }
    return result


def _clearance_bins(
    x: np.ndarray,
    state_means: Mapping[str, Mapping[int, float]],
    state_ids: Sequence[str],
    horizons: Sequence[int],
) -> List[Dict[str, Any]]:
    x = np.asarray(x, dtype=np.float64)
    edges = np.quantile(x, [0.0, 1.0 / 3.0, 2.0 / 3.0, 1.0])
    edges = np.unique(edges)
    bins: List[Dict[str, Any]] = []
    for index in range(max(1, len(edges) - 1)):
        low, high = float(edges[index]), float(edges[index + 1])
        if index == len(edges) - 2:
            members = [state_id for state_id, value in zip(state_ids, x) if low <= value <= high]
        else:
            members = [state_id for state_id, value in zip(state_ids, x) if low <= value < high]
        if not members:
            continue
        bins.append({
            "bin": index,
            "clearance_low_m": low,
            "clearance_high_m": high,
            "n_states": len(members),
            "success_rate_by_horizon": {
                str(horizon): float(np.mean([state_means[state_id][int(horizon)] for state_id in members]))
                for horizon in horizons
            },
            "delta_mean": float(np.mean([
                0.5 * (state_means[state_id][1] + state_means[state_id][2])
                - state_means[state_id][15]
                for state_id in members
            ])),
        })
    return bins


def _b2_inputs(
    run_dir: Path,
    split: str,
    config: Mapping[str, Any],
    project_root: Path = None,
):
    from .b2_protocol import validate_b2_records, validate_state_manifest

    validate_b2_config(config)
    records_path = run_dir / "b2_{}_episodes.jsonl".format(split)
    state_path = run_dir / "b2_{}_state_manifest.jsonl".format(split)
    validation_path = run_dir / "b2_{}_snapshot_validation.json".format(split)
    manifest_path = run_dir / "b2_{}_run.json".format(split)
    if not records_path.is_file():
        raise FileNotFoundError("B2 {} branch records not found: {}".format(split, records_path))
    if not state_path.is_file():
        raise FileNotFoundError("B2 {} state manifest not found: {}".format(split, state_path))
    if not validation_path.is_file():
        raise FileNotFoundError("B2 {} snapshot validation not found: {}".format(split, validation_path))
    if not manifest_path.is_file():
        raise FileNotFoundError(
            "B2 {} run manifest not found: {}; analysis is BLOCKED because the "
            "complete environment fingerprint cannot be verified".format(split, manifest_path)
        )

    root = Path(project_root).resolve() if project_root is not None else Path(__file__).resolve().parents[2]
    b1_manifest_path = Path(str(config["paths"]["b1_full_manifest"]))
    if not b1_manifest_path.is_absolute():
        b1_manifest_path = (root / b1_manifest_path).resolve()
    b1_full_manifest = load_b1_full_manifest(b1_manifest_path)

    records = load_jsonl(records_path)
    states = load_jsonl(state_path)
    run_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    validate_b2_run_manifest(run_manifest, split, b1_full_manifest)
    validate_state_manifest(states, split, config)
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    if validation.get("marker") != "B2":
        raise RuntimeError("B2 {} snapshot validation marker is not B2".format(split))
    if bool(validation.get("scientific_data")) is not True:
        raise RuntimeError("B2 {} snapshot validation is not formally marked".format(split))
    if not validation.get("all_passed"):
        raise RuntimeError(
            "B2 {} snapshot validation did not pass; analysis is BLOCKED".format(split)
        )
    if int(validation.get("n_states", -1)) != int(config["b2"]["selected_states"]):
        raise RuntimeError(
            "B2 {} snapshot validation n_states is not {}".format(
                split, config["b2"]["selected_states"]
            )
        )
    validate_b2_records(records, states, split, config, runtime_manifest=run_manifest)
    return (
        records, states, validation, run_manifest,
        records_path, state_path, validation_path, manifest_path, b1_full_manifest,
    )


def analyze_b2_split(
    run_dir: Path,
    split: str,
    n_bootstrap: int = None,
    seed: int = 20261110,
    config: Mapping[str, Any] = None,
    project_root: Path = None,
) -> Dict[str, Any]:
    """Pre-registered B2 v1.1 state-level analysis for one independent split."""
    run_dir = Path(run_dir)
    if split not in ("discovery", "confirmation"):
        raise ValueError("split must be discovery or confirmation")
    config = config or load_fixed_project_config(project_root)
    lock = validate_b2_config(config)
    frozen_bootstrap = int(lock["values"]["bootstrap_samples"])
    frozen_permutations = int(lock["values"]["permutation_samples"])
    if n_bootstrap is not None and int(n_bootstrap) != frozen_bootstrap:
        raise RuntimeError(
            "B2 analysis bootstrap samples are frozen at {}; override {} is rejected".format(
                frozen_bootstrap, n_bootstrap
            )
        )
    n_bootstrap = frozen_bootstrap
    seed = int(seed)
    (
        records, states, validation, run_manifest,
        records_path, state_path, validation_path, manifest_path, b1_full_manifest,
    ) = _b2_inputs(run_dir, split, config, project_root)
    horizons = [int(x) for x in config["b2"]["horizons"]]
    reference = int(config["b2"]["continuation_horizon"])
    repeats = int(config["b2"]["repeats_per_state_horizon"])
    if sorted(horizons) != [1, 2, 4, 8, 15] or reference != 15:
        raise ValueError("B2 analysis requires horizons [1,2,4,8,15] and reference h=15")

    grouped: Dict[str, Dict[int, List[float]]] = defaultdict(lambda: defaultdict(list))
    clearance_by_state: Dict[str, float] = {}
    for row in records:
        state_id = str(row["state_id"])
        grouped[state_id][int(row["horizon"])].append(float(bool(row["success"])))
        value = float(row["clearance_m"])
        if state_id in clearance_by_state and abs(clearance_by_state[state_id] - value) > 1e-9:
            raise ValueError("Clearance changed across branches for state {}".format(state_id))
        clearance_by_state[state_id] = value

    state_ids = sorted(grouped)
    for state_id in state_ids:
        if set(grouped[state_id]) != set(horizons):
            raise ValueError("State {} does not have all horizons".format(state_id))
        if any(len(grouped[state_id][horizon]) != repeats for horizon in horizons):
            raise ValueError("State {} does not have exactly {} repeats".format(state_id, repeats))

    x = np.asarray([clearance_by_state[state_id] for state_id in state_ids], dtype=np.float64)
    state_means: Dict[str, Dict[int, float]] = {
        state_id: {
            horizon: float(np.mean(grouped[state_id][horizon])) for horizon in horizons
        }
        for state_id in state_ids
    }
    delta = np.asarray([
        0.5 * (state_means[state_id][1] + state_means[state_id][2])
        - state_means[state_id][15]
        for state_id in state_ids
    ], dtype=np.float64)
    c10 = float(np.quantile(x, 0.10))
    c90 = float(np.quantile(x, 0.90))
    primary = _bootstrap_slope_effect(x, delta, c10, c90, n_bootstrap, seed)
    primary_sign_permutation = _clearance_permutation_test(
        x, delta, frozen_permutations, seed + 400
    )
    primary.update({
        "delta_formula": "0.5 * (p_s(1) + p_s(2)) - p_s(15)",
        "independent_unit": "state_id (not individual branch episodes)",
        "bootstrap": "state-cluster bootstrap resampling whole state IDs",
        "bootstrap_samples": int(n_bootstrap),
        "bootstrap_samples_used": int(primary["n_bootstrap_used"]),
        "bootstrap_seed": int(seed),
        "slope_permutation_method": primary_sign_permutation["method"],
        "slope_permutation_p": float(primary_sign_permutation["p_value"]),
        "E_permutation_p": float(primary_sign_permutation["p_value"]),
        "permutation_samples": int(primary_sign_permutation["n_permutations"]),
        "permutation_seed": int(primary_sign_permutation["seed"]),
        "n_states": len(state_ids),
        "n_branch_episodes": len(records),
        "clearance_c10_m": c10,
        "clearance_c90_m": c90,
        "practical_effect_threshold": float(config["b2"]["practical_effect_threshold"]),
        "practical_effect_met": bool(primary["E"] >= float(config["b2"]["practical_effect_threshold"])),
    })

    # Per-horizon rate and state-cluster CI.
    per_horizon: Dict[str, Any] = {}
    for horizon in horizons:
        values = np.asarray([state_means[state_id][horizon] for state_id in state_ids])
        ci = _bootstrap_state_mean_ci(values, n_bootstrap, seed + horizon)
        successes = int(round(float(values.sum() * repeats)))
        per_horizon[str(horizon)] = {
            "mean_state_success_probability": float(values.mean()),
            "branch_successes": successes,
            "branch_n": len(records) // len(horizons),
            "state_cluster_bootstrap_ci95": [ci["ci95_low"], ci["ci95_high"]],
            "bootstrap_seed": int(seed + horizon),
            "bootstrap_samples": int(n_bootstrap),
        }

    # Secondary h-vs-h15 differences and slopes.  CIs use the state-cluster
    # bootstrap; p-values use explicit state-level permutation nulls.
    secondary: Dict[str, Any] = {}
    raw_p = []
    slope_raw_p = []
    comparison_horizons = [h for h in (1, 2, 4, 8) if h in horizons]
    for horizon in comparison_horizons:
        diff = np.asarray([
            state_means[state_id][horizon] - state_means[state_id][15]
            for state_id in state_ids
        ])
        diff_stats = _bootstrap_state_mean_ci(diff, n_bootstrap, seed + 100 * horizon)
        diff_permutation = _sign_flip_permutation_test(
            diff, frozen_permutations, seed + 1000 + horizon
        )
        slope_stats = _bootstrap_slope_effect(
            x, diff, c10, c90, n_bootstrap, seed + 200 * horizon
        )
        slope_permutation = _clearance_permutation_test(
            x, diff, frozen_permutations, seed + 2000 + horizon
        )
        raw_p.append(diff_permutation["p_value"])
        slope_raw_p.append(slope_permutation["p_value"])
        secondary[str(horizon)] = {
            "mean_success_difference_vs_h15": diff_stats["mean"],
            "difference_ci95": [diff_stats["ci95_low"], diff_stats["ci95_high"]],
            "difference_permutation_method": diff_permutation["method"],
            "difference_permutation_p": float(diff_permutation["p_value"]),
            "difference_permutation_samples": int(diff_permutation["n_permutations"]),
            "difference_permutation_seed": int(diff_permutation["seed"]),
            "clearance_slope_per_m": slope_stats["slope_per_m"],
            "clearance_slope_per_mm": slope_stats["slope_per_mm"],
            "clearance_slope_ci95": [slope_stats["slope_ci95_low"], slope_stats["slope_ci95_high"]],
            "slope_permutation_method": slope_permutation["method"],
            "slope_permutation_p": float(slope_permutation["p_value"]),
            "slope_permutation_samples": int(slope_permutation["n_permutations"]),
            "slope_permutation_seed": int(slope_permutation["seed"]),
            "E_h_vs_h15": slope_stats["E"],
            "E_h_vs_h15_ci95": [slope_stats["E_ci95_low"], slope_stats["E_ci95_high"]],
        }
    holm_diff = _holm_adjust(raw_p)
    holm_slope = _holm_adjust(slope_raw_p)
    for horizon, adjusted_diff, adjusted_slope in zip(comparison_horizons, holm_diff, holm_slope):
        secondary[str(horizon)]["difference_holm_adjusted_p"] = float(adjusted_diff)
        secondary[str(horizon)]["slope_holm_adjusted_p"] = float(adjusted_slope)
        secondary[str(horizon)]["holm_correction_scope"] = (
            "four h-vs-h15 comparisons; p-values from state-level permutation tests"
        )

    categorical = _categorical_interaction(
        x, state_means, state_ids, horizons, 15, n_bootstrap, seed + 300
    )
    bins = _clearance_bins(x, state_means, state_ids, horizons)

    from scipy.stats import spearmanr

    spearman_delta = spearmanr(x, delta)
    robustness = {
        "spearman_clearance_vs_delta": {
            "rho": float(getattr(spearman_delta, "statistic", spearman_delta.correlation)),
            "p_value": float(spearman_delta.pvalue),
        },
        "spearman_clearance_vs_horizon_success": {},
    }
    for horizon in horizons:
        values = np.asarray([state_means[state_id][horizon] for state_id in state_ids])
        result = spearmanr(x, values)
        robustness["spearman_clearance_vs_horizon_success"][str(horizon)] = {
            "rho": float(getattr(result, "statistic", result.correlation)),
            "p_value": float(result.pvalue),
        }

    cost: Dict[str, Any] = {}
    for horizon in horizons:
        rows = [row for row in records if int(row["horizon"]) == horizon]
        cost[str(horizon)] = {
            "mean_policy_calls_after_branch": float(np.mean([row["policy_calls_after_branch"] for row in rows])),
            "mean_wall_time_s": float(np.mean([row["wall_time_s"] for row in rows])),
            "total_policy_calls": int(np.sum([row["policy_calls_after_branch"] for row in rows])),
            "total_wall_time_s": float(np.sum([row["wall_time_s"] for row in rows])),
        }

    snapshot_summary = {
        "marker": validation.get("marker"),
        "scientific_data": validation.get("scientific_data"),
        "all_passed": bool(validation.get("all_passed")),
        "n_states": int(validation.get("n_states", len(states))),
        "max_state_abs_error": max(
            (float(item["state_max_abs"]) for item in validation.get("per_state", {}).values()),
            default=float("nan"),
        ),
        "max_observation_mean_abs_error": max(
            (float(item["observation_mean_abs_max"]) for item in validation.get("per_state", {}).values()),
            default=float("nan"),
        ),
        "max_geometry_abs_error": max(
            (float(item["geometry_abs_max"]) for item in validation.get("per_state", {}).values()),
            default=float("nan"),
        ),
        "validation_file": validation_path.name,
    }

    if split == "discovery":
        upper = primary["E_ci95_high"]
        if not np.isfinite(upper):
            decision = "BLOCKED_OR_UNINFORMATIVE"
        elif upper < float(config["b2"]["practical_effect_threshold"]):
            decision = "STOP_LACKING_PLAUSIBLE_PRACTICAL_EFFECT"
        elif primary["E_ci95_low"] >= float(config["b2"]["practical_effect_threshold"]):
            decision = "DISCOVERY_STRONG_SIGNAL_CONFIRMATION_JUSTIFIED"
        else:
            decision = "DISCOVERY_UNCERTAIN_CONFIRMATION_JUSTIFIED"
    else:
        threshold = float(config["b2"]["practical_effect_threshold"])
        if primary["E"] >= threshold and primary["E_ci95_low"] > 0.0:
            decision = "CONFIRMATION_SUPPORTS_B2_MECHANISM"
        elif primary["E_ci95_high"] < threshold:
            decision = "CONFIRMATION_NO_PRACTICALLY_MEANINGFUL_EFFECT"
        else:
            decision = "CONFIRMATION_INCONCLUSIVE"

    output: Dict[str, Any] = {
        "split": split,
        "marker": "B2",
        "protocol_version": B2_PROTOCOL_VERSION,
        "records_file": records_path.name,
        "state_manifest_file": state_path.name,
        "run_manifest_file": manifest_path.name,
        "run_manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "b1_full_manifest_sha256": b1_full_manifest.get("_manifest_sha256"),
        "config_fingerprint": B2_CONFIG_FINGERPRINT,
        "n_states": len(state_ids),
        "n_branch_episodes": len(records),
        "horizons": horizons,
        "reference_horizon": reference,
        "repeats_per_state_horizon": repeats,
        "bootstrap_samples_requested": int(n_bootstrap),
        "bootstrap_samples_used": int(primary.get("bootstrap_samples_used", 0)),
        "bootstrap_seed": int(seed),
        "permutation_samples": int(frozen_permutations),
        "permutation_method": (
            "paired state-level sign-flip test for horizon differences; "
            "state-level clearance permutation test for slopes"
        ),
        "statistical_unit": "state_id; repeats nested within state x horizon",
        "clearance_range_m": [float(np.min(x)), float(np.max(x))],
        "clearance_c10_m": c10,
        "clearance_c90_m": c90,
        "primary": primary,
        "per_horizon": per_horizon,
        "secondary_vs_h15": secondary,
        "categorical_interaction": categorical,
        "clearance_bins_descriptive": bins,
        "robustness": robustness,
        "cost": cost,
        "snapshot_validation": snapshot_summary,
        "integrity": {
            "completeness_verified": True,
            "split_isolation_verified": True,
            "snapshot_hashes_verified": True,
            "horizon_order_verified": True,
            "common_repeat_seed_verified": True,
        },
        "decision": decision,
        "interpretation_limits": [
            "The independent unit is the matched physical state, not the 450 branch episodes.",
            "Repeats are nested within state x horizon; bootstrap resamples whole state IDs.",
            "Hypothesis-test p-values come from state-level permutation nulls, not from "
            "the bootstrap distribution.",
            "Discovery and confirmation are analyzed independently and are never pooled.",
            "A wide interval is inconclusive; non-significance is not proof of no effect.",
            "B2 does not train CAC or establish a deployment-time visual clearance estimator.",
        ],
    }
    write_json(run_dir / "b2_{}_analysis.json".format(split), output)
    return output


def write_b2_report(
    run_dir: Path,
    split: str,
    analysis: Mapping[str, Any],
    filename: str = None,
) -> Path:
    run_dir = Path(run_dir)
    primary = analysis["primary"]
    lines = [
        "# B2 {} report — matched-state CAC intervention".format(split.title()),
        "",
        "Protocol: `B2_PROTOCOL_REVISION_20261116` (B2 v1.1).",
        "Marker: **B2** (not PREFLIGHT).",
        "",
        "## Integrity",
        "",
        "| Check | Result |",
        "|---|---|",
        "| States (`state_id` is the independent unit) | {} |".format(analysis["n_states"]),
        "| Branch episodes | {} (30 x 5 x 3 required) |".format(analysis["n_branch_episodes"]),
        "| Completeness / duplicate / mixed-split gate | passed |",
        "| Snapshot validation (every selected state) | {} |".format(
            "passed" if analysis["snapshot_validation"]["all_passed"] else "FAILED"
        ),
        "| Max snapshot state error | {:.3g} |".format(
            analysis["snapshot_validation"]["max_state_abs_error"]
        ),
        "| Max observation MAE | {:.3g} |".format(
            analysis["snapshot_validation"]["max_observation_mean_abs_error"]
        ),
        "| Max geometry error (m) | {:.3g} |".format(
            analysis["snapshot_validation"]["max_geometry_abs_error"]
        ),
        "",
        "## Per-horizon success",
        "",
        "| h | State-mean success probability | State-cluster 95% CI |",
        "|---:|---:|---|",
    ]
    for horizon in analysis["horizons"]:
        row = analysis["per_horizon"][str(horizon)]
        lines.append("| {} | {:.3f} | [{:.3f}, {:.3f}] |".format(
            horizon,
            row["mean_state_success_probability"],
            row["state_cluster_bootstrap_ci95"][0],
            row["state_cluster_bootstrap_ci95"][1],
        ))
    lines += [
        "",
        "## Primary pre-registered contrast",
        "",
        "`p_s(h) = mean(success over 3 repeats)`; `Delta_s = 0.5*(p_s(1)+p_s(2)) - p_s(15)`.",
        "",
        "| Quantity | Estimate | 95% state-cluster bootstrap CI |",
        "|---|---:|---|",
        "| Slope per metre | {:.4f} | [{:.4f}, {:.4f}] |".format(
            primary["slope_per_m"], primary["slope_ci95_low"], primary["slope_ci95_high"]
        ),
        "| Slope per millimetre | {:.6f} | — |".format(primary["slope_per_mm"]),
        "| Predicted Delta at c10 | {:.4f} | — |".format(primary["predicted_delta_at_c10"]),
        "| Predicted Delta at c90 | {:.4f} | — |".format(primary["predicted_delta_at_c90"]),
        "| **E = pred(c10) - pred(c90)** | **{:.4f}** | **[{:.4f}, {:.4f}]** |".format(
            primary["E"], primary["E_ci95_low"], primary["E_ci95_high"]
        ),
        "",
        "Pre-registered practical threshold: E >= {:.2f}. Point estimate meets threshold: **{}**.".format(
            primary["practical_effect_threshold"], primary["practical_effect_met"]
        ),
        "",
        "Clearance c10/c90: {:.6f} / {:.6f} m.".format(
            primary["clearance_c10_m"], primary["clearance_c90_m"]
        ),
        "",
        "Statistical method: 5,000 state-cluster bootstrap resamples for confidence intervals; "
        "{:,} state-level clearance permutations for the slope null; slope permutation p={:.6g}. "
        "E has the same permutation p because c10/c90 are fixed.".format(
            int(primary["permutation_samples"]), primary["slope_permutation_p"]
        ),
        "",
        "## Secondary h-vs-h15 comparisons",
        "",
        "CIs: state-cluster bootstrap. p-values: paired sign-flip (difference) and clearance "
        "permutation (slope), each with {:,} permutations; Holm correction over the four "
        "h-vs-h15 comparisons.".format(int(primary["permutation_samples"])),
        "",
        "| h | Mean success difference vs h=15 | 95% CI | Holm p (difference) | Clearance slope / m | 95% CI | Holm p (slope) |",
        "|---:|---:|---|---:|---:|---|---:|",
    ]
    for horizon in [1, 2, 4, 8]:
        row = analysis["secondary_vs_h15"].get(str(horizon))
        if not row:
            continue
        lines.append(
            "| {} | {:.3f} | [{:.3f}, {:.3f}] | {:.4g} | {:.4f} | [{:.4f}, {:.4f}] | {:.4g} |".format(
                horizon,
                row["mean_success_difference_vs_h15"],
                row["difference_ci95"][0], row["difference_ci95"][1],
                row["difference_holm_adjusted_p"],
                row["clearance_slope_per_m"],
                row["clearance_slope_ci95"][0], row["clearance_slope_ci95"][1],
                row["slope_holm_adjusted_p"],
            )
        )
    lines += [
        "",
        "## Categorical h x clearance interaction (secondary)",
        "",
        "Linear probability model over state-level `p_s(h)`, reference h=15, state-cluster bootstrap CIs.",
        "",
        "| Term | Coefficient | 95% CI |",
        "|---|---:|---|",
    ]
    for name in analysis["categorical_interaction"]["names"]:
        value = analysis["categorical_interaction"]["coefficients"][name]
        ci = analysis["categorical_interaction"]["ci95"].get(name, {})
        lines.append("| `{}` | {:.4f} | [{:.4f}, {:.4f}] |".format(
            name, value, ci.get("low", float("nan")), ci.get("high", float("nan"))
        ))
    lines += [
        "",
        "## Cost",
        "",
        "| h | Mean policy calls after branch | Mean wall time (s) | Total calls |",
        "|---:|---:|---:|---:|",
    ]
    for horizon in analysis["horizons"]:
        row = analysis["cost"][str(horizon)]
        lines.append("| {} | {:.2f} | {:.2f} | {} |".format(
            horizon, row["mean_policy_calls_after_branch"], row["mean_wall_time_s"], row["total_policy_calls"]
        ))
    lines += [
        "",
        "## Descriptive clearance bins",
        "",
        "| Bin | Clearance range (m) | States | Delta mean |",
        "|---:|---|---:|---:|",
    ]
    for row in analysis["clearance_bins_descriptive"]:
        lines.append("| {} | [{:.6f}, {:.6f}] | {} | {:.3f} |".format(
            row["bin"], row["clearance_low_m"], row["clearance_high_m"],
            row["n_states"], row["delta_mean"],
        ))
    lines += [
        "",
        "## Decision",
        "",
        "**{}**".format(analysis["decision"]),
        "",
        "This is a protocol-level statistical decision for the {} split only. It is"
        " not a claim that B2 has passed, and the other split is not pooled.".format(split),
        "",
        "## Interpretation limits",
        "",
    ]
    lines.extend("- " + item for item in analysis["interpretation_limits"])
    lines.append("")
    path = run_dir / (filename or "b2_{}_report.md".format(split))
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_markdown_summary(run_dir: Path) -> Path:
    run_dir = Path(run_dir)
    sections = ["# Gate B v2 analysis summary", ""]
    import json

    for name, title in (
        ("b1_pilot_analysis.json", "B1 pilot paired horizon scan"),
        ("b1_full_analysis.json", "B1 full paired horizon scan"),
        ("b1_analysis.json", "B1 paired horizon scan"),
    ):
        b1_path = run_dir / name
        if not b1_path.exists():
            continue
        b1 = json.loads(b1_path.read_text(encoding="utf-8"))
        sections += ["## {}".format(title), "", "Initial states: **{}**".format(b1["n_initial_states"]), ""]
        sections += ["| h | Successes | N | Success rate | Wilson 95% CI | Mean policy calls | Mean wall time (s) |",
                     "|---:|---:|---:|---:|---|---:|---:|"]
        for h in b1["horizons"]:
            row = b1["success_rate"][str(h)]
            sections.append("| {} | {} | {} | {:.3f} | [{:.3f}, {:.3f}] | {:.2f} | {:.2f} |".format(
                h, row["successes"], row["n"], row["rate"],
                row.get("wilson_95ci_low", float("nan")), row.get("wilson_95ci_high", float("nan")),
                b1["mean_policy_calls"][str(h)], b1["mean_wall_time_s"][str(h)],
            ))
        sections.append("")
        sections.append("Cochran's Q: q={:.4f}, df={}, p={:.6g}".format(
            b1["overall_cochran_q"].get("q", float("nan")),
            b1["overall_cochran_q"].get("df", 0),
            b1["overall_cochran_q"].get("p_value", float("nan")),
        ))
        sections.append("")
        sections.append("Paired risk differences vs h={} (95% cluster-bootstrap CI, Holm-adjusted p):".format(
            b1.get("reference_horizon", 8)
        ))
        for h, row in b1["paired_risk_difference_vs_h8"].items():
            sections.append("- h={}: {:.3f} [{:.3f}, {:.3f}]; Holm p={:.6g}".format(
                h, row["risk_difference"], row["ci95_low"], row["ci95_high"],
                row.get("holm_adjusted_p", float("nan")),
            ))
        if b1.get("ceiling_effect"):
            sections.append("- Ceiling effect: all horizon success rates >= threshold.")
        if b1.get("floor_effect"):
            sections.append("- Floor effect: all horizon success rates <= threshold.")
        sections.append("")
    for split in ("discovery", "confirmation"):
        path = run_dir / "b2_{}_analysis.json".format(split)
        if path.exists():
            import json
            b2 = json.loads(path.read_text(encoding="utf-8"))
            primary = b2["primary"]
            sections += [
                "## B2 {} matched-state branches".format(split.title()),
                "",
                "States: **{}**; branch episodes: **{}**.".format(
                    b2["n_states"], b2["n_branch_episodes"]
                ),
                "",
                "Primary E = pred(Delta|c10) - pred(Delta|c90): **{:.4f}** "
                "[{:.4f}, {:.4f}] (threshold {:.2f}); decision: **{}**.".format(
                    primary["E"], primary["E_ci95_low"], primary["E_ci95_high"],
                    primary["practical_effect_threshold"], b2["decision"],
                ),
                "",
            ]
            for h, row in b2["per_horizon"].items():
                sections.append(
                    "- h={}: state-mean success={:.3f} [{:.3f}, {:.3f}]".format(
                        h, row["mean_state_success_probability"],
                        row["state_cluster_bootstrap_ci95"][0],
                        row["state_cluster_bootstrap_ci95"][1],
                    )
                )
            sections.append("")
    sections += [
        "## Interpretation limits", "",
        "- B1 pairing is valid only when every seed has the same initial simulator-state hash across horizons.",
        "- B2 is valid only if snapshot/restore deterministic replay passed and discovery/confirmation states are disjoint.",
        "- A wide interval is inconclusive; do not treat non-significance as evidence of no effect.",
        "- This analysis does not train CAC or establish a deployment-time visual clearance estimator.",
        "",
    ]
    path = run_dir / "ANALYSIS.md"
    path.write_text("\n".join(sections), encoding="utf-8")
    return path
