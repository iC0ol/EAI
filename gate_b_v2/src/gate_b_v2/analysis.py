from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple

import numpy as np

from .core import load_jsonl, write_json


def _bootstrap_mean_ci(values: np.ndarray, n_boot: int, seed: int) -> Tuple[float, float]:
    values = np.asarray(values, dtype=np.float64)
    if values.size == 0:
        return float("nan"), float("nan")
    rng = np.random.default_rng(int(seed))
    samples = rng.choice(values, size=(int(n_boot), values.size), replace=True).mean(axis=1)
    return float(np.quantile(samples, 0.025)), float(np.quantile(samples, 0.975))


def analyze_b1(run_dir: Path, n_bootstrap: int = 5000, seed: int = 20261110) -> Dict[str, Any]:
    run_dir = Path(run_dir)
    records = load_jsonl(run_dir / "b1_episodes.jsonl")
    if not records:
        raise ValueError("No B1 episodes found")
    by_seed: Dict[int, Dict[int, Mapping[str, Any]]] = defaultdict(dict)
    for row in records:
        key = (int(row["seed"]), int(row["horizon"]))
        if key[1] in by_seed[key[0]]:
            raise ValueError("Duplicate B1 record for seed/horizon {}".format(key))
        by_seed[key[0]][key[1]] = row
    horizons = sorted({int(row["horizon"]) for row in records})
    reference = 8
    if reference not in horizons:
        raise ValueError("B1 protocol requires h=8 reference")

    for seed_id, rows in by_seed.items():
        if set(rows) != set(horizons):
            raise ValueError("Seed {} does not have all horizons".format(seed_id))
        hashes = {rows[h]["initial_state_sha256"] for h in horizons}
        if len(hashes) != 1 or not all(rows[h].get("paired_initial_state_verified", False) for h in horizons):
            raise ValueError("Initial state pairing failed for seed {}".format(seed_id))

    seed_ids = sorted(by_seed)
    result: Dict[str, Any] = {
        "n_initial_states": len(seed_ids),
        "horizons": horizons,
        "reference_horizon": reference,
        "success_rate": {},
        "paired_risk_difference_vs_h8": {},
        "bootstrap_method": "paired bootstrap resampling initial-state seeds",
    }
    for horizon in horizons:
        success = np.asarray([float(by_seed[s][horizon]["success"]) for s in seed_ids])
        result["success_rate"][str(horizon)] = {
            "successes": int(success.sum()),
            "n": int(success.size),
            "rate": float(success.mean()),
        }
        if horizon == reference:
            continue
        ref_success = np.asarray([float(by_seed[s][reference]["success"]) for s in seed_ids])
        paired_diff = success - ref_success
        lo, hi = _bootstrap_mean_ci(paired_diff, n_bootstrap, seed + horizon)
        result["paired_risk_difference_vs_h8"][str(horizon)] = {
            "risk_difference": float(paired_diff.mean()),
            "ci95_low": lo,
            "ci95_high": hi,
            "n_pairs": int(paired_diff.size),
            "discordant_higher": int(np.sum((success == 1) & (ref_success == 0))),
            "discordant_lower": int(np.sum((success == 0) & (ref_success == 1))),
        }
    result["mean_policy_calls"] = {
        str(h): float(np.mean([by_seed[s][h]["policy_calls"] for s in seed_ids])) for h in horizons
    }
    result["mean_wall_time_s"] = {
        str(h): float(np.mean([by_seed[s][h]["wall_time_s"] for s in seed_ids])) for h in horizons
    }
    write_json(run_dir / "b1_analysis.json", result)
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
    b1_path = run_dir / "b1_analysis.json"
    if b1_path.exists():
        import json
        b1 = json.loads(b1_path.read_text(encoding="utf-8"))
        sections += ["## B1 paired horizon scan", "", "Initial states: **{}**".format(b1["n_initial_states"]), ""]
        sections += ["| h | Successes | N | Success rate | Mean policy calls | Mean wall time (s) |", "|---:|---:|---:|---:|---:|---:|"]
        for h in b1["horizons"]:
            row = b1["success_rate"][str(h)]
            sections.append("| {} | {} | {} | {:.3f} | {:.2f} | {:.2f} |".format(
                h, row["successes"], row["n"], row["rate"],
                b1["mean_policy_calls"][str(h)], b1["mean_wall_time_s"][str(h)],
            ))
        sections.append("")
        sections.append("Paired risk differences vs h=8 (95% cluster-bootstrap CI):")
        for h, row in b1["paired_risk_difference_vs_h8"].items():
            sections.append("- h={}: {:.3f} [{:.3f}, {:.3f}]".format(
                h, row["risk_difference"], row["ci95_low"], row["ci95_high"]
            ))
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
