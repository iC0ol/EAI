"""Deterministic controller tests with nonsingular and singular model fixtures."""

import json
import unittest
from types import SimpleNamespace

import numpy as np
from scipy.spatial.transform import Rotation

from pace_robotwin.controller import AlohaKinematics, apply_component
from pace_robotwin.controller.validation import compare_native_fk


class CartesianArm:
    def __init__(self, upper_x=2.0):
        self.lower = np.full(6, -2.0)
        self.upper = np.array([upper_x, 2, 2, 2, 2, 2])

    def forward(self, q):
        return 0.1 * np.asarray(q[:3], dtype=np.float64), Rotation.from_euler("xyz", q[3:]).as_matrix()

    def forward_jacobian(self, q):
        position, rotation = self.forward(q)
        rz = Rotation.from_euler("z", q[5]).as_matrix()
        ry = Rotation.from_euler("y", q[4]).as_matrix()
        jacobian = np.eye(6)
        jacobian[:3, :3] *= 0.1
        jacobian[3:, 3] = rz @ ry[:, 0]
        jacobian[3:, 4] = rz[:, 1]
        return position, rotation, jacobian


class SingularArm(CartesianArm):
    def forward(self, q):
        position, rotation = super().forward(q)
        position[0] = q[0] ** 2
        return position, rotation

    def forward_jacobian(self, q):
        position, rotation, jacobian = super().forward_jacobian(q)
        jacobian[0, 0] = 2 * q[0]
        return position, rotation, jacobian


def chunks(dtype=np.float64):
    steps = np.arange(50)
    old = np.zeros((50, 14), dtype=dtype)
    old[:, 0] = 0.015 * steps
    old[:, 6] = 0.1
    old[:, 8] = -0.020 * steps
    old[:, 13] = 0.9
    fresh = np.zeros_like(old)
    fresh[:, 0] = 0.015 * (steps + 5) - 0.05
    fresh[:, 1] = 0.035
    fresh[:, 2] = -0.02
    fresh[:, 3:5] = [0.02, -0.04]
    fresh[:, 5] = 0.25 + steps / 1000
    fresh[:, 6] = 0.10
    fresh[:, 7] = 0.02
    fresh[:, 8] = -0.020 * (steps + 5) + 0.04
    fresh[:, 13] = 0.90
    return old, fresh, old[4].copy()


