"""Full-episode evaluation of the component commitment arms."""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

from gate_b_v2.actions import rotation_6d_to_matrix
from gate_b_v2.core import jsonable, seed_everything, seed_policy_rng, sha256_array, sha256_file, sha256_tree
from gate_b_v2.env import EpisodeEnv
from gate_b_v2.geometry import _square_nut, _square_peg_info
from gate_b_v2.locks import load_fixed_project_config
from gate_b_v2.policy import predict_full_future_chunk, reset_policy_or_block
from gate_b_v2.runner import GateBExperiment, _resolve_runtime_paths

from .mechanism import (
    ACTION_DIM,
    ARMS,
    CHUNK_STEPS,
    MAX_STEPS,
    MID_OFFSET,
    GeometryState,
    MidDecision,
    choose_mid_actions,
    hole_coordinates,
)


GATE_B_ROOT = Path(__file__).resolve().parents[1] / "gate_b_v2"
ENV_ACTION_DIM = 7
DEVICE = "cuda:0"
ASSET_KEYS = ("checkpoint_sha256", "dataset_sha256", "dp_source_tree_sha256")
RUNTIME_KEYS = (
    "python", "torch", "torch_cuda", "cuda_available", "gpu_name",
    "robomimic", "robosuite", "mujoco_py", "device_requested",
)
INTERFACE_KEYS = (
    "checkpoint_use_ema", "prediction_horizon", "n_obs_steps", "n_action_steps_checkpoint",
    "available_future_actions", "action_dim", "abs_action", "rotation_rep", "env_action_dim",
    "env_name", "env_version_dataset", "max_steps", "env_kwargs",
)


def _verify_fields(live: dict, frozen: dict, keys: tuple[str, ...]) -> None:
    differences = [key for key in keys if key not in live or key not in frozen or live[key] != frozen[key]]
    if differences:
        raise RuntimeError(f"Component rollout differs from B1 Full for {', '.join(differences)}")


class EpisodeEnvWithTaskSuccess(EpisodeEnv):
    """Expose the per-step result of Gate B's strict task check."""

    task_success = None

    def success(self, threshold=None, *, strict=False):
        value = super().success(threshold, strict=strict)
        if strict:
            self.task_success = value
        return value

    def step(self, action, *, strict=False):
        self.task_success = None
        result = super().step(action, strict=strict)
        if strict and self.task_success is None:
            # EpisodeEnv can skip the strict call if info already reports success.
            self.success(strict=True)
        return result


def create_experiment(run_dir: Path) -> GateBExperiment:
    """Load the verified Gate B image policy and absolute OSC environment."""
    run_dir = Path(run_dir).resolve()
    if not run_dir.is_relative_to(GATE_B_ROOT.parent) or run_dir.is_relative_to(GATE_B_ROOT):
        raise ValueError("Component experiment run directory must be in EAI outside the frozen Gate B directory")
    frozen = json.loads((GATE_B_ROOT / "reports" / "b1_full_environment_manifest.json").read_text(encoding="utf-8"))
    config = load_fixed_project_config(GATE_B_ROOT)
    if config["evaluation"]["device"] != DEVICE or frozen["device_requested"] != DEVICE:
        raise RuntimeError(f"Component rollout requires the frozen device {DEVICE}")
    dp_root, checkpoint, dataset = _resolve_runtime_paths(config, GATE_B_ROOT, {})
    assets = {
        "checkpoint_sha256": sha256_file(checkpoint),
        "dataset_sha256": sha256_file(dataset),
        "dp_source_tree_sha256": sha256_tree(dp_root / "diffusion_policy"),
    }
    _verify_fields(assets, frozen, ASSET_KEYS)

    import torch

    if not torch.cuda.is_available() or torch.cuda.get_device_name(0) != frozen["gpu_name"]:
        raise RuntimeError(f"Component rollout requires {frozen['gpu_name']} on {DEVICE}")
    experiment = GateBExperiment(
        config, GATE_B_ROOT, dp_root, checkpoint, dataset, run_dir,
        max_steps_override=MAX_STEPS, write_environment_manifest=False,
    )
    try:
        _verify_fields(jsonable(experiment.manifest), frozen, ASSET_KEYS + RUNTIME_KEYS + INTERFACE_KEYS)
        env = experiment.env
        robot = env.robosuite_env.robots[0]
        controller = robot.controller
        if (
            experiment.max_steps != MAX_STEPS or experiment.n_obs_steps != 2
            or experiment.prediction_horizon != 16 or experiment.action_dim != ACTION_DIM
            or not experiment.abs_action or experiment.rotation_rep != "rotation_6d"
            or experiment.policy.device != torch.device(DEVICE)
            or env.robomimic_env.action_dimension != ENV_ACTION_DIM
            or controller.name != "OSC_POSE" or controller.use_delta or controller.control_dim != 6
            or controller.position_limits is not None or controller.orientation_limits is not None
            or robot.gripper.dof != 1
        ):
            raise RuntimeError("Unexpected Square-MH policy or absolute OSC action interface")
        experiment.env = EpisodeEnvWithTaskSuccess(experiment.wrapper, experiment.shape_meta, experiment.n_obs_steps, MAX_STEPS)
    except Exception:
        experiment.close()
        raise
    return experiment


