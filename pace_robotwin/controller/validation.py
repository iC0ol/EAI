"""Check controller forward kinematics against the loaded RoboTwin robot."""

from __future__ import annotations

import numpy as np
from scipy.spatial.transform import Rotation

from .kinematics import AlohaKinematics


def compare_native_fk(robot, *, kinematics: AlohaKinematics | None = None) -> dict:
    """Compare world-frame TCPs at the same physical qpos without stepping the scene."""
    if kinematics is None:
        kinematics = AlohaKinematics.from_robot(robot)
    comparison = {}
    for side, model in (("left", kinematics.left), ("right", kinematics.right)):
        q = np.asarray(getattr(robot, f"get_{side}_arm_real_jointState")(), dtype=np.float64)[:6]
        native = np.asarray(getattr(robot, f"get_{side}_tcp_pose")(), dtype=np.float64)
        native_rotation = Rotation.from_quat(native[[4, 5, 6, 3]]).as_matrix()
        position, rotation = model.forward(q)
        rotation_error = Rotation.from_matrix(native_rotation @ rotation.T).magnitude()
        comparison[side] = {
            "joint_q_rad": q.tolist(),
            "native_tcp_xyz_quat_wxyz": native.tolist(),
            "urdf_tcp_m": position.tolist(),
            "urdf_tcp_rotation": rotation.tolist(),
            "position_error_m": float(np.linalg.norm(native[:3] - position)),
            "rotation_error_deg": float(np.rad2deg(rotation_error)),
        }
    return comparison
