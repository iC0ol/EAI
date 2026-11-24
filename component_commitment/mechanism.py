"""Geometry and mid-block action selection for Square-MH."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.spatial.transform import Rotation

from gate_b_v2.actions import rotation_6d_to_matrix


ARMS = ("fixed15", "refresh", "smooth", "always_split", "adaptive")
CHUNK_STEPS = 15
MID_OFFSET = 6
MAX_STEPS = 500
ACTION_DIM = 10
LATERAL_LIMIT_M = 0.12
AXIAL_RMS_LIMIT_M = 0.010
AXIAL_MAX_LIMIT_M = 0.020
STALL_MIN_PLANNED_DOWN_M = 0.004
STALL_MIN_PROGRESS_FRACTION = 0.25
SMOOTH_OLD_WEIGHTS = (0.75, 0.50, 0.25)


@dataclass(frozen=True)
class GeometryState:
    hole_center: np.ndarray
    eef_position: np.ndarray
    eef_rotation: np.ndarray
    peg_origin: np.ndarray
    peg_axis: np.ndarray
    grasped: bool

    @property
    def grasp_offset(self) -> np.ndarray:
        """Offset from OSC's controlled site to the hole in the site frame."""
        return self.eef_rotation.T @ (self.hole_center - self.eef_position)


@dataclass(frozen=True)
class MidDecision:
    actions: np.ndarray
    new_actions: np.ndarray
    chosen_candidate: int
    decision: str
    eligible: bool
    admissible: bool
    all_commands_closed: bool
    stall: bool
    planned_down_m: float
    actual_down_m: float
    axial_rms_m: float
    axial_max_abs_m: float
    old_axial_m: np.ndarray
    new_axial_m: np.ndarray
    candidate_axial_rms_m: tuple[float, float]


def hole_coordinates(
    centers: np.ndarray, state: GeometryState,
) -> tuple[np.ndarray, np.ndarray]:
    """Signed height from the peg collision center and distance to its axis."""
    relative = np.asarray(centers, dtype=np.float64) - state.peg_origin
    axial = relative @ state.peg_axis
    lateral = relative - np.expand_dims(axial, axis=-1) * state.peg_axis
    return axial, np.linalg.norm(lateral, axis=-1)


def policy_hole_centers(actions: np.ndarray, offset: np.ndarray) -> np.ndarray:
    """Estimate a rigidly held nut's center for each 10-D policy target."""
    rotations = np.stack([rotation_6d_to_matrix(action[3:9]) for action in actions])
    return actions[:, :3] + rotations @ offset


def _smooth_pose(old: np.ndarray, new: np.ndarray) -> np.ndarray:
    count = min(len(SMOOTH_OLD_WEIGHTS), len(old))
    weights = np.asarray(SMOOTH_OLD_WEIGHTS[:count], dtype=np.float64)[:, None]
    new_actions = new.copy()
    new_actions[:count, :3] += weights * (old[:count, :3] - new[:count, :3])

    old_rotation = Rotation.from_matrix(np.stack([rotation_6d_to_matrix(row[3:9]) for row in old[:count]]))
    new_rotation = Rotation.from_matrix(np.stack([rotation_6d_to_matrix(row[3:9]) for row in new[:count]]))
    delta = (new_rotation.inv() * old_rotation).as_rotvec()
    interpolated = new_rotation * Rotation.from_rotvec(weights * delta)
    new_actions[:count, 3:9] = interpolated.as_matrix()[:, :2, :].reshape(count, 6)
    return new_actions


def choose_mid_actions(
    arm: str,
    anchor_chunk: np.ndarray,
    candidates: tuple[np.ndarray, np.ndarray],
    anchor: GeometryState,
    mid: GeometryState,
    execution_steps: int,
    pre_success: bool,
) -> MidDecision:
    """Select aligned mid-block actions using geometry outside the learned policy."""
    if arm not in ARMS[1:]:
        raise ValueError(f"Unknown mid-block arm {arm!r}")
    if not 1 <= execution_steps <= CHUNK_STEPS - MID_OFFSET:
        raise ValueError(f"Invalid mid-block execution length {execution_steps}")
    anchor_chunk = np.asarray(anchor_chunk, dtype=np.float64)
    if anchor_chunk.shape != (CHUNK_STEPS, ACTION_DIM) or len(candidates) != 2:
        raise ValueError("Expected one 15-step anchor and two 15-step candidates")
    fresh = np.asarray(candidates, dtype=np.float64)
    if fresh.shape != (2, CHUNK_STEPS, ACTION_DIM):
        raise ValueError("Expected two complete 15-step fresh candidates")
    old = anchor_chunk[MID_OFFSET:MID_OFFSET + execution_steps]
    fresh = fresh[:, :execution_steps]

    # PandaGripper.format_action maps positive commands to closing.
    all_commands_closed = bool(np.all(old[:, -1] > 0) and np.all(fresh[:, :, -1] > 0))
    _, lateral = hole_coordinates(mid.hole_center, mid)
    eligible = bool(mid.grasped and pre_success and lateral <= LATERAL_LIMIT_M and all_commands_closed)

    # All plans in the mid comparison use the same current grasp estimate.
    offset = mid.grasp_offset
    old_axial, _ = hole_coordinates(policy_hole_centers(old, offset), mid)
    candidate_axial = np.stack([
        hole_coordinates(policy_hole_centers(option, offset), mid)[0] for option in fresh
    ])
    changes = old_axial[None, :] - candidate_axial
    rms = np.sqrt(np.mean(np.square(changes), axis=1))
    chosen = int(np.argmin(rms)) if eligible else 0
    axial_rms_m = float(rms[chosen])
    axial_max_abs_m = float(np.max(np.abs(changes[chosen])))

    # Estimate the six-step intent from the real anchor hole center to A[5],
    # with the grasp offset and axis measured at the anchor.
    planned_endpoint = policy_hole_centers(anchor_chunk[MID_OFFSET - 1:MID_OFFSET], anchor.grasp_offset)[0]
    planned_down_m = float((anchor.hole_center - planned_endpoint) @ anchor.peg_axis)
    actual_down_m = float((anchor.hole_center - mid.hole_center) @ anchor.peg_axis)
    stall = bool(
        anchor.grasped and planned_down_m >= STALL_MIN_PLANNED_DOWN_M
        and actual_down_m < STALL_MIN_PROGRESS_FRACTION * planned_down_m
    )
    admissible = bool(
        eligible and axial_rms_m <= AXIAL_RMS_LIMIT_M and axial_max_abs_m <= AXIAL_MAX_LIMIT_M and not stall
    )

    actions = fresh[chosen]
    decision = "fresh"
    if eligible and (arm == "always_split" or arm == "adaptive" and admissible):
        actions = actions.copy()
        actions[:, :3] += changes[chosen, :, None] * mid.peg_axis
        decision = "split"
    elif eligible and arm == "smooth":
        actions = _smooth_pose(old, actions)
        decision = "smooth"
    return MidDecision(
        actions=actions,
        new_actions=fresh[chosen],
        chosen_candidate=chosen,
        decision=decision,
        eligible=eligible,
        admissible=admissible,
        all_commands_closed=all_commands_closed,
        stall=stall,
        planned_down_m=planned_down_m,
        actual_down_m=actual_down_m,
        axial_rms_m=axial_rms_m,
        axial_max_abs_m=axial_max_abs_m,
        old_axial_m=old_axial,
        new_axial_m=candidate_axial[chosen],
        candidate_axial_rms_m=(float(rms[0]), float(rms[1])),
    )
