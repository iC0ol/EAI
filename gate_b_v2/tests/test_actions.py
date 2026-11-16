import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from gate_b_v2.actions import (
    matrix_to_rotation_6d,
    rotation_6d_to_axis_angle,
    rotation_6d_to_matrix,
    undo_transform_action,
)


@pytest.mark.parametrize(
    "rotvec",
    [
        np.zeros(3),
        np.asarray([1e-6, -2e-6, 3e-6]),
        np.asarray([0.3, -0.7, 1.1]),
        np.asarray([np.pi - 1e-4, 0.2, -0.3]),
        np.asarray([2.8, 2.9, -2.7]),
    ],
)
def test_rotation_6d_round_trip_matches_scipy(rotvec):
    matrix = Rotation.from_rotvec(rotvec).as_matrix()
    recovered = rotation_6d_to_axis_angle(matrix_to_rotation_6d(matrix))
    assert np.allclose(
        Rotation.from_rotvec(recovered).as_matrix(), matrix, atol=1e-8
    )


def test_rotation_6d_matrix_is_orthonormal():
    matrix = rotation_6d_to_matrix(np.asarray([0.2, 0.3, -0.1, 0.5, -0.4, 0.9]))
    assert np.allclose(matrix.dot(matrix.T), np.eye(3), atol=1e-12)
    assert abs(np.linalg.det(matrix) - 1.0) < 1e-12


def test_undo_transform_action_orders_position_rotation_gripper():
    identity_6d = np.asarray([1.0, 0.0, 0.0, 0.0, 1.0, 0.0])
    action = np.concatenate([[0.1, 0.2, 0.3], identity_6d, [-0.6]])
    env_action = undo_transform_action(action)
    assert env_action.shape == (7,)
    assert env_action.dtype == np.float32
    assert np.allclose(env_action[:3], [0.1, 0.2, 0.3])
    assert np.allclose(env_action[3:6], [0.0, 0.0, 0.0], atol=1e-7)
    assert np.allclose(env_action[6], -0.6)


def test_undo_transform_action_rejects_wrong_shape():
    with pytest.raises(ValueError, match="must emit 10 values"):
        undo_transform_action(np.zeros(7, dtype=np.float32))
