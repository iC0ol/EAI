"""Full 400-step closed-loop trials with identical frozen simulator resets."""
import argparse
from collections import deque
import hashlib
import json
import time

import h5py
import numpy as np
import torch

from d_alignment.environment import create_env, flatten_obs
from d_alignment.io import ROOT, read_json, sha256, write_json
from d_alignment.policy import make_policy


def evaluate(condition, seed):
    cfg = read_json(ROOT / "configs/gate1.json")
    run = ROOT / f"outputs/gate1/{condition}_seed{seed}"
    metadata = read_json(run / "run.json")
    assert metadata["status"] == "completed" and metadata["updates_completed"] == cfg["updates"]
    checkpoint = metadata["checkpoint"]
    assert sha256(checkpoint) == metadata["checkpoint_sha256"]
    assert not (run / "evaluation.jsonl").exists(), "Refuse test rerun / seed selection"
    torch.set_num_threads(cfg["torch_cpu_threads"])
    policy = make_policy().cuda().eval()
    policy.load_state_dict(torch.load(checkpoint, map_location="cuda")["policy"])
    initial = read_json(ROOT / "data/manifests/eval_initial_conditions.json")
    assert sha256(ROOT / initial["path"]) == initial["sha256"]
    started = time.monotonic()
    env, _ = create_env()
    rows = []
    trace_dir = ROOT / f"outputs/gate1/trajectories/{condition}_seed{seed}"
    trace_dir.mkdir(parents=True)
    with h5py.File(ROOT / initial["path"], "r") as f, open(run / "evaluation.jsonl", "w", buffering=1) as log:
        for item in initial["initial_conditions"]:
            trial = item["seed"]
            np.random.seed(trial)
            torch.manual_seed(trial + 12345)
            torch.cuda.manual_seed_all(trial + 12345)
            reset_started = time.monotonic()
            env.reset()
            g = f[str(trial)]
            obs = env.reset_to({"states": g["states"][:], "model": g.attrs["model"], "ep_meta": g.attrs["ep_meta"]})
            flat = flatten_obs(obs)
            # Require matched observations numerically; tiny reset cache noise is
            # reported instead of changing initial conditions silently.
            initial_error = float(np.max(np.abs(flat - g["obs"][:])))
            assert initial_error < 1e-5, (trial, initial_error)
            reset_wall = time.monotonic() - reset_started
            history = deque([flat.copy() for _ in range(cfg["n_obs_steps"])], maxlen=cfg["n_obs_steps"])
            actions, states, success_steps, contacts, nut_positions = [], [], [], [], []
            sim_wall, inference_wall = 0., 0.
            t = 0
            policy.reset()
            episode_start = time.monotonic()
            while t < cfg["eval_max_steps"]:
                inference_start = time.monotonic()
                with torch.no_grad():
                    act = policy.predict_action({"obs": torch.from_numpy(np.stack(history)[None]).cuda()})["action"][0].cpu().numpy()
                inference_wall += time.monotonic() - inference_start
                assert act.shape == (cfg["n_action_steps"], 7) and np.isfinite(act).all()
                for a in act:
                    if t >= cfg["eval_max_steps"]:
                        break
                    sim_start = time.monotonic()
                    obs, reward, done, info = env.step(a)
                    success = bool(env.is_success()["task"])
                    sim_wall += time.monotonic() - sim_start
                    t += 1
                    actions.append(a.copy())
                    states.append(flatten_obs(obs))
                    history.append(states[-1])
                    if success:
                        success_steps.append(t)
                    contacts.append(int(env.env.sim.data.ncon))
                    nut_positions.append(env.env.sim.data.body_xpos[env.env.obj_body_id[env.env.nuts[env.env.nut_id].name]].copy())
            aa, ss, nn = np.asarray(actions), np.asarray(states), np.asarray(nut_positions)
            # These are auxiliary proxies, not automatic diagnoses of contacts.
            row = {"condition": condition, "train_seed": seed, "test_seed": trial, "steps": t,
                "success": bool(success_steps), "first_success_step": success_steps[0] if success_steps else None,
                "success_steps_count": len(success_steps), "initial_obs_max_error": initial_error,
                "initial_state_sha256": item["state_sha256"], "simulation_wall_seconds": sim_wall,
                "inference_wall_seconds": inference_wall, "reset_wall_seconds": reset_wall,
                "episode_wall_seconds": time.monotonic()-episode_start,
                "gripper_sign_flips": int(np.count_nonzero(np.diff(aa[:, 6] > 0))),
                "mean_action_delta_norm": float(np.linalg.norm(np.diff(aa, axis=0), axis=1).mean()),
                "mean_translation_command_delta_norm": float(np.linalg.norm(np.diff(aa[:, :3], axis=0), axis=1).mean()),
                "max_action_delta_norm": float(np.linalg.norm(np.diff(aa, axis=0), axis=1).max()),
                "max_contact_count": max(contacts), "min_nut_z": float(nn[:, 2].min()),
                "nut_below_table_proxy": bool(nn[:, 2].min() < env.env.table_offset[2] - .05)}
            trace = trace_dir / f"{trial}.npz"
            np.savez_compressed(trace, actions=aa, observations=ss, nut_position=nn, n_contacts=contacts, success_steps=success_steps)
            row["local_trace_path"] = str(trace)
            row["local_trace_sha256"] = sha256(trace)
            log.write(json.dumps(row) + "\n")
            rows.append(row)
            print(json.dumps({k: row[k] for k in ("test_seed", "success", "steps", "simulation_wall_seconds", "inference_wall_seconds")}), flush=True)
    summary = {"condition": condition, "train_seed": seed, "episodes": len(rows), "successes": sum(r["success"] for r in rows),
        "success_rate": float(np.mean([r["success"] for r in rows])), "total_wall_seconds": time.monotonic()-started,
        "simulation_cpu_wall_seconds": sum(r["simulation_wall_seconds"]+r["reset_wall_seconds"] for r in rows),
        "inference_wall_seconds": sum(r["inference_wall_seconds"] for r in rows),
        "initial_conditions_sha256": initial["sha256"], "config_sha256": sha256(ROOT / "configs/gate1.json")}
    write_json(run / "evaluation_summary.json", summary)
    env.env.close()
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--condition", required=True)
    p.add_argument("--seed", type=int, required=True)
    args = p.parse_args()
    evaluate(args.condition, args.seed)
