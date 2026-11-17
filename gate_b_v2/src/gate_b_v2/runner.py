from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

from .core import (
    B1_PHASES,
    append_jsonl,
    b1_records_filename,
    b1_run_filename,
    ensure_new_records_path,
    environment_fingerprint,
    jsonable,
    load_jsonl,
    policy_noise_seed,
    seed_everything,
    seed_policy_rng,
    utc_run_id,
    validate_horizons,
    validate_seed_ranges,
    write_json,
)
from .actions import undo_transform_action
from .authorization import validate_formal_authorization
from .b2_protocol import (
    B2_BRANCH_GEOMETRY_FIELDS,
    branch_order,
    branch_order_seed,
    repeat_seed,
    validate_b2_record,
    validate_b2_records,
    validate_state_manifest,
)
from .env import EpisodeEnv, create_square_image_env, image_for_video
from .geometry import STAGE_GATE_VERSION, compute_square_geometry
from .locks import (
    b2_record_environment_fields,
    build_b1_run_manifest,
    build_b2_run_manifest,
    load_b1_full_manifest,
    record_environment_fields,
)
from .policy import load_diffusion_policy_checkpoint, predict_full_future_chunk, reset_policy_or_block
from .snapshot import (
    load_snapshot,
    require_passed_snapshot_validation,
    validate_snapshot_reference,
    validate_snapshot_restore,
    verify_snapshot_sha256,
)


def ensure_new_b2_branch_outputs(run_dir: Path, split: str) -> None:
    if split not in ("discovery", "confirmation"):
        raise ValueError("split must be discovery or confirmation")
    names = ["b2_{}_{}".format(split, suffix) for suffix in (
        "run.json", "episodes.jsonl", "snapshot_validation.json", "summary.json",
        "status.json", "analysis.json", "report.md",
    )]
    if split == "discovery":
        names.append("B2_REPORT.md")
    names.extend([name + ".tmp" for name in names if name.endswith(".json")])
    conflicts = [name for name in names if (run_dir / name).exists() or (run_dir / name).is_symlink()]
    if conflicts:
        raise FileExistsError(
            "Refusing to overwrite B2 {} branch outputs in {}: {}. Use a new run directory.".format(
                split, run_dir, ", ".join(conflicts),
            )
        )


def _get_cfg_value(cfg: Any, dotted: str, default: Any = None) -> Any:
    value = cfg
    for part in dotted.split("."):
        try:
            value = value[part] if isinstance(value, dict) else getattr(value, part)
        except Exception:
            return default
    return value


def _resolve_runtime_paths(config: Mapping[str, Any], project_root: Path, overrides: Mapping[str, Optional[str]]):
    paths = config["paths"]
    dp_root = Path(overrides.get("dp_root") or paths["dp_root"]).expanduser()
    checkpoint = Path(overrides.get("checkpoint") or paths["checkpoint"]).expanduser()
    dataset = Path(overrides.get("dataset") or paths["dataset"]).expanduser()
    if not dp_root.is_absolute():
        dp_root = (project_root / dp_root).resolve()
    if not checkpoint.is_absolute():
        checkpoint = (project_root / checkpoint).resolve()
    if not dataset.is_absolute():
        dataset = (project_root / dataset).resolve()
    return dp_root, checkpoint, dataset


