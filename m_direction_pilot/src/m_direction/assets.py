"""Read-only reuse audit and offline selection. Never runs a policy rollout."""
import json
import platform
import sys
import time
import xml.etree.ElementTree as ET

import h5py
import numpy as np

from .io import ROOT, D_ROOT, OUT, REPORT, config, sha256, array_hash, read_json, write_json, write_csv, git
from .perturb import intervention


def data_path():
    return (ROOT / config()["data"]).resolve()


def checkpoint_path(seed):
    return D_ROOT / f"outputs/gate1/checkpoints/clean_seed{seed}.pt"


def flatten_obs(obs):
    return np.concatenate([obs["object"][7:14], obs["robot0_eef_pos"],
                           obs["robot0_eef_quat"], obs["robot0_gripper_qpos"]]).astype(np.float32)


def demo_obs(g, t, next_obs=False):
    name = "next_obs" if next_obs else "obs"
    return np.concatenate([g[f"{name}/object"][t, 7:14], g[f"{name}/robot0_eef_pos"][t],
                           g[f"{name}/robot0_eef_quat"][t], g[f"{name}/robot0_gripper_qpos"][t]]).astype(np.float32)


def create_env():
    import robomimic.utils.obs_utils as ObsUtils
    from robomimic.envs.env_robosuite import EnvRobosuite
    ObsUtils.initialize_obs_utils_with_obs_specs({"obs": {"low_dim": config()["obs_keys"]}})
    with h5py.File(data_path(), "r") as f:
        meta = json.loads(f["data"].attrs["env_args"])
    return EnvRobosuite(env_name=meta["env_name"], render=False, render_offscreen=False,
                        use_image_obs=False, **meta["env_kwargs"])


def audit_assets():
    import torch
    import mujoco
    import robomimic
    import robosuite
    started = time.monotonic()
    cfg = config()
    expected = {str(data_path()): cfg["data_sha256"]}
    expected.update({str(checkpoint_path(s)): cfg["checkpoint_sha256"][str(s)] for s in [42, 43]})
    hashes = {p: sha256(p) for p in expected}
    assert hashes == expected, "source/checkpoint mismatch"
    episodes = []
    with h5py.File(data_path(), "r") as f:
        for name in sorted(f["data"], key=lambda x: int(x.split("_")[1])):
            g = f["data"][name]
            n = len(g["actions"])
            assert g["actions"].shape == (n, 7) and g["states"].shape == (n, 45)
            fields = {}
            for key in g["obs"]:
                assert len(g[f"obs/{key}"]) == len(g[f"next_obs/{key}"]) == n
                a, b = g[f"obs/{key}"][:], g[f"next_obs/{key}"][:]
                assert np.isfinite(a).all() and np.isfinite(b).all()
                assert np.array_equal(b[:-1], a[1:])
                fields[key] = {"shape": list(a.shape), "dtype": str(a.dtype)}
            assert np.isfinite(g["actions"][:]).all() and np.isfinite(g["states"][:]).all()
            assert np.max(np.abs(np.diff(g["states"][:, 0]) - .05)) < 1e-8
            episodes.append({"source_episode": name, "T": n, "actions_sha256": array_hash(g["actions"][:]),
                             "states_sha256": array_hash(g["states"][:]), "obs_fields": fields})
        metadata = json.loads(f["data"].attrs["env_args"])
        masks = {k: len(v) for k, v in f["mask"].items()}
    env = create_env()
    ctrl = env.env.robots[0].part_controllers["right"]
    actual = {k: getattr(ctrl, k, None) for k in ["input_min", "input_max", "output_min", "output_max",
              "input_type", "input_ref_frame", "position_limits", "orientation_limits", "_goal_update_mode"]}
    actual.update({"control_freq": env.env.control_freq, "control_timestep": env.env.control_timestep,
                   "model_timestep": env.env.model_timestep, "robosuite_internal_horizon": env.env.horizon,
                   "robomimic_evaluation_horizon": cfg["episode_horizon"],
                   "action_spec": env.env.action_spec, "lite_physics": env.env.lite_physics})
    assert actual["input_type"] == "delta" and actual["input_ref_frame"] == "world"
    np.testing.assert_array_equal(actual["output_max"], [.05, .05, .05, .5, .5, .5])
    assert actual["position_limits"] is None and actual["orientation_limits"] is None
    env.env.close()
    record = {"stage": "read-only asset audit; no action steps or suffixes", "git_head": git("rev-parse", "HEAD"),
              "previous_head": "75c0271", "v1_M_preregistration_or_results_found": False,
              "hashes": hashes, "metadata": metadata, "actual_controller": actual,
              "episodes": episodes, "masks": masks, "python": sys.version, "prefix": sys.prefix,
              "platform": platform.platform(), "versions": {"torch": torch.__version__, "mujoco": mujoco.__version__,
              "robomimic": robomimic.__version__, "robosuite": robosuite.__version__},
              "cuda_available": torch.cuda.is_available(), "audit_wall_seconds": time.monotonic()-started}
    if torch.cuda.is_available():
        record["gpu"] = torch.cuda.get_device_name(0)
    write_json(REPORT / "resource_audit.json", record)
    print(json.dumps({k: v for k, v in record.items() if k not in ["episodes", "metadata"]}, default=str), flush=True)


