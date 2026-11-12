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
EXPECTED_RANGES = {"pilot": (200000, 20), "full": (200020, 100)}


def _outcomes(seeds, all_success=False):
    result = {}
    for seed in seeds:
        result[seed] = {}
        for horizon in HORIZONS:
            result[seed][horizon] = True if all_success else ((seed * 7 + horizon) % 10) < 7
    return result


def _write(run_dir, phase="pilot", start=200000, count=20, all_success=False,
           manifest_overrides=None):
    seeds = list(range(start, start + count))
    outcomes = _outcomes(seeds, all_success=all_success)
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
    records_path = run_dir / "b1_{}_episodes.jsonl".format(phase)
    records_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    manifest = {
        "b1_phase": phase,
        "episodes": count,
        "seed_start": start,
        "seed_end": start + count - 1,
        "horizons": HORIZONS,
        "reference_horizon": 8,
        "records_file": records_path.name,
    }
    manifest.update(manifest_overrides or {})
    (run_dir / "b1_{}_run.json".format(phase)).write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    return records_path, rows


def _rewrite(path, rows):
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def _analyze(run_dir, phase="pilot", **kwargs):
    return analyze_b1(
        run_dir,
        n_bootstrap=100,
        phase=phase,
        reference=8,
        expected_horizons=HORIZONS,
        expected_phase_ranges=EXPECTED_RANGES,
        **kwargs
    )


# --- statistical helpers -------------------------------------------------

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


# --- normal completeness -------------------------------------------------

def test_pilot_20x5_complete_analysis_passes(tmp_path):
    _write(tmp_path, phase="pilot", start=200000, count=20)
    result = _analyze(tmp_path, phase="pilot")
    assert result["n_initial_states"] == 20
    assert result["episodes"] == 20
    assert result["seed_start"] == 200000
    assert result["seed_end"] == 200019
    assert result["completeness_verified"] is True
    assert result["manifest_file"] == "b1_pilot_run.json"
    assert result["horizons"] == HORIZONS
    for horizon in HORIZONS:
        row = result["success_rate"][str(horizon)]
        assert row["n"] == 20
        assert row["wilson_95ci_low"] <= row["rate"] <= row["wilson_95ci_high"]
    assert 0.0 <= result["overall_cochran_q"]["p_value"] <= 1.0
    assert set(result["paired_risk_difference_vs_h8"]) == {"1", "2", "4", "15"}


def test_full_100x5_complete_analysis_passes(tmp_path):
    _write(tmp_path, phase="full", start=200020, count=100)
    result = _analyze(tmp_path, phase="full")
    assert result["n_initial_states"] == 100
    assert result["episodes"] == 100
    assert result["seed_start"] == 200020
    assert result["seed_end"] == 200119
    assert sum(row["n"] for row in result["success_rate"].values()) == 500


def test_ceiling_detection(tmp_path):
    _write(tmp_path, phase="pilot", start=200000, count=20, all_success=True)
    result = _analyze(tmp_path, phase="pilot")
    assert result["ceiling_effect"] is True
    assert result["floor_effect"] is False


# --- seed / horizon / record completeness --------------------------------

def test_missing_seed_fails(tmp_path):
    path, rows = _write(tmp_path, phase="pilot", start=200000, count=20)
    _rewrite(path, [row for row in rows if row["seed"] != 200005])
    with pytest.raises(ValueError, match="coverage mismatch"):
        _analyze(tmp_path, phase="pilot")


def test_missing_horizon_column_fails(tmp_path):
    path, rows = _write(tmp_path, phase="pilot", start=200000, count=20)
    _rewrite(path, [row for row in rows if row["horizon"] != 4])
    with pytest.raises(ValueError, match="do not match"):
        _analyze(tmp_path, phase="pilot")


def test_missing_single_record_fails(tmp_path):
    path, rows = _write(tmp_path, phase="pilot", start=200000, count=20)
    _rewrite(path, rows[:-1])
    with pytest.raises(ValueError, match="record count"):
        _analyze(tmp_path, phase="pilot")


def test_duplicate_record_fails(tmp_path):
    path, rows = _write(tmp_path, phase="pilot", start=200000, count=20)
    _rewrite(path, rows + [rows[0]])
    with pytest.raises(ValueError, match="Duplicate"):
        _analyze(tmp_path, phase="pilot")


