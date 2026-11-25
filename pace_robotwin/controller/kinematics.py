"""Pure URDF forward kinematics in RoboTwin's configured ALOHA TCP frames."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
from scipy.spatial.transform import Rotation
import yaml


@dataclass(frozen=True)
class _Joint:
    index: int | None
    position: np.ndarray
    rotation: np.ndarray
    axis: np.ndarray | None


def _vector(value: str) -> np.ndarray:
    result = np.array([float(part) for part in value.split()])
    if result.shape != (3,) or not np.isfinite(result).all():
        raise ValueError(f"Expected a finite URDF xyz or rpy vector, got {value!r}")
    return result


def _joint_axis(joint: ET.Element) -> np.ndarray:
    element = joint.find("axis")
    axis = _vector("1 0 0" if element is None else element.attrib["xyz"])
    length = np.linalg.norm(axis)
    if length < 1e-3:
        return np.array([1.0, 0.0, 0.0])
    return axis / length


def _ee_anchor_rotation(joint: ET.Element) -> np.ndarray:
    # SAPIEN 3.0.0b1 expresses the URDF joint axis as the x axis of the
    # PhysX joint frame. Joint.global_pose includes this child-frame rotation.
    x = _joint_axis(joint)
    reference = [0, 0, 1] if abs(x[0]) > 0.9 else [1, 0, 0]
    y = np.cross(x, reference)
    y /= np.linalg.norm(y)
    z = np.cross(x, y)
    return np.column_stack((x, y, z))


@dataclass(frozen=True)
class UrdfArm:
    """One serial six-joint arm, in the order of its RoboTwin joint commands."""

    joint_names: tuple[str, ...]
    ee_joint: str
    lower: np.ndarray
    upper: np.ndarray
    _chain: tuple[_Joint, ...]
    _base_position: np.ndarray
    _base_rotation: np.ndarray
    _tool_rotation: np.ndarray
    _gripper_bias: float

    @classmethod
    def from_urdf(
        cls,
        urdf: ET.Element,
        joint_names: tuple[str, ...],
        ee_joint: str,
        base_position: np.ndarray,
        base_quaternion_wxyz: np.ndarray,
        tcp_rotation_from_ee_joint: np.ndarray,
        gripper_bias: float,
    ) -> UrdfArm:
        if len(joint_names) != 6 or len(set(joint_names)) != 6:
            raise ValueError("ALOHA requires six distinct commanded joints per arm")
        joints = urdf.findall("joint")
        joints_by_name = {joint.attrib["name"]: joint for joint in joints}
        joints_by_child = {joint.find("child").attrib["link"]: joint for joint in joints}
        terminal_joint = joints_by_name[ee_joint]

        indices = {name: index for index, name in enumerate(joint_names)}
        lower = np.full(6, -np.inf)
        upper = np.full(6, np.inf)
        chain = []
        used = set()
        joint = terminal_joint
        while joint is not None:
            name = joint.attrib["name"]
            if name in used:
                raise ValueError(f"Cycle in URDF chain for {ee_joint!r}")
            used.add(name)
            kind = joint.attrib["type"]
            index = indices.get(name)
            axis = None
            if index is not None:
                if kind not in {"revolute", "continuous"} or joint.find("mimic") is not None:
                    raise ValueError(f"Expected a commanded revolute ALOHA joint, got {name!r}")
                axis = _joint_axis(joint)
                if kind == "revolute":
                    limit = joint.find("limit")
                    if limit is None:
                        raise ValueError(f"Missing URDF limits for {name!r}")
                    lower[index] = float(limit.attrib["lower"])
                    upper[index] = float(limit.attrib["upper"])
                    if not (np.isfinite(lower[index]) and np.isfinite(upper[index]) and lower[index] <= upper[index]):
                        raise ValueError(f"Invalid URDF limits for {name!r}")
            elif kind != "fixed":
                raise ValueError(f"Unexpected uncommanded joint {name!r} in the chain for {ee_joint!r}")

            origin = joint.find("origin")
            origin_values = {} if origin is None else origin.attrib
            position = _vector(origin_values.get("xyz", "0 0 0"))
            rotation = Rotation.from_euler("xyz", _vector(origin_values.get("rpy", "0 0 0"))).as_matrix()
            chain.append(_Joint(index, position, rotation, axis))
            joint = joints_by_child.get(joint.find("parent").attrib["link"])

        if not indices.keys() <= used:
            raise ValueError(f"Commanded joints outside the chain for {ee_joint!r}: {indices.keys() - used}")
        tcp_rotation_from_ee_joint = np.asarray(tcp_rotation_from_ee_joint, dtype=np.float64)
        if (
            tcp_rotation_from_ee_joint.shape != (3, 3)
            or not np.allclose(tcp_rotation_from_ee_joint.T @ tcp_rotation_from_ee_joint, np.eye(3), atol=1e-8, rtol=0)
            or not np.isclose(np.linalg.det(tcp_rotation_from_ee_joint), 1, atol=1e-8, rtol=0)
        ):
            raise ValueError(f"Invalid RoboTwin TCP rotation for {ee_joint!r}")
        tool_rotation = _ee_anchor_rotation(terminal_joint) @ tcp_rotation_from_ee_joint
        base_position = np.asarray(base_position, dtype=np.float64)
        quaternion = np.asarray(base_quaternion_wxyz, dtype=np.float64)
        if (
            base_position.shape != (3,) or not np.isfinite(base_position).all()
            or quaternion.shape != (4,) or not np.isfinite(quaternion).all()
            or not np.isfinite(gripper_bias)
        ):
            raise ValueError(f"Invalid RoboTwin base pose or TCP bias for {ee_joint!r}")
        base_rotation = Rotation.from_quat(quaternion[[1, 2, 3, 0]]).as_matrix()
        return cls(
            joint_names, ee_joint, lower, upper, tuple(reversed(chain)),
            base_position, base_rotation, tool_rotation, float(gripper_bias),
        )

    def forward(self, q: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """World-frame TCP position in meters and its 3×3 rotation."""
        position, rotation, _, _ = self._frames(q)
        return position, rotation

    def forward_jacobian(self, q: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """TCP pose and its world-frame geometric Jacobian, translation first."""
        position, rotation, origins, axes = self._frames(q)
        linear = np.cross(axes, position - origins)
        jacobian = np.vstack((linear.T, axes.T))
        return position, rotation, jacobian

    def _frames(self, q: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        q = np.asarray(q, dtype=np.float64)
        if q.shape != (6,) or not np.isfinite(q).all():
            raise ValueError("ALOHA forward kinematics requires six finite joint angles")
        position = self._base_position
        rotation = self._base_rotation
        origins = np.empty((6, 3))
        axes = np.empty((6, 3))
        for joint in self._chain:
            position = position + rotation @ joint.position
            rotation = rotation @ joint.rotation
            if joint.index is not None:
                origins[joint.index] = position
                axes[joint.index] = rotation @ joint.axis
                rotation = rotation @ Rotation.from_rotvec(joint.axis * q[joint.index]).as_matrix()

        # RoboTwin Robot._trans_endpose(..., is_endpose=True) uses the EE joint
        # frame, then global_trans_matrix @ delta_matrix and the full gripper bias.
        rotation = rotation @ self._tool_rotation
        position = position + self._gripper_bias * rotation[:, 0]
        return position, rotation, origins, axes


@dataclass(frozen=True)
class AlohaKinematics:
    left: UrdfArm
    right: UrdfArm

    @classmethod
    def from_robot(cls, robot) -> AlohaKinematics:
        """Use the metadata of the initialized official RoboTwin Robot."""
        if not robot.is_dual_arm:
            raise ValueError("Expected the shared dual-arm ALOHA embodiment")
        # RoboTwin sets both root poses on the shared articulation. The second
        # (right) assignment is the configured base pose for both chains.
        base = robot.right_entity_origion_pose
        urdf_path = Path(robot.left_urdf_path)
        urdf = ET.parse(urdf_path).getroot()

        def arm(side: str) -> UrdfArm:
            return UrdfArm.from_urdf(
                urdf,
                tuple(getattr(robot, f"{side}_arm_joints_name")),
                getattr(robot, f"{side}_ee_name"),
                base.p,
                base.q,
                getattr(robot, f"{side}_global_trans_matrix") @ getattr(robot, f"{side}_delta_matrix"),
                getattr(robot, f"{side}_gripper_bias"),
            )

        return cls(arm("left"), arm("right"))

    @classmethod
    def from_embodiment(cls, directory: str | Path) -> AlohaKinematics:
        """Load the same official ALOHA config and URDF without importing RoboTwin."""
        directory = Path(directory)
        config = yaml.safe_load((directory / "config.yml").read_text(encoding="utf-8"))
        urdf = ET.parse(directory / config["urdf_path"]).getroot()
        base = config.get("robot_pose", [[0, -0.65, 0, 1, 0, 0, 1]])
        base = base[0 if len(base) == 1 else 1]
        tool_rotation = np.asarray(config.get("global_trans_matrix", np.eye(3))) @ np.asarray(
            config.get("delta_matrix", np.eye(3))
        )

        def arm(index: int) -> UrdfArm:
            return UrdfArm.from_urdf(
                urdf,
                tuple(config["arm_joints_name"][index]),
                config["ee_joints"][index],
                base[:3],
                base[3:],
                tool_rotation,
                config["gripper_bias"],
            )

        return cls(arm(0), arm(1))
