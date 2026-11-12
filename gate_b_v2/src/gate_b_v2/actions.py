"""Action-space helpers for the official Square-MH absolute-action checkpoint.

The archived checkpoint uses Diffusion Policy's absolute-action variant:
a 10-D policy action = 3 absolute position + 6-D rotation + 1 gripper.
The robosuite OSC_POSE controller consumes a 7-D action
(3 position + 3 axis-angle + 1 gripper) with control_delta=False.

Diffusion Policy performs this conversion with
``RotationTransformer('axis_angle', 'rotation_6d').inverse`` and pytorch3d.
The two functions below reproduce pytorch3d's exact 6-D convention without
adding a CUDA-compiled pytorch3d dependency. Tests verify the round trip
against scipy's independent rotation implementation.
"""
from __future__ import annotations

import numpy as np


def rotation_6d_to_matrix(d6: np.ndarray) -> np.ndarray:
    """pytorch3d ``rotation_6d_to_matrix``: rows are (b1, b2, b1 x b2)."""
    value = np.asarray(d6, dtype=np.float64)
    if value.shape != (6,):
        raise ValueError("Expected a 6-D rotation vector, got {}".format(value.shape))
    a1, a2 = value[:3], value[3:]
    n1 = float(np.linalg.norm(a1))
    if n1 < 1e-12:
        raise ValueError("Degenerate rotation-6D first axis")
    b1 = a1 / n1
    b2 = a2 - float(np.dot(b1, a2)) * b1
    n2 = float(np.linalg.norm(b2))
    if n2 < 1e-12:
        raise ValueError("Degenerate rotation-6D second axis")
    b2 = b2 / n2
    b3 = np.cross(b1, b2)
    return np.stack([b1, b2, b3], axis=0)


def matrix_to_rotation_6d(matrix: np.ndarray) -> np.ndarray:
    """pytorch3d ``matrix_to_rotation_6d``: flatten the first two rows."""
    value = np.asarray(matrix, dtype=np.float64)
    if value.shape != (3, 3):
        raise ValueError("Expected a 3x3 rotation matrix, got {}".format(value.shape))
    return value[:2, :].reshape(6).copy()


def rotation_6d_to_axis_angle(d6: np.ndarray) -> np.ndarray:
    """pytorch3d ``rotation_6d_to_axis_angle`` via an orthonormal matrix."""
    from scipy.spatial.transform import Rotation

    matrix = rotation_6d_to_matrix(d6)
    return np.asarray(Rotation.from_matrix(matrix).as_rotvec(), dtype=np.float64)


def undo_transform_action(action: np.ndarray) -> np.ndarray:
    """Convert one 10-D absolute policy action to a 7-D OSC_POSE env action."""
    value = np.asarray(action, dtype=np.float64)
    if value.shape != (10,):
        raise ValueError(
            "Absolute-action policy must emit 10 values, got {}".format(value.shape)
        )
    position = value[:3]
    rotation_6d = value[3:9]
    gripper = value[9:10]
    rotation_axis_angle = rotation_6d_to_axis_angle(rotation_6d)
    return np.concatenate(
        [position, rotation_axis_angle, gripper], axis=-1
    ).astype(np.float32)
