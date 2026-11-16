import numpy as np

from gate_b_v2.analysis import _slope


def test_clearance_interaction_slope():
    x = np.asarray([-0.02, -0.01, 0.0, 0.01, 0.02])
    y = 2.0 * x + 0.5
    assert abs(_slope(x, y) - 2.0) < 1e-10
