"""Validate and summarize a Gate B v2 B0 episode JSONL.

This tool only reads the run directory; it never reruns or edits episodes.
It refuses to report a rate if the seed set, horizon or record count is
incomplete, so an interrupted run cannot be mistaken for a completed baseline.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

from scipy.stats import beta


def wilson_interval(k: int, n: int, z: float = 1.959963984540054) -> tuple:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    denom = 1.0 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def clopper_pearson(k: int, n: int) -> tuple:
    if n == 0:
        return (float("nan"), float("nan"))
    low = 0.0 if k == 0 else float(beta.ppf(0.025, k, n - k + 1))
    high = 1.0 if k == n else float(beta.ppf(0.975, k + 1, n - k))
    return (low, high)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--expected-episodes", type=int, default=100)
    parser.add_argument("--expected-seed-start", type=int, default=100000)
    parser.add_argument("--expected-horizon", type=int, default=8)
    parser.add_argument("--max-steps", type=int, default=500)
    parser.add_argument("--episodes-file", default="b0_baseline_episodes.jsonl")
    args = parser.parse_args()

    run_dir = args.run_dir.resolve()
    episodes_path = run_dir / args.episodes_file
    if not episodes_path.is_file():
        raise FileNotFoundError(episodes_path)
    rows = [json.loads(line) for line in episodes_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    expected_seeds = list(range(args.expected_seed_start, args.expected_seed_start + args.expected_episodes))
    seeds = [int(row["seed"]) for row in rows]
    problems = []
    if len(rows) != args.expected_episodes:
        problems.append("episode count {} != {}".format(len(rows), args.expected_episodes))
    if len(set(seeds)) != len(seeds):
        problems.append("duplicate seeds")
    missing = sorted(set(expected_seeds) - set(seeds))
    extra = sorted(set(seeds) - set(expected_seeds))
    if missing:
        problems.append("missing seeds: {}".format(missing))
    if extra:
        problems.append("unexpected seeds: {}".format(extra))
    bad_horizon = sorted({int(row["horizon"]) for row in rows} - {args.expected_horizon})
    if bad_horizon:
        problems.append("unexpected horizons: {}".format(bad_horizon))
    bad_steps = [int(row["seed"]) for row in rows if int(row["steps"]) > args.max_steps]
    if bad_steps:
        problems.append("episodes over max_steps: {}".format(bad_steps))
    errors = [(int(row["seed"]), row["success_error"]) for row in rows if row.get("success_error")]
    if errors:
        problems.append("success_error present: {}".format(errors))

    successes = sum(bool(row["success"]) for row in rows)
    n = len(rows)
    rate = successes / n if n else float("nan")
    wall_times = [float(row["wall_time_s"]) for row in rows]
    steps = [int(row["steps"]) for row in rows]
    calls = [int(row["policy_calls"]) for row in rows]

    def mean(values):
        return float(sum(values) / len(values)) if values else float("nan")

    result = {
        "run_dir": str(run_dir),
        "complete": not problems,
        "problems": problems,
        "n_episodes": n,
        "expected_seed_start": args.expected_seed_start,
        "expected_seed_end": args.expected_seed_start + args.expected_episodes - 1,
        "successes": successes,
        "failures": n - successes,
        "success_rate": rate,
        "success_rate_percent": 100.0 * rate,
        "wilson_95ci": list(wilson_interval(successes, n)),
        "clopper_pearson_95ci": list(clopper_pearson(successes, n)),
        "mean_steps": mean(steps),
        "median_steps": float(sorted(steps)[len(steps) // 2]) if steps else float("nan"),
        "mean_policy_calls": mean(calls),
        "mean_wall_time_s": mean(wall_times),
        "median_wall_time_s": float(sorted(wall_times)[len(wall_times) // 2]) if wall_times else float("nan"),
        "total_wall_time_s": float(sum(wall_times)),
        "total_wall_time_h": float(sum(wall_times) / 3600.0),
        "failed_seeds": [int(row["seed"]) for row in rows if not bool(row["success"])],
        "episodes": [
            {
                "seed": int(row["seed"]),
                "success": bool(row["success"]),
                "steps": int(row["steps"]),
                "policy_calls": int(row["policy_calls"]),
                "wall_time_s": float(row["wall_time_s"]),
                "max_reward": float(row["max_reward"]),
                "termination": row["termination"],
                "success_error": row.get("success_error"),
                "initial_state_sha256": row.get("initial_state_sha256"),
            }
            for row in sorted(rows, key=lambda item: int(item["seed"]))
        ],
    }

    out_json = run_dir / "b0_analysis.json"
    out_json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with (run_dir / "b0_episodes.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["seed", "success", "steps", "policy_calls", "wall_time_s", "max_reward", "termination"])
        for item in result["episodes"]:
            writer.writerow([item["seed"], item["success"], item["steps"], item["policy_calls"],
                             item["wall_time_s"], item["max_reward"], item["termination"]])

    print(json.dumps({key: result[key] for key in (
        "complete", "problems", "n_episodes", "successes", "failures", "success_rate",
        "wilson_95ci", "clopper_pearson_95ci", "mean_steps", "mean_policy_calls",
        "mean_wall_time_s", "total_wall_time_h", "failed_seeds")}, indent=2, sort_keys=True))
    return 0 if result["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