def policy_noise_seed(seed: int, t: int, candidate: int) -> int:
    """Share draws at the same observation time and candidate index across arms."""
    value = 2_000_000 + (seed - 520_000) * 4_096 + 3 * t + candidate
    if not 0 <= t < MAX_STEPS or candidate not in (0, 1) or not 0 <= value < 2**31 - 1:
        raise ValueError(f"Invalid policy draw coordinates ({seed}, {t}, {candidate})")
    return value


class LiveTaskGeometry:
    """Read privileged simulator state for the outer-loop mechanism."""

    def __init__(self, robosuite_env):
        self.rs = robosuite_env
        self.sim = robosuite_env.sim
        self.robot = robosuite_env.robots[0]
        self.nut = _square_nut(robosuite_env)
        self.nut_body_id = int(robosuite_env.obj_body_id[self.nut.name])
        self.peg_geom_id = _square_peg_info(robosuite_env)["peg_geom_id"]
        self.site_name = self.robot.controller.eef_name
        self.site_id = self.sim.model.site_name2id(self.site_name)
        if self.site_id != self.robot.eef_site_id:
            raise RuntimeError("OSC controller and robot disagree on their controlled site")

    def provenance(self) -> dict:
        return {
            "privileged_outer_loop": True,
            "policy_observation_includes_geometry": False,
            "grasp_source": "robosuite _check_grasp(Panda gripper, SquareNut contact geoms)",
            "hole_center_source": "SquareNut body_xpos (aperture center)",
            "peg_axis_source": "peg1 collision geom center and world transform, local z pointing up",
            "eef_pose_source": "site_xpos and site_xmat for OSC controller eef_name",
            "nut_body_id": self.nut_body_id,
            "peg_geom_id": self.peg_geom_id,
            "eef_site": self.site_name,
            "eef_site_id": int(self.site_id),
        }

    def hole_center(self) -> np.ndarray:
        center = np.array(self.sim.data.body_xpos[self.nut_body_id], dtype=np.float64, copy=True)
        if not np.isfinite(center).all():
            raise FloatingPointError("Live SquareNut hole center is non-finite")
        return center

    def capture(self) -> GeometryState:
        data = self.sim.data
        eef_position = np.array(data.site_xpos[self.site_id], dtype=np.float64, copy=True)
        eef_rotation = np.array(data.site_xmat[self.site_id], dtype=np.float64, copy=True).reshape(3, 3)
        peg_origin = np.array(data.geom_xpos[self.peg_geom_id], dtype=np.float64, copy=True)
        peg_axis = np.asarray(data.geom_xmat[self.peg_geom_id], dtype=np.float64).reshape(3, 3)[:, 2].copy()
        if not all(np.isfinite(value).all() for value in (eef_position, eef_rotation, peg_origin, peg_axis)):
            raise FloatingPointError("Live OSC site or Square peg pose is non-finite")
        if peg_axis[2] == 0.0:
            raise RuntimeError("Square peg collision geometry has no upward axis")
        peg_axis *= np.sign(peg_axis[2]) / np.linalg.norm(peg_axis)
        return GeometryState(
            hole_center=self.hole_center(),
            eef_position=eef_position,
            eef_rotation=eef_rotation,
            peg_origin=peg_origin,
            peg_axis=peg_axis,
            grasped=bool(self.rs._check_grasp(self.robot.gripper, self.nut.contact_geoms)),
        )


def _osc_commands(experiment: GateBExperiment, actions: np.ndarray) -> np.ndarray:
    commands = np.stack([experiment._env_action(action) for action in actions])
    if commands.shape != (len(actions), ENV_ACTION_DIM) or not np.isfinite(commands).all():
        raise ValueError("Expected finite 7-D absolute OSC commands")
    return commands