def test_seed_outside_range_fails(tmp_path):
    path, rows = _write(tmp_path, phase="pilot", start=200000, count=20)
    extra = dict(rows[0])
    extra["seed"] = 200020
    extra["initial_state_sha256"] = "hash_200020"
    _rewrite(path, rows + [extra])
    with pytest.raises(ValueError, match="coverage mismatch"):
        _analyze(tmp_path, phase="pilot")


def test_unverified_pairing_flag_fails(tmp_path):
    path, rows = _write(tmp_path, phase="pilot", start=200000, count=20)
    rows[0]["paired_initial_state_verified"] = False
    _rewrite(path, rows)
    with pytest.raises(ValueError, match="pairing failed"):
        _analyze(tmp_path, phase="pilot")


def test_inconsistent_initial_hash_fails(tmp_path):
    path, rows = _write(tmp_path, phase="pilot", start=200000, count=20)
    rows[1]["initial_state_sha256"] = "different_hash"
    _rewrite(path, rows)
    with pytest.raises(ValueError, match="pairing failed"):
        _analyze(tmp_path, phase="pilot")


def test_wrong_phase_field_fails(tmp_path):
    path, rows = _write(tmp_path, phase="pilot", start=200000, count=20)
    rows[0]["b1_phase"] = "full"
    _rewrite(path, rows)
    with pytest.raises(ValueError, match="phase values"):
        _analyze(tmp_path, phase="pilot")


# --- manifest validation -------------------------------------------------

def test_missing_manifest_fails(tmp_path):
    path, rows = _write(tmp_path, phase="pilot", start=200000, count=20)
    (tmp_path / "b1_pilot_run.json").unlink()
    with pytest.raises(FileNotFoundError, match="manifest"):
        _analyze(tmp_path, phase="pilot")


def test_manifest_episode_count_mismatch_fails(tmp_path):
    _write(tmp_path, phase="pilot", start=200000, count=20,
           manifest_overrides={"episodes": 19})
    with pytest.raises(ValueError, match="manifest episodes"):
        _analyze(tmp_path, phase="pilot")


def test_manifest_seed_start_mismatch_fails(tmp_path):
    _write(tmp_path, phase="pilot", start=200000, count=20,
           manifest_overrides={"seed_start": 200001})
    with pytest.raises(ValueError, match="manifest seed_start"):
        _analyze(tmp_path, phase="pilot")


def test_manifest_phase_mismatch_fails(tmp_path):
    _write(tmp_path, phase="pilot", start=200000, count=20,
           manifest_overrides={"b1_phase": "full"})
    with pytest.raises(ValueError, match="manifest phase"):
        _analyze(tmp_path, phase="pilot")


def test_manifest_horizon_mismatch_fails(tmp_path):
    _write(tmp_path, phase="pilot", start=200000, count=20,
           manifest_overrides={"horizons": [1, 2, 4, 8, 16]})
    with pytest.raises(ValueError, match="manifest horizons"):
        _analyze(tmp_path, phase="pilot")


def test_full_must_not_reuse_pilot_seed_start(tmp_path):
    # A Full run starting at 200000 would overlap Pilot; the configured Full
    # range is 200020-200119, so the manifest is inconsistent.
    _write(tmp_path, phase="full", start=200000, count=100)
    with pytest.raises(ValueError, match="manifest seed_start"):
        _analyze(tmp_path, phase="full")


# --- phase selection -----------------------------------------------------

def test_both_phases_present_requires_explicit_phase(tmp_path):
    _write(tmp_path, phase="pilot", start=200000, count=20)
    _write(tmp_path, phase="full", start=200020, count=100)
    with pytest.raises(ValueError, match="specify --b1-phase"):
        analyze_b1(
            tmp_path,
            n_bootstrap=100,
            phase=None,
            reference=8,
            expected_horizons=HORIZONS,
            expected_phase_ranges=EXPECTED_RANGES,
        )


def test_single_full_phase_can_be_auto_selected(tmp_path):
    _write(tmp_path, phase="full", start=200020, count=100)
    result = analyze_b1(
        tmp_path,
        n_bootstrap=100,
        phase=None,
        reference=8,
        expected_horizons=HORIZONS,
        expected_phase_ranges=EXPECTED_RANGES,
    )
    assert result["phase"] == "full"
    assert result["n_initial_states"] == 100
