import json

import numpy as np
import pytest

from gate_b_v2.analysis import (
    _cochran_q,
    _holm_adjust,
    _mcnemar_exact,
    _wilson_interval,
    analyze_b1,
)

HORIZONS = [1, 2, 4, 8, 15]


def _write_records(run_dir, seeds, outcomes, phase="pilot"):
    rows = []
    for seed in seeds:
        initial_hash = "hash_{}".format(seed)
        for horizon in HORIZONS:
            success = outcomes[seed][horizon]
            rows.append({
                "seed": seed,
                "horizon": horizon,
                "success": success,
                "initial_state_sha256": initial_hash,
                "paired_initial_state_verified": True,
                "policy_calls": 500 // horizon + (1 if 500 % horizon else 0),
                "wall_time_s": float(100.0 / horizon),
                "steps": 500,
                "max_reward": 1.0 if success else 0.0,
                "termination": "max_steps",
                "success_error": None,
                "b1_phase": phase,
            })
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "b1_{}_episodes.jsonl".format(phase)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    return path


def _paired_outcomes(seeds, all_success=False):
    outcomes = {}
    for seed in seeds:
        outcomes[seed] = {}
        for horizon in HORIZONS:
            if all_success:
                outcomes[seed][horizon] = True
            else:
                outcomes[seed][horizon] = ((seed * 7 + horizon) % 10) < 7
    return outcomes


def test_holm_adjust_is_monotone_and_bounded():
    adjusted = _holm_adjust([0.01, 0.04, 0.03])
    assert adjusted == pytest.approx([0.03, 0.06, 0.06])


def test_cochran_q_handles_no_within_block_variation():
    matrix = np.asarray([[1, 1, 1], [0, 0, 0], [1, 1, 1]], dtype=float)
    q, df, p = _cochran_q(matrix)
    assert np.isnan(q)
    assert df == 2
    assert p == 1.0


def test_wilson_interval_contains_rate():
    low, high = _wilson_interval(8, 10)
    assert low <= 0.8 <= high
    assert 0.0 <= low <= high <= 1.0


def test_mcnemar_exact_no_discordant_pairs():
    assert _mcnemar_exact(0, 0) == 1.0


def test_analyze_b1_reports_paired_cluster_statistics(tmp_path):
    seeds = list(range(200000, 200020))
    _write_records(tmp_path, seeds, _paired_outcomes(seeds))
    result = analyze_b1(
        tmp_path,
        n_bootstrap=200,
        phase="pilot",
        expected_horizons=HORIZONS,
        reference=8,
    )
    assert result["n_initial_states"] == 20
    assert result["horizons"] == HORIZONS
    assert result["phase"] == "pilot"
    for horizon in HORIZONS:
        row = result["success_rate"][str(horizon)]
        assert row["n"] == 20
        assert 0.0 <= row["rate"] <= 1.0
        assert row["wilson_95ci_low"] <= row["rate"] <= row["wilson_95ci_high"]
    assert 0.0 <= result["overall_cochran_q"]["p_value"] <= 1.0
    assert set(result["paired_risk_difference_vs_h8"]) == {"1", "2", "4", "15"}
    for row in result["paired_risk_difference_vs_h8"].values():
        assert 0.0 <= row["mcnemar_exact_p"] <= 1.0
        assert 0.0 <= row["holm_adjusted_p"] <= 1.0
    assert (tmp_path / "b1_pilot_analysis.json").is_file()


def test_analyze_b1_detects_ceiling(tmp_path):
    seeds = list(range(200000, 200020))
    _write_records(tmp_path, seeds, _paired_outcomes(seeds, all_success=True))
    result = analyze_b1(tmp_path, n_bootstrap=100, phase="pilot", expected_horizons=HORIZONS)
    assert result["ceiling_effect"] is True
    assert result["floor_effect"] is False


def test_analyze_b1_rejects_unpaired_initial_states(tmp_path):
    seeds = list(range(200000, 200020))
    path = _write_records(tmp_path, seeds, _paired_outcomes(seeds))
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    rows[1]["initial_state_sha256"] = "different_hash"
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="pairing failed"):
        analyze_b1(tmp_path, n_bootstrap=100, phase="pilot", expected_horizons=HORIZONS)


def test_analyze_b1_requires_reference_horizon(tmp_path):
    seeds = list(range(200000, 200020))
    _write_records(tmp_path, seeds, _paired_outcomes(seeds))
    with pytest.raises(ValueError, match="reference"):
        analyze_b1(tmp_path, n_bootstrap=100, phase="pilot", reference=16)


def test_analyze_b1_rejects_wrong_horizon_set(tmp_path):
    seeds = list(range(200000, 200020))
    _write_records(tmp_path, seeds, _paired_outcomes(seeds))
    with pytest.raises(ValueError, match="amended protocol"):
        analyze_b1(tmp_path, n_bootstrap=100, phase="pilot", expected_horizons=[1, 2, 4, 8, 16])
