import random
import xml.etree.ElementTree as ET
from collections import deque

import numpy as np
import pytest

from gate_b_v2 import geometry as geometry_module
from gate_b_v2 import snapshot as snapshot_module
from gate_b_v2.snapshot import (
    _capture_object_state,
    _capture_rng,
    _restore_rng,
    load_snapshot,
    save_snapshot,
    validate_snapshot_restore,
)


class _Reference:
    pass


class SafeController:
    def __init__(self):
        self.goal_pos = np.asarray([0.1, 0.2, 0.3])
        self.goal_ori = np.eye(3)
        self.new_update = True
        self.sim = _Reference()
        self.interpolator_pos = None


class UnsafeController(SafeController):
    def __init__(self):
        super().__init__()
        self.interpolator_pos = _Reference()


class FakeGripper:
    def __init__(self):
        self.current_action = np.asarray([-1.0])
        self.rotation_offset = np.asarray([1.0, 0.0, 0.0, 0.0])
        self.tree = ET.ElementTree(ET.Element("mujoco"))
        self.root = self.tree.getroot()
        self.worldbody = ET.SubElement(self.root, "worldbody")
        self._elements = {"root": self.root}


def test_capture_object_state_audits_object_references():
    state, audit = _capture_object_state(SafeController(), "controller")
    assert "goal_pos" in state
    assert state["new_update"] is True
    skipped = {item["field"]: item for item in audit["skipped_fields"]}
    assert skipped["sim"]["classification"] == "object_reference_not_serialized"
    assert audit["capture_complete"] is True


def test_capture_object_state_blocks_unknown_mutable_field():
    with pytest.raises(RuntimeError, match="mutable controller fields"):
        _capture_object_state(UnsafeController(), "controller")


def test_gripper_xml_metadata_is_classified_immutable():
    state, audit = _capture_object_state(FakeGripper(), "gripper")
    skipped = {item["field"]: item for item in audit["skipped_fields"]}
    assert skipped["tree"]["classification"] == "immutable_model_metadata"
    assert skipped["_elements"]["classification"] == "immutable_model_metadata"
    assert np.allclose(state["current_action"], [-1.0])
    assert audit["capture_complete"] is True


def test_rng_roundtrip_legacy_and_generator():
    rng = np.random.RandomState(7)
    rng.rand(5)
    captured = _capture_rng(rng)
    expected = rng.rand(3)
    _restore_rng(rng, captured)
    assert np.allclose(rng.rand(3), expected)

    generator = np.random.default_rng(11)
    generator.random(4)
    captured = _capture_rng(generator)
    expected = generator.random(3)
    _restore_rng(generator, captured)
    assert np.allclose(generator.random(3), expected)

    python_rng = random.Random(3)
    python_rng.random()
    captured = _capture_rng(python_rng)
    expected = python_rng.random()
    _restore_rng(python_rng, captured)
    assert python_rng.random() == expected


def test_snapshot_file_roundtrip_and_sha(tmp_path):
    snapshot = {"schema_version": 2, "payload": np.arange(5)}
    path = tmp_path / "snap.pkl.gz"
    digest = save_snapshot(path, snapshot)
    loaded = load_snapshot(path)
    assert np.array_equal(loaded["payload"], snapshot["payload"])
    import hashlib
    assert digest == hashlib.sha256(path.read_bytes()).hexdigest()


_GEOMETRY = {
    "clearance_m": 0.001,
    "clearance_x_positive_m": 0.001,
    "clearance_x_negative_m": 0.002,
    "clearance_y_positive_m": 0.003,
    "clearance_y_negative_m": 0.004,
    "dx_m": 0.0,
    "dy_m": 0.0,
    "d_xy_m": 0.0,
    "relative_yaw_rad": 0.0,
    "z_gap_m": 0.01,
    "nut_bottom_local_z_m": -0.01,
    "peg_top_local_z_m": -0.02,
    "t_nut_m": 0.02,
    "r_hole_m": 0.032,
    "r_peg_m": 0.022,
    "hole_half_x_m": 0.02275,
    "hole_half_y_m": 0.02275,
    "peg_half_x_m": 0.016,
    "peg_half_y_m": 0.016,
}


class FakeRobomimicEnv:
    def get_state(self):
        return {"model": "<mujoco>fake</mujoco>", "states": np.zeros(4)}


