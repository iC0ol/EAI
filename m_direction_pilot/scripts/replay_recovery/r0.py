"""R0 reads source/data/old traces. Does not create or step an environment."""
import xml.etree.ElementTree as ET

import h5py
import numpy as np

from common import ROOT, D_ROOT, OUT, REPORT, CODE, BASE, now, protected, write_json, write_csv, sha256, read_json, git

upstream = {
    "official_rollout": D_ROOT/"external/robomimic-7c66e7a41b5d9dcc905b1a68346bfee1b49b79c9/robomimic/scripts/run_trained_agent.py",
    "official_playback": D_ROOT/"external/robomimic-7c66e7a41b5d9dcc905b1a68346bfee1b49b79c9/robomimic/scripts/playback_dataset.py",
    "offline_extractor": D_ROOT/"external/robomimic-7c66e7a41b5d9dcc905b1a68346bfee1b49b79c9/robomimic/scripts/dataset_states_to_obs.py",
    "wrapper": D_ROOT/"external/robomimic-7c66e7a41b5d9dcc905b1a68346bfee1b49b79c9/robomimic/envs/env_robosuite.py",
    "base": D_ROOT/"external/robosuite-51cc01785bab80ffeed20da15e67d7dd4140e76a/robosuite/environments/base.py",
    "observables": D_ROOT/"external/robosuite-51cc01785bab80ffeed20da15e67d7dd4140e76a/robosuite/utils/observables.py",
    "bindings": D_ROOT/"external/robosuite-51cc01785bab80ffeed20da15e67d7dd4140e76a/robosuite/utils/binding_utils.py",
    "robot_sensors": D_ROOT/"external/robosuite-51cc01785bab80ffeed20da15e67d7dd4140e76a/robosuite/robots/robot.py",
    "osc": D_ROOT/"external/robosuite-51cc01785bab80ffeed20da15e67d7dd4140e76a/robosuite/controllers/parts/arm/osc.py",
    "composite": D_ROOT/"external/robosuite-51cc01785bab80ffeed20da15e67d7dd4140e76a/robosuite/controllers/composite/composite_controller.py"
}


