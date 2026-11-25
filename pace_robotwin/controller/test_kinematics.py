"""Check known URDF poses and the Jacobians used by the controller."""

import os
from pathlib import Path
from types import SimpleNamespace
import unittest
import xml.etree.ElementTree as ET

import numpy as np
from scipy.spatial.transform import Rotation
import yaml

from pace_robotwin.controller import AlohaKinematics, UrdfArm, apply_component


def example_arm():
    names = ("a", "b", "c", "d", "e", "f")
    axes = ("0 0 -2", "0 1 0", "0 1 0", "1 0 0", "0 1 0", "0 0 1")
    origins = ("0.2 0 0.1", "0.3 0 0", "0 0 0.2", "0.1 0 0", "0 0.1 0", "0 0 0.2")
    root = ET.Element("robot")
    parent = "base"
    for index, (name, axis, xyz) in enumerate(zip(names, axes, origins)):
        joint = ET.SubElement(root, "joint", name=name, type="revolute")
        child = f"link_{name}"
        ET.SubElement(joint, "parent", link=parent)
        ET.SubElement(joint, "child", link=child)
        rpy = f"0 0 {np.pi / 2}" if index == 0 else "0 0 0"
        ET.SubElement(joint, "origin", xyz=xyz, rpy=rpy)
        ET.SubElement(joint, "axis", xyz=axis)
        ET.SubElement(joint, "limit", lower=str(-2 - index), upper=str(2 + index))
        parent = child
    tool = ET.SubElement(root, "joint", name="tool", type="fixed")
    ET.SubElement(tool, "parent", link=parent)
    ET.SubElement(tool, "child", link="tcp_mount")
    ET.SubElement(tool, "origin", xyz="0.2 0 0", rpy=f"{np.pi / 2} 0 0")
    ET.SubElement(tool, "axis", xyz="0 0 1")
    gripper = ET.SubElement(root, "joint", name="finger", type="prismatic")
    ET.SubElement(gripper, "parent", link="tcp_mount")
    ET.SubElement(gripper, "child", link="finger_link")

    tool_rotation = Rotation.from_euler("y", 90, degrees=True).as_matrix() @ Rotation.from_euler(
        "z", 90, degrees=True,
    ).as_matrix()
    return UrdfArm.from_urdf(
        root, ("c", "a", "b", "d", "f", "e"), "tool", [1, -2, 0.5], [1, 0, 0, 1], tool_rotation, 0.07,
    )


def finite_difference(model, configuration):
    step = 1e-6
    columns = []
    for delta in step * np.eye(6):
        p_minus, r_minus = model.forward(configuration - delta)
        p_plus, r_plus = model.forward(configuration + delta)
        angular = Rotation.from_matrix(r_plus @ r_minus.T).as_rotvec()
        columns.append(np.concatenate((p_plus - p_minus, angular)) / (2 * step))
    return np.column_stack(columns)


class UrdfTests(unittest.TestCase):
    def test_known_tcp_with_shifted_base_and_noncommuting_frames(self):
        model = example_arm()
        position, rotation = model.forward(np.array([0, np.pi / 2, 0, 0, 0, 0]))
        np.testing.assert_allclose(position, [0.9, -1.2, 1.07], rtol=0, atol=1e-12)
        np.testing.assert_allclose(rotation, [[0, 0, 1], [0, -1, 0], [1, 0, 0]], atol=1e-12)
        np.testing.assert_array_equal(model.upper, [4, 2, 3, 5, 7, 6])
        np.testing.assert_array_equal(model.lower, [-4, -2, -3, -5, -7, -6])

    def test_spatial_jacobian_matches_finite_differences_in_command_order(self):
        model = example_arm()
        q = np.array([-0.22, 0.14, 0.7, 0.23, -0.1, 0.5])
        _, _, jacobian = model.forward_jacobian(q)
        np.testing.assert_allclose(jacobian, finite_difference(model, q), rtol=0, atol=2e-9)


class OfficialAlohaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        asset_override = os.environ.get("ROBOTWIN_ALOHA_EMBODIMENT")
        if asset_override:
            cls.directory = Path(asset_override)
        else:
            package = Path(__file__).resolve().parents[1]
            candidates = (
                package / "vendor" / "RoboTwin-PACE",
                package / "vendor" / "PACE",
            )
            for root in candidates:
                directory = root / "assets" / "embodiments" / "aloha-agilex"
                if (directory / "config.yml").is_file():
                    cls.directory = directory
                    break
            else:
                raise unittest.SkipTest("Official ALOHA asset absent. Set ROBOTWIN_ALOHA_EMBODIMENT to its directory.")
        cls.kinematics = AlohaKinematics.from_embodiment(cls.directory)

    def test_released_aloha_home_tcp_and_wrist_roll(self):
        left_home = [-0.300323693676, -0.193828037223, 0.941999991519]
        right_home = [0.305233154523, -0.192806084345, 0.940999991519]
        for model, expected_home, yaw in (
            (self.kinematics.left, left_home, 0.02),
            (self.kinematics.right, right_home, 0.01),
        ):
            with self.subTest(ee_joint=model.ee_joint):
                # At home only the mount yaw and the static URDF joint rotations
                # remain. ALOHA's configured global rotation cancels the PhysX
                # wrist anchor rotation, and the 0.12 m tool offset is along x.
                expected_rotation = Rotation.from_euler("z", np.pi / 2 + yaw)
                for axis, angle in (("z", -0.015928), ("x", -3.1416), ("z", -0.015928), ("x", -3.1416)):
                    expected_rotation *= Rotation.from_euler(axis, angle)
                home, rotation = model.forward(np.zeros(6))
                np.testing.assert_allclose(home, expected_home, rtol=0, atol=5e-10)
                np.testing.assert_allclose(rotation, expected_rotation.as_matrix(), atol=1e-12)
                rolled, rolled_rotation = model.forward(np.array([0, 0, 0, 0, 0, 0.3]))
                np.testing.assert_allclose(rolled, home, rtol=0, atol=1e-12)
                expected_roll = expected_rotation * Rotation.from_euler("x", 0.3)
                np.testing.assert_allclose(rolled_rotation, expected_roll.as_matrix(), atol=1e-12)

    def test_official_robot_metadata_selects_same_kinematics(self):
        config = yaml.safe_load((self.directory / "config.yml").read_text(encoding="utf-8"))
        base = config["robot_pose"][-1]
        pose = SimpleNamespace(p=np.asarray(base[:3]), q=np.asarray(base[3:]))
        robot = SimpleNamespace(
            is_dual_arm=True, left_urdf_path=self.directory / config["urdf_path"], right_entity_origion_pose=pose,
        )
        for index, side in enumerate(("left", "right")):
            setattr(robot, f"{side}_arm_joints_name", config["arm_joints_name"][index])
            setattr(robot, f"{side}_ee_name", config["ee_joints"][index])
            setattr(robot, f"{side}_global_trans_matrix", np.asarray(config["global_trans_matrix"]))
            setattr(robot, f"{side}_delta_matrix", np.asarray(config["delta_matrix"]))
            setattr(robot, f"{side}_gripper_bias", config["gripper_bias"])
        live = AlohaKinematics.from_robot(robot)
        q = np.array([0.2, -0.4, 0.7, 0.2, -0.2, 0.1])
        for side in ("left", "right"):
            expected = getattr(self.kinematics, side).forward(q)
            actual = getattr(live, side).forward(q)
            np.testing.assert_array_equal(actual[0], expected[0])
            np.testing.assert_array_equal(actual[1], expected[1])

    def test_component_adjusts_both_real_urdf_chains_and_preserves_orientation(self):
        prev_h = 12
        nominal = np.array([0.2, -0.4, 0.7, 0.2, -0.2, 0.1, 0.1, -0.15, -0.31, 0.55, -0.12, 0.26, -0.27, 0.9])
        ramp = np.zeros(14)
        ramp[[0, 9]] = [0.012, -0.014]
        steps = np.arange(50)[:, None]
        old = (nominal + steps * ramp).astype(np.float32)
        fresh = (nominal + (steps + prev_h - 1.2) * ramp).astype(np.float32)
        result = apply_component(
            fresh, old[prev_h - 1], 15, kinematics=self.kinematics, previous_raw=old, prev_h=prev_h,
        )
        np.testing.assert_array_equal(result.actions[7:], fresh[7:])
        np.testing.assert_array_equal(result.actions[:, [6, 13]], fresh[:, [6, 13]])
        for side, selection in (("left", slice(0, 6)), ("right", slice(7, 13))):
            with self.subTest(side=side):
                model = getattr(self.kinematics, side)
                _, _, jacobian = model.forward_jacobian(fresh[0, selection])
                np.testing.assert_allclose(jacobian, finite_difference(model, fresh[0, selection]), atol=2e-9)
                audit = result.audit["arms"][side]
                self.assertTrue(audit["applied"])
                old_start = model.forward(old[prev_h - 1, selection])[0]
                old_positions = np.stack([model.forward(row[selection])[0] for row in old[prev_h:prev_h + 8]])
                direction = old_positions[-1] - old_start
                axis = direction / np.linalg.norm(direction)
                for index, row in enumerate(result.actions[:8]):
                    raw_position, raw_rotation = model.forward(fresh[index, selection])
                    shift = (1 - index / 7) * float((old_positions[index] - raw_position) @ axis)
                    position, rotation = model.forward(row[selection])
                    np.testing.assert_allclose(position, raw_position + shift * axis, rtol=0, atol=1e-7)
                    np.testing.assert_allclose(rotation, raw_rotation, rtol=0, atol=1e-7)
                    self.assertAlmostEqual(float((position - raw_position) @ axis), audit["actual_axial_m"][index])


if __name__ == "__main__":
    unittest.main()
