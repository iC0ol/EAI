"""B2 state harvesting: fixed-h=8 source rollouts and frozen stage gate.

No source reward, source success, branch outcome or clearance rank is used to
select a state.  The source episode stops at the first eligible control step and
the snapshot is taken immediately.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

import numpy as np

from .authorization import validate_formal_authorization
from .b2_protocol import (
    assert_state_seed_in_split,
    discovery_confirmation_seed_ranges,
    seed_blocks,
    seeds_for_block,
    select_candidate_indices,
    selection_metadata,
    source_policy_seed,
    state_id,
    validate_candidate_selection,
    validate_state_manifest,
)
from .core import (
    append_jsonl,
    ensure_new_records_path,
    policy_noise_seed,
    seed_everything,
    seed_policy_rng,
    sha256_array,
    write_json,
)
from .geometry import (
    STAGE_GATE_VERSION,
    compute_square_geometry,
    evaluate_stage_gate,
)
from .locks import (
    B2_RECORD_ENVIRONMENT_KEYS,
    _b2_environment_value,
    b2_record_environment_fields,
    build_b2_run_manifest,
    load_b1_full_manifest,
)
from .policy import predict_full_future_chunk, reset_policy_or_block
from .snapshot import save_snapshot


def _observation_hashes(observation: Mapping[str, np.ndarray]) -> Dict[str, str]:
    return {str(key): sha256_array(np.asarray(value)) for key, value in observation.items()}


def _history_hashes(history: Sequence[Mapping[str, np.ndarray]]) -> List[Dict[str, str]]:
    return [_observation_hashes(item) for item in history]


def _candidate_record(
    experiment: Any,
    split: str,
    source_seed: int,
    source_step: int,
    snapshot_path: Path,
    snapshot: Mapping[str, Any],
    geometry: Mapping[str, Any],
    gate: Mapping[str, Any],
    preflight: bool,
) -> Dict[str, Any]:
    env = experiment.env
    # Save the snapshot captured at the eligible step, not one captured later.
    snapshot_sha256 = save_snapshot(snapshot_path, snapshot)
    current_obs = env.history[-1] if env.history else {}
    record: Dict[str, Any] = {
        "state_id": state_id(split, source_seed) if not preflight else "pre_{:06d}".format(int(source_seed)),
        "split": split,
        "source_seed": int(source_seed),
        "source_step": int(source_step),
        "source_horizon": int(experiment.config["b2"]["source_horizon"]),
        "source_policy_seed": int(source_policy_seed(experiment.config, source_seed)),
        "stage_gate_version": STAGE_GATE_VERSION,
        "stage_gate": dict(gate),
        "geometry": dict(geometry),
        "clearance_m": float(geometry["clearance_m"]),
        "clearance_x_positive_m": float(geometry["clearance_x_positive_m"]),
        "clearance_x_negative_m": float(geometry["clearance_x_negative_m"]),
        "clearance_y_positive_m": float(geometry["clearance_y_positive_m"]),
        "clearance_y_negative_m": float(geometry["clearance_y_negative_m"]),
        "dx_m": float(geometry["dx_m"]),
        "dy_m": float(geometry["dy_m"]),
        "d_xy_m": float(geometry["d_xy_m"]),
        "relative_yaw_rad": float(geometry["relative_yaw_rad"]),
        "z_gap_m": float(geometry["z_gap_m"]),
        "t_nut_m": float(geometry["t_nut_m"]),
        "r_hole_m": float(geometry["r_hole_m"]),
        "r_peg_m": float(geometry["r_peg_m"]),
        "hole_half_x_m": float(geometry["hole_half_x_m"]),
        "hole_half_y_m": float(geometry["hole_half_y_m"]),
        "peg_half_x_m": float(geometry["peg_half_x_m"]),
        "peg_half_y_m": float(geometry["peg_half_y_m"]),
        "snapshot_file": str(snapshot_path),
        "snapshot_sha256": str(snapshot_sha256),
        "sim_state_sha256": snapshot["sim_state_sha256"],
        "model_xml_sha256": snapshot["model_xml_sha256"],
        "observation_key_sha256": _observation_hashes(current_obs),
        "observation_history_sha256": _history_hashes(env.history),
        "snapshot_schema_version": int(snapshot["schema_version"]),
        "controller_gripper_capture_audit": snapshot.get("controller_gripper_audit", []),
        "snapshot_capabilities": snapshot.get("snapshot_capabilities", {}),
        "policy_reset_verified": True,
        "preflight": bool(preflight),
        "scientific_data": not bool(preflight),
    }
    for key in B2_RECORD_ENVIRONMENT_KEYS:
        if key in experiment.manifest:
            record[key] = _b2_environment_value(experiment.manifest, key)
    return record


def run_source_episode(
    experiment: Any,
    split: str,
    source_seed: int,
    snapshot_dir: Path,
    preflight: bool = False,
    fallback_step: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """Run one fixed-h=8 source rollout and capture at most one state.

    When ``fallback_step`` is supplied (preflight only), a snapshot is captured
    at that step if the stage gate is not reached.  Formal harvesting never uses
    this fallback.
    """
    if not preflight:
        assert_state_seed_in_split(experiment.config, split, source_seed)
    env = experiment.env
    source_horizon = int(experiment.config["b2"]["source_horizon"])
    seed_everything(int(source_seed))
    env.reset(int(source_seed))
    reset_policy_or_block(experiment.policy)

    rs_env = env.robosuite_env
    previous = compute_square_geometry(rs_env)
    call_index = 0
    done = False
    policy_seed = source_policy_seed(experiment.config, source_seed)
    while env.steps < env.max_steps and not done:
        seed_policy_rng(experiment.torch, policy_noise_seed(policy_seed, call_index))
        chunk = predict_full_future_chunk(
            experiment.policy,
            experiment.torch,
            env.policy_observation(),
            experiment.device,
            experiment.n_obs_steps,
            experiment.prediction_horizon,
        )
        execute_n = min(source_horizon, env.max_steps - env.steps)
        for action_index in range(execute_n):
            _, _, done, _ = env.step(experiment._env_action(chunk[action_index]))
            geometry = compute_square_geometry(rs_env)
            gate = evaluate_stage_gate(geometry, previous["z_gap_m"])
            previous = geometry
            if gate["eligible"]:
                snapshot_path = Path(snapshot_dir) / "{}.pkl.gz".format(
                    state_id(split, source_seed) if not preflight else "pre_{:06d}".format(int(source_seed))
                )
                # Capture the snapshot before any further environment step.
                snapshot = env.snapshot(metadata={
                    "split": split,
                    "source_seed": int(source_seed),
                    "source_step": int(env.steps),
                    "stage_gate_version": STAGE_GATE_VERSION,
                    "preflight": bool(preflight),
                })
                return _candidate_record(
                    experiment, split, source_seed, int(env.steps),
                    snapshot_path, snapshot, geometry, gate, preflight,
                )
            if done:
                break
        call_index += 1

    if preflight and fallback_step is not None:
        # Deterministic preflight fallback, clearly not a stage-gate candidate.
        while env.steps < min(int(fallback_step), env.max_steps) and not done:
            # Continue the same fixed-h rollout without selecting a formal state.
            seed_policy_rng(experiment.torch, policy_noise_seed(policy_seed, call_index))
            chunk = predict_full_future_chunk(
                experiment.policy,
                experiment.torch,
                env.policy_observation(),
                experiment.device,
                experiment.n_obs_steps,
                experiment.prediction_horizon,
            )
            execute_n = min(source_horizon, env.max_steps - env.steps)
            for action_index in range(execute_n):
                _, _, done, _ = env.step(experiment._env_action(chunk[action_index]))
                if done:
                    break
            call_index += 1
        geometry = compute_square_geometry(rs_env)
        gate = evaluate_stage_gate(geometry, previous["z_gap_m"])
        snapshot_path = Path(snapshot_dir) / "pre_{:06d}.pkl.gz".format(int(source_seed))
        snapshot = env.snapshot(metadata={
            "split": split,
            "source_seed": int(source_seed),
            "source_step": int(env.steps),
            "stage_gate_version": STAGE_GATE_VERSION,
            "preflight": True,
            "fallback": True,
        })
        record = _candidate_record(
            experiment, split, source_seed, int(env.steps),
            snapshot_path, snapshot, geometry, gate, preflight=True,
        )
        record["preflight_fallback"] = True
        record["gate_reached"] = False
        return record
    return None


def _check_no_partial_harvest_artifacts(output_dir: Path, split: str) -> None:
    """Refuse to continue in a directory containing any prior harvest artifact.

    A failed or interrupted harvest must be rerun in a brand-new run directory.
    This function never deletes or cleans old data.
    """
    candidates = [
        output_dir / "b2_{}_harvest_manifest.json".format(split),
        output_dir / "b2_{}_candidates.json".format(split),
        output_dir / "b2_{}_state_manifest.jsonl".format(split),
        output_dir / "b2_{}_harvest_summary.json".format(split),
        output_dir / "b2_{}_status.json".format(split),
        output_dir / "b2_{}_episodes.jsonl".format(split),
        output_dir / "b2_{}_run.json".format(split),
    ]
    snapshot_dir = output_dir / "snapshots" / split
    existing = [str(path) for path in candidates if path.exists()]
    if snapshot_dir.exists():
        existing.append(str(snapshot_dir))
    if existing:
        raise RuntimeError(
            "Refusing to overwrite prior B2 {} harvest artifacts in {}: {}. "
            "Use a brand-new run directory; old data is never deleted automatically.".format(
                split, output_dir, existing
            )
        )


def harvest_split(experiment: Any, split: str) -> Path:
    """Harvest and deterministically select 30 states for one split."""
    if split not in ("discovery", "confirmation"):
        raise ValueError("split must be discovery or confirmation")
    config = experiment.config
    output_dir = Path(experiment.run_dir)
    snapshot_dir = output_dir / "snapshots" / split
    manifest_path = output_dir / "b2_{}_state_manifest.jsonl".format(split)
    candidates_path = output_dir / "b2_{}_candidates.json".format(split)
    summary_path = output_dir / "b2_{}_harvest_summary.json".format(split)

    # Formal harvesting is impossible without a same-directory PASS preflight and
    # a researcher-created split authorization file.
    validate_formal_authorization(
        output_dir,
        split,
        experiment.manifest,
        config=config,
        project_root=experiment.project_root,
    )
    _check_no_partial_harvest_artifacts(output_dir, split)
    ensure_new_records_path(manifest_path)

    config_manifest_path = Path(str(config["paths"]["b1_full_manifest"]))
    if not config_manifest_path.is_absolute():
        config_manifest_path = (experiment.project_root / config_manifest_path).resolve()
    b1_full_manifest = load_b1_full_manifest(config_manifest_path)
    b2_manifest = build_b2_run_manifest(
        config=config,
        runtime_manifest=experiment.manifest,
        b1_full_manifest=b1_full_manifest,
        split=split,
        command="b2-harvest",
    )
    write_json(output_dir / "b2_{}_harvest_manifest.json".format(split), b2_manifest)
    env_fields = b2_record_environment_fields(b2_manifest)

    primary, extension = seed_blocks(config, split)
    candidates: List[Dict[str, Any]] = []
    processed_blocks = []
    for block_name, block in (("primary", primary), ("extension", extension)):
        if block_name == "extension" and len(candidates) >= int(config["b2"]["selected_states"]):
            break
        processed_blocks.append({
            "block": block_name,
            "start": int(block[0]),
            "count": int(block[1]),
            "end": int(block[0]) + int(block[1]) - 1,
        })
        for source_seed in seeds_for_block(block):
            candidate = run_source_episode(
                experiment, split, int(source_seed), snapshot_dir, preflight=False
            )
            if candidate is not None:
                candidate.update(env_fields)
                candidates.append(candidate)

    if len(candidates) < int(config["b2"]["selected_states"]):
        write_json(summary_path, {
            "status": "BLOCKED",
            "reason": "insufficient stage coverage after the pre-registered primary and extension blocks",
            "split": split,
            "eligible_candidates": len(candidates),
            "required_states": int(config["b2"]["selected_states"]),
            "processed_blocks": processed_blocks,
            "seed_range": discovery_confirmation_seed_ranges(config)[split],
            "candidate_source_seeds": [int(item["source_seed"]) for item in candidates],
        })
        raise RuntimeError(
            "B2 {} BLOCKED: only {} eligible states after the frozen seed pools; "
            "the stage gate must not be widened or retuned".format(split, len(candidates))
        )

    metadata = selection_metadata(candidates, split, config)
    selected = [candidates[index] for index in metadata["selected_candidate_indices"]]
    validate_candidate_selection(candidates, selected, split, config)
    validate_state_manifest(selected, split, config)

    write_json(candidates_path, {
        "split": split,
        "seed_range": discovery_confirmation_seed_ranges(config)[split],
        "processed_blocks": processed_blocks,
        "n_candidates": len(candidates),
        "candidates": candidates,
        "selection": metadata,
    })
    for record in selected:
        append_jsonl(manifest_path, record)
    write_json(summary_path, {
        "status": "COMPLETE",
        "split": split,
        "seed_range": discovery_confirmation_seed_ranges(config)[split],
        "processed_blocks": processed_blocks,
        "eligible_candidates": len(candidates),
        "selected_states": len(selected),
        "selected_source_seeds": [int(item["source_seed"]) for item in selected],
        "selection_seed": int(metadata["selection_seed"]),
        "manifest_file": manifest_path.name,
        "candidates_file": candidates_path.name,
        "snapshot_dir": str(snapshot_dir),
        "preflight": False,
    })
    return manifest_path


def run_preflight_smoke(experiment: Any, output_dir: Path, seeds: Sequence[int]) -> Path:
    """Small PREFLIGHT-only source-state smoke test; never a formal manifest."""
    formal = discovery_confirmation_seed_ranges(experiment.config)
    for source_seed in seeds:
        for split, (start, end) in formal.items():
            if start <= int(source_seed) <= end:
                raise ValueError(
                    "PREFLIGHT seed {} lies in the formal {} pool [{}, {}]".format(
                        source_seed, split, start, end
                    )
                )
    output_dir = Path(output_dir)
    snapshot_dir = output_dir / "snapshots" / "preflight"
    records_path = output_dir / "b2_preflight_state_smoke.jsonl"
    ensure_new_records_path(records_path)
    records = []
    for source_seed in seeds:
        record = run_source_episode(
            experiment, "preflight", int(source_seed), snapshot_dir, preflight=True
        )
        if record is not None:
            append_jsonl(records_path, record)
            records.append(record)
    write_json(output_dir / "b2_preflight_state_smoke_summary.json", {
        "marker": "PREFLIGHT",
        "scientific_data": False,
        "n_requested": len(seeds),
        "n_captured": len(records),
        "records_file": records_path.name,
        "note": "Throwaway source-state smoke test; excluded from all B2 formal manifests and results.",
    })
    return records_path
