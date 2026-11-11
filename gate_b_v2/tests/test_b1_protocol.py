from pathlib import Path

import pytest
import yaml

from gate_b_v2.core import (
    available_future_actions,
    b1_records_filename,
    b1_run_filename,
    ensure_new_records_path,
    validate_horizons,
)

ROOT = Path(__file__).resolve().parents[1]


def _config():
    return yaml.safe_load((ROOT / "configs" / "gate_b.yaml").read_text(encoding="utf-8"))


def test_amended_config_has_h15_and_independent_b1_seeds():
    evaluation = _config()["evaluation"]
    assert evaluation["horizons"] == [1, 2, 4, 8, 15]
    assert evaluation["seed_start"] == 100000
    assert evaluation["b1_seed_start"] == 200000
    assert evaluation["b1_seed_start"] != evaluation["seed_start"]
    assert evaluation["b1_pilot_episodes"] == 20
    assert evaluation["b1_full_episodes"] == 100
    assert evaluation["b1_reference_horizon"] == 8
    assert evaluation["b1_practical_diff"] == 0.08


def test_h15_is_accepted_and_h16_is_rejected():
    assert available_future_actions(16, 2) == 15
    assert validate_horizons([1, 2, 4, 8, 15], 16, 2) == [1, 2, 4, 8, 15]
    with pytest.raises(ValueError, match="Do not silently truncate"):
        validate_horizons([1, 2, 4, 8, 16], 16, 2)


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
    ensure_new_records_path(path)  # missing is fine
    path.write_text("", encoding="utf-8")
    ensure_new_records_path(path)  # empty file is fine
    path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="Refusing to append"):
        ensure_new_records_path(path)
