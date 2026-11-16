from collections import defaultdict

import numpy as np
import pytest

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
    result = []
    for index in range(count):
        seed = start + index
        result.append({
            "state_id": state_id(split, seed),
            "split": split,
            "source_seed": seed,
            "source_step": 100 + index,
            "source_horizon": 8,
            "stage_gate_version": "B2_GEOMETRY_GATE_V1_20261116",
            "clearance_m": -0.01 + 0.001 * index,
            "z_gap_m": 0.005,
            "dx_m": 0.0,
            "dy_m": 0.0,
            "d_xy_m": 0.01,
            "relative_yaw_rad": 0.0,
            "t_nut_m": 0.02,
            "r_hole_m": 0.032,
            "r_peg_m": 0.022,
            "snapshot_file": "snapshots/{}.pkl.gz".format(
                state_id(split, seed)
            ),
            "snapshot_sha256": "sha-{}".format(seed),
        })
    return result


def _records(states, config):
    records = []
    for state in states:
        for repeat_index in range(int(config["b2"]["repeats_per_state_horizon"])):
            order = branch_order(config, int(state["source_seed"]), repeat_index)
            order_seed = branch_order_seed(config, int(state["source_seed"]), repeat_index)
            common_repeat_seed = repeat_seed(config, int(state["source_seed"]), repeat_index)
            for order_index, horizon in enumerate(order):
                records.append({
                    "split": state["split"],
                    "state_id": state["state_id"],
                    "source_seed": state["source_seed"],
                    "horizon": horizon,
                    "repeat_index": repeat_index,
                    "repeat_seed": common_repeat_seed,
                    "branch_order_seed": order_seed,
                    "randomized_order_index": order_index,
                    "continuation_horizon": 15,
                    "preflight": False,
                    "snapshot_sha256": state["snapshot_sha256"],
                    "clearance_m": state["clearance_m"],
                    "z_gap_m": state["z_gap_m"],
                    "dx_m": state["dx_m"],
                    "dy_m": state["dy_m"],
                    "d_xy_m": state["d_xy_m"],
                    "relative_yaw_rad": state["relative_yaw_rad"],
                    "policy_noise_seed_schedule": [1000 + call for call in range(3)],
                })
    return records


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
    summary = validate_b2_records(records, states, "discovery", config)
    assert summary["completeness_verified"] is True
    assert summary["n_branch_records"] == 450


def test_missing_duplicate_extra_and_mixed_split_are_rejected():
    config = _config()
    states = _states()
    records = _records(states, config)

    with pytest.raises(ValueError, match="missing"):
        validate_b2_records(records[:-1], states, "discovery", config)

    duplicate = records + [dict(records[0])]
    with pytest.raises(ValueError, match="Duplicate"):
        validate_b2_records(duplicate, states, "discovery", config)

    extra = records + [dict(records[0], horizon=2, repeat_index=0,
                             randomized_order_index=4)]
    with pytest.raises(ValueError, match="Duplicate|missing|extra"):
        validate_b2_records(extra, states, "discovery", config)

    mixed = [dict(row) for row in records]
    mixed[0]["split"] = "confirmation"
    with pytest.raises(ValueError, match="not from split"):
        validate_b2_records(mixed, states, "discovery", config)


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