class FakeRobosuiteEnv:
    pass


class FakeValidationEnv:
    def __init__(self, state, obs, geometry):
        self.state = np.asarray(state, dtype=float)
        self.obs = {key: np.asarray(value, dtype=float) for key, value in obs.items()}
        self.geometry = dict(geometry)
        self.step_count = 0
        self.robomimic_env = FakeRobomimicEnv()
        # The monkeypatched geometry probe reads env.geometry; in the real
        # harness this object is the robosuite environment.
        self.robosuite_env = self

    def current_sim_state(self):
        return np.asarray(self.state, dtype=float).copy()

    def policy_observation(self):
        return {key: value.copy() for key, value in self.obs.items()}

    def restore(self, snapshot):
        self.state = np.asarray(snapshot["test_state"], dtype=float).copy()
        self.obs = {key: np.asarray(value, dtype=float).copy() for key, value in snapshot["test_obs"].items()}
        self.geometry = dict(snapshot["test_geometry"])
        self.step_count = 0
        return {key: value.copy() for key, value in self.obs.items()}

    def step(self, action):
        self.step_count += 1
        self.state = self.state + 1.0
        self.obs = {key: value + 0.001 for key, value in self.obs.items()}
        partial = dict(self.geometry)
        partial["clearance_m"] += 0.0001
        self.geometry = partial
        return {key: value.copy() for key, value in self.obs.items()}, 0.0, False, {}


def _validation_fixture(monkeypatch, state=None, obs=None, geometry=None):
    state = np.zeros(4) if state is None else np.asarray(state)
    obs = {"a": np.zeros(3)} if obs is None else obs
    geometry = dict(_GEOMETRY) if geometry is None else geometry
    env = FakeValidationEnv(state, obs, geometry)
    snapshot = {
        "schema_version": 2,
        "test_state": np.asarray(state, dtype=float).copy(),
        "test_obs": {key: np.asarray(value, dtype=float).copy() for key, value in obs.items()},
        "test_geometry": dict(geometry),
        "sim_state_sha256": "simhash",
        "model_xml_sha256": "modelhash",
    }
    import hashlib

    model_hash = hashlib.sha256("<mujoco>fake</mujoco>".encode("utf-8")).hexdigest()
    monkeypatch.setattr(
        snapshot_module, "capture_validation_reference",
        lambda episode_env: {
            "sim_state": episode_env.current_sim_state(),
            "policy_observation": episode_env.policy_observation(),
            "geometry": dict(episode_env.geometry),
            "model_xml_sha256": model_hash,
        },
    )
    monkeypatch.setattr(geometry_module, "compute_square_geometry", lambda env: dict(env.geometry))
    return env, snapshot


def test_validate_snapshot_restore_passes_for_exact_snapshot(monkeypatch):
    env, snapshot = _validation_fixture(monkeypatch)
    report = validate_snapshot_restore(env, snapshot, np.zeros(7))
    assert report["passed"] is True
    assert all(report["checks"].values())
    assert report["state_max_abs"] <= 1e-7
    assert report["observation_mean_abs_max"] <= 1e-3
    assert report["geometry_abs_max"] <= 1e-6


def test_validate_snapshot_restore_fails_on_state_or_observation_or_geometry(monkeypatch):
    env, snapshot = _validation_fixture(monkeypatch)
    snapshot["test_state"] = np.asarray([1e-3, 0.0, 0.0, 0.0])
    report = validate_snapshot_restore(env, snapshot, np.zeros(7))
    assert report["passed"] is False
    assert report["checks"]["state_restore"] is False

    env, snapshot = _validation_fixture(monkeypatch)
    snapshot["test_obs"] = {"a": np.asarray([0.01, 0.0, 0.0])}
    report = validate_snapshot_restore(env, snapshot, np.zeros(7))
    assert report["passed"] is False
    assert report["checks"]["observation_restore"] is False

    env, snapshot = _validation_fixture(monkeypatch)
    altered = dict(_GEOMETRY)
    altered["z_gap_m"] += 1e-3
    snapshot["test_geometry"] = altered
    report = validate_snapshot_restore(env, snapshot, np.zeros(7))
    assert report["passed"] is False
    assert report["checks"]["geometry_restore"] is False
