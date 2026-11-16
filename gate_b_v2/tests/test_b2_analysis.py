import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import pytest

from gate_b_v2.analysis import (
    _bootstrap_slope_effect,
    _ols,
    analyze_b2_split,
    write_b2_report,
)
from gate_b_v2.b2_protocol import (
    branch_order,
    branch_order_seed,
    repeat_seed,
    state_id,
)


def _config(n_bootstrap=200):
    return {
        "b2": {
            "horizons": [1, 2, 4, 8, 15],
            "selected_states": 30,
            "source_horizon": 8,
            "continuation_horizon": 15,
            "repeats_per_state_horizon": 3,
            "source_policy_seed_offset": 900000,
            "branch_order_seed_base": 20261118,
            "branch_order_seed_stride": 5,
            "repeat_seed_base": 1000000,
            "repeat_seed_stride": 17,
            "practical_effect_threshold": 0.08,
            "bootstrap_samples": n_bootstrap,
            "discovery": {
                "primary_seed_start": 300000, "primary_seed_count": 100,
                "extension_seed_start": 300100, "extension_seed_count": 100,
                "selection_seed": 20261116,
            },
            "confirmation": {
                "primary_seed_start": 310000, "primary_seed_count": 100,
                "extension_seed_start": 310100, "extension_seed_count": 100,
                "selection_seed": 20261117,
            },
        }
    }


def _dataset(run_dir: Path, split="discovery", n_states=30, n_bootstrap=200):
    config = _config(n_bootstrap)
    states = []
    records = []
    for index in range(n_states):
        seed = (300000 if split == "discovery" else 310000) + index
        clearance = -0.02 + 0.04 * index / (n_states - 1)
        item = {
            "state_id": state_id(split, seed),
            "split": split,
            "source_seed": seed,
            "source_step": 100 + index,
            "source_horizon": 8,
            "stage_gate_version": "B2_GEOMETRY_GATE_V1_20261116",
            "clearance_m": clearance,
            "z_gap_m": 0.005,
            "dx_m": 0.0,
            "dy_m": 0.0,
            "d_xy_m": 0.01,
            "relative_yaw_rad": 0.0,
            "t_nut_m": 0.02,
            "r_hole_m": 0.032,
            "r_peg_m": 0.022,
            "snapshot_file": "snapshots/{}.pkl.gz".format(state_id(split, seed)),
            "snapshot_sha256": "sha-{}".format(seed),
        }
        states.append(item)
        tight = clearance < 0.0
        # p_s(15)=2/3 always; p_s(1)=p_s(2)=1 in tight states and 2/3 in wide
        # states, so Delta_s is higher for tighter clearance.
        successes = {1: 3 if tight else 2, 2: 3 if tight else 2, 4: 2, 8: 2, 15: 2}
        for repeat_index in range(3):
            order = branch_order(config, seed, repeat_index)
            order_seed = branch_order_seed(config, seed, repeat_index)
            common_repeat_seed = repeat_seed(config, seed, repeat_index)
            for order_index, horizon in enumerate(order):
                success_count = successes[horizon]
                success = repeat_index < success_count
                records.append({
                    "split": split,
                    "state_id": item["state_id"],
                    "source_seed": seed,
                    "source_step": item["source_step"],
                    "horizon": horizon,
                    "repeat_index": repeat_index,
                    "repeat_seed": common_repeat_seed,
                    "branch_order_seed": order_seed,
                    "randomized_order_index": order_index,
                    "continuation_horizon": 15,
                    "preflight": False,
                    "snapshot_sha256": item["snapshot_sha256"],
                    "clearance_m": clearance,
                    "z_gap_m": 0.005,
                    "dx_m": 0.0,
                    "dy_m": 0.0,
                    "d_xy_m": 0.01,
                    "relative_yaw_rad": 0.0,
                    "success": bool(success),
                    "policy_calls_after_branch": 10 + horizon,
                    "wall_time_s": 1.0 + 0.1 * horizon,
                    "policy_noise_seed_schedule": [1000 + call for call in range(3)],
                })
    run_dir.mkdir(parents=True, exist_ok=True)
    with (run_dir / "b2_{}_state_manifest.jsonl".format(split)).open("w", encoding="utf-8") as stream:
        for item in states:
            stream.write(json.dumps(item) + "\n")
    with (run_dir / "b2_{}_episodes.jsonl".format(split)).open("w", encoding="utf-8") as stream:
        for row in records:
            stream.write(json.dumps(row) + "\n")
    validation = {
        "split": split,
        "all_passed": True,
        "n_states": n_states,
        "per_state": {
            item["state_id"]: {
                "state_max_abs": 1e-9,
                "observation_mean_abs_max": 1e-6,
                "geometry_abs_max": 1e-9,
            }
            for item in states
        },
    }
    (run_dir / "b2_{}_snapshot_validation.json".format(split)).write_text(
        json.dumps(validation), encoding="utf-8"
    )
    return config, states, records


