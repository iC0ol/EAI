"""Exercise the Gate B observation/step adapter with a synthetic Square task."""

from types import SimpleNamespace

import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from gate_b_v2.actions import undo_transform_action

from component_commitment import rollout


class FakeSquareWrapper:
    def __init__(self, done_at=500):
        self.done_at = done_at
        self.steps = 0
        self.seed_state_map = {}
        self.success_checks = []
        self.commands = []
        gripper = object()
        nut = SimpleNamespace(name="SquareNut", contact_geoms=["nut_contact"])
        model = SimpleNamespace(
            geom_bodyid=np.array([1, 1]), geom_type=np.array([6, 6]), geom_group=np.array([0, 1]),
            geom_contype=np.array([1, 0]), geom_conaffinity=np.array([1, 0]),
            geom_size=np.array([[0.016, 0.016, 0.1], [0.016, 0.016, 0.1]]),
            site_name2id={"osc_site": 0}.__getitem__,
        )
        self.data = SimpleNamespace(
            time=0.0,
            site_xpos=np.array([[0.02, 0.0, 0.1]]), site_xmat=np.eye(3).reshape(1, 9),
            geom_xpos=np.array([[0.0, 0.0, 0.0], [9.0, 9.0, 9.0]]),
            geom_xmat=np.array([np.eye(3), np.eye(3)]).reshape(2, 9),
            body_xpos=np.array([[0.03, 0.0, 0.1]]),
        )
        sim = SimpleNamespace(data=self.data, model=model, get_state=lambda: np.array([self.data.time]))
        robot = SimpleNamespace(controller=SimpleNamespace(eef_name="osc_site"), eef_site_id=0, gripper=gripper)

        def check_grasp(current_gripper, contact_geoms):
            assert current_gripper is gripper
            assert contact_geoms is nut.contact_geoms
            return True

        rs = SimpleNamespace(
            sim=sim, robots=[robot], nuts=[nut], obj_body_id={nut.name: 0}, obj_geom_id={nut.name: []},
            peg1_body_id=1, _check_grasp=check_grasp,
        )
        self.env = SimpleNamespace(
            env=rs, is_success=self.is_success, get_state=lambda: {"states": np.array([self.initial_seed])},
        )

    def seed(self, seed):
        self.initial_seed = seed

    def observation(self):
        return {"frame": np.array([self.steps], dtype=np.float32)}

    def reset(self):
        self.steps = 0
        self.data.time = 0.0
        self.data.body_xpos[0, 2] = 0.1
        self.success_checks.clear()
        self.commands.clear()
        return self.observation()

    def step(self, command):
        assert command.shape == (7,) and command.dtype == np.float32
        self.commands.append(command.copy())
        self.steps += 1
        self.data.time += 0.05
        self.data.body_xpos[0, 2] = (0.1, 0.101, 0.099)[self.steps % 3]
        return self.observation(), 0.0, self.steps == self.done_at, {"is_success": self.steps == 3}

    def is_success(self):
        self.success_checks.append(self.steps)
        return {"task": 11 <= self.steps <= 12}


def fake_experiment(monkeypatch, done_at=500):
    wrapper = FakeSquareWrapper(done_at)
    env = rollout.EpisodeEnvWithTaskSuccess(wrapper, {"obs": {"frame": {"shape": [1]}}}, n_obs_steps=2, max_steps=500)
    noise = SimpleNamespace(seed=None)
    reset_calls = []
    sample_times = []

    def predict(policy, torch, obs, device, n_obs_steps, prediction_horizon):
        assert policy is experiment.policy and torch is noise
        assert set(obs) == {"frame"} and n_obs_steps == 2 and prediction_horizon == 16
        t = int(obs["frame"][1, 0])
        np.testing.assert_array_equal(obs["frame"][:, 0], [max(0, t - 1), t])
        assert t == wrapper.steps
        candidate_id = noise.seed - rollout.policy_noise_seed(wrapper.initial_seed, t, 0)
        sample_times.append((t, candidate_id))
        matrix = Rotation.from_euler("z", 0.5 if t % 15 == 6 else 0.0).as_matrix()
        chunk = np.tile(np.concatenate(([0.02, 0.0, 0.1], matrix[:2].reshape(6), [1.0])), (15, 1)).astype(np.float32)
        if t % 15 == 6:
            chunk[:, 1] += 0.015
            chunk[:, 2] -= (0.020, 0.004)[candidate_id]
        return chunk

    experiment = SimpleNamespace(
        env=env, torch=noise, policy=SimpleNamespace(reset=lambda: reset_calls.append(True)), device="fake",
        n_obs_steps=2, prediction_horizon=16, max_steps=500, _env_action=undo_transform_action,
    )
    monkeypatch.setattr(rollout, "seed_everything", lambda seed: None)
    monkeypatch.setattr(rollout, "seed_policy_rng", lambda torch, seed: setattr(torch, "seed", seed))
    monkeypatch.setattr(rollout, "predict_full_future_chunk", predict)
    return experiment, wrapper, reset_calls, sample_times


