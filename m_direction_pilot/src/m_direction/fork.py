"""One expert intervention, then frozen policy closed loop to the common horizon."""
import json
import time
import traceback

import h5py
import numpy as np
import torch

from .assets import data_path
from .audit import Ledger, verify_registration
from .geometry import auxiliary
from .io import ROOT, OUT, LOCAL, config, sha256, array_hash, write_json, git
from .perturb import intervention
from .policy import predict
from .replay import prefix_replay, snapshot


def execute_branch(branch, state, policy):
    registration = verify_registration()
    branch = {**branch, "checkpoint_seed": int(branch["checkpoint_seed"]), "sign": int(branch["sign"]),
              "radius": float(branch["radius"]), "stream": int(branch["stream"])}
    ledger = Ledger()
    ledger.reserve(branch)
    start, cpu_start = time.monotonic(), time.process_time()
    result = {**branch, "source_episode": state["source_episode"], "t": int(state["t"]),
              "split": state["split"], "phase": state["phase"],
              "checkpoint_sha256": config()["checkpoint_sha256"][str(branch["checkpoint_seed"])],
              "protocol_commit": registration["protocol_commit"], "execution_commit": git("rev-parse", "HEAD"),
              "execution_source_sha256": {str(p.relative_to(ROOT)): sha256(p) for p in sorted((ROOT / "src").rglob("*.py"))},
              "status": "started", "prefix_steps": 0, "suffix_steps": 0, "replans": [],
              "sim_wall_seconds": 0., "sim_cpu_seconds": 0., "inference_wall_seconds": 0.,
              "inference_cpu_seconds": 0., "inference_gpu_milliseconds": 0.}
    progress = {"prefix_steps": 0}
    trace = {}
    env = None
    try:
        with h5py.File(data_path(), "r") as f:
            g = f[f"data/{state['source_episode']}"]
            expert = g["actions"][int(state["t"])].copy()
            expected = json.loads(state["expert_action"])
            np.testing.assert_array_equal(expert, expected)
            requested, delta = intervention(expert, branch["direction"], branch["sign"], branch["radius"])
            result.update({"expert_action": expert.tolist(), "intervention_requested": requested.tolist(),
                           "delta": delta.tolist(), "delta_norm": float(np.linalg.norm(delta[:3]))})
            env, history, tap = prefix_replay(g, state, progress)
        t = int(state["t"])
        raw = env.env
        pegpos = raw.sim.data.body_xpos[raw.peg1_body_id].copy()
        pegrot = raw.sim.data.body_xmat[raw.peg1_body_id].reshape(3, 3).copy()
        result["fork_geometry"] = {"nut_pose": history[-1][:7].tolist(), "peg_position": pegpos.tolist(),
                                  "peg_rotation": pegrot.tolist(), "contact_count": int(raw.sim.data.ncon)}
        suffix_obs = [history[-1].copy()]
        suffix_states = [raw.sim.get_state().flatten().copy()]
        acts, clipped, scaled, goals, success, contacts, aux = [], [], [], [], [], [], []
        noise, histories = [], []
        policy.reset()
        action_chunk = None
        replan_index = 0
        for absolute_index in range(t, config()["episode_horizon"]):
            if absolute_index == t:
                action = requested
            else:
                offset = (absolute_index-t-1) % 8
                if offset == 0:
                    histories.append(np.stack(history))
                    torch.cuda.synchronize()
                    iw, ic = time.monotonic(), time.process_time()
                    ev0, ev1 = torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True)
                    ev0.record()
                    action_chunk, schedule, noise_tensor = predict(policy, history, state["state_id"], replan_index, branch["stream"])
                    ev1.record()
                    torch.cuda.synchronize()
                    result["inference_gpu_milliseconds"] += ev0.elapsed_time(ev1)
                    result["inference_wall_seconds"] += time.monotonic()-iw
                    result["inference_cpu_seconds"] += time.process_time()-ic
                    schedule["absolute_step_before"] = absolute_index
                    result["replans"].append(schedule)
                    noise.append(noise_tensor)
                    replan_index += 1
                action = action_chunk[offset]
            sw, sc = time.monotonic(), time.process_time()
            tap.begin()
            obs, _, _, _ = env.step(action)
            result["suffix_steps"] += 1
            receipt = tap.receipt(action)
            result["sim_wall_seconds"] += time.monotonic()-sw
            result["sim_cpu_seconds"] += time.process_time()-sc
            if absolute_index == t:
                if receipt["command_clipped"]:
                    raise RuntimeError("Intervention clipped at controller")
                result["intervention_controller_receipt"] = {k: v.tolist() if isinstance(v, np.ndarray) else v for k, v in receipt.items()}
                np.testing.assert_allclose(receipt["composite_input"] - expert, delta, atol=1e-15, rtol=0)
                result["intervention_effective_delta"] = (receipt["composite_input"] - expert).tolist()
                np.testing.assert_array_equal(receipt["composite_input"][3:], expert[3:])
            from .assets import flatten_obs
            flat = flatten_obs(obs)
            history.append(flat.copy())
            acts.append(receipt["composite_input"])
            clipped.append(receipt["normalized_after_clip"])
            scaled.append(receipt["scaled_arm_command"])
            goals.append(receipt["goal_pos"])
            suffix_obs.append(flat.copy())
            suffix_states.append(raw.sim.get_state().flatten().copy())
            success.append(bool(env.is_success()["task"]))
            contacts.append(int(raw.sim.data.ncon))
            aux.append(auxiliary(flat, pegpos, pegrot))
        assert result["suffix_steps"] == config()["episode_horizon"]-t
        trace.update({"suffix_observations": np.stack(suffix_obs), "suffix_sim_states": np.stack(suffix_states),
                      "suffix_received_actions": np.stack(acts), "suffix_after_clip_actions": np.stack(clipped),
                      "suffix_scaled_arm": np.stack(scaled), "suffix_goal_positions": np.stack(goals),
                      "suffix_success": np.asarray(success), "suffix_contact_count": np.asarray(contacts),
                      "policy_histories": np.stack(histories), "policy_initial_noise": np.stack(noise)})
        result.update({"status": "completed", "ever_success": any(success), "final_success": success[-1],
                       "first_success_absolute_step": t+1+success.index(True) if any(success) else None,
                       "intervention_clipped": False,
                       "policy_clipped_steps": int(np.any(np.stack(acts)[1:, :6] != np.stack(clipped)[1:, :6], axis=1).sum()),
                       "final_auxiliary": aux[-1], "minimum_nut_to_peg_xy_m": min(a["nut_to_peg_xy_m"] for a in aux),
                       "contact_steps": sum(c > 0 for c in contacts), "max_ncon": max(contacts),
                       "final_snapshot": snapshot(env, history), "trajectory_hashes": {k: array_hash(v) for k, v in trace.items()}})
    except Exception as exc:
        result.update({"status": "invalid", "error_type": type(exc).__name__, "error": str(exc),
                       "traceback": traceback.format_exc()})
    finally:
        result["prefix_steps"] = progress["prefix_steps"]
        for key in ["prefix_wall_seconds", "prefix_cpu_seconds", "prefix_diagnostics"]:
            if key in progress: result[key] = progress[key]
        trace.update(progress.get("prefix_trace", {}))
        if trace:
            trace_path = LOCAL / "traces" / f"{branch['branch_id']}.npz"
            trace_path.parent.mkdir(parents=True, exist_ok=True)
            with trace_path.open("xb") as f:
                np.savez_compressed(f, **trace)
            result["trace_path"] = str(trace_path.relative_to(ROOT))
            result["trace_sha256"] = sha256(trace_path)
        if env is not None: env.env.close()
        elif progress.get("env") is not None: progress["env"].env.close()
        result["wall_seconds"] = time.monotonic()-start
        result["cpu_seconds"] = time.process_time()-cpu_start
        result["prefix_integration_steps"] = result["prefix_steps"] * 25
        result["suffix_integration_steps"] = result["suffix_steps"] * 25
        result["peak_cuda_allocated_bytes"] = torch.cuda.max_memory_allocated()
        result["peak_cuda_reserved_bytes"] = torch.cuda.max_memory_reserved()
        path = OUT / "branch_results" / f"{branch['branch_id']}.json"
        write_json(path, result)
        ledger.append({"event": "finished", "time": time.time(), "branch_id": branch["branch_id"],
                       "block": branch["block"], "status": result["status"], "prefix_steps": result["prefix_steps"],
                       "suffix_steps": result["suffix_steps"], "result_sha256": sha256(path)})
        print(json.dumps({k: result.get(k) for k in ["branch_id", "status", "prefix_steps", "suffix_steps",
              "ever_success", "final_success", "error", "wall_seconds"]}), flush=True)
    return result
