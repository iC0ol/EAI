"""Pure B2 v1.1 protocol helpers: seeds, selection, branch order, completeness.

This module is deliberately free of simulator imports so every rule can be
unit-tested deterministically.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

from .locks import B2_LOCKED_CONFIG_VALUES


SPLITS = ("discovery", "confirmation")


def split_config(config: Mapping[str, Any], split: str) -> Mapping[str, Any]:
    if split not in SPLITS:
        raise ValueError("split must be one of {}, got {!r}".format(SPLITS, split))
    return config["b2"][split]


def seed_blocks(config: Mapping[str, Any], split: str) -> Tuple[Tuple[int, int], Tuple[int, int]]:
    """Return ((primary_start, primary_count), (extension_start, extension_count))."""
    section = split_config(config, split)
    primary = (int(section["primary_seed_start"]), int(section["primary_seed_count"]))
    extension = (int(section["extension_seed_start"]), int(section["extension_seed_count"]))
    if primary[1] <= 0 or extension[1] <= 0:
        raise ValueError("Seed block counts must be positive")
    if not (primary[0] + primary[1] - 1 < extension[0]):
        raise ValueError("Extension seed block must follow the primary block")
    return primary, extension


def seeds_for_block(block: Tuple[int, int]) -> List[int]:
    start, count = block
    return list(range(int(start), int(start) + int(count)))


def discovery_confirmation_seed_ranges(config: Mapping[str, Any]) -> Dict[str, Tuple[int, int]]:
    ranges: Dict[str, Tuple[int, int]] = {}
    for split in SPLITS:
        primary, extension = seed_blocks(config, split)
        ranges[split] = (primary[0], extension[0] + extension[1] - 1)
    if not (ranges["discovery"][1] < ranges["confirmation"][0]):
        raise ValueError("Discovery and confirmation seed ranges overlap")
    return ranges


def assert_state_seed_in_split(config: Mapping[str, Any], split: str, source_seed: int) -> None:
    start, end = discovery_confirmation_seed_ranges(config)[split]
    if not (int(start) <= int(source_seed) <= int(end)):
        raise ValueError(
            "Source seed {} is outside the frozen {} pool [{}, {}]".format(
                source_seed, split, start, end
            )
        )
    other = "confirmation" if split == "discovery" else "discovery"
    other_start, other_end = discovery_confirmation_seed_ranges(config)[other]
    if other_start <= int(source_seed) <= other_end:
        raise ValueError(
            "Source seed {} appears in both split pools; discovery/confirmation must be disjoint".format(
                source_seed
            )
        )


def selection_seed(config: Mapping[str, Any], split: str) -> int:
    return int(split_config(config, split)["selection_seed"])


def source_policy_seed(config: Mapping[str, Any], source_seed: int) -> int:
    return int(config["b2"]["source_policy_seed_offset"]) + int(source_seed)


def state_id(split: str, source_seed: int) -> str:
    prefix = "disc" if split == "discovery" else "conf"
    return "{}_{:06d}".format(prefix, int(source_seed))


def select_candidate_indices(
    candidates: Sequence[Mapping[str, Any]],
    seed: int,
    count: int,
) -> List[int]:
    """Deterministically select candidate indices.

    Candidate order is the frozen source-seed order (ascending).  The selection
    is a split-specific pseudorandom sample without replacement; the same input
    and seed always produce the same selection.
    """
    values = list(candidates)
    if len(values) < int(count):
        raise ValueError(
            "Cannot select {} states from {} eligible candidates".format(count, len(values))
        )
    seeds = [int(item["source_seed"]) for item in values]
    if len(set(seeds)) != len(seeds):
        raise ValueError("Candidate list contains duplicate source seeds")
    rng = np.random.default_rng(int(seed))
    chosen = rng.choice(len(values), size=int(count), replace=False)
    return sorted(int(index) for index in chosen)


def selection_metadata(candidates: Sequence[Mapping[str, Any]], split: str, config: Mapping[str, Any]) -> Dict[str, Any]:
    seed = selection_seed(config, split)
    count = int(config["b2"]["selected_states"])
    indices = select_candidate_indices(candidates, seed, count)
    return {
        "algorithm": "numpy.random.default_rng(selection_seed).choice(n, size=count, replace=False)",
        "candidate_order": "ascending source_seed",
        "selection_seed": seed,
        "requested_count": count,
        "eligible_count": len(candidates),
        "selected_candidate_indices": indices,
        "selected_source_seeds": [int(candidates[index]["source_seed"]) for index in indices],
    }


def branch_order_seed(config: Mapping[str, Any], source_seed: int, repeat_index: int) -> int:
    b2 = config["b2"]
    return int(b2["branch_order_seed_base"]) + int(source_seed) * int(b2["branch_order_seed_stride"]) + int(repeat_index)


def branch_order(config: Mapping[str, Any], source_seed: int, repeat_index: int) -> List[int]:
    seed = branch_order_seed(config, source_seed, repeat_index)
    order = np.random.default_rng(seed).permutation(
        np.asarray(config["b2"]["horizons"], dtype=np.int64)
    )
    return [int(value) for value in order]


def repeat_seed(config: Mapping[str, Any], source_seed: int, repeat_index: int) -> int:
    b2 = config["b2"]
    return int(b2["repeat_seed_base"]) + int(source_seed) * int(b2["repeat_seed_stride"]) + int(repeat_index)


def policy_noise_schedule(base_seed: int, n_calls: int) -> List[int]:
    from .core import policy_noise_seed

    return [int(policy_noise_seed(base_seed, index)) for index in range(int(n_calls))]


def expected_branch_keys(
    states: Sequence[Mapping[str, Any]],
    config: Mapping[str, Any],
) -> set:
    horizons = [int(x) for x in config["b2"]["horizons"]]
    repeats = int(config["b2"]["repeats_per_state_horizon"])
    return {
        (str(state["state_id"]), int(horizon), int(repeat))
        for state in states
        for horizon in horizons
        for repeat in range(repeats)
    }


def validate_state_manifest(
    states: Sequence[Mapping[str, Any]],
    split: str,
    config: Mapping[str, Any],
) -> None:
    if split not in SPLITS:
        raise ValueError("Invalid split {!r}".format(split))
    expected_count = int(config["b2"]["selected_states"])
    if len(states) != expected_count:
        raise ValueError(
            "B2 {} state manifest has {} states; exactly {} are required".format(
                split, len(states), expected_count
            )
        )
    ids = [str(item["state_id"]) for item in states]
    seeds = [int(item["source_seed"]) for item in states]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate state_id in the {} manifest".format(split))
    if len(set(seeds)) != len(seeds):
        raise ValueError("Duplicate source_seed in the {} manifest".format(split))
    for item in states:
        if item.get("split") != split:
            raise ValueError(
                "State {} belongs to split {!r}, expected {!r}".format(
                    item.get("state_id"), item.get("split"), split
                )
            )
        assert_state_seed_in_split(config, split, int(item["source_seed"]))
        if int(item.get("source_horizon", -1)) != int(config["b2"]["source_horizon"]):
            raise ValueError("State {} has the wrong source horizon".format(item.get("state_id")))
        if str(item.get("stage_gate_version")) != "B2_GEOMETRY_GATE_V1_20261116":
            raise ValueError("State {} has an unexpected stage gate version".format(item.get("state_id")))
        for key in (
            "clearance_m", "z_gap_m", "dx_m", "dy_m", "d_xy_m", "relative_yaw_rad",
            "t_nut_m", "r_hole_m", "r_peg_m", "snapshot_file", "snapshot_sha256",
        ):
            if key not in item:
                raise ValueError("State {} is missing required field {!r}".format(item.get("state_id"), key))


def validate_candidate_selection(
    candidates: Sequence[Mapping[str, Any]],
    selected_states: Sequence[Mapping[str, Any]],
    split: str,
    config: Mapping[str, Any],
) -> None:
    metadata = selection_metadata(candidates, split, config)
    selected_seeds = {int(item["source_seed"]) for item in selected_states}
    expected_seeds = set(metadata["selected_source_seeds"])
    if selected_seeds != expected_seeds:
        raise ValueError(
            "Selected states do not match the deterministic selection for seed {}".format(
                metadata["selection_seed"]
            )
        )


def validate_b2_records(
    records: Sequence[Mapping[str, Any]],
    state_manifest: Sequence[Mapping[str, Any]],
    split: str,
    config: Mapping[str, Any],
    runtime_manifest: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Strict 30 x 5 x 3 completeness and isolation gate."""
    validate_state_manifest(state_manifest, split, config)
    horizons = [int(x) for x in config["b2"]["horizons"]]
    repeats = int(config["b2"]["repeats_per_state_horizon"])
    states_by_id = {str(item["state_id"]): item for item in state_manifest}
    expected_keys = expected_branch_keys(state_manifest, config)

    actual_keys: List[Tuple[str, int, int]] = []
    seen = set()
    duplicate_keys = []
    for row in records:
        key = (str(row["state_id"]), int(row["horizon"]), int(row["repeat_index"]))
        actual_keys.append(key)
        if key in seen:
            duplicate_keys.append(key)
        seen.add(key)
        if row.get("split") != split:
            raise ValueError("Branch record {} is not from split {!r}".format(key, split))
        state = states_by_id.get(str(row["state_id"]))
        if state is None:
            raise ValueError("Branch record {} refers to an unknown state".format(key))
        if int(row["source_seed"]) != int(state["source_seed"]):
            raise ValueError("Branch record {} has a mismatched source seed".format(key))
        if int(row["horizon"]) not in horizons:
            raise ValueError("Branch record {} has an illegal horizon".format(key))
        if not (0 <= int(row["repeat_index"]) < repeats):
            raise ValueError("Branch record {} has an illegal repeat index".format(key))
        if str(row.get("snapshot_sha256")) != str(state["snapshot_sha256"]):
            raise ValueError("Branch record {} has a mismatched snapshot SHA256".format(key))
        if bool(row.get("preflight", False)):
            raise ValueError("Branch record {} is marked PREFLIGHT".format(key))
        for geometry_key in (
            "clearance_m", "z_gap_m", "dx_m", "dy_m", "d_xy_m", "relative_yaw_rad",
        ):
            if geometry_key in row and geometry_key in state:
                if abs(float(row[geometry_key]) - float(state[geometry_key])) > 1e-9:
                    raise ValueError(
                        "Branch record {} has a geometry value inconsistent with the "
                        "immutable state manifest for {!r}".format(key, geometry_key)
                    )
        if int(row.get("continuation_horizon", -1)) != int(config["b2"]["continuation_horizon"]):
            raise ValueError("Branch record {} has the wrong continuation horizon".format(key))
        expected_order_seed = branch_order_seed(config, int(state["source_seed"]), int(row["repeat_index"]))
        if int(row.get("branch_order_seed", -1)) != expected_order_seed:
            raise ValueError("Branch record {} has the wrong branch order seed".format(key))
        expected_repeat_seed = repeat_seed(config, int(state["source_seed"]), int(row["repeat_index"]))
        if int(row.get("repeat_seed", -1)) != expected_repeat_seed:
            raise ValueError("Branch record {} has the wrong repeat seed".format(key))
        if runtime_manifest is not None:
            from .locks import B2_RECORD_ENVIRONMENT_KEYS, _b2_environment_value

            for field in B2_RECORD_ENVIRONMENT_KEYS:
                if field in runtime_manifest and row.get(field) != _b2_environment_value(runtime_manifest, field):
                    raise ValueError(
                        "Branch record {} environment mismatch for {!r}".format(key, field)
                    )

    if duplicate_keys:
        raise ValueError("Duplicate B2 branch rows: {}".format(duplicate_keys[:5]))
    actual_set = set(actual_keys)
    missing = sorted(expected_keys - actual_set)
    extra = sorted(actual_set - expected_keys)
    if missing or extra:
        raise ValueError(
            "B2 {} branch completeness failed: missing={} extra={}".format(split, missing[:5], extra[:5])
        )
    expected_count = len(state_manifest) * len(horizons) * repeats
    if len(records) != expected_count:
        raise ValueError(
            "B2 {} branch count {} != expected {}".format(split, len(records), expected_count)
        )

    # Verify the realized horizon order within each state x repeat.
    order_by_group: Dict[Tuple[str, int], List[Mapping[str, Any]]] = defaultdict(list)
    for row in records:
        order_by_group[(str(row["state_id"]), int(row["repeat_index"]))].append(row)
    for key, rows in order_by_group.items():
        order = [int(row["horizon"]) for row in sorted(rows, key=lambda item: int(item["randomized_order_index"]))]
        expected_order = branch_order(config, int(states_by_id[key[0]]["source_seed"]), key[1])
        if order != expected_order:
            raise ValueError(
                "Realized horizon order {} != deterministic order {} for state/repeat {}".format(
                    order, expected_order, key
                )
            )
        if sorted(int(row["randomized_order_index"]) for row in rows) != list(range(len(horizons))):
            raise ValueError("randomized_order_index is not a permutation for state/repeat {}".format(key))
        if len({int(row["repeat_seed"]) for row in rows}) != 1:
            raise ValueError("Common repeat seed is not shared across horizons for state/repeat {}".format(key))
        schedules = [list(row.get("policy_noise_seed_schedule", [])) for row in rows]
        common_length = min((len(item) for item in schedules), default=0)
        for call_index in range(common_length):
            if len({int(item[call_index]) for item in schedules}) != 1:
                raise ValueError(
                    "Common policy-noise seed schedule diverges at call index {} "
                    "for state/repeat {}".format(call_index, key)
                )

    return {
        "split": split,
        "n_states": len(state_manifest),
        "horizons": horizons,
        "repeats_per_state_horizon": repeats,
        "n_branch_records": len(records),
        "expected_branch_records": expected_count,
        "unique_keys": len(actual_set),
        "duplicates": 0,
        "missing": 0,
        "extra": 0,
        "completeness_verified": True,
        "split_isolation_verified": True,
        "snapshot_hashes_verified": True,
        "horizon_order_verified": True,
        "common_repeat_seed_verified": True,
    }
