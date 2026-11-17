"""Pure B2 v1.1 protocol helpers: seeds, selection, branch order, completeness.

This module is deliberately free of simulator imports so every rule can be
unit-tested deterministically.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Mapping, Sequence, Tuple

import numpy as np

from .locks import B2_LOCKED_CONFIG_VALUES, B2_RECORD_ENVIRONMENT_KEYS, _b2_environment_value
from .snapshot import GEOMETRY_LENGTH_FIELDS, SNAPSHOT_SCHEMA_VERSION


SPLITS = ("discovery", "confirmation")
B2_BRANCH_GEOMETRY_FIELDS = GEOMETRY_LENGTH_FIELDS + (
    "relative_yaw_rad", "geometry_fingerprint", "aperture_bar_geom_ids",
)


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
    if len({item.get("snapshot_sha256") for item in states}) != len(states):
        raise ValueError("Duplicate snapshot SHA256 in the {} manifest".format(split))
    for item in states:
        if item.get("split") != split:
            raise ValueError(
                "State {} belongs to split {!r}, expected {!r}".format(
                    item.get("state_id"), item.get("split"), split
                )
            )
        assert_state_seed_in_split(config, split, int(item["source_seed"]))
        if item["state_id"] != state_id(split, item["source_seed"]):
            raise ValueError("State ID disagrees with split and source seed: {}".format(item["state_id"]))
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


def _require_finite(value: Any, field: str) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            _require_finite(item, "{}.{}".format(field, key))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _require_finite(item, "{}[{}]".format(field, index))
    elif isinstance(value, np.ndarray):
        if not np.isfinite(value).all():
            raise ValueError("Non-finite B2 value at {}".format(field))
    elif isinstance(value, (float, np.floating)) and not math.isfinite(value):
        raise ValueError("Non-finite B2 value at {}".format(field))


def _integer(row: Mapping[str, Any], field: str) -> int:
    value = row.get(field)
    if type(value) is not int:
        raise ValueError("B2 record requires an integer {!r}, got {!r}".format(field, value))
    return value


def validate_b2_record(
    row: Mapping[str, Any],
    state: Mapping[str, Any],
    split: str,
    config: Mapping[str, Any],
    runtime_manifest: Mapping[str, Any],
) -> None:
    """Check one branch before it can enter the result stream."""
    if not isinstance(row, Mapping):
        raise ValueError("B2 branch record must be an object")
    _require_finite(row, "branch")
    _require_finite(state, "state")
    horizon = _integer(row, "horizon")
    repeat = _integer(row, "repeat_index")
    key = (state["state_id"], horizon, repeat)
    if row.get("state_id") != state["state_id"]:
        raise ValueError("Branch record {} has a mismatched state ID".format(key))
    if row.get("phase") != "B2" or row.get("preflight") is not False:
        raise ValueError("Branch record {} is not a formal B2 record".format(key))
    if row.get("split") != split or state.get("split") != split:
        raise ValueError("Branch record {} is not from split {!r}".format(key, split))
    source_seed = _integer(row, "source_seed")
    if source_seed != _integer(state, "source_seed"):
        raise ValueError("Branch record {} has a mismatched source seed".format(key))
    if horizon not in config["b2"]["horizons"]:
        raise ValueError("Branch record {} has an illegal horizon".format(key))
    if not 0 <= repeat < config["b2"]["repeats_per_state_horizon"]:
        raise ValueError("Branch record {} has an illegal repeat index".format(key))
    if not row.get("snapshot_sha256") or row["snapshot_sha256"] != state["snapshot_sha256"]:
        raise ValueError("Branch record {} has a mismatched snapshot SHA256".format(key))
    if row.get("snapshot_schema_version") != SNAPSHOT_SCHEMA_VERSION or (
        row["snapshot_schema_version"] != state.get("snapshot_schema_version")
    ):
        raise ValueError("Branch record {} has a mismatched snapshot schema".format(key))
    if row.get("policy_reset_verified") is not True:
        raise ValueError("Branch record {} did not verify policy reset".format(key))
    if "success_error" not in row or row["success_error"] not in (None, ""):
        raise ValueError("Branch record {} has missing or nonempty success_error".format(key))
    for field in ("success", "success_seen"):
        if type(row.get(field)) is not bool:
            raise ValueError("Branch record {} requires boolean {}".format(key, field))
    for field in ("max_reward", "wall_time_s"):
        if type(row.get(field)) not in (float, int):
            raise ValueError("Branch record {} requires numeric {}".format(key, field))
    if row["wall_time_s"] < 0:
        raise ValueError("Branch record {} has a negative wall_time_s".format(key))

    source_step = _integer(row, "source_step")
    steps = _integer(row, "steps_from_episode_start")
    executed_steps = _integer(row, "steps_after_branch")
    max_steps = B2_LOCKED_CONFIG_VALUES["max_steps"]
    if not (
        source_step == _integer(state, "source_step")
        and 1 <= source_step < steps <= max_steps
        and executed_steps == steps - source_step
    ):
        raise ValueError("Branch record {} has illegal episode step counts".format(key))
    termination = row.get("termination")
    if termination not in ("environment_done", "max_steps") or (
        termination == "max_steps" and steps != max_steps
    ):
        raise ValueError("Branch record {} has illegal termination {!r}".format(key, termination))
    continuation = _integer(row, "continuation_horizon")
    if continuation != config["b2"]["continuation_horizon"]:
        raise ValueError("Branch record {} has the wrong continuation horizon".format(key))
    remaining = max(executed_steps - horizon, 0)
    expected_calls = 1 + (remaining + continuation - 1) // continuation
    if _integer(row, "policy_calls_after_branch") != expected_calls:
        raise ValueError("Branch record {} has an illegal policy call count".format(key))

    if _integer(row, "branch_order_seed") != branch_order_seed(config, source_seed, repeat):
        raise ValueError("Branch record {} has the wrong branch order seed".format(key))
    expected_order = branch_order(config, source_seed, repeat)
    order_index = _integer(row, "randomized_order_index")
    if (row.get("horizon_order") != expected_order or not 0 <= order_index < len(expected_order)
            or expected_order[order_index] != horizon):
        raise ValueError("Branch record {} has a mismatched randomized horizon order".format(key))
    expected_seed = repeat_seed(config, source_seed, repeat)
    if _integer(row, "repeat_seed") != expected_seed:
        raise ValueError("Branch record {} has the wrong repeat seed".format(key))
    schedule = row.get("policy_noise_seed_schedule")
    if (not isinstance(schedule, list) or any(type(value) is not int for value in schedule)
            or schedule != policy_noise_schedule(expected_seed, expected_calls)):
        raise ValueError("Branch record {} has a mismatched policy-noise seed schedule".format(key))

    geometry = state["geometry"]
    for field in B2_BRANCH_GEOMETRY_FIELDS:
        if (
            field not in geometry or field not in row or row[field] != geometry[field]
            or (field in state and state[field] != geometry[field])
        ):
            raise ValueError("Branch record {} has inconsistent geometry for {!r}".format(key, field))
        if field.endswith(("_m", "_rad")) and type(row[field]) not in (int, float):
            raise ValueError("Branch record {} requires numeric geometry for {!r}".format(key, field))
    for field in B2_RECORD_ENVIRONMENT_KEYS:
        expected = _b2_environment_value(runtime_manifest, field)
        if expected is None or row.get(field) != expected or state.get(field) != expected:
            raise ValueError("Branch record {} environment mismatch for {!r}".format(key, field))


def validate_b2_records(
    records: Sequence[Mapping[str, Any]],
    state_manifest: Sequence[Mapping[str, Any]],
    split: str,
    config: Mapping[str, Any],
    runtime_manifest: Mapping[str, Any],
) -> Dict[str, Any]:
    """Strict 30 x 5 x 3 completeness and isolation gate."""
    validate_state_manifest(state_manifest, split, config)
    states_by_id = {item["state_id"]: item for item in state_manifest}
    expected_keys = expected_branch_keys(state_manifest, config)
    actual_keys = set()
    for row in records:
        if not isinstance(row, Mapping):
            raise ValueError("B2 branch record must be an object")
        identifier = row.get("state_id")
        if not isinstance(identifier, str) or identifier not in states_by_id:
            raise ValueError("Extra B2 branch row refers to an unknown state: {!r}".format(identifier))
        key = (identifier, _integer(row, "horizon"), _integer(row, "repeat_index"))
        if key in actual_keys:
            raise ValueError("Duplicate B2 branch rows: {}".format(key))
        validate_b2_record(row, states_by_id[identifier], split, config, runtime_manifest)
        actual_keys.add(key)

    missing = sorted(expected_keys - actual_keys)
    extra = sorted(actual_keys - expected_keys)
    if missing or extra:
        raise ValueError(
            "B2 {} branch completeness failed: missing={} extra={}".format(split, missing[:5], extra[:5])
        )
    return {
        "split": split,
        "n_states": len(state_manifest),
        "horizons": list(config["b2"]["horizons"]),
        "repeats_per_state_horizon": config["b2"]["repeats_per_state_horizon"],
        "n_branch_records": len(records),
        "expected_branch_records": len(expected_keys),
        "unique_keys": len(actual_keys),
        "duplicates": 0,
        "missing": 0,
        "extra": 0,
        "completeness_verified": True,
        "split_isolation_verified": True,
        "snapshot_hashes_verified": True,
        "horizon_order_verified": True,
        "common_repeat_seed_verified": True,
    }
