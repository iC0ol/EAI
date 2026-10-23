"""Post-stop audit of the frozen failed A attempt. No simulator/policy imports or steps."""
import datetime
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import h5py
import numpy as np

from m_direction.geometry import quat_angle
from m_direction.io import ROOT, OUT, REPORT, LOCAL, config, read_json, read_csv, write_json, write_csv, sha256, git
from m_direction.metrics import delta_loss


def text_file(name, content):
    with (REPORT/name).open("x") as f:
        f.write(content)


def joint_layout(xml):
    joints = list(ET.fromstring(xml).find("worldbody").iter("joint"))
    nq = nv = 0
    positions, velocities = {}, {}
    for joint in joints:
        kind = joint.get("type", "hinge")
        q, v = (7, 6) if kind == "free" else (4, 3) if kind == "ball" else (1, 1)
        positions[joint.get("name")] = (nq, q)
        velocities[joint.get("name")] = (nv, v)
        nq += q; nv += v
    assert (nq, nv) == (23, 21)
    return nq, nv, positions, velocities


def main():
    cfg = config()
    registration = read_json(OUT/"registration.json")
    a = read_json(OUT/"gate_a_summary.json")
    assert a["status"] == "Invalid/Engineering blocked", "This reporter handles the measured engineering stop only"
    states = read_csv(OUT/"frozen_state_manifest.csv")
    by_id = {s["state_id"]: s for s in states}
    plans = read_csv(OUT/"gate_a_plan.csv") + read_csv(OUT/"branch_plan.csv")
    results = {p.stem: read_json(p) for p in (OUT/"branch_results").glob("*.json")}
    assert len(results) == 1 and all(r["block"] == "A" for r in results.values())
    result = next(iter(results.values()))
    assert result["suffix_steps"] == 0 and result["prefix_steps"] == 52 and not result["replans"]
    assert sha256(ROOT/result["trace_path"]) == result["trace_sha256"]
    assert all(sha256(ROOT/p) == h for p, h in registration["frozen_sha256"].items())
    changed = git("diff", "--name-only", cfg["base_commit"]).splitlines()
    assert all(p.startswith("m_direction_pilot/") for p in changed)
    assert git("rev-parse", "research/d-gate1") == cfg["base_commit"]
    assert git("rev-parse", "research/d-gate1-q2").startswith("75c0271")
    assert git("rev-parse", "main").startswith("687d75d")

    ledger, paired = [], []
    for branch in plans:
        state = by_id[branch["state_id"]]
        r = results.get(branch["branch_id"])
        row = {**branch, "source_episode": state["source_episode"], "t": state["t"], "split": state["split"],
               "phase": state["phase"], "planned": True, "attempted": r is not None,
               "status": r["status"] if r else "not_run_gate_A_blocked",
               "stop_reason": r["error"] if r else "First mandatory A prefix failed preregistered fidelity",
               "complete_suffix": bool(r and r["status"] == "completed"),
               "prefix_steps": r["prefix_steps"] if r else 0, "suffix_steps": r["suffix_steps"] if r else 0,
               "official_ever_success": "", "official_final_success": "", "first_success_absolute_step": "",
               "checkpoint_sha256": cfg["checkpoint_sha256"][branch["checkpoint_seed"]],
               "trace_sha256": r.get("trace_sha256", "") if r else "",
               "result_sha256": sha256(OUT/"branch_results"/f"{branch['branch_id']}.json") if r else ""}
        ledger.append(row)
        if branch["block"] != "A":
            paired.append({"branch_id": branch["branch_id"], "state_id": branch["state_id"],
                           "source_episode": state["source_episode"], "t": state["t"], "split": state["split"],
                           "checkpoint_seed": branch["checkpoint_seed"], "checkpoint_sha256": row["checkpoint_sha256"],
                           "direction": branch["direction"], "sign": branch["sign"], "radius": branch["radius"],
                           "status": row["status"], "Y_nominal": "", "Y_perturbed": "", "delta_loss": ""})
    write_csv(OUT/"all_branch_ledger.csv", ledger)
    write_csv(OUT/"paired_outcomes.csv", paired)
    state_rows = [{"state_id": s["state_id"], "source_episode": s["source_episode"], "t": s["t"],
                   "split": s["split"], "phase": s["phase"], "technical_eligible_offline": s["technical_eligible"],
                   "state_status": "prefix_fidelity_failed" if s["state_id"] == "S00" else "not_run_gate_A_blocked",
                   "A_complete_suffixes": 0, "B_complete_suffixes": 0, "in_prespecified_denominator": True} for s in states]
    write_csv(OUT/"frozen_state_status.csv", state_rows)
    sources = []
    for episode in dict.fromkeys(s["source_episode"] for s in states):
        subset = [s for s in states if s["source_episode"] == episode]
        sources.append({"source_episode": episode, "split": subset[0]["split"], "planned_states": len(subset),
                        "prefix_attempts": sum(r["source_episode"] == episode for r in results.values()),
                        "prefix_fidelity_failures": int(episode == result["source_episode"]),
                        "complete_A_suffixes": 0, "complete_B_suffixes": 0, "observed_Y_pairs": 0,
                        "scientific_evidence": "unavailable"})
    write_csv(OUT/"by_source.csv", sources)

    with h5py.File(ROOT/cfg["data"], "r") as f, np.load(ROOT/result["trace_path"]) as z:
        g = f[f"data/{result['source_episode']}"]
        nq, nv, positions, velocities = joint_layout(g.attrs["model_file"])
        qo, qn = positions["SquareNut_joint0"]
        vo, vn = velocities["SquareNut_joint0"]
        actual = z["prefix_sim_states"]
        recorded = g["states"][:len(actual)]
        raw_obs = g["obs/object"][:len(actual), 7:14]
        live_obs = z["prefix_observations"]
        direct_pos = np.linalg.norm(actual[:, 1+qo:1+qo+3]-recorded[:, 1+qo:1+qo+3], axis=1)
        aq = actual[:, 1+qo+3:1+qo+7][:, [1, 2, 3, 0]]
        rq = recorded[:, 1+qo+3:1+qo+7][:, [1, 2, 3, 0]]
        direct_angle = quat_angle(aq, rq)
        live_cache_gap = np.linalg.norm(live_obs[:, :3]-actual[:, 1+qo:1+qo+3], axis=1)
        source_obs_gap = np.linalg.norm(raw_obs[:, :3]-recorded[:, 1+qo:1+qo+3], axis=1)
        errnames = list(result["prefix_diagnostics"]["max_errors"])
        errors = z["prefix_errors"]
        delta = actual-recorded
        maximum_step, maximum_index = map(int, np.unravel_index(np.abs(delta).argmax(), delta.shape))
        rows = []
        for t in range(len(actual)):
            rows.append({"source_episode": result["source_episode"], "state_index": t,
                         **dict(zip(errnames, errors[t].tolist())),
                         "direct_square_qpos_position_m": float(direct_pos[t]),
                         "direct_square_qpos_rotation_rad": float(direct_angle[t]),
                         "live_observation_to_qpos_position_m": float(live_cache_gap[t]),
                         "source_observation_to_qpos_position_m": float(source_obs_gap[t]),
                         "qpos_max_abs": float(np.max(np.abs(delta[t, 1:1+nq]))),
                         "qvel_max_abs": float(np.max(np.abs(delta[t, 1+nq:]))),
                         "time_error_s": float(abs(delta[t, 0]))})
        write_csv(OUT/"prefix_fidelity_by_step.csv", rows)
        diagnostic = {"no_new_environment_or_policy_steps": True, "read_only_post_stop_investigations": 1,
                      "initial_sim_state_byte_identical": bool(np.array_equal(actual[0], recorded[0])),
                      "expert_prefix_actions_byte_identical": bool(np.array_equal(z["prefix_received_actions"], g["actions"][:52])),
                      "initial_obs_max_abs": float(np.max(errors[0])), "time_error_max_s": float(np.max(abs(delta[:, 0]))),
                      "first_state_difference_step": int(np.flatnonzero(np.any(delta != 0, axis=1))[0]),
                      "largest_flat_state_difference": {"step": maximum_step, "index": maximum_index,
                            "abs_error": float(abs(delta[maximum_step, maximum_index])),
                            "component": "SquareNut free-joint angular velocity x (rad/s)"},
                      "square_qpos_fork_position_error_m": float(direct_pos[-1]),
                      "square_qpos_max_position_error_m": float(direct_pos.max()),
                      "square_qpos_fork_geodesic_rotation_rad": float(direct_angle[-1]),
                      "square_qpos_max_geodesic_rotation_rad": float(direct_angle.max()),
                      "live_observation_max_position_cache_gap_m": float(live_cache_gap.max()),
                      "source_observation_max_position_cache_gap_m": float(source_obs_gap.max()),
                      "early_step2": {"observed_nut_error_m": float(errors[2, errnames.index("object_position_m")]),
                                      "direct_qpos_nut_error_m": float(direct_pos[2]),
                                      "live_observation_to_qpos_gap_m": float(live_cache_gap[2])},
                      "causal_claim_limit": "Early observed gap is predominantly sensor-cache timing; later physical drift is also present. Exact cause of physical drift is unresolved without a new authorized reconstruction study."}
        assert maximum_index == 1+nq+vo+3
        write_json(OUT/"read_only_diagnosis.json", diagnostic)
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(2, 1, figsize=(9, 6), sharex=True, constrained_layout=True)
        x = np.arange(len(actual))
        axes[0].plot(x, errors[:, errnames.index("object_position_m")]*1000, label="Live observation vs source observation", color="#c65d21")
        axes[0].plot(x, direct_pos*1000, label="Live qpos vs source qpos", color="#2166ac")
        axes[0].axhline(1, color="#666666", linestyle="--", label="Preregistered position tolerance (1 mm)")
        axes[0].set_ylabel("Square position error (mm)"); axes[0].legend(fontsize=8)
        axes[1].plot(x, errors[:, errnames.index("object_rotation_rad")], label="Observation quaternion geodesic error", color="#c65d21")
        axes[1].plot(x, direct_angle, label="qpos quaternion geodesic error", color="#2166ac")
        axes[1].axhline(.01, color="#666666", linestyle="--", label="Preregistered angle tolerance (0.01 rad)")
        axes[1].set_ylabel("Square orientation error (rad)"); axes[1].set_xlabel("Expert prefix state index (fork at t=52)")
        axes[1].legend(fontsize=8)
        fig.suptitle("M Gate 0-A: source reconstruction failed before any suffix")
        for ax in axes: ax.grid(alpha=.2); ax.set_xlim(0, 52)
        fig.savefig(REPORT/"expert_prefix_fidelity.png", dpi=160)
        fig.savefig(REPORT/"expert_prefix_fidelity.svg")
        plt.close(fig)

    events = [json.loads(x) for x in (OUT/"attempt_ledger.jsonl").read_text().splitlines()]
    starts = [x for x in events if x["event"] == "started"]
    finishes = [x for x in events if x["event"] == "finished"]
    assert len(starts) == len(finishes) == 1
    actual_costs = {"A_attempts_reserved": 1, "A_complete_suffixes": 0, "B_attempts": 0,
                   "B_complete_suffixes": 0, "all_complete_suffixes": 0, "all_partial_suffix_steps": 0,
                   "expert_prefix_control_steps": result["prefix_steps"], "expert_prefix_integration_steps": 1300,
                   "simulated_prefix_seconds": 52/20, "prefix_wall_seconds": result["prefix_wall_seconds"],
                   "prefix_cpu_seconds": result["prefix_cpu_seconds"], "branch_wall_seconds": result["wall_seconds"],
                   "branch_cpu_seconds": result["cpu_seconds"], "A_loop_wall_seconds": a["wall_seconds"],
                   "inference_calls": 0, "inference_wall_seconds": 0., "inference_gpu_milliseconds": 0.,
                   "peak_cuda_allocated_bytes": result["peak_cuda_allocated_bytes"],
                   "peak_cuda_reserved_bytes": result["peak_cuda_reserved_bytes"],
                   "asset_audit_internal_wall_seconds": read_json(REPORT/"resource_audit.json")["audit_wall_seconds"],
                   "policy_load_wall_seconds": None,
                   "timing_limit": "Branch and A-loop timers exclude Python imports and policy loading; end-to-end shell wall was not independently timed. No inference ran."}
    write_json(OUT/"commands_and_costs.json", actual_costs)
    summary = {"decision": "Invalid / Engineering blocked", "scientific_M_verdict": "not evaluated",
               "stop_trigger": "First required expert-prefix reconstruction exceeds frozen fidelity thresholds",
               "protocol_commit": registration["protocol_commit"], "execution_commit": result["execution_commit"],
               "registered_before_all_M_outcomes": True, "v1_M_results": False,
               "frozen_states": 12, "source_episodes": 6, "dev_states": 8, "held_out_states": 4,
               "prefix_attempted_states": 1, "prefix_failed_states": 1, "unattempted_states": 11,
               "all_planned_branch_rows": 144, "B_planned": 120, "A_primary_planned": 24,
               "A_repair_reserve_unused": 6, "measured_zero_repeat_pairs": 0,
               "completed_B_pairs": 0, "Y_available": False, "sign_asymmetry_or_improvement": "not observed / no outcome measurements",
               "baseline_fits": 0, "new_policy_training": 0, "new_downloads": 0, "new_tasks": 0,
               "geometry_baselines": "source frames readable; no valid live fork or outcomes for evaluation",
               "contact_normal_baseline": "unavailable; ncon is not a normal", "costs": actual_costs,
               "protected_trees_unchanged": True, "researcher_review_required_before_new_experiments": True,
               "generated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()}
    write_json(OUT/"summary.json", summary)

    metrics = result["prefix_diagnostics"]
    table = "| 检查量 | 前缀最大误差 | 分叉点 t=52 | 预登记容差 |\n|---|---:|---:|---:|\n"
    for k, limit in cfg["prefix_tolerances"].items():
        table += f"| {k} | {metrics['max_errors'][k]:.9g} | {metrics['at_fork'][k]:.9g} | {limit:g} |\n"
    text_file("expert_fork_fidelity.md", f"""# Gate A：专家状态重建未通过

结论：**Invalid / Engineering blocked**。首个预选状态 S00（demo_191，t=52，grasp）
的完整专家前缀超过事前容差。仅执行52个专家动作，在执行 a*_52 或冻结策略之前停止。
没有完成任何 suffix，也没有完成零扰动重复对，不能声称重复成功一致或出现成功翻转。

{table}

初态45维仿真 state 逐字节一致，所有52个控制器收到的前缀动作与原专家动作逐字节一致，
时间误差为0。分叉点 source state hash 为
`{metrics['source_fork_state_sha256']}`，live state hash 为
`{metrics['live_fork_state_sha256']}`。完整 controller/cache/history/RNG 哈希在分支JSON中。

一次有界只读诊断只分析已保存的 trace，没有新增模拟步或后缀：

- t=2 的观测物体位置误差3.829777mm，而仿真 qpos 中物体位置误差约
  {diagnostic['early_step2']['direct_qpos_nut_error_m']:.3g}m；早期差主要来自在线观测缓存时序。
  原始HDF5的绝对物体观测与其 qpos 位置逐项一致。在线 step 返回的绝对物体观测也有
  缓存滞后，排除旧相对字段并未消除此处差异。
- t=52 仿真 qpos 本身的物体位置误差为
  {diagnostic['square_qpos_fork_position_error_m']*1000:.6f}mm，前缀最大为
  {diagnostic['square_qpos_max_position_error_m']*1000:.6f}mm；因此不能只靠观测刷新解释失败。
- 原始state最大差0.931848663出现在t=42、flat index36，对应SquareNut自由关节
  x角速度（rad/s），不是0.93米的位置误差。接触附近物理漂移的具体根因尚未确定。
- 当前使用官方包装器 reset_to(initial XML/state) 并重放真实动作前缀；其model路径内部reset。
  官方action playback另有外层env.reset，本轮没有据此重跑，不能声称控制器初始内部状态
  与采集时完全一致。上游播放器也检查并警告action replay与记录state的差异。
  仅有states/actions并不保证
  完整控制器、积分器和观测缓存状态可被精确重建。不能据现有证据断言warm-start、版本或
  控制器中任何一个就是根因。M分支未更改这些接口或源数据。

![专家前缀误差](expert_prefix_fidelity.png)

图中橙线比较策略实际可用观测与源观测；蓝线比较仿真qpos。旋转均为四元数测地角，
不是四元数分量相减。逐步数值见 outputs/gate0/prefix_fidelity_by_step.csv。
原始NPZ仅本地保存，SHA256=`{result['trace_sha256']}`。

不放宽阈值、不替换S00、不传送到t、不继续专家后缀、不执行额外修复试验。
24条A主计划中仅首条尝试了前缀，其余23条及所有120条B均列为未执行。
若研究者以后批准重建排错，应先解决观测采样和物理重放差异，再独立登记；本轮到此停止。
""")
    text_file("fixed_baseline_audit.md", """# 固定解释基线审计

没有获得可信专家分叉和任何名义/扰动终局Y，故全部科学比较为**不可评估**，拟合次数0。
没有以缺失结果代替失败标签，也没有据未运行的baseline声称M有必要。

| 解释 | 输入/可计算性 | 本轮证据 |
|---|---|---|
| Isotropic / state scalar | 等模长设计已冻结 | 无有效方向后果，无法评价 |
| Fixed world axes / diagonal | 世界系控制与方向已核验 | 无Y；未拟合 |
| General state-independent3x3 | dev仅xyz，非对角不可辨识 | 未排除；不能以diag代替全部global metric |
| Fixed object frame | 原始nut绝对四元数可读 | 可信live fork未建立；未拟合 |
| Fixed task / insertion frame | XML peg1位置可读，任务轴可定义 | 无有效留出配对；未拟合 |
| Exact contact-normal frame | 本轮未建立可信法向提取 | baseline unavailable；ncon不构成法向 |
| Signed asymmetry / improvement | 需正负/名义官方成功Y | 全部未观测，不能解释为不存在 |
| State dependence / held-out mixed | B2的S08/S09/S10已事前冻结 | B未启动，不能检验 |

六个episode、12个状态完整保留在分母。没有NLL、state-shuffle显著性、曲率或跨策略
泛化结论。seed43只完成资产SHA审计；未运行其分叉。SDP/AggreVaTeD/SCRIM的机制与
非等价性见resource_audit.md；本轮没有训练或运行这些方法。
""")
    text_file("gate0_go_no_go.md", f"""# M-Gate 0 v2 决策：Invalid / Engineering blocked

**Gate A未通过；M科学假设尚未检验。** demo_191,t=52专家前缀重建超出预登记容差，
故在任何名义/扰动后缀前停止。不能解读为方向无效、简单基线充分、对称PSD被否定或
M有论文新意。没有No-Go或Potential Go证据，也不启动Gate1。

协议起始commit：`{registration['protocol_commit']}`。
真实执行代码commit：`{result['execution_commit']}`。
顺序为只读资产审计→独立协议commit→运行代码commit→首个A前缀→停止→只读诊断/报告。
所有M方向及名义终局结果都未产生；不存在事后替换预登记或把探索数据冒充盲测的问题。

保留12个候选状态，来自6个episode；dev8/4来源，held-out4/2来源，无来源交叉。
完整清单见frozen_state_manifest.csv；全部状态状态见frozen_state_status.csv。

- A：1条前缀尝试，52个control steps / 1300个integration steps，0条完整suffix。
- B：0/120条尝试，名义分支同样未执行；paired_outcomes.csv保留全部120行，Y/Delta均空缺。
- A全部24条主计划与B120条的逐条总账见all_branch_ledger.csv（144行）；另6条修复预留未使用。
- 零扰动重复对0，seed43后缀0，正负/改善/留出混合结果0。0表示计数，不是观察到失败。
- 无训练、下载、第二任务、系统/ROS/CUDA变更。D与spatial目录及旧分支未改变。

关键证据：分叉点物体观测误差2.040859mm，物理qpos位置误差1.778535mm；
前缀观测最大3.829777mm，物理qpos最大{diagnostic['square_qpos_max_position_error_m']*1000:.6f}mm。
源初态与动作完全一致，时序一致，仍存在在线观测滞后与接触段物理漂移。
详细阈值、姿态角、哈希和根因局限见expert_fork_fidelity.md。

本轮交付后停止，等待研究者review；不自动使用剩余预算排错、不更换状态、不放宽阈值、
不写Gate1执行计划来启动下一轮。若后续允许继续，应另行授权可复现性修复，并保持本轮
失败记录及协议SHA不变。
""")
    text_file("commands_and_costs.md", f"""# 命令与实际成本

实际运行（均在/home/asus/EAI；没有执行D实验脚本）：

```text
git switch -c research/m-gate0 cea2502eee1dd6504035f4fcde47af1833a90b93
bash m_direction_pilot/scripts/run.sh m_direction_pilot/scripts/audit_assets.py
git commit ...  # b2a64fb：独立协议/冻结矩阵
bash m_direction_pilot/scripts/run.sh m_direction_pilot/tests/test_gate0.py
bash m_direction_pilot/scripts/run.sh m_direction_pilot/scripts/freeze_registration.py
git commit ...  # 946091e：执行代码
bash m_direction_pilot/scripts/run.sh m_direction_pilot/scripts/validate_demo_fork.py > m_direction_pilot/reports/gate0/logs/gate_a.txt 2>&1
bash m_direction_pilot/scripts/run.sh m_direction_pilot/scripts/report_gate0.py
```

Gate A命令exit2是事前检查触发的工程停机；没有运行run_gate0.py。首次GPU沙箱访问失败，
沙箱外同一nvidia-smi成功；首次Git索引写入只读失败后使用已批准的元数据访问。没有系统修复。
另外的只读内联命令仅读取HDF5/源码/已保存NPZ做检查，无额外模拟步。

| 成本 | 实测 |
|---|---:|
| 资产审计内部wall | {actual_costs['asset_audit_internal_wall_seconds']:.6f}s |
| 专家前缀wall，含环境构建/初态恢复 | {actual_costs['prefix_wall_seconds']:.6f}s |
| 专家前缀process CPU | {actual_costs['prefix_cpu_seconds']:.6f}s |
| 分支wall，含保存 | {actual_costs['branch_wall_seconds']:.6f}s |
| 分支process CPU | {actual_costs['branch_cpu_seconds']:.6f}s |
| A执行循环wall，含最终JSON/哈希 | {actual_costs['A_loop_wall_seconds']:.6f}s |
| prefix control / integration steps | 52 / 1300 |
| prefix模拟时间 | 2.6s |
| 完整suffix / suffix steps | 0 / 0 |
| DP续跑推理调用 / GPU推理时间 | 0 / 0ms |
| CUDA峰值allocated / reserved | {result['peak_cuda_allocated_bytes']} / {result['peak_cuda_reserved_bytes']} bytes |

模型已加载3090，尚无真实DP forward；不能把模型驻留显存解释成完成了推理验证。
上述分支/循环计时不含Python导入和策略加载；它们没有单独计时，也没有伪造端到端墙钟或
GPU占用小时。CPU为process_time，GPU时间只针对真正推理调用；本次调用数为0。
9项单元测试首轮0.393s通过，使用本地checkpoint，无训练；真实零扰动同态检查尚未进行。

每次尝试先写append-only attempt_ledger.jsonl，分支JSON与本地NPZ均独占创建。
本轮预算保守按1次A reservation记账；完整suffix实际上为0，远低于A30/B120/总150上限。
未使用额度不构成继续实验的理由。所有成果仅M目录；Git排除原始HDF5、权重、环境、缓存和NPZ。
""")
    local_traces = [{"path": result["trace_path"], "sha256": result["trace_sha256"],
                     "bytes": (ROOT/result["trace_path"]).stat().st_size}]
    write_json(OUT/"local_trace_index.json", local_traces)
    write_json(REPORT/"final_audit.json", {"decision": summary["decision"], "protocol_unchanged": True,
        "all_12_states_retained": len(state_rows) == 12, "all_120_B_rows_retained": len(paired) == 120,
        "all_144_planned_branch_rows_retained": len(ledger) == 144,
        "no_missing_Y_coerced_to_failure": all(r["Y_nominal"] == r["Y_perturbed"] == r["delta_loss"] == "" for r in paired),
        "budget_reservations": {"A": 1, "B": 0, "total": 1}, "complete_suffixes": 0,
        "prefix_steps": 52, "no_B_or_training": True, "protected_tree_diff": [],
        "preserved_branch_heads": {b: git("rev-parse", b) for b in ["main", "research/d-gate1", "research/d-gate1-q2"]},
        "local_trace_sha256_verified": True, "read_only_diagnostic_simulation_steps": 0,
        "registration_commit_verified": registration["protocol_commit"], "suffix_execution_commit": result["execution_commit"]})
    print(json.dumps({"decision": summary["decision"], "planned_branch_rows": len(ledger), "prefix_steps": 52,
                      "complete_suffixes": 0, "new_simulation_steps_in_report": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
