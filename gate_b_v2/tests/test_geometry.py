import numpy as np

from gate_b_v2.geometry import compute_square_clearance, infer_square_nut_hole_half_extents


class FakeModel:
    def __init__(self):
        self.geom_type = np.asarray([6, 6, 6, 6, 6, 6])
        self.geom_bodyid = np.asarray([3, 3, 3, 3, 3, 2])
        self.geom_contype = np.ones(6, dtype=int)
        self.geom_conaffinity = np.ones(6, dtype=int)
        self.geom_group = np.zeros(6, dtype=int)
        self.geom_size = np.asarray([
            [0.0105, 0.04375, 0.01],
            [0.0105, 0.04375, 0.01],
            [0.03125, 0.0105, 0.01],
            [0.03125, 0.0105, 0.01],
            [0.02525, 0.015875, 0.01],
            [0.016, 0.016, 0.1],
        ])


class FakeData:
    def __init__(self, peg_x=0.0, peg_y=0.0, peg_yaw=0.0):
        self.body_xpos = np.asarray([[0, 0, 0], [0, 0, 0.1], [peg_x, peg_y, 0]], dtype=float)
        self.body_xmat = np.asarray([np.eye(3).reshape(-1), np.eye(3).reshape(-1), np.eye(3).reshape(-1)])
        self.geom_xpos = np.asarray([
            [-0.03325, 0, 0.1], [0.03325, 0, 0.1], [0, 0.03325, 0.1],
            [0, -0.03325, 0.1], [0.054, 0, 0.1], [peg_x, peg_y, 0],
        ], dtype=float)
        c, s = np.cos(peg_yaw), np.sin(peg_yaw)
        peg_rot = np.asarray([[c, -s, 0], [s, c, 0], [0, 0, 1]], dtype=float)
        self.geom_xmat = np.asarray([np.eye(3).reshape(-1)] * 5 + [peg_rot.reshape(-1)])


class FakeSim:
    def __init__(self, peg_x=0.0, peg_y=0.0, peg_yaw=0.0):
        self.model = FakeModel()
        self.data = FakeData(peg_x, peg_y, peg_yaw)


class FakeNut:
    name = "SquareNut"


class FakeEnv:
    def __init__(self, peg_x=0.0, peg_y=0.0, peg_yaw=0.0):
        self.sim = FakeSim(peg_x, peg_y, peg_yaw)
        self.nuts = [FakeNut()]
        self.obj_body_id = {"SquareNut": 1}
        self.obj_geom_id = {"SquareNut": [0, 1, 2, 3, 4]}
        self.peg1_body_id = 2


def test_infers_square_nut_aperture_from_four_live_bars():
    env = FakeEnv()
    hole = infer_square_nut_hole_half_extents(env)
    assert np.allclose(hole, [0.02275, 0.02275], atol=1e-8)


def test_signed_clearance_centered_square_peg():
    result = compute_square_clearance(FakeEnv())
    assert abs(result["clearance_m"] - 0.00675) < 1e-8
    assert abs(result["dx_m"]) < 1e-8
    assert abs(result["dy_m"]) < 1e-8


def test_signed_clearance_detects_offset_and_yaw():
    offset = compute_square_clearance(FakeEnv(peg_x=0.01))
    rotated = compute_square_clearance(FakeEnv(peg_yaw=np.pi / 4))
    assert offset["clearance_m"] < 0
    assert 0 <= rotated["clearance_m"] < 0.001
