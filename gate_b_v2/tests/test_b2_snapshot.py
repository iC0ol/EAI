import random
import xml.etree.ElementTree as ET
from collections import deque
from types import SimpleNamespace

import numpy as np
import pytest

from b2_test_data import GEOMETRY as _GEOMETRY

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


class FakeValidationEnv:
    def __init__(self, state, obs, geometry):
        self.state = np.asarray(state, dtype=float)
        self.history = deque(maxlen=2)
        self._set_history(obs)
        self.fresh = {key: value.copy() for key, value in obs.items()}
        self.fresh_error = None
        self.geometry = dict(geometry)
        self.step_count = 0
        self.steps = 124
        self.shape_meta = {"obs": {
            key: {"type": "rgb" if key == "rgb" else "low_dim"} for key in obs
        }}
        self.robomimic_env = SimpleNamespace(get_state=self.get_state)
        self.robosuite_env = self
        self.robots = [SimpleNamespace(controller=SafeController(), gripper=FakeGripper())]
        self.sim = SimpleNamespace(data=SimpleNamespace(
            **{key: np.zeros(1) for key in snapshot_module._MUJOCO_DATA_FIELDS}
        ))

    def get_state(self):
        return {"model": "<mujoco>fake</mujoco>", "states": self.state.copy()}

    def _set_history(self, obs):
        frame = {key: np.array(value, copy=True) for key, value in obs.items()}
        self.history.clear()
        self.history.extend((frame, frame))

    def current_sim_state(self):
        return self.state.copy()

    def policy_observation(self):
        return {key: np.stack([item[key] for item in self.history]) for key in self.history[-1]}

    def fresh_observation(self):
        if self.fresh_error:
            raise RuntimeError(self.fresh_error)
        return {key: value.copy() for key, value in self.fresh.items()}

    def restore(self, snapshot):
        self.state = snapshot["test_state"].copy()
        self._set_history(snapshot["test_obs"])
        self.fresh = snapshot["test_fresh"]
        self.fresh_error = snapshot.get("render_error")
        self.geometry = dict(snapshot["test_geometry"])
        self.step_count = 0
        self.robots[0].gripper.current_action[:] = snapshot.get("gripper_action", -1.0)

    def step(self, action, *, strict=False):
        self.step_count += 1
        self.state = self.state + 1.0
        self.history.append({key: value + 0.001 for key, value in self.history[-1].items()})
        self.geometry["clearance_m"] += 0.0001
        return self.history[-1], 0.0, False, {}


def _validation_fixture(monkeypatch, state=None, obs=None, geometry=None):
    state = np.zeros(4) if state is None else np.asarray(state, dtype=float)
    obs = {"a": np.zeros(3), "rgb": np.zeros((3, 2, 2), dtype=np.float32)} if obs is None else obs
    geometry = dict(_GEOMETRY) if geometry is None else geometry
    env = FakeValidationEnv(state, obs, geometry)
    reference = snapshot_module.capture_validation_reference(env, geometry)
    snapshot = {
        "schema_version": snapshot_module.SNAPSHOT_SCHEMA_VERSION,
        "validation_reference": reference,
        "env_state": env.get_state(),
        "test_state": state.copy(),
        "test_obs": dict(obs),
        "test_fresh": dict(obs),
        "test_geometry": dict(geometry),
        "sim_state_sha256": snapshot_module.sim_state_sha256(state),
        "model_xml_sha256": reference["model_xml_sha256"],
    }
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
    snapshot["test_obs"]["a"] = np.asarray([0.01, 0.0, 0.0])
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


def test_original_reference_is_not_replaced_by_the_live_env_or_consistent_replays(monkeypatch):
    env, snapshot = _validation_fixture(monkeypatch)
    snapshot["validation_reference"]["sim_state"][0] = 0.02
    env.restore(snapshot)
    report = validate_snapshot_restore(env, snapshot, np.zeros(7))
    assert report["status"] == "BLOCKED"
    assert report["checks"]["deterministic_state"] is True
    assert report["checks"]["deterministic_observation"] is True
    assert report["checks"]["state_restore"] is False
    assert report["checks"]["snapshot_payload_matches_source"] is False
    assert report["original_vs_restored_max_abs_error"] == 0.02


