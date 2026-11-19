"""Post-hoc paired diagnostic on the accepted B2 Confirmation snapshots."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from itertools import groupby
from operator import itemgetter
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

from gate_b_v2.analysis import _b2_inputs
from gate_b_v2.authorization import validate_formal_authorization
from gate_b_v2.b2_protocol import B2_BRANCH_GEOMETRY_FIELDS, branch_order, policy_noise_schedule
from gate_b_v2.core import (
    environment_fingerprint, jsonable, load_jsonl, policy_noise_seed, seed_policy_rng,
    sha256_file, write_json,
)
from gate_b_v2.locks import (
    B2_RECORD_ENVIRONMENT_KEYS, current_git_commit, load_fixed_project_config, validate_b2_environment,
)
from gate_b_v2.policy import predict_full_future_chunk, reset_policy_or_block
from gate_b_v2.runner import GateBExperiment, _resolve_runtime_paths
from gate_b_v2.snapshot import (
    load_snapshot, require_passed_snapshot_validation, validate_snapshot_reference, verify_snapshot_sha256,
)


PHASE = "DIAGNOSTIC_CONTINUATION_H4"
PREFIX = "b2_continuation_h4_"
SOURCE_SPLIT = "confirmation"
SOURCE_RUN_ID = "b2_confirmation_20261118T110331"
SOURCE_CHECKSUM_LIST = "B2_CONFIRMATION_SHA256SUMS.txt"
# SHA256 of the accepted raw inventory published with the original closeout.
SOURCE_CHECKSUM_LIST_SHA256 = "cb7f653935ea0fe691535c036b0c4a252b41355038b22711a21159378a3e991c"
FIRST_HORIZONS = (1, 2, 4, 8, 15)
CONTINUATION_HORIZON = 4
MAX_STEPS = 500
N_STATES = 30
REPEATS = 3
N_BRANCHES = N_STATES * len(FIRST_HORIZONS) * REPEATS
WORKER_FILES = {PREFIX + suffix for suffix in (
    "launcher.log", "launcher.pid", "worker.pid", "gpu.csv", "gpu.stderr.log",
)}
PAIRED_FIELDS = (
    "state_id", "source_seed", "source_step", "repeat_index", "repeat_seed", "branch_order_seed",
    "randomized_order_index", "horizon_order", "snapshot_sha256", "snapshot_schema_version",
    *B2_BRANCH_GEOMETRY_FIELDS, *B2_RECORD_ENVIRONMENT_KEYS,
)
LIVE_ENV_FIELDS = (
    "python", "platform", "torch", "torch_cuda", "cuda_available", "gpu_name", "robomimic", "robosuite",
    "mujoco_py", "checkpoint_sha256", "dataset_sha256", "dp_source_tree_sha256", "device_requested",
)


@dataclass(frozen=True)
class ConfirmationInputs:
    run_dir: Path
    config: dict
    manifest: dict
    states: list
    branches: list
    runtime_paths: tuple
    provenance: dict


def timestamp() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def log(message: str) -> None:
    print(f"[{timestamp()}] {message}", flush=True)


def verify_original_archive(run_dir: Path) -> None:
    if sha256_file(run_dir / SOURCE_CHECKSUM_LIST) != SOURCE_CHECKSUM_LIST_SHA256:
        raise RuntimeError("Original Confirmation checksum list differs from the accepted closeout")
    subprocess.run(["sha256sum", "--check", "--quiet", SOURCE_CHECKSUM_LIST], cwd=run_dir, check=True)


def verify_live_fields(live: dict, recorded: dict, fields: tuple) -> None:
    mismatches = [key for key in fields if key not in live or live[key] != recorded[key]]
    if mismatches:
        raise RuntimeError(f"Live environment differs from Confirmation for {', '.join(mismatches)}")


def verified_snapshot_path(source_dir: Path, state: dict) -> Path:
    relative_path = Path("snapshots") / SOURCE_SPLIT / f"{state['state_id']}.pkl.gz"
    recorded = Path(state["snapshot_file"])
    if recorded.parts[-len(relative_path.parts):] != relative_path.parts:
        raise RuntimeError(f"Unexpected snapshot locator for {state['state_id']}")
    path = source_dir / relative_path
    if path.resolve(strict=True) != path:
        raise RuntimeError(f"Snapshot resolves outside its expected locator for {state['state_id']}")
    return path


def verify_source(project_root: Path, source_dir: Path) -> ConfirmationInputs:
    source_dir = source_dir.resolve(strict=True)
    if not source_dir.is_relative_to(project_root.parent):
        raise ValueError("Original Confirmation must be inside the EAI workspace")
    verify_original_archive(source_dir)
    config = load_fixed_project_config(project_root)
    branches, states, _, manifest, branches_path, states_path, validation_path, manifest_path, _ = (
        _b2_inputs(source_dir, SOURCE_SPLIT, config, project_root)
    )
    expected_order = [
        (state["state_id"], repeat_index, horizon)
        for state in states
        for repeat_index in range(REPEATS)
        for horizon in branch_order(config, state["source_seed"], repeat_index)
    ]
    if (
        len(states) != N_STATES or len(branches) != N_BRANCHES or manifest["continuation_horizon"] != 15
        or [(row["state_id"], row["repeat_index"], row["horizon"]) for row in branches] != expected_order
    ):
        raise RuntimeError("Original Confirmation cardinality, continuation or serialized branch order differs")

    runtime_paths = _resolve_runtime_paths(config, project_root, {})
    live = environment_fingerprint(*runtime_paths, config["evaluation"]["device"])
    verify_live_fields(live, manifest, LIVE_ENV_FIELDS)
    authorization = validate_formal_authorization(
        source_dir, SOURCE_SPLIT, {**manifest, **live}, config=config, project_root=project_root,
    )
    located_states = []
    for state in states:
        path = verified_snapshot_path(source_dir, state)
        validate_snapshot_reference(load_snapshot(path, expected_sha256=state["snapshot_sha256"]), state)
        located_states.append({**state, "snapshot_file": str(path)})
    provenance = {
        "source_run_id": SOURCE_RUN_ID,
        "source_split": SOURCE_SPLIT,
        "source_raw_checksum_list_sha256": SOURCE_CHECKSUM_LIST_SHA256,
        "source_records_sha256": sha256_file(branches_path),
        "source_state_manifest_sha256": sha256_file(states_path),
        "source_run_manifest_sha256": sha256_file(manifest_path),
        "source_snapshot_validation_sha256": sha256_file(validation_path),
        "source_authorization_sha256": authorization["authorization_sha256"],
        "source_implementation_commit": authorization["preflight"]["implementation_commit"],
        "source_tree_sha256": authorization["preflight"]["source_tree_sha256"],
        "source_environment_fingerprint_sha256": authorization["preflight"]["environment_fingerprint_sha256"],
    }
    return ConfirmationInputs(source_dir, config, manifest, located_states, branches, runtime_paths, provenance)


def policy_calls_for_steps(executed_steps: int, first_horizon: int) -> int:
    remaining = max(0, executed_steps - first_horizon)
    return 1 + (remaining + CONTINUATION_HORIZON - 1) // CONTINUATION_HORIZON


def paired_fields(baseline: dict, config_sha256: str) -> dict:
    return {
        **{key: baseline[key] for key in PAIRED_FIELDS},
        "phase": PHASE,
        "source_split": SOURCE_SPLIT,
        "first_horizon": baseline["horizon"],
        "continuation_horizon": CONTINUATION_HORIZON,
        "diagnostic_config_fingerprint": config_sha256,
    }


def execute_branch(experiment, snapshot: dict, baseline: dict, progress=None) -> dict:
    first_horizon = baseline["horizon"]
    if first_horizon not in FIRST_HORIZONS:
        raise ValueError(f"Illegal first horizon {first_horizon}")
    env = experiment.env
    env.restore(snapshot)
    source_step = baseline["source_step"]
    original = snapshot["validation_reference"]["sim_state"]
    restored = env.current_sim_state()
    state_atol = experiment.config["b2"]["snapshot_validation"]["state_atol"]
    if (
        env.steps != source_step or snapshot["robosuite_internal"]["done"]
        or original.shape != restored.shape or not np.isfinite(restored).all()
        or not np.all(np.abs(original - restored) <= state_atol)
    ):
        raise RuntimeError("Restored branch start disagrees with the original snapshot reference")
    reset_policy_or_block(experiment.policy)

    noise_schedule = []
    env_done = False
    started = time.perf_counter()
    while env.steps < experiment.max_steps and not env_done:
        horizon = first_horizon if not noise_schedule else CONTINUATION_HORIZON
        noise_seed = policy_noise_seed(baseline["repeat_seed"], len(noise_schedule))
        seed_policy_rng(experiment.torch, noise_seed)
        chunk = predict_full_future_chunk(
            experiment.policy, experiment.torch, env.policy_observation(), experiment.device,
            experiment.n_obs_steps, experiment.prediction_horizon,
        )
        if not np.isfinite(chunk).all():
            raise RuntimeError("Non-finite diagnostic policy action chunk")
        execute_n = min(horizon, experiment.max_steps - env.steps)
        for action_index in range(execute_n):
            _, _, env_done, _ = env.step(experiment._env_action(chunk[action_index]), strict=True)
            if env_done:
                break
        noise_schedule.append(noise_seed)
        if progress is not None and len(noise_schedule) % 20 == 0:
            progress(env.steps, len(noise_schedule), time.perf_counter() - started)
    elapsed = time.perf_counter() - started

    success = env.success(float(experiment.config["evaluation"]["success_threshold"]), strict=True)
    if env.success_error:
        raise RuntimeError(f"Diagnostic task success predicate failed: {env.success_error}")
    return {
        "policy_noise_seed_schedule": noise_schedule,
        "policy_reset_verified": True,
        "restored_snapshot_verified": True,
        "success": success,
        "success_seen": bool(env.success_seen),
        "success_error": env.success_error,
        "max_reward": float(env.max_reward),
        "steps_from_episode_start": int(env.steps),
        "steps_after_branch": int(env.steps - source_step),
        "policy_calls_after_branch": len(noise_schedule),
        "wall_time_s": elapsed,
        "termination": "environment_done" if env_done else "max_steps",
    }


def validate_branch(row: dict, baseline: dict, config_sha256: str) -> None:
    for key, expected in paired_fields(baseline, config_sha256).items():
        if key not in row or type(row[key]) is not type(expected) or row[key] != expected:
            raise ValueError(f"Diagnostic branch differs from paired Confirmation record for {key}")
    source_step = baseline["source_step"]
    end = row.get("steps_from_episode_start")
    if (
        type(end) is not int or not 1 <= source_step < end <= MAX_STEPS
        or type(row.get("steps_after_branch")) is not int or row["steps_after_branch"] != end - source_step
    ):
        raise ValueError("Diagnostic branch has invalid step counts")
    termination = row.get("termination")
    if termination not in ("max_steps", "environment_done") or (termination == "max_steps" and end != MAX_STEPS):
        raise ValueError("Diagnostic branch has invalid termination")
    calls = policy_calls_for_steps(end - source_step, baseline["horizon"])
    if type(row.get("policy_calls_after_branch")) is not int or row["policy_calls_after_branch"] != calls:
        raise ValueError("Diagnostic branch has invalid policy-call count")
    schedule = row.get("policy_noise_seed_schedule")
    if (
        not isinstance(schedule, list) or any(type(seed) is not int for seed in schedule)
        or schedule != policy_noise_schedule(baseline["repeat_seed"], calls)
    ):
        raise ValueError("Diagnostic branch has invalid policy-noise schedule")
    if (
        type(row.get("success")) is not bool or type(row.get("success_seen")) is not bool
        or "success_error" not in row or row["success_error"] not in (None, "")
        or row.get("policy_reset_verified") is not True or row.get("restored_snapshot_verified") is not True
    ):
        raise ValueError("Diagnostic branch has invalid success, policy reset or restore evidence")
    for key in ("max_reward", "wall_time_s"):
        if type(row.get(key)) not in (float, int) or not math.isfinite(row[key]):
            raise ValueError(f"Diagnostic branch has invalid {key}")
    if row["wall_time_s"] < 0:
        raise ValueError("Diagnostic branch has negative wall time")


def validate_complete(records: list, baseline: list, config_sha256: str) -> None:
    if len(records) != N_BRANCHES or len(baseline) != N_BRANCHES:
        raise ValueError(f"Diagnostic requires exactly {N_BRANCHES} paired Branch records")
    keys = {(row["state_id"], row["first_horizon"], row["repeat_index"]) for row in records}
    if len(keys) != N_BRANCHES:
        raise ValueError("Duplicate diagnostic Branch keys")
    for row, original in zip(records, baseline):
        validate_branch(row, original, config_sha256)


def reserve_run(project_root: Path, run_dir: Path) -> Path:
    run_dir = run_dir.resolve()
    if run_dir.parent != (project_root / "runs").resolve() or not run_dir.name.startswith(PREFIX):
        raise ValueError(f"Run directory must be a new {PREFIX} directory under the project runs directory")
    run_dir.mkdir(exist_ok=True)
    if {path.name for path in run_dir.iterdir()} - WORKER_FILES:
        raise FileExistsError(f"Refusing to reuse diagnostic run directory {run_dir}")
    return run_dir


def run_diagnostic(project_root: Path, source_dir: Path, run_dir: Path) -> None:
    run_dir = reserve_run(project_root, run_dir)
    status_path = run_dir / (PREFIX + "status.json")
    started_at = timestamp()
    stage, completed = "SOURCE_VALIDATION", 0
    status = {"phase": PHASE, "started_at": started_at, "expected_branch_records": N_BRANCHES}
    with status_path.open("x", encoding="utf-8") as stream:
        json.dump({**status, "status": stage, "n_branch_records": completed}, stream)
        stream.write("\n")

    try:
        log("SOURCE_VALIDATION_START")
        source = verify_source(project_root, source_dir)
        log(f"SOURCE_VALIDATION_PASS snapshots={len(source.states)} paired_branches={len(source.branches)}")

        stage = "SNAPSHOT_VALIDATION"
        validation_dir = run_dir / "snapshot_recheck"
        write_json(status_path, {**status, "status": stage, "n_branch_records": completed})
        log("SNAPSHOT_VALIDATION_START")
        dp_root, checkpoint, dataset = source.runtime_paths
        experiment = GateBExperiment(
            source.config, project_root, dp_root, checkpoint, dataset, validation_dir,
            write_environment_manifest=False,
        )
        try:
            validate_b2_environment(experiment.manifest, source.manifest)
            verify_live_fields(
                jsonable(experiment.manifest), source.manifest, LIVE_ENV_FIELDS + ("env_kwargs", "env_version_dataset"),
            )
            expected_snapshots = {state["state_id"]: state["snapshot_sha256"] for state in source.states}
            validation_path = experiment._validate_all_b2_snapshots(source.states, SOURCE_SPLIT)
            validation = json.loads(validation_path.read_text(encoding="utf-8"))
            require_passed_snapshot_validation(validation, SOURCE_SPLIT, expected_snapshots)
            log(f"SNAPSHOT_VALIDATION_PASS snapshots={len(expected_snapshots)}")

            settings = {
                "base_b2_config_fingerprint": source.manifest["config_fingerprint"],
                "continuation_horizon": CONTINUATION_HORIZON, "first_horizons": list(FIRST_HORIZONS),
                "max_steps": MAX_STEPS, "n_states": N_STATES, "repeats_per_state_horizon": REPEATS,
                "success_threshold": source.config["evaluation"]["success_threshold"],
                "snapshot_validation": source.config["b2"]["snapshot_validation"],
                "phase": PHASE,
            }
            config_sha256 = hashlib.sha256(
                json.dumps(settings, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()
            run_path = run_dir / (PREFIX + "run.json")
            records_path = run_dir / (PREFIX + "episodes.jsonl")
            validation_sha256 = sha256_file(validation_path)
            write_json(run_path, {
                **settings, **source.provenance, "post_hoc_exploratory": True, "run_id": run_dir.name,
                "started_at": started_at, "diagnostic_config_fingerprint": config_sha256,
                "diagnostic_implementation_commit": current_git_commit(project_root),
                "diagnostic_runner_sha256": sha256_file(Path(__file__)),
                "snapshot_recheck_file": validation_path.relative_to(run_dir).as_posix(),
                "snapshot_recheck_sha256": validation_sha256,
                "environment": {
                    key: source.manifest[key] for key in dict.fromkeys((*LIVE_ENV_FIELDS, *B2_RECORD_ENVIRONMENT_KEYS))
                },
                "expected_branch_records": N_BRANCHES,
                "policy_calls_at_max_steps": sum(
                    policy_calls_for_steps(MAX_STEPS - row["source_step"], row["horizon"])
                    for row in source.branches
                ),
            })
            stage = "BRANCH_RUNNING"
            write_json(status_path, {**status, "status": stage, "n_branch_records": completed})
            states_by_id = {state["state_id"]: state for state in source.states}
            with records_path.open("x", encoding="utf-8") as stream:
                for state_id, branches in groupby(source.branches, key=itemgetter("state_id")):
                    snapshot_path = Path(states_by_id[state_id]["snapshot_file"])
                    snapshot_sha256 = expected_snapshots[state_id]
                    snapshot = load_snapshot(snapshot_path, expected_sha256=snapshot_sha256)
                    for baseline in branches:
                        ordinal = completed + 1
                        label = f"branch={ordinal}/{N_BRANCHES} state={state_id}"
                        log(f"BRANCH_START {label} first_h={baseline['horizon']} repeat={baseline['repeat_index']}")
                        verify_snapshot_sha256(snapshot_path, snapshot_sha256)
                        measurements = execute_branch(
                            experiment, snapshot, baseline,
                            progress=lambda step, calls, wall: log(
                                f"BRANCH_PROGRESS {label} steps={step}/{MAX_STEPS} calls={calls} elapsed_s={wall:.2f}"
                            ),
                        )
                        row = {**paired_fields(baseline, config_sha256), **measurements}
                        validate_branch(row, baseline, config_sha256)
                        stream.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")
                        stream.flush()
                        completed += 1
                        write_json(status_path, {**status, "status": stage, "n_branch_records": completed})
                        log(f"BRANCH_WRITTEN {label} elapsed_s={row['wall_time_s']:.2f}")
        finally:
            experiment.close()

        stage = "COMPLETENESS_VALIDATION"
        write_json(status_path, {**status, "status": stage, "n_branch_records": completed})
        validate_complete(load_jsonl(records_path), source.branches, config_sha256)
        verify_original_archive(source.run_dir)
        completion = {
            **status, "status": "COMPLETE", "completed_at": timestamp(), "n_branch_records": completed,
            "n_states": N_STATES, "continuation_horizon": CONTINUATION_HORIZON,
            "completeness_verified": True, "original_checksums_verified": True,
            "snapshot_validation_all_passed": True,
        }
        write_json(run_dir / (PREFIX + "integrity.json"), {
            **completion, **source.provenance, "diagnostic_config_fingerprint": config_sha256,
            "episodes_sha256": sha256_file(records_path), "run_manifest_sha256": sha256_file(run_path),
            "snapshot_recheck_sha256": validation_sha256,
        })
        write_json(status_path, completion)
        log(f"COMPLETE paired_branches={completed}")
    except (Exception, KeyboardInterrupt) as exc:
        write_json(status_path, {
            **status, "status": "BLOCKED", "stage": stage, "n_branch_records": completed,
            "blocked_at": timestamp(), "reason": f"{type(exc).__name__}: {exc}",
        })
        log(f"BLOCKED stage={stage} validated_branches={completed} reason={type(exc).__name__}: {exc}")
        raise


def main() -> None:
    project_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-run-dir", type=Path, default=project_root / "runs" / SOURCE_RUN_ID)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check-source", action="store_true", help="Read-only checks of the original evidence and runtime")
    mode.add_argument("--run-dir", type=Path, help="New diagnostic output directory")
    args = parser.parse_args()
    if args.check_source:
        source = verify_source(project_root, args.source_run_dir)
        print(json.dumps({
            **source.provenance, "phase": PHASE, "status": "PASS",
            "n_states": len(source.states), "n_baseline_records": len(source.branches),
        }, indent=2, sort_keys=True))
    else:
        run_diagnostic(project_root, args.source_run_dir, args.run_dir)


if __name__ == "__main__":
    main()