def test_ols_and_bootstrap_effect_recover_negative_slope():
    x = np.linspace(-0.03, 0.03, 30)
    y = 0.2 - 2.5 * x
    intercept, slope = _ols(x, y)
    assert abs(intercept - 0.2) < 1e-10
    assert abs(slope + 2.5) < 1e-10
    result = _bootstrap_slope_effect(x, y, float(np.quantile(x, 0.1)),
                                     float(np.quantile(x, 0.9)), 500, 123)
    assert abs(result["slope_per_m"] + 2.5) < 1e-10
    assert result["E"] > 0
    assert result["E_ci95_low"] <= result["E"] <= result["E_ci95_high"]
    assert result["n_bootstrap_used"] > 0


def test_analyze_b2_split_reports_primary_and_secondary(tmp_path):
    config, states, records = _dataset(tmp_path)
    result = analyze_b2_split(
        tmp_path, "discovery", n_bootstrap=300, seed=7, config=config
    )
    assert result["n_states"] == 30
    assert result["n_branch_episodes"] == 450
    assert set(result["per_horizon"]) == {"1", "2", "4", "8", "15"}
    assert result["reference_horizon"] == 15
    assert result["primary"]["delta_formula"] == "0.5 * (p_s(1) + p_s(2)) - p_s(15)"
    assert result["primary"]["E"] > 0
    assert result["primary"]["practical_effect_met"] is True
    assert "difference_holm_adjusted_p" in result["secondary_vs_h15"]["1"]
    assert result["snapshot_validation"]["all_passed"] is True
    assert result["decision"] in {
        "STOP_LACKING_PLAUSIBLE_PRACTICAL_EFFECT",
        "DISCOVERY_STRONG_SIGNAL_CONFIRMATION_JUSTIFIED",
        "DISCOVERY_UNCERTAIN_CONFIRMATION_JUSTIFIED",
    }
    assert (tmp_path / "b2_discovery_analysis.json").is_file()
    report = write_b2_report(tmp_path, "discovery", result)
    text = report.read_text(encoding="utf-8")
    assert "Primary pre-registered contrast" in text
    assert "Decision" in text
    assert "state_id" in text


def test_analysis_rejects_incomplete_records(tmp_path):
    config, states, records = _dataset(tmp_path)
    with (tmp_path / "b2_discovery_episodes.jsonl").open("w", encoding="utf-8") as stream:
        for row in records[:-1]:
            stream.write(json.dumps(row) + "\n")
    with pytest.raises(ValueError, match="completeness|missing"):
        analyze_b2_split(tmp_path, "discovery", n_bootstrap=10, seed=7, config=config)


def test_analysis_rejects_failed_snapshot_validation(tmp_path):
    config, states, records = _dataset(tmp_path)
    validation_path = tmp_path / "b2_discovery_snapshot_validation.json"
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    validation["all_passed"] = False
    validation_path.write_text(json.dumps(validation), encoding="utf-8")
    with pytest.raises(RuntimeError, match="snapshot validation"):
        analyze_b2_split(tmp_path, "discovery", n_bootstrap=10, seed=7, config=config)
