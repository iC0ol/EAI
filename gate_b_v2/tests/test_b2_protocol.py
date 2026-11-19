from collections import defaultdict

import numpy as np
import pytest

from b2_test_data import RUNTIME, branch_record, state_record

from gate_b_v2.b2_protocol import (
    assert_state_seed_in_split,
    branch_order,
    branch_order_seed,
    discovery_confirmation_seed_ranges,
    repeat_seed,
    seed_blocks,
    seeds_for_block,
    select_candidate_indices,
    selection_metadata,
    source_policy_seed,
    state_id,
    validate_b2_records,
    validate_state_manifest,
)


def _config():
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
            "bootstrap_samples": 5000,
            "discovery": {
                "primary_seed_start": 300000,
                "primary_seed_count": 100,
                "extension_seed_start": 300100,
                "extension_seed_count": 100,
                "selection_seed": 20261116,
            },
            "confirmation": {
                "primary_seed_start": 310000,
                "primary_seed_count": 100,
                "extension_seed_start": 310100,
                "extension_seed_count": 100,
                "selection_seed": 20261117,
            },
        }
    }


def _states(count=30, split="discovery", start=300000):
    return [
        state_record(split, start + index, 100 + index, -0.01 + 0.001 * index)
        for index in range(count)
    ]


def _records(states, config):
    return [
        branch_record(config, state, repeat, horizon)
        for state in states
        for repeat in range(config["b2"]["repeats_per_state_horizon"])
        for horizon in branch_order(config, state["source_seed"], repeat)
    ]


def test_frozen_seed_pools_are_exact_and_disjoint():
    config = _config()
    primary, extension = seed_blocks(config, "discovery")
    assert primary == (300000, 100)
    assert extension == (300100, 100)
    assert seeds_for_block(primary)[0] == 300000
    assert seeds_for_block(primary)[-1] == 300099
    ranges = discovery_confirmation_seed_ranges(config)
    assert ranges["discovery"] == (300000, 300199)
    assert ranges["confirmation"] == (310000, 310199)
    assert ranges["discovery"][1] < ranges["confirmation"][0]
    with pytest.raises(ValueError, match="outside the frozen"):
        assert_state_seed_in_split(config, "discovery", 310000)


def test_state_ids_and_source_policy_seed_are_deterministic():
    config = _config()
    assert state_id("discovery", 300000) == "disc_300000"
    assert state_id("confirmation", 310000) == "conf_310000"
    assert source_policy_seed(config, 300000) == 1200000
    assert source_policy_seed(config, 310000) == 1210000


def test_candidate_selection_is_reproducible_and_split_specific():
    config = _config()
    candidates = [
        {"source_seed": 300000 + index, "state_id": "disc_{}".format(300000 + index)}
        for index in range(45)
    ]
    first = select_candidate_indices(candidates, 20261116, 30)
    second = select_candidate_indices(candidates, 20261116, 30)
    assert first == second
    assert len(first) == 30
    assert len(set(first)) == 30
    metadata = selection_metadata(candidates, "discovery", config)
    assert metadata["selection_seed"] == 20261116
    assert metadata["selected_candidate_indices"] == first
    assert len(metadata["selected_source_seeds"]) == 30
    # Confirmation uses a different frozen seed.
    other = select_candidate_indices(candidates, 20261117, 30)
    assert first != other


def test_branch_order_is_randomized_reproducible_and_complete():
    config = _config()
    orders = {
        tuple(branch_order(config, 300000 + index, 0))
        for index in range(20)
    }
    assert len(orders) > 1
    assert all(sorted(order) == [1, 2, 4, 8, 15] for order in orders)
    assert branch_order(config, 300000, 0) == branch_order(config, 300000, 0)
    assert branch_order_seed(config, 300000, 0) == 20261118 + 300000 * 5
    assert repeat_seed(config, 300000, 0) == 1000000 + 300000 * 17


def test_complete_b2_records_pass_strict_gate():
    config = _config()
    states = _states()
    records = _records(states, config)
    assert len(records) == 30 * 5 * 3
    summary = validate_b2_records(records, states, "discovery", config, RUNTIME)
    assert summary["completeness_verified"] is True
    assert summary["n_branch_records"] == 450


