from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

from .core import (
    append_jsonl,
    environment_fingerprint,
    jsonable,
    policy_noise_seed,
    seed_everything,
    seed_policy_rng,
    sha256_file,
    utc_run_id,
    validate_horizons,
    write_json,
)
from .env import EpisodeEnv, create_square_image_env, image_for_video
from .geometry import compute_square_clearance
from .policy import load_diffusion_policy_checkpoint, predict_full_future_chunk
from .snapshot import load_snapshot, save_snapshot, validate_snapshot_restore


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

        self.wrapper, self.env_meta = create_square_image_env(self.dp_root, self.dataset, self.shape_meta)
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
                obs, _, done, _ = self.env.step(chunk[action_index])
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

    def run_b1(self, episodes: Optional[int] = None, collect_b2_states: bool = False) -> Path:
        evaluation = self.config["evaluation"]
        count = int(episodes or evaluation.get("b1_pilot_episodes", 20))
        requested_horizons = [int(x) for x in evaluation.get("horizons", [1, 2, 4, 8, 16])]
        horizons = validate_horizons(requested_horizons, self.prediction_horizon, self.n_obs_steps)
        if collect_b2_states:
            stage_gate = self._stage_gate()
        else:
            stage_gate = None

        records_path = self.run_dir / "b1_episodes.jsonl"
        state_dir = self.run_dir / "states" / "b2_candidates"
        candidates: List[Dict[str, Any]] = []
        seed_start = int(evaluation.get("seed_start", 100000))
        base_policy_seed = int(evaluation.get("policy_seed_offset", 700000))
        for index in range(count):
            seed = seed_start + index
            paired_initial_hash = None
            for horizon in horizons:
                saved_this_episode = [False]

                def maybe_save_state(episode_env: EpisodeEnv, call_index: int) -> None:
                    if not collect_b2_states or horizon != int(self.config["b2"].get("continuation_horizon", 8)):
                        return
                    if saved_this_episode[0] or episode_env.success_seen:
                        return
                    try:
                        geometry = compute_square_clearance(episode_env.robosuite_env)
                    except Exception as exc:
                        # Geometry failures are explicit evidence; never replace with a radial proxy.
                        if not saved_this_episode[0]:
                            append_jsonl(self.run_dir / "b2_geometry_errors.jsonl", {
                                "source_seed": seed, "decision_index": call_index, "error": repr(exc)
                            })
                        return
                    if not (
                        float(stage_gate["z_gap_min_m"]) <= geometry["z_gap_m"] <= float(stage_gate["z_gap_max_m"])
                        and geometry["xy_center_distance_m"] <= float(stage_gate["max_xy_center_distance_m"])
                    ):
                        return
                    state_id = "sqmh_seed_{}_call_{}".format(seed, call_index)
                    snapshot = episode_env.snapshot()
                    path = state_dir / (state_id + ".pkl.gz")
                    save_snapshot(path, snapshot)
                    candidates.append({
                        "state_id": state_id,
                        "source_seed": seed,
                        "source_decision_index": call_index,
                        "snapshot_file": str(path.relative_to(self.run_dir)),
                        "snapshot_sha256": sha256_file(path),
                        "geometry": geometry,
                    })
                    saved_this_episode[0] = True

                record = self._run_episode(
                    seed=seed,
                    horizon=horizon,
                    policy_seed=base_policy_seed + seed,
                    decision_callback=maybe_save_state if collect_b2_states else None,
                    phase="B1",
                )
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

        if collect_b2_states:
            # Deterministic alternating split balances the two independent state sets
            # without looking at branch outcomes or success labels.
            candidates.sort(key=lambda item: (int(item["source_seed"]), int(item["source_decision_index"])))
            manifest_path = self.run_dir / "b2_state_manifest.jsonl"
            for index, item in enumerate(candidates):
                item["split"] = "discovery" if index % 2 == 0 else "confirmation"
                append_jsonl(manifest_path, item)
            write_json(self.run_dir / "b2_state_collection_summary.json", {
                "n_candidates": len(candidates),
                "n_discovery": sum(item["split"] == "discovery" for item in candidates),
                "n_confirmation": sum(item["split"] == "confirmation" for item in candidates),
                "stage_gate": stage_gate,
                "note": "State split is assigned before any B2 branch outcomes are observed.",
            })
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
                _, _, done, _ = self.env.step(chunk[action_index])
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
            self.config["evaluation"].get("horizons", [1, 2, 4, 8, 16]),
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
                    self.env, snapshot, probe_chunk[0],
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
