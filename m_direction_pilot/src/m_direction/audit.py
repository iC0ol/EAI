"""Immutable registration, bounded attempt ledger and zero-repeat comparisons."""
import fcntl
import json
import os
import time

import numpy as np

from .geometry import quat_angle
from .io import ROOT, OUT, WORKSPACE, config, read_json, read_csv, sha256, git, encode


FROZEN_PATHS = ["reports/gate0/protocol.md", "reports/gate0/task_brief_v2.md", "configs/gate0.json",
                "outputs/gate0/frozen_state_manifest.csv", "outputs/gate0/selection_pool.csv",
                "outputs/gate0/branch_plan.csv", "outputs/gate0/gate_a_plan.csv"]


def verify_registration():
    r = read_json(OUT / "registration.json")
    for p, h in r["frozen_sha256"].items():
        assert sha256(ROOT / p) == h, f"frozen input changed: {p}"
    for p, h in r["reuse_input_sha256"].items():
        assert sha256(WORKSPACE / p) == h, f"read-only reused input changed: {p}"
    git("merge-base", "--is-ancestor", r["protocol_commit"], "HEAD")
    assert not git("diff", "--name-only", "HEAD", "--", "m_direction_pilot/src", "m_direction_pilot/scripts",
                   "m_direction_pilot/configs"), "Commit execution code before running"
    assert time.time()-r["registered_unix_time"] <= 48*3600, "wall limit reached"
    assert sha256(ROOT / config()["data"]) == config()["data_sha256"]
    return r


class Ledger:
    def __init__(self, out=OUT):
        self.out = out
        self.path = out / "attempt_ledger.jsonl"
        self.out.mkdir(parents=True, exist_ok=True)

    def events(self):
        return [json.loads(line) for line in self.path.read_text().splitlines()] if self.path.exists() else []

    def reserve(self, branch):
        with (self.out / ".ledger.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            events = self.events()
            starts = [e for e in events if e["event"] == "started"]
            if any(e["branch_id"] == branch["branch_id"] for e in starts):
                raise RuntimeError("Refuse repeat/overwrite of started branch")
            finished = {e["branch_id"] for e in events if e["event"] == "finished"}
            if any(e["branch_id"] not in finished for e in starts):
                raise RuntimeError("Unfinished attempt exists; causal audit required, no automatic retry")
            cfg = config()
            na = sum(e["block"] == "A" for e in starts) + (branch["block"] == "A")
            nb = sum(e["block"] != "A" for e in starts) + (branch["block"] != "A")
            if na > cfg["max_A_suffixes"] or nb > cfg["max_B_suffixes"] or na+nb > 150:
                raise RuntimeError("suffix attempt budget exhausted")
            self.append({"event": "started", "time": time.time(), **branch})

    def append(self, event):
        with self.path.open("a") as f:
            f.write(json.dumps(event, default=encode, allow_nan=False)+"\n")
            f.flush()
            os.fsync(f.fileno())


def compare_zero(a, b, trace_a, trace_b):
    x, y = trace_a, trace_b
    for key in ["suffix_observations", "suffix_received_actions", "suffix_sim_states"]:
        assert x[key].shape == y[key].shape
    xo, yo = x["suffix_observations"], y["suffix_observations"]
    result = {"initial_obs_max_abs": float(np.max(np.abs(xo[0]-yo[0]))),
              "trajectory_obs_max_abs": float(np.max(np.abs(xo-yo))),
              "trajectory_action_max_abs": float(np.max(np.abs(x["suffix_received_actions"]-y["suffix_received_actions"]))),
              "trajectory_position_m": float(max(np.linalg.norm(xo[:, :3]-yo[:, :3], axis=1).max(),
                                                      np.linalg.norm(xo[:, 7:10]-yo[:, 7:10], axis=1).max())),
              "trajectory_rotation_rad": float(max(quat_angle(xo[:, 3:7], yo[:, 3:7]).max(),
                                                       quat_angle(xo[:, 10:14], yo[:, 10:14]).max())),
              "state_max_abs": float(np.max(np.abs(x["suffix_sim_states"]-y["suffix_sim_states"])))}
    keys = ["replan_index", "seed", "generator_before_sha256", "initial_noise_sha256", "generator_after_sha256"]
    schedule = lambda r: [{k: p[k] for k in keys} for p in r["replans"]]
    result["noise_and_replan_identical"] = schedule(a) == schedule(b)
    result["ever_success_identical"] = a["ever_success"] == b["ever_success"]
    result["final_success_identical"] = a["final_success"] == b["final_success"]
    result["all_success_flags_identical"] = np.array_equal(x["suffix_success"], y["suffix_success"])
    result["all_actions_byte_identical"] = np.array_equal(x["suffix_received_actions"], y["suffix_received_actions"])
    result["all_states_byte_identical"] = np.array_equal(x["suffix_sim_states"], y["suffix_sim_states"])
    result["fork_snapshot_identical"] = a["prefix_diagnostics"]["fork_snapshot"] == b["prefix_diagnostics"]["fork_snapshot"]
    result["passed"] = all(result[k] <= tol for k, tol in config()["zero_repeat_tolerances"].items()) and all(
        result[k] for k in ["noise_and_replan_identical", "ever_success_identical", "final_success_identical", "all_success_flags_identical"])
    return result