def _mid_evidence(
    t: int,
    decision: MidDecision,
    anchor: GeometryState,
    mid: GeometryState,
    first_success_before_mid: int | None,
    commands: np.ndarray,
    actual_centers: list[np.ndarray],
) -> dict:
    issued_rotations = Rotation.from_rotvec(commands[:, 3:6])
    new_rotations = Rotation.from_matrix(np.stack([rotation_6d_to_matrix(row[3:9]) for row in decision.new_actions]))
    offset = mid.grasp_offset
    requested_holes = commands[:, :3] + issued_rotations.apply(offset)
    new_holes = decision.new_actions[:, :3] + new_rotations.apply(offset)
    requested_axial, _ = hole_coordinates(requested_holes, mid)
    minus_old = requested_axial - decision.old_axial_m
    minus_new = requested_axial - decision.new_axial_m
    lateral_error = requested_holes - new_holes - minus_new[:, None] * mid.peg_axis
    actual_axial, actual_lateral = hole_coordinates(np.vstack([mid.hole_center, *actual_centers]), mid)
    return {
        "t": t,
        "eligible": decision.eligible,
        "admissible": decision.admissible,
        "decision": decision.decision,
        "chosen_candidate": decision.chosen_candidate,
        "pre_success": first_success_before_mid is None,
        "first_success_before_mid": first_success_before_mid,
        "mid_grasped": mid.grasped,
        "anchor_grasped": anchor.grasped,
        "all_commands_closed": decision.all_commands_closed,
        "stall": decision.stall,
        "planned_down_m": decision.planned_down_m,
        "actual_down_m": decision.actual_down_m,
        "anchor_grasp_offset_eef_m": anchor.grasp_offset.tolist(),
        "mid_grasp_offset_eef_m": mid.grasp_offset.tolist(),
        "peg_axis_world": mid.peg_axis.tolist(),
        "peg_origin_world_m": mid.peg_origin.tolist(),
        "old_action_indices": list(range(MID_OFFSET, MID_OFFSET + len(commands))),
        "new_action_indices": list(range(len(commands))),
        "axial_rms_m": decision.axial_rms_m,
        "axial_max_abs_m": decision.axial_max_abs_m,
        "candidate_axial_rms_m": list(decision.candidate_axial_rms_m),
        "old_hole_axial_m": decision.old_axial_m.tolist(),
        "new_hole_axial_m": decision.new_axial_m.tolist(),
        "issued_hole_axial_minus_old_m": minus_old.tolist(),
        "issued_hole_axial_minus_new_m": minus_new.tolist(),
        "issued_hole_axial_minus_new_rms_m": float(np.sqrt(np.mean(np.square(minus_new)))),
        "issued_hole_axial_minus_new_max_abs_m": float(np.max(np.abs(minus_new))),
        "issued_hole_lateral_max_error_m": float(np.max(np.linalg.norm(lateral_error, axis=1))),
        "issued_orientation_max_error_rad": float(np.max((new_rotations.inv() * issued_rotations).magnitude())),
        "issued_gripper_max_abs_error": float(np.max(np.abs(commands[:, -1] - decision.new_actions[:, -1]))),
        "actual_hole_axial_start_m": float(actual_axial[0]),
        "actual_hole_axial_end_m": float(actual_axial[-1]),
        "actual_hole_lateral_start_m": float(actual_lateral[0]),
        "actual_hole_lateral_end_m": float(actual_lateral[-1]),
        "actual_hole_upward_travel_m": float(np.maximum(0.0, np.diff(actual_axial)).sum()),
        "actual_hole_axial_m": actual_axial.tolist(),
        "actual_hole_lateral_m": actual_lateral.tolist(),
    }


