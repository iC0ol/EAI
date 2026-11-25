"""Recompute episode identities, pairing, policy horizons, geometry and task endpoints."""

import argparse
import hashlib
import sys

import numpy as np
from scipy.spatial.transform import Rotation

from design import CACHE_SHA, LIMITS, ROOT, SIM, STAGES, TASKS, UPSTREAM, file_hash, methods, pair_dir, read_json, scenes, verify_record, write_json
from supervise import FORMAL, accepted_root, engineering_path

sys.path[:0] = [str(UPSTREAM / "pace/src"), str(ROOT.parent)]
from pace import select_horizon
from pace_robotwin.controller import AlohaKinematics


def check(condition, message):
    if not condition:
        raise ValueError(message)


def native_task_success(task, snapshot):
    points = np.asarray(snapshot["points"])
    check(np.isfinite(points).all() and np.isfinite(snapshot["grippers"]).all(), "nonfinite terminal geometry")
    if task == "stack_blocks_three":
        placed = (np.abs(np.diff(points, axis=0) - [0, 0, .05]) < [.025, .025, .012]).all()
    else:
        placed = (np.abs(points[0] - points[1]) < [.045, .04, .04]).all()
    succeeded = bool(placed and min(snapshot["grippers"]) > .8)
    check(succeeded == snapshot["native_predicate"], "native success disagrees with recorded geometry")
    return succeeded


def audit_arm(arm, arm_log, old, previous_h, new, proposed, state, h, columns, gripper):
    window = min(8, 50 - previous_h, h) if old is not None else 0
    unchanged = np.array_equal(new[:, columns], proposed[:, columns])
    check(bool(arm_log["applied"]) != unchanged, "arm change flag disagrees with proposed joint values")
    if window < 3:
        check(unchanged and not arm_log["eligible"], "changes on a missing/short overlap")
        return
    previous = old[previous_h:previous_h + window, columns]
    new_q = new[:window, columns]
    old_p = np.array([arm.forward(q)[0] for q in previous])
    new_fk = [arm.forward(q) for q in new_q]
    new_p = np.array([value[0] for value in new_fk])
    old_vector = old_p[-1] - arm.forward(old[previous_h - 1, columns])[0]
    new_vector = new_p[-1] - arm.forward(state[columns])[0]
    old_norm = np.linalg.norm(old_vector)
    new_norm = np.linalg.norm(new_vector)
    axis = old_vector / old_norm if old_norm > 0 else np.zeros(3)
    axial = (old_p - new_p) @ axis
    grippers = np.r_[old[previous_h:previous_h + window, gripper], new[:window, gripper], state[gripper]]
    eligible = (
        min(old_norm, new_norm) >= .004
        and (new_vector @ axis) / new_norm >= np.sqrt(.5)
        and (grippers.max() <= .25 or grippers.min() >= .75) and np.ptp(grippers) <= .15
        and np.sqrt(np.mean(axial**2)) <= .010 and max(np.abs(axial)) <= .020
    )
    check(bool(arm_log["eligible"]) == bool(eligible), "logged geometric gate differs from independent FK")
    if not eligible:
        check(unchanged, "ineligible arm changed")
        return
    shift = np.linspace(1., 0., window) * axial
    np.testing.assert_allclose(arm_log["proposed_axial_m"], shift, rtol=1e-4, atol=2e-7)
    if unchanged:
        check(arm_log["release_reason"].startswith("ik_") or arm_log["release_reason"] == "no_joint_change",
              "eligible arm reverted without an IK reason")
        return
    check(np.array_equal(proposed[window-1:, columns], new[window-1:, columns]), "correction leaks beyond taper")
    q = proposed[:window, columns]
    check(np.all((arm.lower <= q) & (q <= arm.upper)) and np.max(np.abs(q - new_q)) <= .120001, "joint bound exceeded")
    for k, target in enumerate(q):
        position, rotation = arm.forward(target)
        delta = position - new_p[k]
        check(abs(float(delta @ axis) - arm_log["actual_axial_m"][k]) < 1e-6, "logged shift differs from issued FK")
        check(np.linalg.norm(delta - axis * shift[k]) <= .000501, "translation differs from registered correction")
        check(np.degrees(Rotation.from_matrix(rotation @ new_fk[k][1].T).magnitude()) <= .5001,
              "orientation residual exceeds registered bound")


