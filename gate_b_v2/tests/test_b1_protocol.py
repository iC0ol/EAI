import inspect
from pathlib import Path

import pytest
import yaml

from gate_b_v2.cli import build_parser
from gate_b_v2.core import (
    available_future_actions,
    b1_records_filename,
    b1_run_filename,
    ensure_new_records_path,
    validate_horizons,
    validate_seed_ranges,
)
from gate_b_v2.runner import GateBExperiment

ROOT = Path(__file__).resolve().parents[1]


def _config():
    return yaml.safe_load((ROOT / "configs" / "gate_b.yaml").read_text(encoding="utf-8"))


def test_amended_config_has_disjoint_b1_seed_ranges():
    evaluation = _config()["evaluation"]
    assert evaluation["horizons"] == [1, 2, 4, 8, 15]
    assert evaluation["seed_start"] == 100000
    assert evaluation["b0_baseline_episodes"] == 100
    assert evaluation["b1_pilot_seed_start"] == 200000
    assert evaluation["b1_full_seed_start"] == 200020
    assert evaluation["b1_pilot_episodes"] == 20
    assert evaluation["b1_full_episodes"] == 100
    assert evaluation["b1_reference_horizon"] == 8
    assert evaluation["b1_practical_diff"] == 0.08


def test_h15_is_accepted_and_h16_is_rejected():
    assert available_future_actions(16, 2) == 15
    assert validate_horizons([1, 2, 4, 8, 15], 16, 2) == [1, 2, 4, 8, 15]
    with pytest.raises(ValueError, match="Do not silently truncate"):
        validate_horizons([1, 2, 4, 8, 16], 16, 2)


def test_seed_ranges_are_disjoint_and_cover_expected_intervals():
    ranges = validate_seed_ranges({
        "B0": (100000, 100),
        "B1_pilot": (200000, 20),
        "B1_full": (200020, 100),
    })
    assert ranges["B0"] == (100000, 100099)
    assert ranges["B1_pilot"] == (200000, 200019)
    assert ranges["B1_full"] == (200020, 200119)


def test_seed_range_overlap_is_detected_beyond_start_values():
    with pytest.raises(RuntimeError, match="Seed ranges overlap"):
        validate_seed_ranges({
            "B1_pilot": (200000, 20),
            "B1_full": (200010, 100),
        })
    with pytest.raises(RuntimeError, match="Seed ranges overlap"):
        validate_seed_ranges({
            "B1_pilot": (200000, 20),
            "B1_full": (200000, 100),
        })


def test_pilot_and_full_records_are_separate_files():
    assert b1_records_filename("pilot") == "b1_pilot_episodes.jsonl"
    assert b1_records_filename("full") == "b1_full_episodes.jsonl"
    assert b1_run_filename("pilot") == "b1_pilot_run.json"
    assert b1_run_filename("full") == "b1_full_run.json"
    with pytest.raises(ValueError):
        b1_records_filename("validation")
    with pytest.raises(ValueError):
        b1_run_filename("validation")


def test_existing_records_are_not_appended_to(tmp_path):
    path = tmp_path / "b1_pilot_episodes.jsonl"
    ensure_new_records_path(path)
    path.write_text("", encoding="utf-8")
    ensure_new_records_path(path)
    path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="Refusing to append"):
        ensure_new_records_path(path)


def test_b1_run_signature_has_no_custom_count_or_b2_collection():
    signature = inspect.signature(GateBExperiment.run_b1)
    assert "phase" in signature.parameters
    assert "episodes" not in signature.parameters
    assert "collect_b2_states" not in signature.parameters


def test_b1_cli_rejects_custom_count_and_b2_collection():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["b1", "--episodes", "5"])
    with pytest.raises(SystemExit):
        parser.parse_args(["b1", "--collect-b2-states"])
    args = parser.parse_args(["b1", "--b1-phase", "full"])
    assert args.b1_phase == "full"
