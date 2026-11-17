import json
from pathlib import Path

import numpy as np
import pytest

from gate_b_v2.analysis import (
    _bootstrap_slope_effect,
    _clearance_permutation_test,
    _ols,
    _sign_flip_permutation_test,
    analyze_b2_split,
    write_b2_report,
)
from gate_b_v2.b2_protocol import (
    branch_order,
    branch_order_seed,
    repeat_seed,
    state_id,
)
from gate_b_v2.locks import (
    b2_record_environment_fields,
    build_b2_run_manifest,
    load_b1_full_manifest,
    load_fixed_project_config,
)


def _fixed_config():
    return load_fixed_project_config()


def _runtime_manifest_like_b1(b1_manifest):
    runtime = dict(b1_manifest)
    runtime["device_requested"] = runtime.get("device", "cuda:0")
    runtime["checkpoint"] = "/local/checkpoint"
    runtime["dataset"] = "/local/dataset"
    runtime["dp_root"] = "/local/dp"
    runtime.pop("_manifest_path", None)
    runtime.pop("_manifest_sha256", None)
    return runtime


def _dataset(run_dir: Path, split="discovery", n_states=30):
    config = _fixed_config()
    b1 = load_b1_full_manifest(Path(__file__).resolve().parents[1] / "reports" / "b1_full_run.json")
    runtime = _runtime_manifest_like_b1(b1)
    b2_manifest = build_b2_run_manifest(
        config, runtime, b1, split=split, command="test"
    )
    env_fields = b2_record_environment_fields(b2_manifest)
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
        successes = {1: 3 if tight else 2, 2: 3 if tight else 2, 4: 2, 8: 2, 15: 2}
        for repeat_index in range(3):
            order = branch_order(config, seed, repeat_index)
            order_seed = branch_order_seed(config, seed, repeat_index)
            common_repeat_seed = repeat_seed(config, seed, repeat_index)
            for order_index, horizon in enumerate(order):
                success = repeat_index < successes[horizon]
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
                    "policy_reset_verified": True,
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
                    **env_fields,
                })
    run_dir.mkdir(parents=True, exist_ok=True)
    with (run_dir / "b2_{}_state_manifest.jsonl".format(split)).open("w", encoding="utf-8") as stream:
        for item in states:
            stream.write(json.dumps(item) + "\n")
    with (run_dir / "b2_{}_episodes.jsonl".format(split)).open("w", encoding="utf-8") as stream:
        for row in records:
            stream.write(json.dumps(row) + "\n")
    (run_dir / "b2_{}_run.json".format(split)).write_text(
        json.dumps(b2_manifest), encoding="utf-8"
    )
    validation = {
        "split": split,
        "marker": "B2",
        "scientific_data": True,
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
    (run_dir / "b2_{}_summary.json".format(split)).write_text(json.dumps({
        "status": "COMPLETE", "completeness_verified": True, "n_branch_records": 450,
    }), encoding="utf-8")
    (run_dir / "b2_{}_status.json".format(split)).write_text(json.dumps({
        "status": "COMPLETE", "snapshot_validation_all_passed": True,
    }), encoding="utf-8")
    (run_dir / "B2_REPORT.md").write_text("# discovery\n", encoding="utf-8")
    return config, states, records


def test_ols_and_bootstrap_effect_recover_negative_slope():
    x = np.linspace(-0.03, 0.03, 30)
    y = 0.2 - 2.5 * x
    intercept, slope = _ols(x, y)
    assert abs(intercept - 0.2) < 1e-10
    assert abs(slope + 2.5) < 1e-10
    result = _bootstrap_slope_effect(
        x, y, float(np.quantile(x, 0.1)), float(np.quantile(x, 0.9)), 500, 123
    )
    assert abs(result["slope_per_m"] + 2.5) < 1e-10
    assert result["E"] > 0
    assert result["E_ci95_low"] <= result["E"] <= result["E_ci95_high"]
    assert result["n_bootstrap_used"] > 0
    assert "slope_bootstrap_p" not in result


def test_sign_flip_and_clearance_permutation_tests_are_reproducible():
    rng = np.random.default_rng(1)
    positive = np.full(30, 0.2) + rng.normal(0, 0.01, 30)
    first = _sign_flip_permutation_test(positive, n_permutations=2000, seed=11)
    second = _sign_flip_permutation_test(positive, n_permutations=2000, seed=11)
    assert first["p_value"] == second["p_value"]
    assert first["n_permutations"] == 2000
    assert first["p_value"] < 0.01

    x = np.linspace(-0.03, 0.03, 30)
    y = -3.0 * x + rng.normal(0, 0.005, 30)
    first_slope = _clearance_permutation_test(x, y, n_permutations=2000, seed=17)
    second_slope = _clearance_permutation_test(x, y, n_permutations=2000, seed=17)
    assert first_slope["p_value"] == second_slope["p_value"]
    assert first_slope["n_permutations"] == 2000
    assert first_slope["p_value"] < 0.01


def test_analyze_b2_split_uses_frozen_config_and_permutation_p(tmp_path):
    config, states, records = _dataset(tmp_path)
    result = analyze_b2_split(tmp_path, "discovery", seed=7, config=config)
    assert result["n_states"] == 30
    assert result["n_branch_episodes"] == 450
    assert result["protocol_version"] == "B2_PROTOCOL_REVISION_20261116"
    assert result["bootstrap_samples_requested"] == 5000
    assert result["permutation_samples"] == 100000
    assert result["primary"]["bootstrap_samples"] == 5000
    assert result["primary"]["permutation_samples"] == 100000
    assert "slope_permutation_p" in result["primary"]
    assert "E_permutation_p" in result["primary"]
    assert "slope_bootstrap_p" not in result["primary"]
    assert result["primary"]["E"] > 0
    assert result["primary"]["practical_effect_met"] is True
    assert "difference_permutation_p" in result["secondary_vs_h15"]["1"]
    assert "difference_holm_adjusted_p" in result["secondary_vs_h15"]["1"]
    assert result["snapshot_validation"]["all_passed"] is True
    assert (tmp_path / "b2_discovery_analysis.json").is_file()
    report = write_b2_report(tmp_path, "discovery", result, filename="B2_REPORT.md")
    text = report.read_text(encoding="utf-8")
    assert "Primary pre-registered contrast" in text
    assert "sign-flip" in text
    assert "State-cluster" in text or "state-cluster" in text


def test_analysis_rejects_bootstrap_override(tmp_path):
    config, states, records = _dataset(tmp_path)
    with pytest.raises(RuntimeError, match="bootstrap samples are frozen"):
        analyze_b2_split(tmp_path, "discovery", n_bootstrap=10, seed=7, config=config)


def test_analysis_rejects_missing_run_manifest(tmp_path):
    config, states, records = _dataset(tmp_path)
    (tmp_path / "b2_discovery_run.json").unlink()
    with pytest.raises(FileNotFoundError, match="run manifest not found"):
        analyze_b2_split(tmp_path, "discovery", seed=7, config=config)


def test_analysis_rejects_tampered_run_manifest(tmp_path):
    config, states, records = _dataset(tmp_path)
    path = tmp_path / "b2_discovery_run.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["config_fingerprint"] = "0" * 64
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(RuntimeError, match="config fingerprint"):
        analyze_b2_split(tmp_path, "discovery", seed=7, config=config)


def test_analysis_rejects_incomplete_records(tmp_path):
    config, states, records = _dataset(tmp_path)
    with (tmp_path / "b2_discovery_episodes.jsonl").open("w", encoding="utf-8") as stream:
        for row in records[:-1]:
            stream.write(json.dumps(row) + "\n")
    with pytest.raises(ValueError, match="completeness|missing"):
        analyze_b2_split(tmp_path, "discovery", seed=7, config=config)


def test_analysis_rejects_failed_snapshot_validation(tmp_path):
    config, states, records = _dataset(tmp_path)
    validation_path = tmp_path / "b2_discovery_snapshot_validation.json"
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    validation["all_passed"] = False
    validation_path.write_text(json.dumps(validation), encoding="utf-8")
    with pytest.raises(RuntimeError, match="snapshot validation"):
        analyze_b2_split(tmp_path, "discovery", seed=7, config=config)


def test_threshold_override_is_rejected_by_config_lock():
    from gate_b_v2.locks import validate_b2_config
    import yaml

    config = _fixed_config()
    broken = yaml.safe_load(yaml.safe_dump(config))
    broken["b2"]["practical_effect_threshold"] = 0.5
    with pytest.raises(RuntimeError, match="B2 config lock failed"):
        validate_b2_config(broken)