def main():
    hashes = protected()
    old = read_json(ROOT/"outputs/gate0/branch_results/A_S00_repeat0.json")
    assert sha256(ROOT/old["trace_path"]) == old["trace_sha256"]
    cfg = read_json(ROOT/"configs/gate0.json")
    assets = [ROOT/cfg["data"], D_ROOT/"outputs/gate1/checkpoints/clean_seed42.pt",
              D_ROOT/"outputs/gate1/checkpoints/clean_seed43.pt", D_ROOT/"configs/gate1.json",
              D_ROOT/"data/manifests/normalization.json", D_ROOT/"requirements.lock"]
    asset_hashes = {str(p.resolve().relative_to(ROOT.parent)): sha256(p) for p in assets}
    assert sha256(assets[0]) == cfg["data_sha256"]
    for seed in [42, 43]:
        assert sha256(D_ROOT/f"outputs/gate1/checkpoints/clean_seed{seed}.pt") == cfg["checkpoint_sha256"][str(seed)]
    with h5py.File(assets[0], "r") as f:
        g = f["data/demo_191"]
        record = {"root_attributes": {k: str(v) for k, v in f.attrs.items()},
                  "data_attribute_names": list(f["data"].attrs), "episode_attribute_names": list(g.attrs),
                  "episode_datasets": list(g), "env_metadata": __import__("json").loads(f["data"].attrs["env_args"])}
        positions = g["states"][:, 10:13]
        record["source_nut_obs_minus_free_joint_position_max_m"] = float(np.abs(g["obs/object"][:, 7:10]-positions).max())
        record["collection_runtime_exact_mujoco_version_available"] = False
        record["extraction_command_provenance_available"] = False
    rows = []
    with (ROOT/"outputs/gate0/prefix_fidelity_by_step.csv").open() as f:
        import csv
        for r in csv.DictReader(f):
            if 38 <= int(r["state_index"]) <= 52:
                rows.append(r)
    write_csv(OUT/"R0_P0_window38_52.csv", rows)
    hypotheses = [
        {"id": "H_reset", "hypothesis": "Extra outer reset changes controller/model/cache initialization and source replay", "test": "P1 vs archived P0 with same state seed and expert actions; do not infer root cause from code alone"},
        {"id": "H_cache", "hypothesis": "Offline forced-state observations and native online observable sampling differ", "test": "P2 native vs forced refresh vs qpos-derived clone at identical physical state; record any cache/physical side effects"},
        {"id": "H_controller", "hypothesis": "Controller or gripper internal initialization affects contact entry", "test": "Capture goals/ref/update flags/gripper action at reset boundaries and each substep; source internals absent, so causal proof limited"},
        {"id": "H_contact", "hypothesis": "Small physical differences amplify near nut/finger contact", "test": "Separate qpos/qvel/angles, new contact normals/forces/substeps/warmstart around t38..52; contact coincidence is not causal proof"},
        {"id": "H_runtime", "hypothesis": "Unrecorded collection runtime/integrator state prevents exact reconstruction", "test": "Audit metadata/XML/pinned runtime. Missing collection MuJoCo version and warmstart cannot be recovered from flattened states"}
    ]
    write_json(OUT/"R0_audit.json", {"utc": now(), "base": BASE, "new_simulation_steps": 0,
        "historical_M_files": hashes, "asset_files": asset_hashes,
        "source_files": {str(p.relative_to(ROOT.parent)): sha256(p) for p in upstream.values()},
        "metadata": record, "hypotheses": hypotheses,
        "old_trace_missing_fields": ["per-step controller goals", "per-step gripper controller state", "ncon", "contact points/normals/forces", "per-substep states", "per-step qacc_warmstart", "sensor sample timestamps"],
        "source_HDF5_missing_fields": ["qacc_warmstart", "controller goals/caches", "contact solver state/forces", "RNG state", "observable sampling clock", "exact collection MuJoCo/runtime version"],
        "old_branch_heads": {b: git("rev-parse", b) for b in ["main", "research/d-gate1", "research/d-gate1-q2", "research/m-gate0"]}})
    excerpts = []
    ranges = {"official_rollout": (94, 104), "official_playback": (118, 138), "offline_extractor": (92, 143),
              "wrapper": (124, 205), "base": (374, 419), "observables": (214, 285), "bindings": (1148, 1185), "robot_sensors": (401, 468)}
    for name, (lo, hi) in ranges.items():
        lines = upstream[name].read_text().splitlines()
        excerpts.append(f"## {name}: {upstream[name].relative_to(ROOT.parent)}\n\n```text\n"+
                        "\n".join(f"{i+1}: {s}" for i, s in enumerate(lines) if lo <= i+1 <= hi)+"\n```\n")
    REPORT.mkdir(parents=True, exist_ok=True)
    with (REPORT/"R0_source_audit.md").open("x") as f:
        f.write("# R0：锁定源码与历史证据（0新仿真步）\n\n")
        f.write("官方run_trained_agent是reset→get_state→reset_to；给定示教XML/state的playback明确采用reset→reset_to。model路径reset_to内部还会reset并重建XML。外层reset是否修复物理偏离待P1检验。\n\n")
        f.write("offline extractor逐状态reset_to(states[t])并强制更新观测，在线step直接返回采样缓存。HDF5的绝对物体位置与free-joint qpos一致，但未存提取命令，不能证明该文件曾执行哪一个转换命令。\n\n")
        f.write("P0只保存state/obs/收到的前缀动作及末端hash；历史t38..52的接触、控制器目标及warmstart数值不可追溯，不能虚构。新P1/P2将补记录；源示教仍缺这些采集中间量。EEF位置来自site，EEF四元数沿用body，不能偷换成site quat。\n\n")
        f.write("\n".join(excerpts))
    print("R0 complete: assets/source/history hashes verified; 0 new simulation steps")


if __name__ == "__main__": main()