def run_episode(experiment: GateBExperiment, seed: int, arm: str) -> dict:
    """Run 500 physical control steps and record matched-time policy samples."""
    if arm not in ARMS:
        raise ValueError(f"Unknown component commitment arm {arm!r}")
    if experiment.max_steps != MAX_STEPS:
        raise ValueError(f"Component rollout requires exactly {MAX_STEPS} physical steps")
    seed = int(seed)
    policy_noise_seed(seed, 0, 0)
    started = time.perf_counter()
    env = experiment.env
    seed_everything(seed)
    env.reset(seed)
    initial_state_hash = env.initial_state_hash()
    reset_policy_or_block(experiment.policy)
    geometry = LiveTaskGeometry(env.robosuite_env) if arm != "fixed15" else None

    query_schedule = []
    events = []
    task_success_bits = []
    inference_seconds = 0.0
    first_success_step = None

    def sample(t: int, phase: str, count: int) -> list[np.ndarray]:
        nonlocal inference_seconds
        observation = env.policy_observation()
        chunks = []
        seeds = [policy_noise_seed(seed, t, index) for index in range(count)]
        for noise_seed in seeds:
            seed_policy_rng(experiment.torch, noise_seed)
            sample_started = time.perf_counter()
            chunk = predict_full_future_chunk(
                experiment.policy, experiment.torch, observation, experiment.device,
                experiment.n_obs_steps, experiment.prediction_horizon,
            )
            inference_seconds += time.perf_counter() - sample_started
            if chunk.shape != (CHUNK_STEPS, ACTION_DIM) or not np.isfinite(chunk).all():
                raise ValueError("Expected a complete finite 15-by-10 action chunk")
            chunks.append(chunk)
        query_schedule.append({
            "t": t,
            "phase": phase,
            "candidate_count": count,
            "noise_seeds": seeds,
            "chunk_sha256": [sha256_array(chunk) for chunk in chunks],
        })
        return chunks

    def take_steps(commands: np.ndarray, track_geometry: LiveTaskGeometry | None = None) -> list[np.ndarray]:
        nonlocal first_success_step
        centers = []
        for command in commands:
            expected_step = env.steps + 1
            _, _, done, _ = env.step(command, strict=True)
            if env.steps != expected_step:
                raise RuntimeError(f"Expected exactly one physical step, got counter {env.steps} instead of {expected_step}")
            if done and env.steps < MAX_STEPS:
                raise RuntimeError(f"Square-MH terminated early at step {env.steps}")
            if first_success_step is None and env.task_success:
                first_success_step = int(env.steps)
            task_success_bits.append("1" if env.task_success else "0")
            if track_geometry is not None:
                centers.append(track_geometry.hole_center())
        return centers

    for anchor_t in range(0, MAX_STEPS, CHUNK_STEPS):
        if env.steps != anchor_t:
            raise RuntimeError(f"Expected physical anchor time {anchor_t}, got {env.steps}")
        block_steps = min(CHUNK_STEPS, MAX_STEPS - anchor_t)
        anchor_state = geometry.capture() if geometry is not None and block_steps > MID_OFFSET else None
        anchor_chunk, = sample(anchor_t, "anchor", 1)
        prefix_steps = block_steps if geometry is None else min(block_steps, MID_OFFSET)
        take_steps(_osc_commands(experiment, anchor_chunk[:prefix_steps]))
        if anchor_state is None:
            continue

        mid_t = int(env.steps)
        mid_state = geometry.capture()
        fresh0, fresh1 = sample(mid_t, "mid", 2)
        first_success_before_mid = first_success_step
        decision = choose_mid_actions(
            arm, anchor_chunk, (fresh0, fresh1), anchor_state, mid_state,
            block_steps - prefix_steps, first_success_before_mid is None,
        )
        commands = _osc_commands(experiment, decision.actions)
        actual_centers = take_steps(commands, geometry)
        events.append(_mid_evidence(mid_t, decision, anchor_state, mid_state, first_success_before_mid, commands, actual_centers))

    policy_queries = len(query_schedule)
    policy_samples = sum(query["candidate_count"] for query in query_schedule)
    expected_budget = (34, 34, 0) if geometry is None else (67, 100, 33)
    if env.steps != MAX_STEPS or (policy_queries, policy_samples, len(events)) != expected_budget:
        raise RuntimeError("Square-MH rollout did not complete the frozen step and sampling schedule")
    return {
        "seed": seed,
        "arm": arm,
        "initial_state_hash": initial_state_hash,
        "first_chunk_sha256": query_schedule[0]["chunk_sha256"][0],
        "steps": int(env.steps),
        "success": task_success_bits[-1] == "1",
        "first_success_step": first_success_step,
        "task_success_bits": "".join(task_success_bits),
        "policy_queries": policy_queries,
        "policy_samples": policy_samples,
        "inference_seconds": inference_seconds,
        "wall_seconds": time.perf_counter() - started,
        "query_schedule": query_schedule,
        "events": events,
        "task_geometry": geometry.provenance() if geometry is not None else None,
    }
