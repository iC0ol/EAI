import numpy as np
import pytest

from gate_b_v2.geometry import (
    GeometryError,
    STAGE_GATE_VERSION,
    compute_square_geometry,
    evaluate_stage_gate,
    square_nut_aperture,
)


_AXIS = np.asarray([[1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=float)


def _rot_x(angle):
    c, s = np.cos(angle), np.sin(angle)
    return np.asarray([[1, 0, 0], [0, c, -s], [0, s, c]], dtype=float)


class FakeModel:
    def __init__(self, peg_type=6, drop_bar=None, asymmetric=False):
        bar_specs = [
            (-0.03325, 0.0, 0.0, 0.0105, 0.04375, 0.01),
            (0.03325, 0.0, 0.0, 0.0105, 0.04375, 0.01),
            (0.0, 0.03325, 0.0, 0.03125, 0.0105, 0.01),
            (0.0, -0.03325, 0.0, 0.03125, 0.0105, 0.01),
            (0.054, 0.0, 0.0, 0.02525, 0.015875, 0.01),
        ]
        if drop_bar is not None:
            bar_specs.pop(drop_bar)
        if asymmetric:
            bar_specs[1] = (0.03425, 0.0, 0.0, 0.0105, 0.04375, 0.01)
        self.geom_type = np.asarray([6] * len(bar_specs) + [peg_type])
        self.geom_bodyid = np.asarray([1] * len(bar_specs) + [2])
        self.geom_contype = np.asarray([1] * len(bar_specs) + [1])
        self.geom_conaffinity = np.asarray([1] * len(bar_specs) + [1])
        self.geom_group = np.asarray([0] * len(bar_specs) + [0])
        self.geom_size = np.asarray(
            [[size_x, size_y, size_z] for _, _, _, size_x, size_y, size_z in bar_specs]
            + [[0.016, 0.016, 0.1]]
        )
        self.geom_pos = np.asarray([[x, y, z] for x, y, z, _, _, _ in bar_specs] + [[0.0, 0.0, 0.0]])
        self.geom_quat = np.asarray([[1.0, 0.0, 0.0, 0.0]] * (len(bar_specs) + 1))
        self.body_jntadr = np.asarray([-1, 0, -1])
        self.body_jntnum = np.asarray([0, 1, 0])
        self.jnt_type = np.asarray([0])
        self.jnt_qposadr = np.asarray([0])

    def body_id2name(self, body_id):
        return {1: "SquareNut_main", 2: "peg1"}.get(int(body_id), "world")

    def get_xml(self):
        return "<mujoco>fake-square</mujoco>"


class FakeData:
    def __init__(self, model, nut_pos, nut_rot, peg_pos=(0.0, 0.0, 0.95)):
        self.model = model
        self.body_xpos = np.asarray([np.zeros(3), nut_pos, peg_pos], dtype=float)
        self.body_xmat = np.asarray(
            [_AXIS.reshape(-1), np.asarray(nut_rot).reshape(-1), _AXIS.reshape(-1)]
        )
        geom_xpos = []
        geom_xmat = []
        for index in range(len(model.geom_type)):
            if int(model.geom_bodyid[index]) == 1:
                geom_xpos.append(np.asarray(nut_pos) + np.asarray(nut_rot).dot(model.geom_pos[index]))
                geom_xmat.append(np.asarray(nut_rot).reshape(-1))
            else:
                geom_xpos.append(np.asarray(peg_pos) + model.geom_pos[index])
                geom_xmat.append(_AXIS.reshape(-1))
        self.geom_xpos = np.asarray(geom_xpos)
        self.geom_xmat = np.asarray(geom_xmat)
        self.qpos = np.asarray([0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0])


class FakeSim:
    def __init__(self, model, data):
        self.model = model
        self.data = data
        self.forward = lambda: None


class FakeNut:
    name = "SquareNut"


class FakeEnv:
    def __init__(self, nut_pos=(0.0, 0.0, 1.07), nut_rot=None, peg_type=6,
                 drop_bar=None, asymmetric=False):
        nut_rot = _AXIS if nut_rot is None else np.asarray(nut_rot)
        self.model = FakeModel(peg_type=peg_type, drop_bar=drop_bar, asymmetric=asymmetric)
        self.data = FakeData(self.model, nut_pos, nut_rot)
        self.sim = FakeSim(self.model, self.data)
        self.nuts = [FakeNut()]
        self.obj_body_id = {"SquareNut": 1}
        self.obj_geom_id = {"SquareNut": list(range(len(self.model.geom_type) - 1))}
        self.peg1_body_id = 2


def test_aperture_uses_exactly_four_mirror_paired_bars():
    env = FakeEnv()
    info = square_nut_aperture(env)
    assert len(info["aperture_bar_geom_ids"]) == 4
    assert info["handle_geom_ids"] == [4]
    assert abs(info["t_nut_m"] - 0.02) < 1e-12
    assert abs(info["hole_half_x_m"] - 0.02275) < 1e-12
    assert abs(info["hole_half_y_m"] - 0.02275) < 1e-12


def test_signed_c_xy_positive_zero_negative_in_nut_local_frame():
    centered = compute_square_geometry(FakeEnv(nut_pos=(0.0, 0.0, 1.07)))
    assert centered["clearance_m"] > 0
    assert abs(centered["clearance_m"] - 0.00675) < 1e-9

    # Moving the nut in +x gives dx_m < 0; the projected boundary gap is zero
    # when the peg's near face touches the aperture face.
    zero = compute_square_geometry(FakeEnv(nut_pos=(0.00675, 0.0, 1.07)))
    assert abs(zero["clearance_m"]) < 1e-9

    negative = compute_square_geometry(FakeEnv(nut_pos=(0.02, 0.0, 1.07)))
    assert negative["clearance_m"] < 0


def test_signed_z_gap_positive_zero_negative_in_nut_local_frame():
    # peg top is at 1.05; nut thickness 0.02.
    positive = compute_square_geometry(FakeEnv(nut_pos=(0.0, 0.0, 1.07)))
    zero = compute_square_geometry(FakeEnv(nut_pos=(0.0, 0.0, 1.06)))
    negative = compute_square_geometry(FakeEnv(nut_pos=(0.0, 0.0, 1.05)))
    assert abs(positive["z_gap_m"] - 0.01) < 1e-9
    assert abs(zero["z_gap_m"]) < 1e-9
    assert abs(negative["z_gap_m"] + 0.01) < 1e-9
    assert positive["z_gap_m"] > zero["z_gap_m"] > negative["z_gap_m"]


def test_tilted_nut_local_axial_gap_differs_from_world_z():
    env = FakeEnv(nut_pos=(0.0, 0.0, 1.13), nut_rot=_rot_x(np.deg2rad(30.0)))
    geometry = compute_square_geometry(env)
    assert abs(geometry["world_vs_local_z_gap_difference_m"]) > 1e-4
    assert np.isfinite(geometry["z_gap_m"])
    assert geometry["t_nut_m"] > 0


def test_stage_gate_boundaries_and_approach_direction():
    base = {
        "z_gap_m": 0.01,
        "t_nut_m": 0.02,
        "d_xy_m": 0.02,
        "r_hole_m": 0.032,
        "r_peg_m": 0.022,
        "clearance_m": 0.0,
        "stage_gate_version": STAGE_GATE_VERSION,
    }
    assert evaluate_stage_gate(base, previous_z_gap_m=0.02)["eligible"] is True
    # Boundary: z_gap == t_nut is allowed.
    at_top = dict(base, z_gap_m=0.02)
    assert evaluate_stage_gate(at_top, previous_z_gap_m=0.03)["eligible"] is True
    # z_gap == 0 is not.
    at_contact = dict(base, z_gap_m=0.0)
    assert evaluate_stage_gate(at_contact, previous_z_gap_m=0.01)["eligible"] is False
    # Beyond the nut thickness is not.
    above = dict(base, z_gap_m=0.021)
    assert evaluate_stage_gate(above, previous_z_gap_m=0.03)["eligible"] is False
    # XY envelope boundary is allowed, beyond is not.
    at_xy = dict(base, d_xy_m=0.054)
    assert evaluate_stage_gate(at_xy, previous_z_gap_m=0.02)["eligible"] is True
    beyond_xy = dict(base, d_xy_m=0.055)
    assert evaluate_stage_gate(beyond_xy, previous_z_gap_m=0.02)["eligible"] is False
    # Retreating is not eligible; no previous is not eligible.
    assert evaluate_stage_gate(base, previous_z_gap_m=0.005)["eligible"] is False
    assert evaluate_stage_gate(base, previous_z_gap_m=None)["eligible"] is False


def test_ambiguous_aperture_fails_closed():
    with pytest.raises(GeometryError, match="four aperture bars|mirror"):
        compute_square_geometry(FakeEnv(drop_bar=0))
    with pytest.raises(GeometryError, match="asymmetric|mirror|distinguish"):
        compute_square_geometry(FakeEnv(asymmetric=True))


def test_non_box_peg_fails_closed():
    with pytest.raises(GeometryError, match="No collision box geom"):
        compute_square_geometry(FakeEnv(peg_type=5))


def test_live_geometry_audit_writes_blocked_on_ambiguous_geometry(tmp_path):
    from gate_b_v2.geometry import run_live_geometry_audit

    output = tmp_path / "b2_geometry_audit.json"
    audit = run_live_geometry_audit(FakeEnv(drop_bar=0), output)
    assert audit["status"] == "BLOCKED"
    assert audit["marker"] == "PREFLIGHT"
    assert output.is_file()
    import json
    stored = json.loads(output.read_text(encoding="utf-8"))
    assert stored["status"] == "BLOCKED"
    assert "reason" in stored
