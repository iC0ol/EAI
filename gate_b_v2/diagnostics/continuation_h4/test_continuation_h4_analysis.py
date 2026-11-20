import csv
import json
from itertools import product

import numpy as np
import pytest

from analyze_b2_continuation_h4 import analyze_pairs, analyze_run, gpu_summary, short_contrast, sign_flip_test
from run_b2_continuation_h4 import FIRST_HORIZONS


def test_exact_sign_flip_includes_ties_and_zero_states():
    result = sign_flip_test(np.array([1, 0, 1, 0]))
    assert result["n_nonzero_states"] == 2
    assert result["draws"] == 4
    assert result["p_value"] == 0.5
    zero = sign_flip_test(np.zeros(30, dtype=int))
    assert zero["p_value"] == 1.0 and zero["draws"] == 1


def test_multivariate_flip_preserves_the_whole_state_vector():
    scores = np.array([[4, -4, 0], [0, 2, -2], [1, 1, -2]])
    observed = np.sum(scores.sum(axis=0) ** 2)
    tail = sum(
        np.sum((np.array(signs) @ scores) ** 2) >= observed
        for signs in product((-1, 1), repeat=len(scores))
    )
    assert sign_flip_test(scores)["p_value"] == tail / 8


def test_short_contrast_uses_both_short_horizons_and_h15():
    counts = np.array([[3, 2, 3, 3, 3], [3, 3, 0, 0, 1], [3, 3, 0, 0, 3]])
    assert short_contrast(counts).tolist() == [-1, 4, 0]


def test_paired_analysis_keeps_equal_loss_separate_from_horizon_differentiation():
    baseline, diagnostic = [], []
    for state, first_h, repeat in product(range(4), FIRST_HORIZONS, range(3)):
        shared = {
            "state_id": str(state), "source_seed": 310000 + state, "clearance_m": -0.05 + state * 0.005,
            "snapshot_sha256": f"{state:064x}", "repeat_index": repeat,
        }
        baseline.append({
            **shared, "horizon": first_h, "success": True,
            "policy_calls_after_branch": 20, "wall_time_s": 40.0,
        })
        success = state != 0 and not (state == 1 and first_h == 15 and repeat < 2)
        diagnostic.append({
            **shared, "first_horizon": first_h, "success": success,
            "policy_calls_after_branch": 75, "wall_time_s": 95.0,
        })
    result = analyze_pairs(baseline, diagnostic)
    assert result["overall_success"]["h4"]["successes"] == 43
    assert result["overall_success"]["h4_minus_h15"]["estimate"] == pytest.approx(-17 / 60)
    assert result["short_vs_h15"]["delta_h4_minus_delta_h15"]["estimate"] == pytest.approx(1 / 6)
    assert result["ceiling"]["previously_perfect_now_imperfect"] == ["0", "1"]
    assert result["ceiling"]["newly_differentiated_first_horizons"] == ["1"]
    assert result["ceiling"]["h4_failures_by_state"] == {"0": 15, "1": 2}
    assert result["omnibus_interaction"]["test"]["n_nonzero_states"] == 1
    assert result["efficiency"]["overall"]["h4"]["policy_calls_per_success"] == pytest.approx(4500 / 43)


def test_analyzer_refuses_unfinished_run(tmp_path):
    for suffix, data in (
        ("run.json", {}), ("integrity.json", {}), ("status.json", {"status": "BRANCH_RUNNING"}),
    ):
        (tmp_path / f"b2_continuation_h4_{suffix}").write_text(json.dumps(data))
    with pytest.raises(ValueError, match="complete 450-row"):
        analyze_run(tmp_path, tmp_path / "baseline.jsonl")


def test_gpu_sample_summary_parses_nvidia_units(tmp_path):
    path = tmp_path / "gpu.csv"
    with path.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow([
            "timestamp", "name", "driver_version", "temperature.gpu", "utilization.gpu [%]",
            "memory.used [MiB]", "power.draw [W]", "clocks.current.sm [MHz]",
        ])
        writer.writerow(["2026/11/19 17:00:00", "NVIDIA GeForce RTX 3090", "580.178.04", 45,
                         "0 %", "500 MiB", "100 W", "1695 MHz"])
        writer.writerow(["2026/11/19 17:00:30", "NVIDIA GeForce RTX 3090", "580.178.04", 85,
                         "88 %", "3553 MiB", "265 W", "1905 MHz"])
    result = gpu_summary(path)
    assert result["samples"] == 2
    assert result["temperature_c"] == {"min": 45.0, "median": 65.0, "max": 85.0}
    assert result["utilization_percent"]["median"] == 44.0
    assert result["memory_used_mib"]["max"] == 3553.0
