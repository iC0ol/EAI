import numpy as np
from scipy.spatial.transform import Rotation


def quat_angle(a, b):
    """Geodesic angle, xyzw; sign invariant, never quaternion subtraction."""
    a, b = np.asarray(a), np.asarray(b)
    dot = np.abs(np.sum(a * b, axis=-1) / (np.linalg.norm(a, axis=-1) * np.linalg.norm(b, axis=-1)))
    return 2 * np.arccos(np.clip(dot, 0., 1.))


def object_direction(world_direction, quat_xyzw):
    return Rotation.from_quat(quat_xyzw).as_matrix().T @ np.asarray(world_direction)


def task_direction(world_direction, peg_rotation):
    return np.asarray(peg_rotation).T @ np.asarray(world_direction)


def auxiliary(flat_obs, peg_position, peg_rotation):
    nut = np.asarray(flat_obs[:3])
    nut_R = Rotation.from_quat(flat_obs[3:7]).as_matrix()
    peg_R = np.asarray(peg_rotation)
    angle = np.arccos(np.clip(abs(nut_R[:, 2] @ peg_R[:, 2]), 0., 1.))
    return {"nut_to_peg_xy_m": float(np.linalg.norm((nut - peg_position)[:2])),
            "nut_to_peg_z_m": float(nut[2] - peg_position[2]),
            "nut_axis_to_peg_axis_rad": float(angle),
            "eef_to_nut_m": float(np.linalg.norm(flat_obs[7:10] - nut))}
