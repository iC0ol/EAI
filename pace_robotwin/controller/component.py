"""Carry one TCP translation component across a RoboTwin PACE query."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

import numpy as np
from scipy.spatial.transform import Rotation

from .kinematics import AlohaKinematics, UrdfArm


CHUNK_SHAPE = (50, 14)
MAX_WINDOW = 8
MIN_WINDOW = 3
MIN_PROGRESS_M = 0.004
MIN_DIRECTION_COSINE = sqrt(0.5)
CLOSED_MAX = 0.25
OPEN_MIN = 0.75
MAX_GRIPPER_RANGE = 0.15
MAX_AXIAL_RMS_M = 0.010
MAX_AXIAL_ABS_M = 0.020
MAX_JOINT_DELTA_RAD = 0.12
MAX_POSITION_RESIDUAL_M = 0.0005
MAX_ROTATION_RESIDUAL_DEG = 0.5

# Numerical settings of the six-dimensional damped least squares solver.
_IK_DAMPING = 0.001
_IK_ITERATIONS = 30
_IK_GOAL = 1e-8
_DAMPING_MATRIX = _IK_DAMPING**2 * np.eye(6)


@dataclass(frozen=True)
class ComponentResult:
    actions: np.ndarray
    audit: dict


def apply_component(
    new_raw: np.ndarray,
    state: np.ndarray,
    h: int,
    *,
    kinematics: AlohaKinematics,
    previous_raw: np.ndarray | None = None,
    prev_h: int | None = None,
) -> ComponentResult:
    """Transform the execution prefix after PACE has chosen ``h`` from ``new_raw``.

    ``state`` is the official 14-channel observation, in the same order as
    the commands: six left joints, left gripper, six right joints, right
    gripper. Supply the preceding raw policy chunk and its executed action
    count together. Callers execute ``actions[:h]`` and retain ``new_raw``.

    ``eligible`` in the audit records the geometry gate. ``applied`` records
    whether the output joints actually changed after per-arm IK validation.
    Indices in the window and in the per-waypoint audit start at zero.
    """
    new_raw = _action_chunk(new_raw, "new_raw")
    state = np.asarray(state, dtype=np.float64)
    if state.shape != (CHUNK_SHAPE[1],) or not np.isfinite(state).all():
        raise ValueError("state must have 14 finite joint and gripper channels")
    h = _action_count(h, "h")
    if (previous_raw is None) != (prev_h is None):
        raise ValueError("previous_raw and its executed action count prev_h must be provided together")

    output = new_raw.copy()
    if previous_raw is None:
        return _unchanged(output, h, None, 0, "no_previous_chunk")
    previous_raw = _action_chunk(previous_raw, "previous_raw")
    prev_h = _action_count(prev_h, "prev_h")
    window = min(MAX_WINDOW, CHUNK_SHAPE[0] - prev_h, h)
    if window < MIN_WINDOW:
        return _unchanged(output, h, prev_h, window, "short_overlap")

    old = previous_raw[prev_h:prev_h + window]
    arms = {}
    for side, model, joints, gripper in (
        ("left", kinematics.left, slice(0, 6), 6),
        ("right", kinematics.right, slice(7, 13), 13),
    ):
        audit = _arm_audit(window)
        _apply_arm(
            model,
            previous_raw[prev_h - 1, joints],
            old[:, joints],
            new_raw[:window, joints],
            state[joints],
            np.concatenate((old[:, gripper], new_raw[:window, gripper], state[gripper:gripper + 1])),
            output[:window, joints],
            audit,
        )
        arms[side] = audit
    return ComponentResult(output, {"h": h, "prev_h": prev_h, "window": window, "arms": arms})


def _action_chunk(value: np.ndarray, name: str) -> np.ndarray:
    result = np.asarray(value)
    if (
        result.shape != CHUNK_SHAPE
        or not np.issubdtype(result.dtype, np.floating)
        or not np.isfinite(result).all()
    ):
        raise ValueError(f"{name} must be a finite floating-point {CHUNK_SHAPE} action chunk")
    return result


def _action_count(value: int, name: str) -> int:
    if (
        isinstance(value, (bool, np.bool_))
        or not isinstance(value, (int, np.integer))
        or not 1 <= value <= CHUNK_SHAPE[0]
    ):
        raise ValueError(f"{name} must be an action count from 1 to {CHUNK_SHAPE[0]}")
    return int(value)


def _arm_audit(window: int) -> dict:
    return {
        "eligible": False,
        "applied": False,
        "release_reason": None,
        "axis": None,
        "old_last_executed_tcp_m": None,
        "current_tcp_m": None,
        "old_tcp_m": [],
        "new_tcp_m": [],
        "old_displacement_m": None,
        "new_displacement_m": None,
        "old_progress_m": None,
        "new_progress_m": None,
        "direction_cosine": None,
        "gripper_state": None,
        "gripper_min": None,
        "gripper_max": None,
        "gripper_range": None,
        "pair_axial_difference_m": [],
        "axial_rms_m": None,
        "axial_max_abs_m": None,
        "proposed_axial_m": [0.0] * window,
        "actual_axial_m": [0.0] * window,
        "actual_lateral_m": [0.0] * window,
        "actual_rotation_change_deg": [0.0] * window,
        "actual_position_residual_m": [0.0] * window,
        "failed_step": None,
        "ik_steps": [],
    }


def _unchanged(output: np.ndarray, h: int, prev_h: int | None, window: int, reason: str) -> ComponentResult:
    arms = {side: _arm_audit(window) for side in ("left", "right")}
    for audit in arms.values():
        audit["release_reason"] = reason
    return ComponentResult(output, {"h": h, "prev_h": prev_h, "window": window, "arms": arms})


def _arm_gate(
    old_start: np.ndarray,
    current: np.ndarray,
    old_positions: np.ndarray,
    new_positions: np.ndarray,
    grippers: np.ndarray,
    audit: dict,
) -> str | None:
    old_advance = old_positions[-1] - old_start
    new_advance = new_positions[-1] - current
    old_length = float(np.linalg.norm(old_advance))
    new_length = float(np.linalg.norm(new_advance))
    grip_min = float(np.min(grippers))
    grip_max = float(np.max(grippers))
    grip_range = grip_max - grip_min
    grip_state = None
    if grip_max <= CLOSED_MAX:
        grip_state = "closed"
    elif grip_min >= OPEN_MIN:
        grip_state = "open"
    audit.update(
        old_last_executed_tcp_m=old_start.tolist(),
        current_tcp_m=current.tolist(),
        old_tcp_m=old_positions.tolist(),
        new_tcp_m=new_positions.tolist(),
        old_displacement_m=old_advance.tolist(),
        new_displacement_m=new_advance.tolist(),
        old_progress_m=old_length,
        new_progress_m=new_length,
        gripper_state=grip_state,
        gripper_min=grip_min,
        gripper_max=grip_max,
        gripper_range=grip_range,
    )
    if old_length > 0:
        axis = old_advance / old_length
        differences = (old_positions - new_positions) @ axis
        audit.update(
            axis=axis.tolist(),
            pair_axial_difference_m=differences.tolist(),
            axial_rms_m=float(np.sqrt(np.mean(np.square(differences)))),
            axial_max_abs_m=float(np.max(np.abs(differences))),
        )
        if new_length > 0:
            cosine = (new_advance @ axis) / new_length
            audit["direction_cosine"] = float(np.clip(cosine, -1.0, 1.0))

    if old_length < MIN_PROGRESS_M:
        return "old_inactive"
    if new_length < MIN_PROGRESS_M:
        return "new_inactive"
    if audit["direction_cosine"] < MIN_DIRECTION_COSINE:
        return "direction_mismatch"
    if grip_state is None:
        return "gripper_state"
    if grip_range > MAX_GRIPPER_RANGE:
        return "gripper_range"
    if audit["axial_rms_m"] > MAX_AXIAL_RMS_M:
        return "axial_rms"
    if audit["axial_max_abs_m"] > MAX_AXIAL_ABS_M:
        return "axial_max"
    return None


def _rotation_error(target: np.ndarray, current: np.ndarray) -> np.ndarray:
    return Rotation.from_matrix(target @ current.T).as_rotvec()


def _inverse(
    model: UrdfArm, seed: np.ndarray, target_position: np.ndarray, target_rotation: np.ndarray,
) -> tuple[np.ndarray, int]:
    q = seed.copy()
    for iteration in range(_IK_ITERATIONS):
        position, rotation, jacobian = model.forward_jacobian(q)
        translation_error = target_position - position
        rotation_error = _rotation_error(target_rotation, rotation)
        if np.linalg.norm(translation_error) <= _IK_GOAL and np.linalg.norm(rotation_error) <= _IK_GOAL:
            return q, iteration
        error = np.concatenate((translation_error, rotation_error))
        delta = jacobian.T @ np.linalg.solve(jacobian @ jacobian.T + _DAMPING_MATRIX, error)
        q += delta
        if not np.isfinite(q).all():
            raise FloatingPointError("Non-finite IK update")
    return q, _IK_ITERATIONS


def _inside_limits(model: UrdfArm, q: np.ndarray) -> bool:
    return bool(np.all(q >= model.lower) and np.all(q <= model.upper))


def _apply_arm(
    model: UrdfArm,
    old_start_q: np.ndarray,
    old_q: np.ndarray,
    new_q: np.ndarray,
    current_q: np.ndarray,
    grippers: np.ndarray,
    output: np.ndarray,
    audit: dict,
) -> None:
    old_start, _ = model.forward(old_start_q)
    current, _ = model.forward(current_q)
    old_positions = np.stack([model.forward(q)[0] for q in old_q])
    new_poses = [model.forward(q) for q in new_q]
    new_positions = np.stack([position for position, _ in new_poses])
    new_rotations = np.stack([rotation for _, rotation in new_poses])
    reason = _arm_gate(old_start, current, old_positions, new_positions, grippers, audit)
    audit["release_reason"] = reason
    if reason is not None:
        return

    audit["eligible"] = True
    axis = np.asarray(audit["axis"])
    window = len(new_q)
    weights = 1 - np.arange(window, dtype=np.float64) / (window - 1)
    proposed = weights * np.asarray(audit["pair_axial_difference_m"])
    proposed[-1] = 0.0
    audit["proposed_axial_m"] = proposed.tolist()
    # Until every waypoint passes, the executed window is the original one.
    audit["actual_position_residual_m"] = np.abs(proposed).tolist()
    adjusted = new_q.copy()
    for step, shift in enumerate(proposed):
        candidate, report = _adjust_step(
            model, new_q[step], new_positions[step], new_rotations[step], axis, float(shift),
        )
        audit["ik_steps"].append(report)
        if report["release_reason"] is not None:
            audit["release_reason"] = report["release_reason"]
            audit["failed_step"] = step
            return
        adjusted[step] = candidate

    output[:] = adjusted
    audit["applied"] = bool(np.any(adjusted != new_q))
    if not audit["applied"]:
        audit["release_reason"] = "no_joint_change"
    audit["actual_axial_m"] = [step["axial_m"] for step in audit["ik_steps"]]
    audit["actual_lateral_m"] = [step["lateral_m"] for step in audit["ik_steps"]]
    audit["actual_rotation_change_deg"] = [step["rotation_residual_deg"] for step in audit["ik_steps"]]
    audit["actual_position_residual_m"] = [step["position_residual_m"] for step in audit["ik_steps"]]


def _adjust_step(
    model: UrdfArm,
    new_q: np.ndarray,
    position: np.ndarray,
    rotation: np.ndarray,
    axis: np.ndarray,
    shift: float,
) -> tuple[np.ndarray, dict]:
    seed = np.asarray(new_q, dtype=np.float64)
    target = position + shift * axis
    iterations = 0
    q = seed
    candidate = new_q
    achieved_position = position
    achieved_rotation = rotation
    seed_in_limits = _inside_limits(model, seed)
    if shift != 0 and seed_in_limits:
        try:
            q, iterations = _inverse(model, seed, target, rotation)
            candidate = q.astype(new_q.dtype)
            if not np.isfinite(candidate).all():
                raise FloatingPointError("Non-finite joint command")
            achieved_position, achieved_rotation = model.forward(candidate)
        except (FloatingPointError, np.linalg.LinAlgError):
            return new_q, {"release_reason": "ik_numerical_failure"}

    change = achieved_position - position
    axial = float(change @ axis)
    position_error = float(np.linalg.norm(target - achieved_position))
    rotation_error = 0.0
    if shift:
        rotation_error = float(np.rad2deg(np.linalg.norm(_rotation_error(rotation, achieved_rotation))))
    joint_delta = float(max(np.max(np.abs(q - seed)), np.max(np.abs(candidate - seed))))
    inside = seed_in_limits and _inside_limits(model, q) and _inside_limits(model, candidate)
    reason = None
    if not inside:
        reason = "ik_joint_limit"
    elif joint_delta > MAX_JOINT_DELTA_RAD:
        reason = "ik_joint_delta"
    elif position_error > MAX_POSITION_RESIDUAL_M:
        reason = "ik_position_residual"
    elif rotation_error > MAX_ROTATION_RESIDUAL_DEG:
        reason = "ik_rotation_residual"

    return candidate, {
        "release_reason": reason,
        "iterations": iterations,
        "axial_m": axial,
        "lateral_m": float(np.linalg.norm(change - axial * axis)),
        "position_residual_m": position_error,
        "rotation_residual_deg": rotation_error,
        "max_joint_delta_rad": joint_delta,
        "inside_joint_limits": inside,
    }
