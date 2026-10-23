"""Post-stop analysis of saved telemetry only. No simulator or policy is instantiated."""
import csv
import gzip
import json

import h5py
import numpy as np

from common import ROOT, OUT, REPORT, BASE, LOCAL, read_json, write_json, write_csv, protected, sha256, digest, git, plan
from m_direction.geometry import quat_angle


def rows(path):
    with path.open() as f: return list(csv.DictReader(f))


def markdown(path, text):
    with path.open("x") as f: f.write(text)


def main():
    summary = read_json(OUT/"run_summary.json")
    assert summary["status"] == "R-Fail / Engineering blocked"
    assert len(summary["prefix_results"]) == 2 and not summary["suffix_results"]
    historical = protected()
    r1 = read_json(OUT/"D1_P1_S00.json"); r2 = read_json(OUT/"D2_P2_S00.json")
    assert not r1["technical_pass"] and not r2["technical_pass"]
    for r in [r1, r2]:
        for f in r["local_files"]: assert sha256(ROOT/f["path"]) == f["sha256"]
    old = read_json(ROOT/"outputs/gate0/branch_results/A_S00_repeat0.json")
    with np.load(ROOT/old["trace_path"]) as z0, np.load(LOCAL/"D1_P1_S00/trace.npz") as z1, np.load(LOCAL/"D2_P2_S00/trace.npz") as z2:
        comparisons = {}
        for x, y in [("prefix_sim_states", "states"), ("prefix_observations", "native_obs"), ("prefix_received_actions", "received_actions")]:
            comparisons[f"P0_P1_{y}"] = {"byte_identical": bool(np.array_equal(z0[x], z1[y])),
                                          "max_abs": float(np.abs(z0[x]-z1[y]).max())}
        comparisons["P1_P2_states"] = {"byte_identical": bool(np.array_equal(z1["states"], z2["states"])),
                                         "max_abs": float(np.abs(z1["states"]-z2["states"]).max())}
        # Read-only calculations from saved states; direct free-joint poses use double precision.
        live = z1["states"].copy(); source = z1["source_states"].copy()
        physical_position = np.linalg.norm(live[:, 10:13]-source[:, 10:13], axis=1)
        physical_angle = quat_angle(live[:, 13:17][:, [1,2,3,0]], source[:, 13:17][:, [1,2,3,0]])
        p1rows, p2rows = rows(OUT/"D1_P1_S00_by_step.csv"), rows(OUT/"D2_P2_S00_by_step.csv")
        all_rows = []
        for t in range(53):
            all_rows.append({"t": t, "time_s": float(live[t, 0]),
                "P0_P1_flat_state_max_abs": float(abs(z0["prefix_sim_states"][t]-z1["states"][t]).max()),
                "P1_P2_flat_state_max_abs": float(abs(z1["states"][t]-z2["states"][t]).max()),
                "P1_native_vs_source_max_abs": float(abs(z1["native_obs"][t]-z1["source_obs"][t]).max()),
                "P2_forced_vs_source_max_abs": float(abs(z2["forced_obs"][t]-z2["source_obs"][t]).max()),
                "P1_synchronous_vs_source_max_abs": float(abs(z1["sync_obs"][t]-z1["source_obs"][t]).max()),
                "P1_native_vs_source_nut_m": float(np.linalg.norm(z1["native_obs"][t,:3]-z1["source_obs"][t,:3])),
                "P2_forced_vs_source_nut_m": float(np.linalg.norm(z2["forced_obs"][t,:3]-z2["source_obs"][t,:3])),
                "direct_physical_square_position_m": float(physical_position[t]),
                "direct_physical_square_rotation_rad": float(physical_angle[t]),
                "P2_forced_vs_sync_nut_m": float(np.linalg.norm(z2["forced_obs"][t,:3]-z2["sync_obs"][t,:3])),
                **{k: float(p1rows[t][k]) for k in ["qpos_max_abs", "qvel_max_abs", "robot_qvel_max_abs", "gripper_qvel_max_abs", "square_linear_qvel_max_abs", "square_angular_qvel_max_abs"]}})
        write_csv(OUT/"P0_P1_P2_comparison_by_step.csv", all_rows)
        new = r1["new_max_errors"]
        comparisons["physical_metrics"] = {"fork_position_m": float(physical_position[-1]), "max_position_m": float(physical_position.max()),
            "fork_geodesic_rad": float(physical_angle[-1]), "max_geodesic_rad": float(physical_angle.max()),
            "source_kinematic_observer_max_abs": r1["source_sync_observer_max_abs"]}
        # Saved substep data permits an exact qpos time-origin check without a new simulation.
        with gzip.open(LOCAL/"D1_P1_S00/substeps.jsonl.gz", "rt") as f: substeps = [json.loads(s) for s in f]
        lag_examples = []
        for t in [1, 2]:
            native_before = substeps[t*25-2]["integration_before"]
            forced_before = substeps[t*25-1]["integration_before"]
            lag_examples.append({"control_state_index": t, "boundary_time_s": float(live[t,0]),
                "native_nut_value_matches_preintegration_qpos_time": native_before["time"],
                "native_qpos_value_max_abs": float(np.max(abs(z1["native_obs"][t,:3]-np.array(native_before["qpos"][9:12], dtype=np.float32)))),
                "forced_nut_value_matches_preintegration_qpos_time": forced_before["time"],
                "forced_qpos_value_max_abs": float(np.max(abs(z2["forced_obs"][t,:3]-np.array(forced_before["qpos"][9:12], dtype=np.float32))))})
        comparisons["lag_examples"] = lag_examples
        write_json(OUT/"paired_path_comparison.json", comparisons)

    boundaries1 = read_json(LOCAL/"D1_P1_S00/boundaries.json")
    boundaries2 = read_json(LOCAL/"D2_P2_S00/boundaries.json")
    cache_rows = []
    contact_peaks = []
    with h5py.File(ROOT/"../d_alignment_pilot/data/raw/square_ph_low_dim_v15.hdf5", "r") as f:
        actions = f["data/demo_191/actions"][:52]
    for t in range(53):
        b = boundaries1[t]; arm = b["controller"]["arm"]
        if 38 <= t <= 52:
            sensor = b["cache_before_forcing"]["SquareNut_pos"]
            cache_rows.append({"t": t, "previous_action_index": t-1, "previous_expert_command": actions[t-1],
                "goal_position": arm.get("goal_pos"), "goal_orientation": arm.get("goal_ori"),
                "reference_position": arm.get("ref_pos"), "goal_update_mode": arm.get("_goal_update_mode"),
                "gripper_current_action": b["controller"]["gripper"].get("current_action"),
                "max_abs_warmstart": float(np.abs(b["controller"]["qacc_warmstart"]).max()),
                "P1_P2_controller_same": digest(b["controller"]) == digest(boundaries2[t]["controller"]),
                "sample_period_s": sensor["sample_period_s"], "last_sensor_call_sim_time": sensor["last_sensor_call_sim_time"],
                "time_since_last_sample_s": sensor["time_since_last_sample_s"], "sampled": sensor["sampled"]})
    write_csv(OUT/"controller_cache_window38_52.csv", cache_rows)
    for j in range(37, 52):
        group = [s for s in substeps if s["control_action_index"] == j]
        contacts = [(s,c) for s in group for c in s["contacts"] if any("SquareNut" in (n or "") for n in c["geom_names"])]
        s, c = max(contacts, key=lambda item: abs(item[1]["force_torque_contact_frame"][0]))
        contact_peaks.append({"action_index": j, "resulting_source_state_index": j+1,
            "expert_gripper_command": float(actions[j,6]), "integration_before_time": s["integration_before"]["time"],
            "ncon_min": min(x["ncon"] for x in group), "ncon_max": max(x["ncon"] for x in group),
            "peak_square_contact_geom_names": c["geom_names"], "contact_position_world": c["position_world"],
            "normal_geom0_to_geom1_world": c["normal_geom0_to_geom1_world"],
            "contact_force_torque": c["force_torque_contact_frame"], "force_dt_impulse_proxy": c["force_dt_impulse_proxy"]})
    write_csv(OUT/"contact_peaks38_52.csv", contact_peaks)
    init_rows = []
    for r in [r1, r2]:
        for s in read_json(LOCAL/r["attempt_id"]/"reset_snapshots.json"):
            init_rows.append({"attempt_id": r["attempt_id"], "point": s["point"], "state_hash": digest(s["state"]),
                             "controller_hash": digest(s["controller"]), "controller_goal_pos": s["controller"]["arm"].get("goal_pos"),
                             "gripper_current_action": s["controller"]["gripper"].get("current_action"),
                             "warmstart_max_abs": float(np.abs(s["controller"]["qacc_warmstart"]).max())})
    write_csv(OUT/"reset_stage_comparison.csv", init_rows)

    budgets = []
    for kind, records in [("prefix", plan()["prefix_plan"]), ("suffix", plan()["suffix_plan"])]:
        for item in records:
            path = OUT/f"{item['attempt_id']}.json"
            r = read_json(path) if path.exists() else None
            budgets.append({"attempt_id": item["attempt_id"], "kind": kind, "state_id": item["state_id"],
                "source_episode": item.get("source_episode", "demo_21" if item["state_id"] == "S02" else "demo_105"),
                "planned": True, "attempted": r is not None,
                "status": r["status"] if r else "not_run_R1_technical_gate_failed",
                "technical_pass": r["technical_pass"] if r and kind == "prefix" else "",
                "control_steps": r.get("expert_control_steps", r.get("suffix_steps", 0)) if r else 0,
                "integration_steps": r["integration_steps"] if r else 0,
                "wall_seconds": r["wall_seconds"] if r else 0., "process_cpu_seconds": r["cpu_seconds"] if r else 0.,
                "gpu_inference_calls": r.get("gpu_inference_calls", r.get("inference_calls", 0)) if r else 0,
                "Y_ever": "", "Y_final": ""})
    write_csv(OUT/"complete_budget_ledger.csv", budgets)
    actual = {"prefix_attempts": 2, "complete_prefixes": 2, "invalid_attempts": 0,
        "expert_control_steps": sum(r["expert_control_steps"] for r in [r1,r2]),
        "integration_steps": sum(r["integration_steps"] for r in [r1,r2]),
        "simulated_prefix_seconds": 104/20, "prefix_wall_seconds_sum": r1["wall_seconds"]+r2["wall_seconds"],
        "prefix_process_cpu_seconds_sum": r1["cpu_seconds"]+r2["cpu_seconds"],
        "run_loop_wall_seconds": summary["wall_seconds"], "run_loop_process_cpu_seconds": summary["cpu_seconds"],
        "complete_zero_suffixes": 0, "zero_control_steps": 0, "gpu_inference_calls": 0,
        "new_training": 0, "directional_interventions": 0, "Gate_B_branches": 0,
        "preflight_real_integration_steps": 0, "remaining_prefix_slots_not_used": 4, "remaining_suffix_slots_not_used": 4,
        "timing_scope": "Run loop excludes Python imports; each prefix includes creation/reset/telemetry, excludes final NPZ/hash saving. Full terminal wall not independently timed."}
    write_json(OUT/"costs.json", actual)
    write_json(OUT/"stage_status.json", {"R0": "read-only complete; 0 simulation steps", "R1": "failed technical gate",
        "R2": "not run; R1 physical reconstruction failed", "zero_repeat": "not run; no technically valid fork"})

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(3,1,figsize=(10,9), sharex=True, constrained_layout=True)
    x = np.arange(53)
    axes[0].plot(x,[r["P1_native_vs_source_nut_m"]*1000 for r in all_rows],label="P0 = P1 native observation",color="#d95f02")
    axes[0].plot(x,[r["P2_forced_vs_source_nut_m"]*1000 for r in all_rows],label="P2 forced observable refresh",color="#7570b3")
    axes[0].plot(x,physical_position*1000,label="Raw qpos physical error (P0 = P1 = P2)",color="#1b9e77")
    axes[0].axhline(1,color="gray",ls="--",label="Frozen 1 mm tolerance")
    axes[0].set_ylabel("Nut position error (mm)");axes[0].legend(fontsize=8)
    axes[1].plot(x,physical_angle,color="#1b9e77",label="Raw quaternion geodesic error")
    axes[1].axhline(.01,color="gray",ls="--",label="Frozen 0.01 rad tolerance")
    axes[1].set_ylabel("Nut orientation error (rad)");axes[1].legend(fontsize=8)
    subrows = rows(OUT/"D1_P1_S00_contact_by_substep.csv")
    axes[2].plot([float(r["control_action_index"])+((int(r["integration_index"])-1)%25+1)/25 for r in subrows],
                 [float(r["max_square_normal_force_N"]) for r in subrows],color="#386cb0",label="Max measured Square contact normal force")
    axes[2].set_ylabel("Normal force (N)");axes[2].set_xlabel("Expert prefix control-state index (fork at 52)")
    axes[2].legend(fontsize=8)
    for ax in axes: ax.grid(alpha=.2);ax.set_xlim(0,52)
    fig.suptitle("M-Gate 0-R: repeatable replay still differs from the recorded expert state")
    fig.savefig(REPORT/"reset_sensor_physical_comparison.png",dpi=160)
    fig.savefig(REPORT/"reset_sensor_physical_comparison.svg")
    plt.close(fig)

    table = "| 指标 | P1全前缀最大 | P1 t52 | 原数值阈值 |\n|---|---:|---:|---:|\n"
    for k, lim in plan()["physical_limits"].items():
        table += f"| {k} | {r1['new_max_errors'][k]:.9g} | {r1['new_at_fork'][k]:.9g} | {lim:g} |\n"
    markdown(REPORT/"reset_and_sensor_diagnosis.md",f"""# Reset、传感器与物理重放诊断

结论：P0/P1/P2在本次专家前缀的物理轨迹逐字节一致，原示教状态重建仍失败。
同步观测消除了早期缓存时序差，但后期直接qpos位置/姿态及qvel仍超阈值。

| 路径 | 初始化/观测访问 | 新前缀次数 | 对照结果 |
|---|---|---:|---|
| P0 | 旧reset_to(model,state)，native step obs | 0（沿用封存trace） | 旧Invalid不变 |
| P1 | 外层reset→reset_to，native obs；只读克隆动力学观测 | 1 | 与P0全部53个state、53个native obs、52个收到动作逐字节一致 |
| P2 | P1初始化；每边界额外get_observation强制刷新缓存 | 1 | 与P1全部53个物理state逐字节一致；仅观测/采样时钟变化 |

两条新前缀均完成52步，无异常、无裁剪改写、无策略调用。P0是历史对照，未重新运行。
外层reset没有改善此来源/随机流的重建；这不证明所有任务/版本中两种reset都等价。
P1/P2每个边界的controller/warmstart数值亦相同，原示教未保存这些量，无法作源对源比较。

## 缓存差异的实测分解

独立MjData、mj_kinematics从全部53个source states导出的16D，与原HDF5选中16D逐项相等
（max error=0）。沿用EEF site位置、EEF body四元数及原gripper qpos；没有替换为site quat。
每次observer前后live time/qpos/qvel/act/warmstart/ctrl hash一致，未调用live forward。

t=2，native nut位置误差3.829777mm；P2强制刷新后1.933694mm；原始物理qpos误差仅
约2.14e-9m。强制刷新观测不能使body/site派生数据跟随最终积分qpos：

- t=1控制边界0.050s，P1 native nut数值精确匹配0.046s子步前qpos；P2 forced数值
  精确匹配0.048s子步前qpos（均按16D的float32比较，max=0）。
- t=2边界0.100s，对应native=0.096s、forced=0.098s。缓存采样在最后边界前2ms调用，
  读取的body pose又来自上一轮forward，形成这里测得的4ms有效位置滞后；仅force后仍为2ms。

这些对应关系来自本轮保存的子步qpos和传感器调用时刻，没有新增状态重放。
不把所有阶段都概括为固定4ms延迟；静止值也不能唯一反推采样时刻。

## t38～52：真实接触段偏离

qpos直接计算：t40 nut位置误差约0.000277mm，t41增至0.207630mm，t42约0.498853mm；
t48达到2.831569mm，t52仍1.778535mm。t49四元数测地角最大0.010503221rad。
source与live时间完全一致。state max0.931848663是t42 SquareNut自由关节x角速度差(rad/s)，
不能解释成米。qpos、机器人/夹爪/物体线速度和角速度分项见CSV。

动作40（导致state41）开始专家gripper命令由-1变+1，内部gripper累积控制逐步变化；
动作41的ncon在1～21间变化，SquareNut_g3与两个finger及table有接触。
动作47（导致state48）ncon在20～58间变化，并出现finger1 pad与SquareNut_g4接触；
该步所选Square接触峰值normal force约3.346282N。接下来动作48峰值约6.795927N。
接触峰值对应点/法向/力矩及force×dt代理均保存在contact_peaks38_52.csv。

这些是本次replay的真实接触数据，说明误差放大与接触转换时间邻近；源demo没有同样数据，
不能证明该接触法向、warmstart或某个goal就是漂移根因，也不能证明与采集时接触相同。
原始逐子步qpos/qvel/warmstart/ctrl、目标/参考值/更新标志、接触点与sensor缓存在本地
substeps.jsonl.gz及boundaries.json，SHA列于local_trace_index.json。Git保留完整逐步摘要。
另提供两份raw_control_boundaries.csv，共106个边界的原始source/live qpos、qvel、16D观测、
实际前一控制命令、controller目标和live warmstart。源未保存的warmstart/contact保持空缺。

## 同步观测定义与原Gate A独立比较

{table}

FP32同步16D的物理位置误差与直接双精度qpos计算略有舍入差；两者均明确超过1mm。
原native Gate A的最大误差在D1 JSON另列，全部阈值保持原值，旧实验仍为Invalid。
本轮没有因同步观测定义而宣布旧A通过。

![完整0..52曲线](reset_sensor_physical_comparison.png)

## 已排查范围与未决信息

外层reset单独不足以修复；只刷新observable缓存也不足以修复真实物理偏移。
控制器/夹爪初始化及逐子步目标、solver100 iterations/tolerance1e-8、Euler积分、dt0.002
均被记录，未修改。源HDF5仅保存time+23qpos+21qvel，无act(na=0)，不包含采集时controller
缓存、warmstart、contact solver状态、RNG/采样时钟和精确MuJoCo版本。当前资料不足以
把物理残差进一步归因为具体采集运行时或隐藏状态。R1门槛失败，R2与zero suffix不运行。

接触字段按[MuJoCo3.2.3 contact结构](https://mujoco.readthedocs.io/en/3.2.3/APIreference/APItypes.html#mjcontact)
和[mj_contactForce](https://mujoco.readthedocs.io/en/3.2.3/APIreference/APIfunctions.html#mj-contactforce)
解释：法向从geom0指向geom1，力/力矩在contact frame；dt乘积只是子步冲量代理。
""")
    markdown(REPORT/"zero_repeat.md","""# 零扰动后缀：未执行

R1真实物理门槛失败，故R2 S02/S09均未重放，也没有任何有效专家分叉交给Clean策略。
计划Z1/Z2(S02)、Z3/Z4(S09)全部保留为not_run_R1_technical_gate_failed，Y为空。
本轮完整suffix=0、zero-zero配对=0、DP推理调用=0；不存在名义成功率或终局稳定性结论。
P0/P1/P2前缀物理逐字节一致，不能替代策略续跑到400步的零扰动验证。
剩余4个prefix槽位和4个suffix槽位不自动使用。
""")
    markdown(REPORT/"go_no_go.md",f"""# M-Gate0-R 技术决策：R-Fail / Engineering blocked

**当前RoboMimic专家前缀恢复路径技术No-Go。M方向性科研假设仍未检验。**

P1官方外层reset路径与封存P0的所有前缀state/观测/动作逐字节一致；P2强制缓存刷新
仍保持同样物理轨迹。缓存时序可独立定位，接触段真实物理漂移没有被本次固定路径修复。
分叉点raw qpos位置误差1.778535mm、前缀最大2.831569mm，超过保持不变的1mm阈值。
姿态峰值0.010503221rad和state分量峰值0.931848663亦越界。

预登记commit：`{r1['protocol_commit']}`。
执行commit：`{r1['execution_commit']}`。
R0无新step→独立协议commit→零积分预检→执行代码commit→P1/P2→R1失败停机→只读分析。

- 新前缀2/6，均完整52步：共104 control steps、2600 integration steps、模拟时间5.2s。
- 完整suffix0/4，DP推理0，方向扰动0，Gate B0，训练0，下载0，其他任务0。
- R2原S02/S09来源与阶段事前冻结，因R1门槛未过而未执行；没有更换状态或放宽阈值。
- 旧Gate0文件、哈希、旧D/spatial及旧分支保留；旧结论仍是Invalid / Engineering blocked。

已经提供P0/P1/P2对比、0..52分项曲线、接触/控制器/采样时刻证据、全部10个计划槽位
总账及本地原始trace索引。源示教未保存的中间状态继续标为缺失，根因不夸大。

本轮停止。没有提交或执行附件后续科学120分支矩阵；只有未来技术恢复并经研究者另行
审阅，才具备讨论新科学预登记的条件。本结果不构成M的科研No-Go。
""")
    markdown(REPORT/"commands_and_costs.md",f"""# 命令、预算和审计成本

```text
git switch -c research/m-gate0-replay-recovery 537e6a6db79ed1e8aa884b4bad8a44f08b17c480
bash m_direction_pilot/scripts/run.sh m_direction_pilot/scripts/replay_recovery/r0.py
git commit ... # cdb04a6 independent protocol
bash m_direction_pilot/scripts/run.sh m_direction_pilot/scripts/replay_recovery/register.py
bash m_direction_pilot/scripts/run.sh m_direction_pilot/scripts/replay_recovery/test_recovery.py
git commit ... # b906e6e execution code
bash m_direction_pilot/scripts/run.sh m_direction_pilot/scripts/replay_recovery/run_diagnostics.py
bash m_direction_pilot/scripts/run.sh m_direction_pilot/scripts/replay_recovery/report_recovery.py
```

实验脚本exit2是R1技术门槛失败后的计划停机。前缀2条完整、无invalid/partial尝试。
预检6项通过，3.986s，真实积分步0；一条构建/重置测试环境用于只读kinematics API验证，
未运行专家前缀或策略。R0与报告均未构造推进仿真的环境。每个integration由StepGuard计数；
构造/reset期间若有积分调用会被拒绝，本轮没有这类额外步。

| 项目 | P1 | P2 | 合计 |
|---|---:|---:|---:|
| expert control steps |52|52|104|
| integration steps |1300|1300|2600|
| prefix内部wall(s) |{r1['wall_seconds']:.6f}|{r2['wall_seconds']:.6f}|{actual['prefix_wall_seconds_sum']:.6f}|
| prefix process CPU(s) |{r1['cpu_seconds']:.6f}|{r2['cpu_seconds']:.6f}|{actual['prefix_process_cpu_seconds_sum']:.6f}|
| GPU推理调用 |0|0|0|

整个执行循环wall={summary['wall_seconds']:.6f}s，process CPU={summary['cpu_seconds']:.6f}s。
prefix计时包含环境构建/reset/逐子步遥测，截止最终NPZ/哈希写入前；循环计时还包含
prefix归档与gate比较，不含Python导入。终端端到端墙钟、只读报告CPU及GPU显存驻留
未另行计时，不伪造成0GPU占用小时。CPU使用2线程，process CPU可以略大于wall。
没有加载Clean网络进行续跑、没有新优化器更新。预算10个槽位均列于complete_budget_ledger.csv。
""")
    write_json(OUT/"local_trace_index.json", [f for r in [r1,r2] for f in r["local_files"]])
    final = {"decision": summary["status"], "scientific_M_verdict": "untested", "protocol_commit": r1["protocol_commit"],
        "execution_commit": r1["execution_commit"], "costs": actual, "P0_P1": comparisons,
        "R2_executed": False, "zero_repeat_executed": False, "historical_M_hashes_unchanged": len(historical),
        "source_missing_data_prevents_exact_causal_attribution": True, "new_simulation_steps_during_analysis": 0,
        "stop_for_researcher_review": True}
    write_json(OUT/"final_summary.json", final)
    print(json.dumps({"decision": final["decision"], "prefixes": 2, "expert_steps": 104, "integration_steps": 2600,
                      "suffixes": 0, "post_stop_analysis_new_steps": 0}))


if __name__ == "__main__": main()