def test_policy_history_and_fresh_rgb_are_independent_checks(monkeypatch):
    env, snapshot = _validation_fixture(monkeypatch)
    snapshot["test_fresh"]["rgb"] = np.full((3, 2, 2), 0.01, dtype=np.float32)
    report = validate_snapshot_restore(env, snapshot, np.zeros(7))
    assert report["status"] == "BLOCKED"
    assert report["checks"]["observation_restore"] is True
    assert report["fresh_observation_status"] == "BLOCKED"
    history = report["observation_history_comparison"]["by_key"]["rgb"]
    assert history["original_shape"] == [2, 3, 2, 2]
    assert history["restored_shape"] == [2, 3, 2, 2]
    fresh = report["fresh_observation_comparison"]["by_key"]["rgb"]
    assert fresh["observation_key"] == "rgb"
    assert fresh["original_shape"] == fresh["restored_shape"] == [3, 2, 2]
    assert fresh["original_dtype"] == fresh["restored_dtype"] == "float32"
    assert fresh["mean_abs_error"] == pytest.approx(0.01)
    assert fresh["max_abs_error"] == pytest.approx(0.01)
    assert report["fresh_observation_comparison"]["by_key"]["a"]["passed"]


def test_fresh_renderer_unavailable_blocks_even_if_history_matches(monkeypatch):
    env, snapshot = _validation_fixture(monkeypatch)
    snapshot["render_error"] = "camera context lost"
    report = validate_snapshot_restore(env, snapshot, np.zeros(7))
    assert report["status"] == "BLOCKED"
    assert report["checks"]["observation_restore"] is True
    assert report["fresh_observation_status"] == "BLOCKED"
    assert report["restore_fresh_observation_error"] == "RuntimeError: camera context lost"


def test_state_hash_diagnostics_distinguish_representation_and_value_changes():
    original = np.array([0.0, 1.0], dtype=">f8")
    restored = np.array([-0.0, 8.0, 1.0, 9.0], dtype="<f8")[::2]
    report = snapshot_module.compare_sim_state(original, restored)
    assert report["max_abs_error"] == 0.0
    assert report["original_legacy_sha256"] != report["restored_legacy_sha256"]
    assert report["original_state_sha256"] == report["restored_state_sha256"]
    assert report["original_strides"] != report["restored_strides"]


def test_state_tolerance_is_checked_against_original_capture(monkeypatch):
    for delta, expected in ((9e-8, "PASS"), (1.1e-7, "BLOCKED")):
        env, snapshot = _validation_fixture(monkeypatch)
        snapshot["test_state"][0] = delta
        report = validate_snapshot_restore(env, snapshot, np.zeros(7))
        assert report["status"] == expected
        assert report["original_vs_restored_max_abs_error"] == delta


def test_yaw_uses_wrapped_radians_and_geometry_checks_meters_separately(monkeypatch):
    geometry = dict(_GEOMETRY, relative_yaw_rad=np.pi - 1e-7)
    env, snapshot = _validation_fixture(monkeypatch, geometry=geometry)
    snapshot["test_geometry"]["relative_yaw_rad"] = -np.pi + 1e-7
    snapshot["test_geometry"]["z_gap_m"] += 1.2e-6
    report = validate_snapshot_restore(env, snapshot, np.zeros(7))
    assert report["status"] == "BLOCKED"
    geometry = report["geometry_comparison"]
    assert geometry["relative_yaw_abs_error_rad"] == pytest.approx(2e-7)
    assert geometry["max_abs_error_m"] == pytest.approx(1.2e-6)
    assert "relative_yaw_rad" not in geometry["abs_error_by_metric_m"]


def test_controller_and_gripper_changes_are_detected(monkeypatch):
    env, snapshot = _validation_fixture(monkeypatch)
    snapshot["gripper_action"] = 0.5
    report = validate_snapshot_restore(env, snapshot, np.zeros(7))
    assert report["status"] == "BLOCKED"
    assert report["controller_gripper"]["0.gripper"]["mismatched_fields"] == ["current_action"]


def test_load_snapshot_rejects_changed_file_before_deserialization(tmp_path):
    path = tmp_path / "snap.pkl.gz"
    digest = save_snapshot(path, {"schema_version": 2})
    path.write_bytes(b"corrupted bytes")
    with pytest.raises(RuntimeError, match="SHA256 mismatch"):
        load_snapshot(path, expected_sha256=digest)
