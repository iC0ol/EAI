from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple

import numpy as np
from scipy.stats import binomtest, chi2

from .core import load_jsonl, write_json
from .locks import RECORD_ENVIRONMENT_KEYS, validate_b1_environment


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


def analyze_b2_split(
    run_dir: Path,
    split: str,
    n_bootstrap: int = 5000,
    seed: int = 20261110,
) -> Dict[str, Any]:
    run_dir = Path(run_dir)
    records = load_jsonl(run_dir / "b2_{}_episodes.jsonl".format(split))
    if not records:
        raise ValueError("No B2 {} episodes found".format(split))
    grouped: Dict[str, Dict[int, List[float]]] = defaultdict(lambda: defaultdict(list))
    clearance_by_state: Dict[str, float] = {}
    for row in records:
        state_id = str(row["state_id"])
        horizon = int(row["horizon"])
        grouped[state_id][horizon].append(float(bool(row["success"])))
        value = float(row["clearance_m"])
        if state_id in clearance_by_state and abs(clearance_by_state[state_id] - value) > 1e-9:
            raise ValueError("Clearance changed across branches for state {}".format(state_id))
        clearance_by_state[state_id] = value

    horizons = sorted({int(row["horizon"]) for row in records})
    reference = 8
    if reference not in horizons:
        raise ValueError("B2 protocol requires h=8 continuation/reference")
    state_ids = sorted(
        state_id for state_id, values in grouped.items()
        if reference in values and all(h in values for h in horizons)
    )
    if len(state_ids) < 3:
        raise ValueError("Too few complete matched B2 states: {}".format(len(state_ids)))

    x = np.asarray([clearance_by_state[state_id] for state_id in state_ids], dtype=np.float64)
    state_means = {
        state_id: {h: float(np.mean(grouped[state_id][h])) for h in horizons}
        for state_id in state_ids
    }
    output: Dict[str, Any] = {
        "split": split,
        "n_states": len(state_ids),
        "horizons": horizons,
        "reference_horizon": reference,
        "clearance_range_m": [float(np.min(x)), float(np.max(x))],
        "per_horizon_success_rate": {},
        "interaction_contrast_vs_h8": {},
        "method": (
            "For each state, average stochastic branch outcomes by horizon; regress "
            "(p_success(h)-p_success(8)) on continuous signed clearance; obtain 95% "
            "intervals by resampling whole states. This is a descriptive linear-probability "
            "interaction contrast, not a threshold-selected oracle label."
        ),
    }
    for horizon in horizons:
        y_h = np.asarray([state_means[s][horizon] for s in state_ids], dtype=np.float64)
        output["per_horizon_success_rate"][str(horizon)] = float(y_h.mean())
        if horizon == reference:
            continue
        diff = np.asarray([state_means[s][horizon] - state_means[s][reference] for s in state_ids])
        point, lo, hi = _cluster_bootstrap_slope_ci(x, diff, n_bootstrap, seed + horizon)
        output["interaction_contrast_vs_h8"][str(horizon)] = {
            "mean_success_difference": float(diff.mean()),
            "clearance_slope_per_meter": point,
            "clearance_slope_ci95_low": lo,
            "clearance_slope_ci95_high": hi,
            "n_states": len(state_ids),
        }
    write_json(run_dir / "b2_{}_analysis.json".format(split), output)
    return output


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
            sections += ["## B2 {} matched-state branches".format(split.title()), "", "States: **{}**".format(b2["n_states"]), ""]
            for h, row in b2["interaction_contrast_vs_h8"].items():
                sections.append(
                    "- h={}: mean Δsuccess={:.3f}; clearance slope={:.4f} "
                    "[{:.4f}, {:.4f}] per meter".format(
                        h, row["mean_success_difference"], row["clearance_slope_per_meter"],
                        row["clearance_slope_ci95_low"], row["clearance_slope_ci95_high"],
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