class GateBExperiment:
    def __init__(
        self,
        config: Mapping[str, Any],
        project_root: Path,
        dp_root: Path,
        checkpoint: Path,
        dataset: Path,
        run_dir: Path,
        max_steps_override: Optional[int] = None,
        write_environment_manifest: bool = True,
    ):
        self.config = dict(config)
        self.project_root = Path(project_root).resolve()
        self.dp_root = Path(dp_root).resolve()
        self.checkpoint = Path(checkpoint).resolve()
        self.dataset = Path(dataset).resolve()
        self.run_dir = Path(run_dir).resolve()
        self.run_dir.mkdir(parents=True, exist_ok=True)

        evaluation = self.config["evaluation"]
        self.device = str(evaluation["device"])
        self.runtime = load_diffusion_policy_checkpoint(self.dp_root, self.checkpoint, self.device)
        self.torch = self.runtime["torch"]
        self.policy = self.runtime["policy"]
        self.shape_meta = self.runtime["shape_meta"]
        self.n_obs_steps = int(self.runtime["n_obs_steps"])
        self.prediction_horizon = int(self.runtime["prediction_horizon"])
        self.action_dim = int(self.runtime["action_dim"])
        self.abs_action = bool(self.runtime["abs_action"])
        self.rotation_rep = str(self.runtime["rotation_rep"])
        self.cfg = self.runtime["cfg"]

        expected_horizon = int(evaluation.get("expected_prediction_horizon", 16))
        if self.prediction_horizon != expected_horizon:
            raise RuntimeError(
                "Checkpoint prediction horizon is {}, protocol expects {}. Stop and inspect "
                "the exact archived checkpoint config; do not alter model weights.".format(
                    self.prediction_horizon, expected_horizon
                )
            )
        task_name = str(_get_cfg_value(self.cfg, "task.task_name", ""))
        dataset_type = str(_get_cfg_value(self.cfg, "task.dataset_type", ""))
        if task_name != str(evaluation.get("expected_task_name", "square")):
            raise RuntimeError("Expected Square task, checkpoint config says {!r}".format(task_name))
        if dataset_type != str(evaluation.get("expected_dataset_type", "mh")):
            raise RuntimeError("Expected MH dataset, checkpoint config says {!r}".format(dataset_type))

        runner_max_steps = _get_cfg_value(self.cfg, "task.env_runner.max_steps", None)
        self.max_steps = int(max_steps_override or evaluation.get("max_steps") or runner_max_steps or 500)
        if self.max_steps <= 0:
            raise ValueError("max_steps must be positive")

        self.wrapper, self.env_meta = create_square_image_env(
            self.dp_root, self.dataset, self.shape_meta, abs_action=self.abs_action
        )
        self.env = EpisodeEnv(
            wrapper=self.wrapper,
            shape_meta=self.shape_meta,
            n_obs_steps=self.n_obs_steps,
            max_steps=self.max_steps,
        )
        self.manifest = environment_fingerprint(self.dp_root, self.checkpoint, self.dataset, self.device)
        self.manifest.update({
            "run_id": self.run_dir.name,
            "checkpoint_use_ema": bool(self.runtime["use_ema"]),
            "prediction_horizon": self.prediction_horizon,
            "n_obs_steps": self.n_obs_steps,
            "n_action_steps_checkpoint": int(getattr(self.policy, "n_action_steps", -1)),
            "available_future_actions": self.prediction_horizon - (self.n_obs_steps - 1),
            "action_dim": self.action_dim,
            "abs_action": self.abs_action,
            "rotation_rep": self.rotation_rep,
            "env_action_dim": 7 if self.abs_action else self.action_dim,
            "env_name": self.env_meta.get("env_name"),
            "env_version_dataset": self.env_meta.get("env_version"),
            "max_steps": self.max_steps,
            "env_kwargs": self.env_meta.get("env_kwargs", {}),
        })
        if write_environment_manifest:
            write_json(self.run_dir / "environment_manifest.json", self.manifest)

    def close(self) -> None:
        self.env.close()

    def _save_video(self, frames: List[np.ndarray], path: Path) -> Optional[str]:
        if not frames:
            return None
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            import imageio.v2 as imageio
            imageio.mimsave(str(path), frames, fps=int(self.config["runtime"].get("video_fps", 10)))
            return str(path)
        except Exception as exc:
            fallback = path.with_suffix(".npz")
            np.savez_compressed(str(fallback), frames=np.asarray(frames, dtype=np.uint8))
            return "{} (video encoder unavailable: {})".format(fallback, exc)

    def _env_action(self, policy_action: np.ndarray) -> np.ndarray:
        """Map a policy-space action to the robosuite OSC_POSE action."""
        if self.abs_action:
            return undo_transform_action(policy_action)
        return np.asarray(policy_action, dtype=np.float32)

    def _run_episode(
        self,
        seed: int,
        horizon: int,
        policy_seed: int,
        video_path: Optional[Path] = None,
        decision_callback=None,
        phase: str = "unknown",
        split: Optional[str] = None,
        state_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if horizon > self.manifest["available_future_actions"]:
            raise ValueError(
                "h={} exceeds checkpoint's {} future action slots".format(
                    horizon, self.manifest["available_future_actions"]
                )
            )
        seed_everything(int(seed))
        initial_obs = self.env.reset(int(seed))
        initial_state_hash = self.env.initial_state_hash()
        reset_policy_or_block(self.policy)

        frames: List[np.ndarray] = []
        capture = video_path is not None and bool(self.config["runtime"].get("capture_video", True))
        if capture:
            frames.append(image_for_video(initial_obs))
        video_stride = max(1, int(self.config["runtime"].get("video_frame_stride", 2)))
        call_index = 0
        env_done = False
        started = time.perf_counter()
        while self.env.steps < self.max_steps and not env_done:
            if decision_callback is not None:
                decision_callback(self.env, call_index)
            seed_policy_rng(self.torch, policy_noise_seed(policy_seed, call_index))
            obs_batch = self.env.policy_observation()
            chunk = predict_full_future_chunk(
                self.policy, self.torch, obs_batch, self.device,
                self.n_obs_steps, self.prediction_horizon,
            )
            execute_n = min(int(horizon), self.max_steps - self.env.steps)
            for action_index in range(execute_n):
                obs, _, done, _ = self.env.step(self._env_action(chunk[action_index]))
                if capture and (self.env.steps % video_stride == 0 or self.env.steps >= self.max_steps):
                    frames.append(image_for_video(obs))
                if done:
                    env_done = True
                    break
            call_index += 1

        elapsed = time.perf_counter() - started
        video_result = self._save_video(frames, video_path) if capture else None
        threshold = float(self.config["evaluation"].get("success_threshold", 0.99))
        return {
            "phase": phase,
            "split": split,
            "state_id": state_id,
            "seed": int(seed),
            "horizon": int(horizon),
            "policy_seed": int(policy_seed),
            "success": bool(self.env.success(threshold)),
            "success_seen": bool(self.env.success_seen),
            "success_error": self.env.success_error,
            "max_reward": float(self.env.max_reward),
            "steps": int(self.env.steps),
            "policy_calls": int(call_index),
            "wall_time_s": float(elapsed),
            "initial_state_sha256": initial_state_hash,
            "video": video_result,
            "termination": "environment_done" if env_done else "max_steps",
        }

    def run_smoke(self, episodes: Optional[int] = None) -> Path:
        count = int(episodes or self.config["evaluation"].get("smoke_episodes", 10))
        horizon = int(self.config["evaluation"].get("smoke_horizon", 8))
        records_path = self.run_dir / "b0_smoke_episodes.jsonl"
        video_count = int(self.config["evaluation"].get("smoke_video_episodes", 2))
        for index in range(count):
            seed = int(self.config["evaluation"].get("seed_start", 100000)) + index
            video_path = self.run_dir / "videos" / "smoke_seed_{}.mp4".format(seed) if index < video_count else None
            record = self._run_episode(
                seed=seed,
                horizon=horizon,
                policy_seed=int(self.config["project"].get("seed", 20261110)) + seed,
                video_path=video_path,
                phase="B0_smoke",
            )
            append_jsonl(records_path, record)
        write_json(self.run_dir / "b0_smoke_summary.json", self._summarize(records_path))
        return records_path

    def run_b0_baseline(self, episodes: Optional[int] = None) -> Path:
        count = int(episodes or self.config["evaluation"].get("b0_baseline_episodes", 100))
        horizon = int(self.config["evaluation"].get("smoke_horizon", 8))
        records_path = self.run_dir / "b0_baseline_episodes.jsonl"
        for index in range(count):
            seed = int(self.config["evaluation"].get("seed_start", 100000)) + index
            record = self._run_episode(
                seed=seed,
                horizon=horizon,
                policy_seed=int(self.config["evaluation"].get("policy_seed_offset", 700000)) + seed,
                phase="B0_baseline",
            )
            append_jsonl(records_path, record)
        write_json(self.run_dir / "b0_baseline_summary.json", self._summarize(records_path))
        return records_path

    def _summarize(self, records_path: Path) -> Dict[str, Any]:
        from .core import load_jsonl
        rows = load_jsonl(records_path)
        if not rows:
            return {"n": 0}
        successes = sum(bool(row["success"]) for row in rows)
        return {
            "n": len(rows),
            "successes": int(successes),
            "success_rate": float(successes / len(rows)),
            "mean_steps": float(np.mean([row["steps"] for row in rows])),
            "mean_policy_calls": float(np.mean([row["policy_calls"] for row in rows])),
            "mean_wall_time_s": float(np.mean([row["wall_time_s"] for row in rows])),
        }

    def _stage_gate(self) -> Mapping[str, Any]:
        b2 = self.config["b2"]
        if str(b2.get("stage_gate_version")) != STAGE_GATE_VERSION:
            raise RuntimeError(
                "B2 stage gate version {!r} does not match the frozen geometry-derived "
                "version {!r}".format(b2.get("stage_gate_version"), STAGE_GATE_VERSION)
            )
        forbidden = ("z_gap_min_m", "z_gap_max_m", "max_xy_center_distance_m")
        if any(key in b2 for key in forbidden):
            raise RuntimeError(
                "B2 config still contains unfrozen numeric stage-gate bounds; the v1.1 "
                "protocol requires the live-geometry-derived gate only"
            )
        return {
            "stage_gate_version": STAGE_GATE_VERSION,
            "source": "live MuJoCo collision geometry",
            "conditions": [
                "0 < z_gap_m <= t_nut_m",
                "d_xy_m <= r_hole_m + r_peg_m",
                "z_gap_current < z_gap_previous",
            ],
        }

    def run_b1(self, phase: str = "pilot") -> Path:
        if phase not in B1_PHASES:
            raise ValueError("B1 phase must be one of {}, got {!r}".format(B1_PHASES, phase))
        evaluation = self.config["evaluation"]
        seed_ranges = validate_seed_ranges({
            "B0": (evaluation.get("seed_start", 100000),
                   evaluation.get("b0_baseline_episodes", 100)),
            "B1_pilot": (evaluation.get("b1_pilot_seed_start", 200000),
                         evaluation.get("b1_pilot_episodes", 20)),
            "B1_full": (evaluation.get("b1_full_seed_start", 200020),
                        evaluation.get("b1_full_episodes", 100)),
        })
        phase_key = "B1_{}".format(phase)
        seed_start, seed_end = seed_ranges[phase_key]
        count = seed_end - seed_start + 1

        requested_horizons = [int(x) for x in evaluation.get("horizons", [1, 2, 4, 8, 15])]
        horizons = validate_horizons(requested_horizons, self.prediction_horizon, self.n_obs_steps)
        reference_horizon = int(evaluation.get("b1_reference_horizon", 8))
        if reference_horizon not in horizons:
            raise ValueError(
                "B1 reference horizon h={} is not in horizons {}".format(reference_horizon, horizons)
            )

        records_path = self.run_dir / b1_records_filename(phase)
        ensure_new_records_path(records_path)
        b1_manifest = build_b1_run_manifest(
            config=self.config,
            max_steps=self.max_steps,
            runtime_manifest=self.manifest,
            device=self.device,
            phase=phase,
            seed_start=seed_start,
            seed_end=seed_end,
            horizons=horizons,
            records_file=records_path.name,
        )
        b1_manifest["reference_horizon"] = reference_horizon
        b1_manifest["seed_ranges"] = {name: list(value) for name, value in seed_ranges.items()}
        b1_manifest["note"] = (
            "Formal B1 count and environment are locked. Pilot and Full use "
            "disjoint seed intervals; B2 state collection is not part of B1."
        )
        write_json(self.run_dir / b1_run_filename(phase), b1_manifest)
        base_policy_seed = int(b1_manifest["policy_seed_offset"])
        env_fields = record_environment_fields(b1_manifest)
        for index in range(count):
            seed = seed_start + index
            paired_initial_hash = None
            for horizon in horizons:
                record = self._run_episode(
                    seed=seed,
                    horizon=horizon,
                    policy_seed=base_policy_seed + seed,
                    phase="B1_{}".format(phase),
                )
                record["b1_phase"] = phase
                record["b1_seed_start"] = seed_start
                record["b1_seed_end"] = seed_end
                record.update(env_fields)
                if paired_initial_hash is None:
                    paired_initial_hash = record["initial_state_sha256"]
                elif record["initial_state_sha256"] != paired_initial_hash:
                    raise RuntimeError(
                        "Initial state changed across horizons for seed {} ({} != {}). "
                        "Do not report this B1 run as paired; investigate environment RNG/reset.".format(
                            seed, record["initial_state_sha256"], paired_initial_hash
                        )
                    )
                record["paired_initial_state_verified"] = True
                append_jsonl(records_path, record)
        return records_path

    def _snapshot_path(self, state_record: Mapping[str, Any]) -> Path:
        path = Path(str(state_record["snapshot_file"]))
        return path if path.is_absolute() else (self.run_dir / path)

    def _validate_all_b2_snapshots(
        self,
        states: Sequence[Mapping[str, Any]],
        split: str,
    ) -> Path:
        thresholds = self.config["b2"].get("snapshot_validation", {})
        state_atol = float(thresholds.get("state_atol", 1e-7))
        observation_tol = float(thresholds.get("observation_mean_abs_tol", 1e-3))
        geometry_tol = float(thresholds.get("geometry_atol", 1e-6))
        validation_path = self.run_dir / "b2_{}_snapshot_validation.json".format(split)
        per_state: Dict[str, Any] = {}
        initialized = False
        for state_record in states:
            state_id = str(state_record["state_id"])
            try:
                snapshot_path = self._snapshot_path(state_record)
                snapshot = load_snapshot(snapshot_path, expected_sha256=state_record["snapshot_sha256"])
                validate_snapshot_reference(snapshot, state_record)
                if not initialized:
                    self.env.reset(int(state_record["source_seed"]))
                    initialized = True
                # Use the original policy observation to choose a reproducible probe.
                reset_policy_or_block(self.policy)
                seed_policy_rng(self.torch, 424242)
                probe_chunk = predict_full_future_chunk(
                    self.policy,
                    self.torch,
                    snapshot["validation_reference"]["policy_observation"],
                    self.device,
                    self.n_obs_steps,
                    self.prediction_horizon,
                )
                report = validate_snapshot_restore(
                    self.env,
                    snapshot,
                    self._env_action(probe_chunk[0]),
                    state_atol=state_atol,
                    observation_mean_abs_tol=observation_tol,
                    geometry_atol=geometry_tol,
                )
            except Exception as exc:
                report = {
                    "status": "BLOCKED",
                    "passed": False,
                    "error": "{}: {}".format(type(exc).__name__, exc),
                    "source_step": state_record["source_step"],
                }
            report["snapshot_sha256"] = state_record["snapshot_sha256"]
            per_state[state_id] = report

        failed_states = [state_id for state_id, report in per_state.items() if not report["passed"]]
        write_json(validation_path, {
            "split": split,
            "marker": "PREFLIGHT" if split == "preflight" else "B2",
            "scientific_data": split != "preflight",
            "status": "PASS" if per_state and not failed_states else "BLOCKED",
            "all_passed": bool(per_state) and not failed_states,
            "n_states": len(states),
            "failed_states": failed_states,
            "per_state": per_state,
            "thresholds": {
                "state_atol": state_atol,
                "observation_mean_abs_tol": observation_tol,
                "geometry_atol": geometry_tol,
            },
        })
        return validation_path

    def _run_b2_branch(
        self,
        snapshot: Mapping[str, Any],
        state_record: Mapping[str, Any],
        first_horizon: int,
        repeat_seed_value: int,
        split: str,
        repeat_index: int,
        randomized_order_index: int,
        order_seed: int,
        horizon_order: Sequence[int],
    ) -> Dict[str, Any]:
        # Restore the same snapshot anew before every horizon x repeat branch.
        self.env.restore(snapshot)
        source_step = int(state_record["source_step"])
        original = snapshot["validation_reference"]["sim_state"]
        restored = self.env.current_sim_state()
        state_atol = self.config["b2"].get("snapshot_validation", {}).get("state_atol", 1e-7)
        if (self.env.steps != source_step or snapshot["robosuite_internal"]["done"]
                or original.shape != restored.shape or not np.isfinite(restored).all()
                or not np.all(np.abs(original - restored) <= state_atol)):
            raise RuntimeError("B2 restored branch start disagrees with the original snapshot reference")
        reset_policy_or_block(self.policy)
        call_index = 0
        first_commitment = True
        env_done = False
        started = time.perf_counter()
        continuation_h = int(self.config["b2"]["continuation_horizon"])
        if continuation_h != 15:
            raise RuntimeError("B2 continuation horizon must be 15, got {}".format(continuation_h))
        noise_schedule: List[int] = []
        while self.env.steps < self.max_steps and not env_done:
            h = int(first_horizon if first_commitment else continuation_h)
            noise_seed = policy_noise_seed(repeat_seed_value, call_index)
            noise_schedule.append(int(noise_seed))
            seed_policy_rng(self.torch, noise_seed)
            chunk = predict_full_future_chunk(
                self.policy, self.torch, self.env.policy_observation(), self.device,
                self.n_obs_steps, self.prediction_horizon,
            )
            if not np.isfinite(chunk).all():
                raise RuntimeError("Non-finite B2 policy action chunk")
            execute_n = min(h, self.max_steps - self.env.steps)
            for action_index in range(execute_n):
                _, _, done, _ = self.env.step(self._env_action(chunk[action_index]), strict=True)
                if done:
                    env_done = True
                    break
            call_index += 1
            first_commitment = False
        elapsed = time.perf_counter() - started
        threshold = float(self.config["evaluation"].get("success_threshold", 0.99))
        success = self.env.success(threshold, strict=True)
        if self.env.success_error:
            raise RuntimeError("B2 task success predicate failed: {}".format(self.env.success_error))
        return {
            "phase": "B2",
            "split": split,
            "preflight": False,
            "state_id": state_record["state_id"],
            "source_seed": int(state_record["source_seed"]),
            "source_step": source_step,
            "horizon": int(first_horizon),
            "continuation_horizon": int(continuation_h),
            "repeat_index": int(repeat_index),
            "repeat_seed": int(repeat_seed_value),
            "branch_order_seed": int(order_seed),
            "randomized_order_index": int(randomized_order_index),
            "horizon_order": [int(value) for value in horizon_order],
            "policy_noise_seed_schedule": noise_schedule,
            "policy_reset_verified": True,
            "success": success,
            "success_seen": bool(self.env.success_seen),
            "success_error": self.env.success_error,
            "max_reward": float(self.env.max_reward),
            "steps_from_episode_start": int(self.env.steps),
            "steps_after_branch": int(self.env.steps - source_step),
            "policy_calls_after_branch": int(call_index),
            "wall_time_s": float(elapsed),
            **{key: state_record["geometry"][key] for key in B2_BRANCH_GEOMETRY_FIELDS},
            "snapshot_sha256": state_record["snapshot_sha256"],
            "snapshot_schema_version": int(snapshot.get("schema_version", -1)),
            "termination": "environment_done" if env_done else "max_steps",
        }

    def run_b2(self, split: str) -> Path:
        ensure_new_b2_branch_outputs(self.run_dir, split)
        gate = self._stage_gate()
        validate_formal_authorization(
            self.run_dir,
            split,
            self.manifest,
            config=self.config,
            project_root=self.project_root,
        )
        config_manifest_path = self.project_root / self.config["paths"]["b1_full_manifest"]
        b1_full_manifest = load_b1_full_manifest(config_manifest_path)
        b2_run_manifest = build_b2_run_manifest(
            config=self.config,
            runtime_manifest=self.manifest,
            b1_full_manifest=b1_full_manifest,
            split=split,
            command="b2-branch",
        )
        b2_run_manifest["stage_gate"] = dict(gate)
        prefix = "b2_{}_".format(split)
        run_path = self.run_dir / (prefix + "run.json")
        status_path = self.run_dir / (prefix + "status.json")
        records_path = self.run_dir / (prefix + "episodes.jsonl")
        # Exclusive creation reserves this run even if two invocations pass the
        # read-only precheck at the same time. The losing process writes nothing.
        with run_path.open("x", encoding="utf-8") as stream:
            json.dump(jsonable(b2_run_manifest), stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")

        progress: Dict[str, Any] = {"stage": "harvest inputs"}
        valid_records = 0
        try:
            manifest_path = self.run_dir / (prefix + "state_manifest.jsonl")
            harvest_path = self.run_dir / (prefix + "harvest_summary.json")
            states = load_jsonl(manifest_path)
            validate_state_manifest(states, split, self.config)
            harvest = json.loads(harvest_path.read_text(encoding="utf-8"))
            if (harvest.get("status") != "COMPLETE" or harvest.get("split") != split
                    or harvest.get("manifest_file") != manifest_path.name
                    or harvest.get("selected_source_seeds") != [item["source_seed"] for item in states]):
                raise RuntimeError("B2 requires a completed Harvest for the selected state manifest")
            env_fields = b2_record_environment_fields(b2_run_manifest)
            for state_record in states:
                if any(state_record.get(key) != value for key, value in env_fields.items()):
                    raise RuntimeError("B2 harvested environment mismatch for {}".format(state_record["state_id"]))

            other = "confirmation" if split == "discovery" else "discovery"
            other_manifest = self.run_dir / "b2_{}_state_manifest.jsonl".format(other)
            if other_manifest.is_file():
                other_states = load_jsonl(other_manifest)
                for key in ("source_seed", "state_id", "snapshot_sha256"):
                    shared = {item[key] for item in states} & {item[key] for item in other_states}
                    if shared:
                        raise RuntimeError("B2 split manifests share {} values: {}".format(key, sorted(shared)))

            progress = {"stage": "snapshot validation"}
            validation_path = self._validate_all_b2_snapshots(states, split)
            validation = json.loads(validation_path.read_text(encoding="utf-8"))
            if validation["all_passed"] is not True:
                progress["failed_states"] = validation["failed_states"]
                progress["snapshot_validation"] = validation_path.name
                raise RuntimeError("Independent snapshot validation failed for {}".format(validation["failed_states"]))
            require_passed_snapshot_validation(
                validation, split, {state["state_id"]: state["snapshot_sha256"] for state in states},
            )

            progress = {"stage": "branch execution"}
            for state_record in states:
                progress = {"stage": "branch execution", "state_id": state_record["state_id"]}
                snapshot_path = self._snapshot_path(state_record)
                snapshot = load_snapshot(snapshot_path, expected_sha256=state_record["snapshot_sha256"])
                source_seed = state_record["source_seed"]
                for repeat_index in range(self.config["b2"]["repeats_per_state_horizon"]):
                    order_seed = branch_order_seed(self.config, source_seed, repeat_index)
                    order = branch_order(self.config, source_seed, repeat_index)
                    repeat_seed_value = repeat_seed(self.config, source_seed, repeat_index)
                    for order_index, horizon in enumerate(order):
                        progress.update({"horizon": horizon, "repeat_index": repeat_index})
                        verify_snapshot_sha256(snapshot_path, state_record["snapshot_sha256"])
                        record = self._run_b2_branch(
                            snapshot=snapshot,
                            state_record=state_record,
                            first_horizon=horizon,
                            repeat_seed_value=repeat_seed_value,
                            split=split,
                            repeat_index=repeat_index,
                            randomized_order_index=order_index,
                            order_seed=order_seed,
                            horizon_order=order,
                        )
                        record.update(env_fields)
                        validate_b2_record(record, state_record, split, self.config, b2_run_manifest)
                        append_jsonl(records_path, record)
                        valid_records += 1

            progress = {"stage": "record completeness"}
            summary = validate_b2_records(
                load_jsonl(records_path), states, split, self.config, runtime_manifest=b2_run_manifest,
            )
            summary.update({
                "status": "COMPLETE",
                "records_file": records_path.name,
                "run_manifest": run_path.name,
                "snapshot_validation": validation_path.name,
                "stage_gate": dict(gate),
                "preflight": False,
            })
            write_json(self.run_dir / (prefix + "summary.json"), summary)
            write_json(status_path, {
                "status": "COMPLETE",
                "split": split,
                "completeness_verified": True,
                "snapshot_validation_all_passed": True,
                "n_branch_records": valid_records,
            })
        except Exception as exc:
            write_json(status_path, {
                "status": "BLOCKED",
                "split": split,
                "reason": "{}: {}".format(type(exc).__name__, exc),
                "success_error": getattr(self.env, "success_error", None),
                "partial_records": records_path.name if records_path.exists() else None,
                "valid_records_before_failure": valid_records,
                **progress,
            })
            raise
        return records_path
