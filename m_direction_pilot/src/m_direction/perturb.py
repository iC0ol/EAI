import numpy as np

DIRECTIONS = dict(zip(["x", "y", "z"], np.eye(3)))
DIRECTIONS.update({"xy": np.array([1., 1., 0.]) / np.sqrt(2),
                   "xz": np.array([1., 0., 1.]) / np.sqrt(2),
                   "yz": np.array([0., 1., 1.]) / np.sqrt(2)})


def intervention(expert, direction, sign, radius):
    expert = np.asarray(expert, dtype=np.float64)
    if expert.shape != (7,) or not np.isfinite(expert).all():
        raise ValueError("invalid expert control command")
    delta = np.zeros(7)
    if direction != "nominal":
        if sign not in (-1, 1) or radius <= 0:
            raise ValueError("invalid direction/sign/radius")
        delta[:3] = DIRECTIONS[direction] * sign * radius
    elif sign != 0 or radius != 0:
        raise ValueError("nominal is exactly expert step")
    requested = expert + delta
    # Translation must be strictly interior. Gripper +-1 is a valid unchanged
    # expert command, not a translation clipping event.
    if np.any(np.abs(requested[:3]) >= 1.) or np.any(np.abs(requested[3:6]) > 1.) or abs(requested[6]) > 1.:
        raise ValueError("technical rejection: action touches/exceeds command boundary")
    if not np.array_equal(requested[3:], expert[3:]):
        raise AssertionError("non-translation expert command changed")
    return requested, delta