class ComponentTests(unittest.TestCase):
    def run_component(self, old, fresh, state, *, h=17, prev_h=5, left=None):
        return apply_component(
            fresh, state, h,
            kinematics=AlohaKinematics(left or CartesianArm(), CartesianArm()),
            previous_raw=old, prev_h=prev_h,
        )

    def test_aligned_arms_match_only_the_requested_translation_component(self):
        old, fresh, state = chunks(np.float32)
        old.setflags(write=False)
        fresh.setflags(write=False)
        result = self.run_component(old, fresh, state)
        actions = result.actions
        self.assertEqual(actions.dtype, fresh.dtype)
        self.assertFalse(np.shares_memory(actions, fresh))
        self.assertEqual(result.audit["window"], 8)
        json.dumps(result.audit, allow_nan=False)
        np.testing.assert_array_equal(actions[7:], fresh[7:])
        np.testing.assert_array_equal(actions[:, [6, 13]], fresh[:, [6, 13]])
        for side, direction, magnitude, joints in (
            ("left", [1, 0, 0], 0.005, slice(0, 6)),
            ("right", [0, -1, 0], 0.004, slice(7, 13)),
        ):
            with self.subTest(side=side):
                audit = result.audit["arms"][side]
                self.assertTrue(audit["eligible"])
                self.assertTrue(audit["applied"])
                self.assertIsNone(audit["release_reason"])
                np.testing.assert_allclose(audit["axis"], direction, atol=1e-12)
                expected = np.linspace(magnitude, 0.0, 8)
                np.testing.assert_allclose(audit["proposed_axial_m"], expected, atol=1e-8)
                np.testing.assert_allclose(audit["actual_axial_m"], expected, atol=1e-8)
                np.testing.assert_allclose(audit["actual_lateral_m"], 0, atol=1e-12)
                np.testing.assert_allclose(audit["actual_rotation_change_deg"], 0, atol=1e-10)
                self.assertTrue(all(step["inside_joint_limits"] for step in audit["ik_steps"]))
                self.assertEqual(audit["ik_steps"][-1]["iterations"], 0)
                self.assertEqual(audit["ik_steps"][-1]["max_joint_delta_rad"], 0)
                model = CartesianArm()
                for index, shift in enumerate(expected):
                    raw_position, raw_rotation = model.forward(fresh[index, joints])
                    position, rotation = model.forward(actions[index, joints])
                    np.testing.assert_allclose(position - raw_position, shift * np.asarray(direction), atol=1e-8)
                    np.testing.assert_array_equal(rotation, raw_rotation)

    def test_releases_orthogonal_and_inactive_arms_independently(self):
        for reason in ("direction_mismatch", "old_inactive", "new_inactive"):
            with self.subTest(reason=reason):
                old, fresh, state = chunks()
                if reason == "direction_mismatch":
                    state[0] = fresh[7, 0]
                    state[2] = fresh[7, 2]
                    fresh[:, 1] += 0.05
                elif reason == "old_inactive":
                    old[5:, 0] = old[4, 0]
                else:
                    state[:3] = fresh[7, :3]
                result = self.run_component(old, fresh, state)
                audit = result.audit["arms"]["left"]
                self.assertFalse(audit["eligible"])
                self.assertEqual(audit["release_reason"], reason)
                self.assertTrue(result.audit["arms"]["right"]["applied"])
                np.testing.assert_array_equal(result.actions[:, :7], fresh[:, :7])

    def test_gripper_event_and_same_state_range_are_both_checked(self):
        for source in ("old", "new", "state", "range"):
            with self.subTest(source=source):
                old, fresh, state = chunks()
                if source == "old":
                    old[12, 6] = 0.9
                elif source == "new":
                    fresh[7, 6] = 0.5
                elif source == "state":
                    state[6] = 0.9
                else:
                    old[5, 6] = 0
                    fresh[0, 6] = 0.25
                result = self.run_component(old, fresh, state)
                reason = "gripper_range" if source == "range" else "gripper_state"
                self.assertEqual(result.audit["arms"]["left"]["release_reason"], reason)
                self.assertTrue(result.audit["arms"]["right"]["applied"])
                np.testing.assert_array_equal(result.actions[:, :7], fresh[:, :7])

    def test_gripper_events_outside_the_paired_window_are_ignored(self):
        old, fresh, state = chunks()
        old[:5, 6] = 1
        old[13:, 6] = 1
        fresh[8:, 6] = 1
        result = self.run_component(old, fresh, state)
        self.assertTrue(result.audit["arms"]["left"]["applied"])
        np.testing.assert_array_equal(result.actions[:, 6], fresh[:, 6])

    def test_candidate_ahead_of_the_previous_plan_gets_a_negative_axial_correction(self):
        old, fresh, state = chunks()
        fresh[:8, 0] += 0.1
        result = self.run_component(old, fresh, state)
        left = result.audit["arms"]["left"]
        self.assertTrue(left["applied"])
        np.testing.assert_allclose(left["proposed_axial_m"], np.linspace(-0.005, 0, 8), atol=1e-12)
        np.testing.assert_allclose(left["actual_axial_m"], left["proposed_axial_m"], atol=1e-8)

    def test_rms_and_maximum_axial_gates(self):
        for reason, offsets in (
            ("axial_rms", np.full(8, 0.011)),
            ("axial_max", np.array([0.021, 0, 0, 0, 0, 0, 0, 0])),
        ):
            with self.subTest(reason=reason):
                old, fresh, state = chunks()
                fresh[:8, 0] = old[5:13, 0] - offsets / 0.1
                state[0] = fresh[7, 0] - 0.08
                result = self.run_component(old, fresh, state)
                self.assertEqual(result.audit["arms"]["left"]["release_reason"], reason)
                np.testing.assert_array_equal(result.actions[:, :7], fresh[:, :7])

    def test_joint_delta_failure_rolls_back_earlier_successes_on_one_arm(self):
        old, fresh, state = chunks()
        fresh[2, 0] = old[7, 0] - 0.018 / 0.1
        result = self.run_component(old, fresh, state)
        left = result.audit["arms"]["left"]
        self.assertTrue(left["eligible"])
        self.assertFalse(left["applied"])
        self.assertEqual(left["failed_step"], 2)
        self.assertEqual(left["release_reason"], "ik_joint_delta")
        self.assertGreater(left["ik_steps"][0]["axial_m"], 0.004)
        self.assertGreater(left["ik_steps"][2]["max_joint_delta_rad"], 0.12)
        np.testing.assert_array_equal(left["actual_axial_m"], np.zeros(8))
        np.testing.assert_allclose(left["actual_position_residual_m"], np.abs(left["proposed_axial_m"]))
        np.testing.assert_array_equal(result.actions[:, :7], fresh[:, :7])
        self.assertTrue(result.audit["arms"]["right"]["applied"])

    def test_joint_limit_failure_rolls_back_without_clipping(self):
        old, fresh, state = chunks()
        old[6, 0] = 0.22
        fresh[1, 0] = 0.11
        result = self.run_component(old, fresh, state, left=CartesianArm(upper_x=0.19))
        left = result.audit["arms"]["left"]
        self.assertEqual(left["release_reason"], "ik_joint_limit")
        self.assertEqual(left["failed_step"], 1)
        self.assertFalse(left["ik_steps"][1]["inside_joint_limits"])
        np.testing.assert_array_equal(result.actions[:, :7], fresh[:, :7])
        self.assertTrue(result.audit["arms"]["right"]["applied"])

    def test_singular_seed_releases_on_ik_position_error(self):
        old, fresh, state = chunks()
        old[4:13, 0] = np.sqrt(np.linspace(0, 0.016, 9))
        fresh[:8, 0] = np.sqrt(np.linspace(0, 0.014, 8))
        old[5, 0] = np.sqrt(0.006)
        fresh[:, 1:3] = 0
        state[:3] = 0
        result = self.run_component(old, fresh, state, left=SingularArm())
        left = result.audit["arms"]["left"]
        self.assertTrue(left["eligible"])
        self.assertEqual(left["failed_step"], 0)
        self.assertEqual(left["release_reason"], "ik_position_residual")
        self.assertAlmostEqual(left["ik_steps"][0]["position_residual_m"], 0.006)
        np.testing.assert_array_equal(result.actions[:, :7], fresh[:, :7])

    def test_out_of_limit_last_waypoint_releases_even_though_its_shift_is_zero(self):
        old, fresh, state = chunks()
        fresh[7, 0] = 0.18
        result = self.run_component(old, fresh, state, left=CartesianArm(upper_x=0.175))
        left = result.audit["arms"]["left"]
        self.assertEqual(left["failed_step"], 7)
        self.assertEqual(left["release_reason"], "ik_joint_limit")
        self.assertEqual(left["ik_steps"][7]["iterations"], 0)
        np.testing.assert_array_equal(result.actions[:, :7], fresh[:, :7])

    def test_no_previous_and_short_window_return_a_separate_raw_copy(self):
        old, fresh, state = chunks()
        for previous, count, h, window, reason in (
            (None, None, 17, 0, "no_previous_chunk"),
            (old, 50, 17, 0, "short_overlap"),
            (old, 48, 17, 2, "short_overlap"),
            (old, 5, 2, 2, "short_overlap"),
        ):
            with self.subTest(count=count, h=h):
                result = self.run_component(previous, fresh, state, h=h, prev_h=count)
                self.assertEqual(result.audit["window"], window)
                for audit in result.audit["arms"].values():
                    self.assertEqual(audit["release_reason"], reason)
                    self.assertFalse(audit["eligible"])
                np.testing.assert_array_equal(result.actions, fresh)
                self.assertFalse(np.shares_memory(result.actions, fresh))

    def test_previous_executed_count_and_selected_horizon_define_the_indices(self):
        old, fresh, state = chunks()
        prev_h = 45
        state = old[prev_h - 1].copy()
        fresh[:4] = old[prev_h:prev_h + 4]
        fresh[0, 0] -= 0.01
        result = self.run_component(old, fresh, state, h=4, prev_h=prev_h)
        left = result.audit["arms"]["left"]
        self.assertEqual(result.audit["window"], 4)
        self.assertTrue(left["applied"])
        self.assertAlmostEqual(left["old_last_executed_tcp_m"][0], 0.1 * old[44, 0])
        self.assertAlmostEqual(left["old_tcp_m"][-1][0], 0.1 * old[48, 0])
        np.testing.assert_array_equal(result.actions[3:], fresh[3:])

    def test_zero_proposal_preserves_every_original_joint(self):
        old, fresh, state = chunks()
        fresh[:8] = old[5:13]
        result = self.run_component(old, fresh, state)
        for audit in result.audit["arms"].values():
            self.assertTrue(audit["eligible"])
            self.assertFalse(audit["applied"])
            self.assertEqual(audit["release_reason"], "no_joint_change")
            self.assertTrue(all(step["iterations"] == 0 for step in audit["ik_steps"]))
        np.testing.assert_array_equal(result.actions, fresh)

    def test_native_comparison_uses_the_reported_physical_joint_configuration(self):
        model = CartesianArm()
        q = np.array([0.2, 0.4, 0.1, 0.3, -0.2, 0.1])
        position, orientation = model.forward(q)
        native_rotation = Rotation.from_euler("z", 0.2, degrees=True) * Rotation.from_matrix(orientation)
        native_pose = np.concatenate((position + [0.0003, 0, 0], np.roll(native_rotation.as_quat(), 1)))
        robot = SimpleNamespace(
            get_left_arm_real_jointState=lambda: np.append(q, 0.9),
            get_right_arm_real_jointState=lambda: np.append(q, 0.1),
            get_left_tcp_pose=lambda: native_pose,
            get_right_tcp_pose=lambda: native_pose,
        )
        result = compare_native_fk(robot, kinematics=AlohaKinematics(model, model))
        for audit in result.values():
            self.assertAlmostEqual(audit["position_error_m"], 0.0003)
            self.assertAlmostEqual(audit["rotation_error_deg"], 0.2)
            self.assertEqual(audit["joint_q_rad"], q.tolist())


if __name__ == "__main__":
    unittest.main()
