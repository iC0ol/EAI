"""Deterministic checks of the rigid-hole projection and treatment rules."""

from dataclasses import replace

import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from gate_b_v2.actions import rotation_6d_to_matrix

from component_commitment.mechanism import GeometryState, choose_mid_actions, hole_coordinates, policy_hole_centers


def geometry(axis, center, offset, angle=0.0, grasped=True):
    matrix = Rotation.from_euler("y", angle).as_matrix()
    return GeometryState(center, center - matrix @ offset, matrix, np.zeros(3), axis, grasped)


def actions(centers, matrix, offset, gripper=1.0):
    result = np.empty((15, 10))
    result[:, :3] = centers - matrix @ offset
    result[:, 3:9] = matrix[:2, :].reshape(6)
    result[:, 9] = gripper
    return result


@pytest.fixture
def tilted_plans():
    axis = np.array([0.6, 0.0, 0.8])
    side = np.array([0.8, 0.0, -0.6])
    offset = np.array([0.03, -0.016, 0.045])
    state = geometry(axis, 0.025 * axis + 0.05 * side, offset, angle=0.6)
    anchor_target = np.arange(15)[:, None] * 0.001 * axis + state.hole_center
    old = actions(anchor_target, Rotation.from_euler("x", 0.8).as_matrix(), offset)
    new_target = anchor_target.copy()
    new_target[:9] = anchor_target[6:] + 0.015 * side
    fresh0 = actions(new_target + 0.018 * axis, np.eye(3), offset, gripper=0.7)
    fresh1 = actions(new_target - 0.005 * axis, Rotation.from_euler("z", -1.2).as_matrix(), offset, gripper=0.9)
    return state, old, fresh0, fresh1


@pytest.mark.parametrize("arm,decision", [("refresh", "fresh"), ("always_split", "split"), ("adaptive", "split")])
def test_tilted_peg_selects_same_candidate_and_only_split_retains_old_axis(tilted_plans, arm, decision):
    state, old, fresh0, fresh1 = tilted_plans
    result = choose_mid_actions(arm, old, (fresh0, fresh1), state, state, 9, True)

    assert result.eligible and result.admissible
    assert result.chosen_candidate == 1
    assert result.decision == decision
    assert result.axial_rms_m == pytest.approx(0.005)
    assert result.axial_max_abs_m == pytest.approx(0.005)
    np.testing.assert_array_equal(result.actions[:, 3:], fresh1[:9, 3:])
    if decision == "split":
        expected_holes = policy_hole_centers(old[6:], state.grasp_offset)
        expected_axial, _ = hole_coordinates(expected_holes, state)
        observed_holes = policy_hole_centers(result.actions, state.grasp_offset)
        observed_axial, _ = hole_coordinates(observed_holes, state)
        np.testing.assert_allclose(observed_axial, expected_axial, atol=1e-12, rtol=0)
        np.testing.assert_allclose(result.actions[:, :3] - fresh1[:9, :3], np.tile(0.005 * state.peg_axis, (9, 1)))
    else:
        np.testing.assert_array_equal(result.actions, fresh1[:9])


@pytest.mark.parametrize("reason", ["no_grasp", "already_succeeded", "too_far", "old_opens", "new0_opens", "new1_idle"])
def test_ineligible_always_uses_complete_fresh0_unchanged(tilted_plans, reason):
    state, old, fresh0, fresh1 = tilted_plans
    mid = state
    pre_success = True
    if reason == "no_grasp":
        mid = replace(state, grasped=False)
    elif reason == "already_succeeded":
        pre_success = False
    elif reason == "too_far":
        mid = replace(state, hole_center=state.hole_center + np.array([0.0, 0.13, 0.0]))
    elif reason == "old_opens":
        old[6, 9] = -1
    elif reason == "new0_opens":
        fresh0[8, 9] = -1
    else:
        fresh1[8, 9] = 0

    for arm in ("refresh", "smooth", "always_split", "adaptive"):
        result = choose_mid_actions(arm, old, (fresh0, fresh1), state, mid, 9, pre_success)
        assert (result.eligible, result.admissible, result.chosen_candidate, result.decision) == (False, False, 0, "fresh")
        np.testing.assert_array_equal(result.actions, fresh0[:9])


