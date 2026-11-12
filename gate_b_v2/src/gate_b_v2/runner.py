from __future__ import annotations

import json
import math
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
    policy_noise_seed,
    seed_everything,
    seed_policy_rng,
    sha256_file,
    utc_run_id,
    validate_horizons,
    validate_seed_ranges,
    write_json,
)
from .actions import undo_transform_action
from .env import EpisodeEnv, create_square_image_env, image_for_video
from .locks import build_b1_run_manifest, record_environment_fields
from .policy import load_diffusion_policy_checkpoint, predict_full_future_chunk
from .snapshot import load_snapshot, validate_snapshot_restore


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
        try:
            self.policy.reset()
        except Exception:
            pass

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
        gate = self.config["b2"].get("stage_gate", {})
        required = ("z_gap_min_m", "z_gap_max_m", "max_xy_center_distance_m")
        if not bool(gate.get("frozen", False)) or any(gate.get(key) is None for key in required):
            raise RuntimeError(
                "B2 stage gate is not frozen. The protocol requires pre-registering "
                "z-gap and XY-distance bounds before examining outcomes. Do not invent them."
            )
        if float(gate["z_gap_min_m"]) >= float(gate["z_gap_max_m"]):
            raise ValueError("B2 z_gap_min_m must be less than z_gap_max_m")
        return gate

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

    def _run_b2_branch(
        self,
        snapshot: Mapping[str, Any],
        state_record: Mapping[str, Any],
        first_horizon: int,
        repeat_seed: int,
        split: str,
    ) -> Dict[str, Any]:
        self.env.restore(snapshot)
        try:
            self.policy.reset()
        except Exception:
            pass
        call_index = 0
        first_commitment = True
        env_done = False
        started = time.perf_counter()
        continuation_h = int(self.config["b2"].get("continuation_horizon", 8))
        while self.env.steps < self.max_steps and not env_done:
            h = int(first_horizon if first_commitment else continuation_h)
            seed_policy_rng(self.torch, policy_noise_seed(repeat_seed, call_index))
            chunk = predict_full_future_chunk(
                self.policy, self.torch, self.env.policy_observation(), self.device,
                self.n_obs_steps, self.prediction_horizon,
            )
            execute_n = min(h, self.max_steps - self.env.steps)
            for action_index in range(execute_n):
                _, _, done, _ = self.env.step(self._env_action(chunk[action_index]))
                if done:
                    env_done = True
                    break
            call_index += 1
            first_commitment = False
        elapsed = time.perf_counter() - started
        threshold = float(self.config["evaluation"].get("success_threshold", 0.99))
        geometry = state_record["geometry"]
        return {
            "phase": "B2",
            "split": split,
            "state_id": state_record["state_id"],
            "source_seed": int(state_record["source_seed"]),
            "horizon": int(first_horizon),
            "repeat_seed": int(repeat_seed),
            "success": bool(self.env.success(threshold)),
            "success_seen": bool(self.env.success_seen),
            "success_error": self.env.success_error,
            "max_reward": float(self.env.max_reward),
            "steps_from_episode_start": int(self.env.steps),
            "steps_after_branch": int(self.env.steps - int(snapshot["episode"]["steps"])),
            "policy_calls_after_branch": int(call_index),
            "wall_time_s": float(elapsed),
            "clearance_m": float(geometry["clearance_m"]),
            "z_gap_m": float(geometry["z_gap_m"]),
            "dx_m": float(geometry["dx_m"]),
            "dy_m": float(geometry["dy_m"]),
            "relative_yaw_rad": float(geometry["relative_yaw_rad"]),
            "snapshot_sha256": state_record["snapshot_sha256"],
            "termination": "environment_done" if env_done else "max_steps",
        }

    def run_b2(self, split: str) -> Path:
        if split not in ("discovery", "confirmation"):
            raise ValueError("split must be discovery or confirmation")
        self._stage_gate()
        from .core import load_jsonl
        manifest_path = self.run_dir / "b2_state_manifest.jsonl"
        if not manifest_path.is_file():
            raise FileNotFoundError("B2 state manifest not found: {}".format(manifest_path))
        all_states = load_jsonl(manifest_path)
        states = [item for item in all_states if item.get("split") == split]
        minimum = int(self.config["b2"].get("min_{}_states".format(split), 30))
        if len(states) < minimum:
            raise RuntimeError(
                "B2 {} set has {} states; protocol requires at least {} independent states".format(
                    split, len(states), minimum
                )
            )

        horizons = validate_horizons(
            self.config["evaluation"].get("horizons", [1, 2, 4, 8, 15]),
            self.prediction_horizon,
            self.n_obs_steps,
        )
        repeats = int(self.config["b2"].get("repeats_per_state_horizon", 3))
        records_path = self.run_dir / "b2_{}_episodes.jsonl".format(split)
        validation_path = self.run_dir / "b2_snapshot_validation_{}.json".format(split)
        validated = validation_path.exists()
        for state_index, state_record in enumerate(states):
            snapshot_path = self.run_dir / state_record["snapshot_file"]
            if not snapshot_path.is_file():
                raise FileNotFoundError("Snapshot missing: {}".format(snapshot_path))
            if sha256_file(snapshot_path) != state_record["snapshot_sha256"]:
                raise RuntimeError("Snapshot SHA256 mismatch: {}".format(snapshot_path))
            snapshot = load_snapshot(snapshot_path)
            # Initialise a live renderer/environment before the first reset_to.
            if state_index == 0 and not validated:
                self.env.reset(int(state_record["source_seed"]))
                self.env.restore(snapshot)
                seed_policy_rng(self.torch, 1234567)
                probe_chunk = predict_full_future_chunk(
                    self.policy, self.torch, self.env.policy_observation(), self.device,
                    self.n_obs_steps, self.prediction_horizon,
                )
                thresholds = self.config["b2"].get("snapshot_validation", {})
                report = validate_snapshot_restore(
                    self.env, snapshot, self._env_action(probe_chunk[0]),
                    state_atol=float(thresholds.get("state_atol", 1e-7)),
                    observation_mean_abs_tol=float(thresholds.get("observation_mean_abs_tol", 1e-3)),
                )
                write_json(validation_path, report)
                if not report["passed"]:
                    write_json(self.run_dir / "b2_status.json", {
                        "status": "BLOCKED",
                        "reason": "Snapshot/restore deterministic replay validation failed",
                        "validation": report,
                    })
                    raise RuntimeError("B2 BLOCKED: snapshot/restore validation failed; see b2_snapshot_validation_{}.json".format(split))
                validated = True

            for horizon in horizons:
                for repeat in range(repeats):
                    # Same repeat seed across horizons gives common policy noise at
                    # the shared branch point; subsequent observations naturally diverge.
                    repeat_seed = int(self.config["project"].get("seed", 20261110)) + int(state_record["source_seed"]) * 17 + repeat
                    record = self._run_b2_branch(
                        snapshot=snapshot,
                        state_record=state_record,
                        first_horizon=horizon,
                        repeat_seed=repeat_seed,
                        split=split,
                    )
                    record["repeat_index"] = repeat
                    append_jsonl(records_path, record)
        write_json(self.run_dir / "b2_{}_summary.json".format(split), {
            "status": "COMPLETE",
            "n_states": len(states),
            "horizons": horizons,
            "repeats_per_state_horizon": repeats,
            "n_branch_episodes": len(states) * len(horizons) * repeats,
            "snapshot_validation": str(validation_path),
        })
        return records_path
