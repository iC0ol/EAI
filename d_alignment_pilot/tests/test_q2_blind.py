"""Synthetic tests only. No independent lag-test actions or labels are read."""
import copy
import json
from pathlib import Path
import subprocess

import h5py
import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from d_alignment.q2.build import view_from_group
from d_alignment.q2.common import load_view, read_json, save_view, validate_view, write_json
from d_alignment.q2.estimate import estimate
from d_alignment.q2.fit import fit_anchors
from d_alignment.q2.metrics import cluster_summary, midrank, repair_metrics
from d_alignment.q2.models import calibrate, curve, fit_ridge, fit_xcorr, summarize
from d_alignment.q2.runtime import ROOT, sandbox_command, snapshot_code
from d_alignment.q2 import score as scorer
from d_alignment.q2.signals import features, motion, times

CONFIG = read_json(ROOT / "configs/q2_blind/experiment.json")
SETTINGS = CONFIG["estimator_settings"]


def synthetic(length=160, seed=4, phase=2):
    rng = np.random.default_rng(seed)
    command = rng.normal(0, .25, (length, 7))
    command[:, 3:6] = 0
    command[:, 6] = np.where(np.arange(length) < length//2, -1., 1.)
    delta = np.zeros((length, 3))
    delta[phase:] = .05 * command[:length-phase, :3]
    positions = np.vstack([np.zeros(3), np.cumsum(delta, axis=0)])
    return {"sample_id": np.asarray(f"synthetic_sample_{seed}"), "trajectory_id": np.asarray(f"synthetic_source_{seed}"),
            "command": command, "position": positions[:-1], "next_position": positions[1:],
            "quaternion": np.tile([0.,0.,0.,1.], (length,1)), "next_quaternion": np.tile([0.,0.,0.,1.], (length,1)),
            "gripper": np.zeros((length,2)), "next_gripper": np.zeros((length,2))}


def inject(view, delta):
    idx = np.arange(4, len(view["command"])-4)
    result = {k: value[idx].copy() if value.ndim else value.copy() for k,value in view.items()}
    result["command"] = view["command"][idx+delta].copy()
    return result


def small_model(view):
    return {"settings": SETTINGS, "arx": fit_ridge([view], 4, .0001, SETTINGS),
            "xcorr": fit_xcorr([view], SETTINGS),
            "calibration": {m: {"tau": .05, "quality_q95": 1000., "model_mismatch": False} for m in ("xcorr", "arx")}}


@pytest.mark.parametrize("delta", [0,-1,1,-2,2,-4,4])
def test_ramp_injection_and_oracle_inverse(tmp_path, delta):
    view = synthetic(80)
    view["command"] = np.tile(np.arange(80)[:, None], (1,7)).astype(float)
    with h5py.File(tmp_path / "fake.hdf5", "w") as f:
        group = f.create_group("demo")
        group.create_dataset("actions", data=view["command"])
        for h5key, prefix in [("obs", ""), ("next_obs", "next_")]:
            g = group.create_group(h5key)
            for key, name in [("position","robot0_eef_pos"),("quaternion","robot0_eef_quat"),("gripper","robot0_gripper_qpos")]:
                g.create_dataset(name, data=view[prefix+key])
        blinded = view_from_group(group, "anonymous_sample", "anonymous_source", delta)
    idx = times(len(blinded["command"]), SETTINGS)
    assert np.array_equal(blinded["command"], view["command"][4+np.arange(72)+delta])
    assert np.array_equal(blinded["command"][idx-delta], view["command"][4+idx])
    assert len(blinded["command"]) == 72
    assert all(np.isfinite(v).all() for k,v in blinded.items() if v.dtype.kind == "f")


def test_all_conditions_equal_lengths_and_no_nan_edge_shortcut():
    clean = synthetic()
    variants = [inject(clean, d) for d in CONFIG["injected_lags"]]
    assert len({len(v["command"]) for v in variants}) == 1
    assert [int(np.isnan(v["command"]).sum()) for v in variants] == [0]*7
    assert all(set(v) == set(variants[0]) for v in variants)


@pytest.mark.parametrize("candidate", list(range(-4,5)))
def test_every_candidate_same_times_and_guard(candidate):
    view = inject(synthetic(90), 0)
    expected = times(len(view["command"]), SETTINGS)
    for history in (1,2,4):
        x, y = features(view, history, candidate, SETTINGS)
        assert len(x) == len(y) == len(expected)
    for phase in range(5):
        indices = expected-phase-candidate
        assert indices.min() >= 0 and indices.max() < len(view["command"])
    assert np.array_equal(expected, np.arange(8,78))


@pytest.mark.parametrize("bad", ["nan", "inf", "delta_field"])
def test_reject_leaky_or_nonfinite_input(bad):
    view = synthetic()
    if bad == "delta_field":
        view["delta"] = np.asarray(2)
    else:
        view["command"][0,0] = np.nan if bad == "nan" else np.inf
    with pytest.raises(AssertionError):
        validate_view(view)


def test_rotation_world_increment_not_quaternion_difference():
    view = synthetic(40)
    current = Rotation.from_euler("xyz", [.2,-.1,.4])
    delta = Rotation.from_rotvec([.02,-.01,.03])
    view["quaternion"][:] = current.as_quat()
    view["next_quaternion"][:] = (delta*current).as_quat()
    assert np.allclose(motion(view)[:,3:6], [.02,-.01,.03])
    view["next_quaternion"] *= -1
    assert np.allclose(motion(view)[:,3:6], [.02,-.01,.03])


@pytest.mark.parametrize("delta", list(range(-4,5)))
def test_both_baselines_recover_synthetic_extra_log_lag(delta):
    clean = synthetic(240)
    model = small_model(inject(clean, 0))
    assert model["xcorr"]["phase"] == 2
    for result in estimate(inject(clean, delta), model):
        assert result["estimated_lag"] == delta
        assert len(result["scores"]) == 9


def test_filename_and_dispatch_order_invariance(tmp_path):
    clean = inject(synthetic(), 0)
    model = small_model(clean)
    a, b = tmp_path/"something_delta_plus99.npz", tmp_path/"random.npz"
    save_view(a, clean)
    b.write_bytes(a.read_bytes())
    first = estimate(load_view(a), model)
    _ = estimate(inject(synthetic(seed=8), -4), model)
    second = estimate(load_view(b), model)
    assert first == second


def test_constant_label_wrong_lag_is_negligible():
    view = synthetic(60)
    view["command"][:] = .2
    corrupted = inject(view, 4)
    idx = times(len(corrupted["command"]), SETTINGS)
    out = repair_metrics(corrupted["command"], view["command"], 4, idx, -4, SETTINGS, CONFIG["label_negligibility"], [0.,1.])
    assert out["action_exact"] and out["negligible_label_consequence"]
    assert out["gripper_switch_disagreement"] is None


def test_gripper_transition_consequence():
    clean = synthetic(100)
    shifted = inject(clean, 4)
    idx = times(len(shifted["command"]), SETTINGS)
    wrong = repair_metrics(shifted["command"], clean["command"], 4, idx, 0, SETTINGS, CONFIG["label_negligibility"], [0.,1.])
    oracle = repair_metrics(shifted["command"], clean["command"], 4, idx, 4, SETTINGS, CONFIG["label_negligibility"], [0.,1.])
    assert wrong["meaningful_switch_error"] and not wrong["negligible_label_consequence"]
    assert oracle["action_exact"] and oracle["gripper_sign_disagreement"] == 0


def test_flat_score_and_tied_rank_do_not_imply_information():
    pred = summarize(np.ones(9), {"tau":.05,"quality_q95":2,"model_mismatch":False}, SETTINGS)
    assert pred["estimated_lag"] == 0 and pred["unidentifiable"] and len(pred["near_lags"]) == 9
    assert midrank(np.ones(9), 0, 1e-10) == 5


def test_episode_cluster_bootstrap_preserves_correlated_repetitions():
    once = [{"episode":f"ep{i}","value":int(i < 8)} for i in range(16)]
    repeated = [dict(row) for row in once for _ in range(7)]
    assert cluster_summary(once,"value") == cluster_summary(repeated,"value")
    assert cluster_summary(repeated,"value")["independent_sources"] == 16


def test_scorer_refuses_before_prediction_freeze_without_truth_access(tmp_path, monkeypatch):
    touched = []
    original = scorer.read_json
    def guarded(path):
        if Path(path).name == "truth.json":
            touched.append(path)
            raise AssertionError("Truth read before freeze")
        return original(path)
    monkeypatch.setattr(scorer,"read_json",guarded)
    with pytest.raises(FileNotFoundError):
        scorer.validate_frozen_predictions(tmp_path, tmp_path)
    assert not touched


def test_estimator_dependency_boundary():
    import ast
    forbidden = {"build", "score", "runtime", "train", "evaluate", "h5py", "torch", "robosuite", "robomimic"}
    for filename in ("common.py","signals.py","models.py","fit.py","estimate.py"):
        tree = ast.parse((ROOT/"src/d_alignment/q2"/filename).read_text())
        for node in ast.walk(tree):
            if isinstance(node,ast.ImportFrom):
                assert not set((node.module or "").split(".")) & forbidden
            if isinstance(node,ast.Import):
                assert all(not set(a.name.split(".")) & forbidden for a in node.names)


def test_real_mount_namespace_blocks_host_sentinel_and_raw_dataset(tmp_path):
    code, output = tmp_path/"code", tmp_path/"output"
    snapshot_code(code)
    output.mkdir()
    secret = tmp_path/"DO_NOT_READ.txt"
    secret.write_text("synthetic truth sentinel")
    cmd = sandbox_command(code, [], output, "d_alignment.q2.probe", ["--output","/out/probe.json","--forbidden",str(secret),"--forbidden",str(ROOT/"data/raw/square_ph_low_dim_v15.hdf5"),"--forbidden","/code/d_alignment/q2/score.py"])
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    assert read_json(output/"probe.json")["all_forbidden_reads_denied"]


def test_real_isolated_estimator_loads_only_single_view(tmp_path):
    code, output = tmp_path/"code", tmp_path/"output"
    snapshot_code(code)
    output.mkdir()
    clean = inject(synthetic(),0)
    save_view(tmp_path/"view.npz",clean)
    write_json(tmp_path/"model.json",small_model(clean))
    cmd = sandbox_command(code,[(tmp_path/"view.npz","/input.npz"),(tmp_path/"model.json","/model.json")],output,"d_alignment.q2.estimate",["--input","/input.npz","--model","/model.json","--output","/out/pred.json"])
    result = subprocess.run(cmd,capture_output=True,text=True,timeout=60)
    assert result.returncode == 0,result.stderr
    assert all(r["estimated_lag"] == 0 for r in read_json(output/"pred.json"))


def test_anchor_selection_has_no_query_argument():
    import inspect
    assert list(inspect.signature(fit_anchors).parameters) == ["views","settings"]
    model, selection = fit_anchors([inject(synthetic(seed=i),0) for i in range(8)], SETTINGS)
    assert selection["query_samples_used_for_fitting_or_selection"] == 0
    assert len(selection["grid"]) == 18 and selection["folds"] == 8
    assert selection["selected_history"] == 4
    assert model["xcorr"]["phase"] == 2


def decision_fixture(error_sources=0, informative=True):
    rows = []
    for episode in range(16):
        for case in range(7):
            error = episode < error_sources and case == 0
            for method in ("xcorr", "arx", "zero"):
                rows.append({"episode":str(episode),"sample_id":f"{episode}_{case}","method":method,
                    "negligible_label_consequence":not error,"meaningful_switch_error":error,
                    "exact_lag":not error,"true_in_near_set":informative,"near_set_size":2 if informative else 9,
                    "true_midrank":2 if informative else 5,"unreliable":False,"unidentifiable":False,
                    "low_change_error_energy_fraction":0.})
    summary={m:{"top3_advantage_over_fixed":{"cluster_bootstrap_95ci":[.1,.5]},"top3_support":{"mean":.9}} for m in ("xcorr","arx")}
    selection={"arx_oof_R2":.8 if informative else -.1,"xcorr_oof_correlation":.8}
    return rows,summary,selection


def test_decision_does_not_promote_rare_error_to_method_necessity():
    rows,summary,selection=decision_fixture(1)
    assert scorer.make_decision(rows,summary,CONFIG,selection)["category"] == "A"


def test_potential_go_requires_repeated_meaningful_supported_errors():
    rows,summary,selection=decision_fixture(3)
    assert scorer.make_decision(rows,summary,CONFIG,selection)["category"] == "C"
    rows,summary,selection=decision_fixture(2)
    assert scorer.make_decision(rows,summary,CONFIG,selection)["category"] == "D"


def test_model_failure_without_lag_information_is_not_potential_go():
    rows,summary,selection=decision_fixture(3,informative=False)
    assert scorer.make_decision(rows,summary,CONFIG,selection)["category"] == "B"
