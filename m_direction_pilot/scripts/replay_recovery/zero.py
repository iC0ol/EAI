"""Conditional zero-zero continuation only. No directional action API."""
import json
import random
import time
import traceback

import h5py
import numpy as np
import torch

from common import ROOT, OUT, LOCAL, Ledger, verify, plan, sha256, array_hash, write_json, git
from diagnostics import StepGuard, state, fingerprint
from m_direction.assets import data_path
from m_direction.policy import predict
from m_direction.audit import compare_zero


def run_zero(item, prefix, context, policy):
    verify()
    assert item in plan()["suffix_plan"]
    assert item["prefix_id"] == prefix["attempt_id"] and item["state_id"] == context["state_id"]
    assert prefix["technical_pass"]
    for stage in ["R1_gate.json", "R2_gate.json"]:
        from common import read_json
        assert read_json(OUT/stage)["technical_pass"], stage
    ledger = Ledger(); ledger.reserve(item, "suffix")
    r = {**item, "status": "started", "execution_commit": git("rev-parse", "HEAD"),
         "checkpoint_seed": 42, "checkpoint_sha256": __import__("m_direction.io", fromlist=["config"]).config()["checkpoint_sha256"]["42"],
         "replans": [], "suffix_steps": 0, "inference_calls": 0, "inference_wall_seconds": 0.,
         "inference_cpu_seconds": 0., "inference_gpu_ms": 0., "sim_wall_seconds": 0., "sim_cpu_seconds": 0.,
         "prefix_diagnostics": {"fork_snapshot": prefix["fork_snapshot"]}}
    env, observer, tap, history = [context[k] for k in ["env", "observer", "tap", "history"]]
    np.random.set_state(context["numpy_rng"]); random.setstate(context["python_rng"])
    start, cpu = time.monotonic(), time.process_time()
    arrays = {"suffix_observations": [observer.live()], "suffix_sim_states": [state(env.env.sim)],
              "suffix_received_actions": [], "suffix_success": [], "policy_initial_noise": [], "policy_histories": []}
    guard = None
    try:
        with h5py.File(data_path(), "r") as f:
            expert = f[f"data/{context['episode']}/actions"][context["t"]]
        r["expert_action"] = expert
        assert fingerprint(env.env) == prefix["fork_snapshot"]["physical"]
        policy.reset()
        with StepGuard(None) as guard:
            for index in range(context["t"], plan()["episode_horizon"]):
                if index == context["t"]:
                    action = expert
                else:
                    offset = (index-context["t"]-1) % 8
                    if offset == 0:
                        arrays["policy_histories"].append(np.stack(history))
                        torch.cuda.synchronize(); iw, ic = time.monotonic(), time.process_time()
                        e0, e1 = torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True)
                        e0.record()
                        chunk, noise_record, noise = predict(policy, history, context["state_id"], len(r["replans"]), 0)
                        e1.record(); torch.cuda.synchronize()
                        r["inference_wall_seconds"] += time.monotonic()-iw
                        r["inference_cpu_seconds"] += time.process_time()-ic
                        r["inference_gpu_ms"] += e0.elapsed_time(e1)
                        r["inference_calls"] += 1
                        noise_record["absolute_step_before"] = index
                        r["replans"].append(noise_record); arrays["policy_initial_noise"].append(noise)
                    action = chunk[offset]
                sw, sc = time.monotonic(), time.process_time()
                tap.begin(); guard.env_step(env, action, index); r["suffix_steps"] += 1
                receipt = tap.receipt(action)
                if index == context["t"]:
                    np.testing.assert_array_equal(receipt["composite_input"], expert)
                    assert not receipt["command_clipped"]
                    r["intervention_controller_receipt"] = receipt
                    r["delta"] = np.zeros(7)
                flat = observer.live(); history.append(flat.copy())
                arrays["suffix_observations"].append(flat); arrays["suffix_sim_states"].append(state(env.env.sim))
                arrays["suffix_received_actions"].append(receipt["composite_input"])
                arrays["suffix_success"].append(bool(env.is_success()["task"]))
                r["sim_wall_seconds"] += time.monotonic()-sw
                r["sim_cpu_seconds"] += time.process_time()-sc
        success = arrays["suffix_success"]
        r.update({"status": "completed", "ever_success": any(success), "final_success": success[-1],
                  "first_success_absolute_step": context["t"]+1+success.index(True) if any(success) else None})
    except Exception as exc:
        r.update({"status": "invalid", "error": str(exc), "traceback": traceback.format_exc()})
    finally:
        r.update({"wall_seconds": time.monotonic()-start, "cpu_seconds": time.process_time()-cpu,
                  "integration_steps": guard.steps if guard else 0})
        path = LOCAL/f"{item['attempt_id']}.npz"
        with path.open("xb") as f: np.savez_compressed(f, **{k: np.asarray(v) for k, v in arrays.items()})
        r["trace_path"] = str(path.relative_to(ROOT)); r["trace_sha256"] = sha256(path)
        write_json(OUT/f"{item['attempt_id']}.json", r)
        ledger.append({"event": "finish", "kind": "suffix", "attempt_id": item["attempt_id"], "status": r["status"],
                       "suffix_control_steps": r["suffix_steps"], "integration_steps": r["integration_steps"],
                       "result_sha256": sha256(OUT/f"{item['attempt_id']}.json")})
        env.env.close()
        print(json.dumps({k: r.get(k) for k in ["attempt_id", "status", "suffix_steps", "inference_calls", "ever_success", "error"]}), flush=True)
    return r


def compare(a, b):
    with np.load(ROOT/a["trace_path"]) as x, np.load(ROOT/b["trace_path"]) as y:
        return compare_zero(a, b, x, y)