def test_missing_duplicate_extra_and_mixed_split_are_rejected():
    config = _config()
    states = _states()
    records = _records(states, config)

    with pytest.raises(ValueError, match="missing"):
        validate_b2_records(records[:-1], states, "discovery", config, RUNTIME)

    duplicate = records + [dict(records[0])]
    with pytest.raises(ValueError, match="Duplicate"):
        validate_b2_records(duplicate, states, "discovery", config, RUNTIME)

    extra = records + [dict(records[0], horizon=2, repeat_index=0,
                             randomized_order_index=4)]
    with pytest.raises(ValueError, match="Duplicate|missing|extra"):
        validate_b2_records(extra, states, "discovery", config, RUNTIME)

    mixed = [dict(row) for row in records]
    mixed[0]["split"] = "confirmation"
    with pytest.raises(ValueError, match="not from split"):
        validate_b2_records(mixed, states, "discovery", config, RUNTIME)


def test_state_manifest_requires_exactly_thirty_and_split_isolation():
    config = _config()
    states = _states()
    validate_state_manifest(states, "discovery", config)
    with pytest.raises(ValueError, match="exactly 30"):
        validate_state_manifest(states[:-1], "discovery", config)
    wrong = [dict(item) for item in states]
    wrong[0]["split"] = "confirmation"
    with pytest.raises(ValueError, match="belongs to split"):
        validate_state_manifest(wrong, "discovery", config)


def test_common_repeat_seed_is_shared_across_horizons():
    config = _config()
    states = _states()
    records = _records(states, config)
    grouped = defaultdict(set)
    for row in records:
        grouped[(row["state_id"], row["repeat_index"])].add(row["repeat_seed"])
    assert all(len(values) == 1 for values in grouped.values())
    assert len({next(iter(values)) for values in grouped.values()}) > 1


@pytest.mark.parametrize(("field", "invalid", "message"), [
    ("success_error", "predicate failed", "success_error"),
    ("success", 0, "boolean success"),
    ("max_reward", float("nan"), "Non-finite"),
    ("wall_time_s", float("inf"), "Non-finite"),
    ("policy_noise_seed_schedule", [0, float("-inf")], "Non-finite"),
    ("termination", "simulation_error", "termination"),
    ("steps_from_episode_start", 501, "step counts"),
    ("steps_from_episode_start", 499.0, "integer"),
    ("steps_after_branch", 0, "step counts"),
    ("source_step", -1, "step counts"),
    ("policy_calls_after_branch", 1, "policy call count"),
    ("policy_calls_after_branch", False, "integer"),
    ("policy_reset_verified", False, "policy reset"),
    ("snapshot_sha256", "incorrect", "snapshot SHA256"),
    ("checkpoint_sha256", "incorrect", "environment mismatch"),
    ("clearance_x_positive_m", 4.2, "inconsistent geometry"),
    ("randomized_order_index", 7, "horizon order"),
])
def test_abnormal_rows_are_rejected_from_an_otherwise_complete_split(field, invalid, message):
    config = _config()
    states = _states()
    records = _records(states, config)
    records[0][field] = invalid
    with pytest.raises(ValueError, match=message):
        validate_b2_records(records, states, "discovery", config, RUNTIME)


def test_missing_statistics_field_is_rejected():
    config = _config()
    states = _states()
    records = _records(states, config)
    records[0].pop("wall_time_s")
    with pytest.raises(ValueError, match="wall_time_s"):
        validate_b2_records(records, states, "discovery", config, RUNTIME)


def test_environment_termination_and_max_steps_counts_must_agree():
    config = _config()
    states = _states()
    records = _records(states, config)
    row = records[0]
    row["steps_from_episode_start"] = row["source_step"] + 1
    row["steps_after_branch"] = 1
    row["policy_calls_after_branch"] = 1
    row["policy_noise_seed_schedule"] = row["policy_noise_seed_schedule"][:1]
    with pytest.raises(ValueError, match="termination"):
        validate_b2_records(records, states, "discovery", config, RUNTIME)
    row["termination"] = "environment_done"
    assert validate_b2_records(records, states, "discovery", config, RUNTIME)["n_branch_records"] == 450