def freeze_selection():
    cfg = config()
    states, pools = [], []
    with h5py.File(data_path(), "r") as f:
        names = sorted([x.decode() for x in f[f"mask/{cfg['source_mask']}"][:]], key=lambda x: int(x.split("_")[1]))
        chosen = list(np.random.default_rng(cfg["selection_seed"]).permutation(names)[:6])
        for i, ep in enumerate(chosen):
            g = f[f"data/{ep}"]
            a, pos, eef = g["actions"][:], g["obs/object"][:, 7:10], g["obs/robot0_eef_pos"][:]
            n = len(a)
            xml = ET.fromstring(g.attrs["model_file"])
            peg = next(x for x in xml.iter("body") if x.attrib.get("name") == "peg1")
            pegpos = np.fromstring(peg.attrib["pos"], sep=" ")
            tt = np.arange(n)
            nonterm = (g["dones"][:] == 0) & (tt >= 8) & (tt < n-5)
            masks = {"grasp": nonterm & (pos[:, 2] < .85) & (a[:, 6] > 0) & (np.linalg.norm(eef-pos, axis=1) < .09),
                     "insertion": nonterm & (np.linalg.norm(pos[:, :2]-pegpos[:2], axis=1) < .055) & (pos[:, 2] > .85) & (a[:, 6] > 0)}
            rng = np.random.default_rng(cfg["selection_seed"] + int(ep.split("_")[1]))
            for phase, mask in masks.items():
                candidates = np.flatnonzero(mask)
                if not len(candidates):
                    raise RuntimeError(f"No {phase} pool for {ep}; stop, no replacement")
                t = int(rng.choice(candidates))
                sid = f"S{len(states):02d}"
                eligible, reason = True, ""
                try:
                    for direction in ["x", "y", "z", "xy", "xz", "yz"]:
                        for sign in [-1, 1]:
                            intervention(a[t], direction, sign, cfg["r1"])
                except ValueError as exc:
                    eligible, reason = False, str(exc)
                states.append({"state_id": sid, "source_episode": ep, "t": t,
                               "split": "development" if i < 4 else "held-out", "phase": phase,
                               "T": n, "phase_pool_size": len(candidates), "technical_eligible": eligible,
                               "technical_rejection": reason, "expert_action": a[t].tolist(),
                               "raw_state_sha256": array_hash(g["states"][t]),
                               "raw_history_sha256": array_hash(np.stack([demo_obs(g, t-1), demo_obs(g, t)])),
                               "prefix_actions_sha256": array_hash(a[:t]), "object_pose": g["obs/object"][t, 7:14],
                               "eef_pose": np.r_[g["obs/robot0_eef_pos"][t], g["obs/robot0_eef_quat"][t]],
                               "peg_position": pegpos})
                for candidate in candidates:
                    pools.append({"state_id": sid, "source_episode": ep, "phase": phase,
                                  "t": int(candidate), "selected": int(candidate) == t})
    write_csv(OUT / "frozen_state_manifest.csv", states)
    write_csv(OUT / "selection_pool.csv", pools)
    branches = []
    def add(block, sid, seed, direction, sign, radius, repeat=""):
        branches.append({"branch_id": f"{block}_{sid}_p{seed}_{direction}_{sign:+d}_r{radius:g}{repeat}",
                         "block": block, "state_id": sid, "checkpoint_seed": seed,
                         "direction": direction, "sign": sign, "radius": radius, "stream": 0})
    for s in states:
        add("B1", s["state_id"], 42, "nominal", 0, 0.)
        for d in ["x", "y", "z"]:
            for sign in [-1, 1]: add("B1", s["state_id"], 42, d, sign, cfg["r1"])
    for sid in cfg["b2_states"]:
        for d in ["xy", "xz", "yz"]:
            for sign in [-1, 1]: add("B2", sid, 42, d, sign, cfg["r1"])
    for sid in cfg["b3_states"]:
        for sign in [-1, 1]: add("B3", sid, 42, cfg["b3_axis"], sign, cfg["r2"])
    for sid in cfg["b4_states"]:
        add("B4", sid, 43, "nominal", 0, 0.)
        for d in ["x", "y", "z"]:
            for sign in [-1, 1]: add("B4", sid, 43, d, sign, cfg["r1"])
    assert len(branches) == 120
    write_csv(OUT / "branch_plan.csv", branches)
    ab = []
    for s in states:
        for repeat in [0, 1]:
            ab.append({"branch_id": f"A_{s['state_id']}_repeat{repeat}", "block": "A", "state_id": s["state_id"],
                       "checkpoint_seed": 42, "direction": "nominal", "sign": 0, "radius": 0., "stream": 0})
    write_csv(OUT / "gate_a_plan.csv", ab)
    print(json.dumps({"states": [(s["state_id"], s["source_episode"], s["t"], s["technical_eligible"]) for s in states],
                      "B_suffixes": len(branches), "A_planned": len(ab)}, default=str))