def test_five_arms_pair_reset_first_chunk_and_physical_query_times(monkeypatch):
    experiment, wrapper, reset_calls, sample_times = fake_experiment(monkeypatch)
    paired_keys = set()
    for arm in rollout.ARMS:
        sample_times.clear()
        row = rollout.run_episode(experiment, 520000, arm)
        paired_keys.add((row["initial_state_hash"], row["first_chunk_sha256"]))
        assert wrapper.success_checks == list(range(1, 501))
        assert row["task_success_bits"] == "0" * 10 + "11" + "0" * 488
        assert len(wrapper.commands) == row["steps"] == 500
        assert row["first_success_step"] == 11 and row["success"] is False
        assert 0 < row["inference_seconds"] <= row["wall_seconds"]

        anchors = list(range(0, 500, 15))
        mids = [] if arm == "fixed15" else list(range(6, 500, 15))
        expected_draws = sorted([(t, 0) for t in anchors] + [(t, k) for t in mids for k in (0, 1)])
        assert sample_times == expected_draws
        assert row["policy_queries"] == len(anchors) + len(mids)
        assert row["policy_samples"] == len(expected_draws)
        for query in row["query_schedule"]:
            t = query["t"]
            assert query["phase"] == ("anchor" if t in anchors else "mid")
            assert query["noise_seeds"] == [2_000_000 + 3 * t + k for k in range(query["candidate_count"])]
            assert len(query["chunk_sha256"]) == query["candidate_count"]
        assert [event["t"] for event in row["events"]] == mids
        if arm == "fixed15":
            assert row["task_geometry"] is None
            continue

        assert row["task_geometry"]["eef_site"] == "osc_site"
        assert row["task_geometry"]["peg_geom_id"] == 0
        first, *later = row["events"]
        expected_decision = {"refresh": "fresh", "smooth": "smooth", "always_split": "split", "adaptive": "split"}[arm]
        assert first["chosen_candidate"] == 1 and first["decision"] == expected_decision
        assert first["eligible"] and first["admissible"] and first["pre_success"]
        assert first["axial_rms_m"] == pytest.approx(0.004, abs=1e-8)
        assert first["old_action_indices"] == list(range(6, 15))
        assert first["new_action_indices"] == list(range(9))
        assert first["actual_hole_upward_travel_m"] == pytest.approx(0.006)
        assert first["actual_hole_axial_start_m"] == first["actual_hole_axial_end_m"] == 0.1
        assert first["actual_hole_lateral_start_m"] == first["actual_hole_lateral_end_m"] == 0.03
        assert len(first["actual_hole_axial_m"]) == len(first["actual_hole_lateral_m"]) == 10
        assert first["issued_gripper_max_abs_error"] == 0.0
        if expected_decision == "split":
            np.testing.assert_allclose(first["issued_hole_axial_minus_old_m"], np.zeros(9), atol=2e-8)
            assert first["issued_hole_axial_minus_new_rms_m"] == pytest.approx(0.004, abs=1e-8)
        if expected_decision == "smooth":
            assert first["issued_hole_lateral_max_error_m"] > 1e-3
            assert first["issued_orientation_max_error_rad"] == pytest.approx(0.375, abs=1e-7)
            np.testing.assert_allclose(first["issued_hole_axial_minus_new_m"][3:], np.zeros(6), atol=2e-8)
        else:
            assert first["issued_hole_lateral_max_error_m"] < 2e-8
            assert first["issued_orientation_max_error_rad"] < 2e-8
        assert all(event["decision"] == "fresh" and event["chosen_candidate"] == 0 for event in later)
        assert all(not event["eligible"] and not event["pre_success"] for event in later)
    assert len(paired_keys) == 1
    assert len(reset_calls) == 5


def test_early_done_aborts_instead_of_emitting_short_row(monkeypatch):
    experiment, _, _, _ = fake_experiment(monkeypatch, done_at=17)
    with pytest.raises(RuntimeError, match="terminated early at step 17"):
        rollout.run_episode(experiment, 520096, "adaptive")


def test_policy_noise_is_unique_across_study_seed_and_time_coordinates():
    seeds = range(520000, 520101)
    assert len({rollout.policy_noise_seed(seed, t, k) for seed in seeds for t in range(500) for k in (0, 1)}) == len(seeds) * 500 * 2