def test_equality_uses_candidate_zero_and_open_commands_outside_overlap_do_not_count():
    state = geometry(np.array([0.0, 0.0, 1.0]), np.array([0.12, 0.0, 0.0]), np.zeros(3))
    old = actions(np.zeros((15, 3)), np.eye(3), np.zeros(3))
    old[:6, 9] = -1
    fresh0 = old.copy()
    fresh0[:, 2] = -0.01
    fresh0[:9, 9] = 0.5
    fresh0[9:, 9] = -1
    fresh1 = fresh0.copy()
    fresh1[:, 2] *= -1
    result = choose_mid_actions("adaptive", old, (fresh0, fresh1), state, state, 1, True)
    assert result.eligible and result.admissible
    assert result.chosen_candidate == 0
    assert result.axial_rms_m == 0.010
    assert result.decision == "split"


@pytest.mark.parametrize("delta", [np.full(9, 0.011), np.array([0.021] + [0.0] * 8)])
def test_adaptive_checks_both_compatibility_limits(tilted_plans, delta):
    state, old, _, _ = tilted_plans
    fresh0 = old.copy()
    fresh0[:9] = old[6:]
    fresh0[:9, :3] += delta[:, None] * state.peg_axis
    fresh1 = fresh0.copy()
    for arm, expected in (("adaptive", "fresh"), ("always_split", "split")):
        result = choose_mid_actions(arm, old, (fresh0, fresh1), state, state, 9, True)
        assert result.eligible and not result.admissible and not result.stall
        assert result.decision == expected


@pytest.mark.parametrize("down,anchor_grasped,stall", [(0.003, True, True), (1 / 256, True, False), (0.0, False, False)])
def test_stall_uses_anchor_offset_for_old_5_and_actual_contact_motion(down, anchor_grasped, stall):
    axis = np.array([0.0, 0.0, 1.0])
    anchor_offset = np.array([0.0, 0.0, 0.125])
    mid_offset = np.array([0.0, 0.0, 0.02])
    anchor = geometry(axis, np.zeros(3), anchor_offset, grasped=anchor_grasped)
    mid = geometry(axis, -down * axis, mid_offset, angle=1.2)
    old = actions(np.tile(-axis / 64, (15, 1)), np.eye(3), anchor_offset)
    fresh = old.copy()
    for arm in ("adaptive", "always_split"):
        result = choose_mid_actions(arm, old, (fresh, fresh), anchor, mid, 9, True)
        assert result.stall == stall
        assert result.planned_down_m == 1 / 64
        assert result.actual_down_m == pytest.approx(down)
        assert result.decision == ("fresh" if stall and arm == "adaptive" else "split")


def test_smooth_interpolates_whole_pose_by_shortest_arc_for_only_three_steps():
    state = geometry(np.array([0.0, 0.0, 1.0]), np.zeros(3), np.zeros(3))
    old_rotation = Rotation.from_euler("z", 170, degrees=True).as_matrix()
    new_rotation = Rotation.from_euler("z", -170, degrees=True).as_matrix()
    old = actions(np.full((15, 3), [0.020, 0.05, 0.04]), old_rotation, np.zeros(3))
    new = actions(np.full((15, 3), [0.030, 0.03, 0.05]), new_rotation, np.zeros(3), gripper=0.67)
    result = choose_mid_actions("smooth", old, (new, new), state, state, 9, True)

    assert result.decision == "smooth"
    np.testing.assert_array_equal(result.actions[3:], new[3:9])
    np.testing.assert_array_equal(result.actions[:, 9], new[:9, 9])
    weights = np.array([[0.75], [0.50], [0.25]])
    np.testing.assert_allclose(result.actions[:3, :3], weights * old[6:9, :3] + (1 - weights) * new[:3, :3])
    np.testing.assert_allclose(
        np.stack([rotation_6d_to_matrix(action[3:9]) for action in result.actions[:3]]),
        Rotation.from_euler("z", [175, 180, -175], degrees=True).as_matrix(), atol=1e-12,
    )