def audit_trial(path, identity, model, threshold, common):
    r = verify_record(path, identity)
    task, method = r["task"], r["method"]
    limit = LIMITS[task]
    check(type(r["success"]) is bool and r["step_limit"] == limit and r["cache_sha256"] == CACHE_SHA, "bad trial metadata")
    check(1 <= r["steps"] <= limit and (r["success"] or r["steps"] == limit), "bad termination or step limit")
    check(not native_task_success(task, r["predicate_initial"]), "scene started successful")
    check(native_task_success(task, r["predicate_terminal"]) == r["success"], "terminal success label disagrees")
    check(r["initial_sha256"] == common, "shared input hash mismatch")
    expected_meta = {"task": task, "config": f"pi05_robotwin_{task}", "action_horizon": 50, "action_dim": 14,
                     "candidate_count": 1, "denoising_steps": 10, "action_space": "absolute_joint"}
    check(all(r["policy_metadata"][k] == v for k, v in expected_meta.items()), "model metadata mismatch")
    check(r["native_reset"]["physics_max"] <= 1e-4 and r["native_reset"]["state_max"] <= 1e-5, "reset drift")
    for cam in ("cam_high", "cam_left_wrist", "cam_right_wrist"):
        diff = r["native_reset"][cam]
        check(diff["mean_gray"] <= 5 and diff["p99_gray"] <= 30, "reset camera drift")
    if r["stage"] == "engineering":
        for t in ("initial", "terminal"):
            for side in ("left", "right"):
                test = r["native_fk"][t][side]
                check(test["position_error_m"] <= .0005 and test["rotation_error_deg"] <= .5, f"native FK failed {t}/{side}: {test}")
    step = 0
    previous_h = 0
    with np.load(path / "chunks.npz", allow_pickle=False) as saved:
        raw, proposed, issued, states = (saved[k] for k in ("raw", "proposed", "issued", "states"))
        queries = r["queries"]
        check(queries == len(r["query_log"]) and raw.shape == proposed.shape == (queries, 50, 14), "wrong query or candidate budget")
        check(states.shape == (queries, 14) and issued.shape == (r["steps"], 14), "invalid state/issued shapes")
        check(all(np.isfinite(a).all() for a in (raw, proposed, issued, states)), "nonfinite policy/action")
        first = np.ascontiguousarray(raw[0])
        digest = hashlib.sha256(str(first.shape).encode() + first.dtype.str.encode() + first.tobytes()).hexdigest()
        check(r["first_raw_sha256"] == digest, "first policy response hash mismatch")
        with np.load(path.parent / "initial.npz", allow_pickle=False) as anchor:
            check(np.array_equal(states[0], anchor["state"]) and str(anchor["prompt"]) == r["instruction"],
                  "first model state or instruction disagrees with native anchor")
        for i, log in enumerate(r["query_log"]):
            h = int(method[5:]) if method.startswith("fixed") else int(select_horizon(raw[i], threshold))
            check((log["step"], log["h"], log["index"]) == (step, h, i), "official selector or timing differs")
            n = min(h, r["steps"] - step)
            check(n > 0 and np.array_equal(issued[step:step+n], proposed[i, :n]), "executed prefix differs from trace")
            for name in ("rpc_s", "policy_s", "server_s", "selection_s", "component_s"):
                check(np.isfinite(log[name]) and log[name] >= 0, f"invalid {name}")
            if method == "component":
                dec = log["decision"]
                check(dec["h"] == h and dec["prev_h"] == (previous_h if i else None), "wrong raw-chunk provenance")
                check(np.array_equal(raw[i, :, [6, 13]], proposed[i, :, [6, 13]]), "gripper channel was modified")
                for side, arm, cols, grip in (("left", model.left, slice(0, 6), 6), ("right", model.right, slice(7, 13), 13)):
                    audit_arm(arm, dec["arms"][side], raw[i-1] if i else None, previous_h, raw[i],
                              proposed[i], states[i], h, cols, grip)
            else:
                check(np.array_equal(raw[i], proposed[i]) and log["decision"] is None, "baseline prediction changed")
            previous_h = n
            step += n
    check(step == r["steps"], "issued actions do not cover the episode")
    return r["instruction"], r["first_raw_sha256"], digest, r["steps"], r["queries"]


def audit(formal):
    root = FORMAL if formal else engineering_path()
    if formal:
        accepted_root(True)
    stages = ("reproduction", "heldout") if formal else ("engineering",)
    count = 100 if formal else 1
    expected = 1600 if formal else 10
    model = AlohaKinematics.from_embodiment(SIM / "assets/embodiments/aloha-agilex")
    manifest_hash = file_hash(root / "MANIFEST.json")
    evidence = {}
    steps = queries = pairs = 0
    for stage in stages:
        for task in TASKS:
            rows = scenes(stage, task)
            threshold = read_json(UPSTREAM / "pace/configs/calibration" / f"{task}.json")["threshold"]
            for index, row in enumerate(rows[:count]):
                pair = pair_dir(root, stage, task, index)
                anchor = file_hash(pair / "initial.npz")
                paired = set()
                for method in methods(stage, index):
                    path = pair / method
                    identity = dict(stage=stage, task=task, method=method, index=index,
                                    scene_seed=row["scene_seed"], manifest_sha256=manifest_hash)
                    instruction, first, digest, n, q = audit_trial(path, identity, model, threshold, anchor)
                    paired.add((instruction, first, digest))
                    steps += n
                    queries += q
                    evidence[str(path.relative_to(root))] = file_hash(path / "sha256.json")
                check(len(paired) == 1, f"pairing mismatch {pair}")
                pairs += 1
    observed = {str(p.parent.relative_to(root)) for stage in stages for p in (root / stage).glob("*/*/*/sha256.json")
                if not p.parent.name.startswith(".")}
    check(observed == set(evidence) and len(evidence) == expected, "unexpected, missing or duplicate trial")
    audit_record = {"verified_records": len(evidence), "verified_pairs": pairs, "verified_control_steps": steps,
                    "verified_single_candidate_queries": queries, "manifest_sha256": manifest_hash, "record_manifests": evidence}
    destination = root / "AUDIT.json"
    if destination.exists():
        check(read_json(destination) == audit_record, "existing independent audit disagrees with current verification")
    else:
        write_json(destination, audit_record)
    return {k: v for k, v in audit_record.items() if k != "record_manifests"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["engineering", "formal"])
    print(audit(parser.parse_args().stage == "formal"))
