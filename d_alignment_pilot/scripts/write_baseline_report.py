"""Summarize measured runs; never substitute missing trials with failures."""
import json

from d_alignment.io import ROOT, read_json

data = read_json(ROOT / "outputs/gate1/comparison.json")
cfg = read_json(ROOT / "configs/gate1.json")
labels = {"clean": "Clean", "mixed_small_lag": "Mixed Small Lag", "larger_lag": "Larger-Lag Control"}
all_attempts = list(data["runs"].values()) + data.get("archived_attempts", [])
completed_count = sum(r["training"]["status"] == "completed" for r in all_attempts)
lines = ["# Gate 1 闭环基线结果", "", f"共启动 {len(all_attempts)} 次训练：{completed_count} 次完成，{sum(r['training']['status']=='interrupted' for r in all_attempts)} 次中断。只有完成 50,000 次更新的最后 EMA 才进入闭环评估，没有按测试表现选择 checkpoint。中断尝试保留日志和算力，不以失败回合替代缺失结果。", "", "## 运行与资源", "", "| 条件 | 已启动/完成训练（含归档） | 结果训练种子 | 训练 GPU 占用墙钟小时 | 正式评估回合 |", "|---|---:|---|---:|---:|"]
for condition, label in labels.items():
    runs = [r for r in all_attempts if r["training"]["condition"] == condition]
    completed = [r for r in runs if r["training"]["status"] == "completed"]
    gpu = sum(r["training"].get("gpu_allocated_wall_hours", r["training"].get("gpu_allocated_wall_hours_lower_bound", 0.)) for r in runs)
    prefix = "≥" if any(r["training"]["status"] != "completed" for r in runs) else ""
    episodes = sum(r.get("evaluation", {}).get("episodes", 0) for r in runs)
    lines.append(f'| {label} | {len(runs)}/{len(completed)} | {", ".join(str(s) for s in sorted({r["training"]["seed"] for r in runs})) or "未运行"} | {prefix}{gpu:.4f} | {episodes} |')
complete_gpu = sum(r["training"].get("gpu_allocated_wall_hours", 0.) for r in all_attempts)
partial_gpu = sum(r["training"].get("gpu_allocated_wall_hours_lower_bound", 0.) for r in all_attempts)
total_gpu = complete_gpu + partial_gpu
sim = sum(r.get("evaluation", {}).get("simulation_cpu_wall_seconds", 0.) for r in data["runs"].values())
infer = sum(r.get("evaluation", {}).get("inference_wall_seconds", 0.) for r in data["runs"].values())
episodes = sum(r.get("evaluation", {}).get("episodes", 0) for r in data["runs"].values())
lines += ["", f"完成的 {completed_count} 次训练 GPU 占用墙钟 **{complete_gpu:.4f} h**，中断训练已确认 **≥{partial_gpu:.4f} h**，合计 **≥{total_gpu:.4f} h**；正式策略评估 **{episodes} 回合 / {episodes*400:,} 控制步**；仿真及 reset CPU 墙钟 **{sim:.1f}s**；推理墙钟 **{infer:.1f}s**。", "", "GPU 小时是本进程训练阶段占用设备的墙钟，包含该阶段验证和保存开销，不是 profiler 统计的纯 kernel 时间。CPU 墙钟是正式评估 env.step + reset 调用耗时，不是 CPU 核时。部署下载、源码审计、数据/重置验证开销不冒充训练资源。"]
if data.get("retry_authorization"):
    lines += ["", "研究者在 2026-10-23 明确授权 Larger seed 43 补跑一次，总尝试数由原预算六次扩至七次，仍只有原六个条件/种子组合。原 42,400 更新尝试保存在 `outputs/gate1/interrupted_attempts/`；`interruption.json`、归档文件及哈希保留，不删除或扣除其算力。补跑沿用全部 29 个冻结文件/manifest、相同 50,000 更新和 50 初态，未挑选多个完整候选。授权记录见 `retry_authorization.md`。", "", "历史会话明确记录 2026-10-22 22:53:21 +08:00 的 `usage_limit_exceeded`，确认额度耗尽结束了智能体轮次。训练仍继续到 23:28:08；没有进程退出码，不能证明额度直接终止训练，也不归因为 OOM 或数值发散。证据见 `interruption_diagnosis.json`。"]
else:
    lines += ["", "Larger seed 43 最后确认 42,400/50,000 更新，无最终 checkpoint，不评估部分策略，不把缺失记成 0/50；见 `interruption.json`。"]
lines += ["", "单独的 GPU 部署 smoke 为 0 optimizer updates；原始示教 replay 和冻结初态检查不计为策略评估。所有已执行正式评估均为同一批 50 个初态、每回合完整 400 步，首次成功后继续到 400 步。", "", "## 每个实际结果", "", "| 条件 | 训练 seed | 最后确认更新数 | 成功/回合 | 成功率及 Wilson 95% CI | 最后训练 noise MSE | 最后 EMA clean-valid MSE（更新） | 峰值分配/保留显存 GiB |", "|---|---:|---:|---:|---|---:|---|---|"]
for name, run in data["runs"].items():
    tr = run["training"]
    path = ROOT / "outputs/gate1" / name / "metrics.jsonl"
    metrics = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
    final = metrics[-1] if metrics else {}
    ev = run.get("evaluation")
    if ev:
        lo, hi = run["wilson_success_95ci"]
        success = f'{ev["successes"]}/{ev["episodes"]}'
        rate = f'{100*ev["success_rate"]:.1f}% [{100*lo:.1f}, {100*hi:.1f}]'
    else:
        success, rate = "未完成", "未完成"
    memory = f'{tr["peak_gpu_allocated_bytes"]/2**30:.3f}/{tr["peak_gpu_reserved_bytes"]/2**30:.3f}' if "peak_gpu_allocated_bytes" in tr and "peak_gpu_reserved_bytes" in tr else "未记录"
    train_loss = f'{final["train_noise_mse"]:.5f}' if "train_noise_mse" in final else "无"
    val = [m for m in metrics if "ema_validation_clean_noise_mse" in m]
    val_loss = f'{val[-1]["ema_validation_clean_noise_mse"]:.5f} ({val[-1]["update"]:,})' if val else "无"
    update_label = str(tr["updates_completed"]) + ("（中断，非最终）" if tr["status"] != "completed" else "")
    lines.append(f'| {labels[tr["condition"]]} | {tr["seed"]} | {update_label} | {success} | {rate} | {train_loss} | {val_loss} | {memory} |')
lines += ["", "训练 loss 是对本条件标签的扩散噪声预测 MSE；验证始终采用相同的 clean valid 数据。二者均不是动作执行误差或闭环成功率。过拟合迹象应与正式闭环结果一并阅读。", "", "## 配对比较", "", "正差表示 Clean 成功率更高；同一个测试 seed 的两结果成对。", "", "| 污染条件 | 训练 seed | Clean−污染 pp | 初态配对 bootstrap 95% CI pp | Clean-only / 污染-only 成功 | 该种子达到数值标准 |", "|---|---:|---:|---|---:|---|"]
found = False
for condition, comp in data["comparisons"].items():
    for seed, value in comp["by_train_seed"].items():
        found = True
        lo, hi = value["paired_bootstrap_95ci_pp"]
        lines.append(f'| {labels[condition]} | {seed} | {value["clean_minus_corrupt_pp"]:.1f} | [{lo:.1f}, {hi:.1f}] | {value["clean_only_success"]}/{value["corrupt_only_success"]} | {value["predeclared_material_drop"]} |')
if not found:
    lines += ["| 未形成完整配对比较 | — | — | — | — | 否 |"]
lines += ["", "| 污染条件 | 两种子平均下降 pp | 共同初态聚类 bootstrap 95% CI pp | 整个条件达到 Step D 门槛 |", "|---|---:|---|---|"]
for condition, comp in data["comparisons"].items():
    if not comp["all_train_seeds_available"]:
        continue
    lo, hi = comp["paired_initial_condition_cluster_bootstrap_95ci_pp"]
    lines.append(f'| {labels[condition]} | {comp["mean_clean_minus_corrupt_pp"]:.1f} | [{lo:.1f},{hi:.1f}] | {comp["step_d_eligible"]} |')
    if any(v["predeclared_material_drop"] for v in comp["by_train_seed"].values()) and not comp["step_d_eligible"]:
        lines += ["", f'{labels[condition]} 有单种子的实质损害信号，应保留报告；条件层面的跨种子重复性门槛仍未通过。平均值区间只反映当前固定策略的初态差异，不能覆盖训练种子总体方差，也不能取代预登记的两个种子要求。', ""]
lines += ["", "门槛为同一污染条件的两个训练种子均下降至少 10pp，且每种子配对区间下界大于零。聚类初态 bootstrap、精确 McNemar 结果及完整 discordant counts 在 `outputs/gate1/comparison.json`。", "", "50 初态和两个训练种子不足以排除 1–3pp 等小效应。区间只反映这些固定策略对测试初态的不确定性，不能估计训练随机性总体方差，也不是所有模仿学习系统的结论。", "", "## 辅助行为与原始记录", "", "| 条件/seed | 平均夹爪符号翻转 | 平均动作相邻差范数 | nut 低于桌面代理回合 |", "|---|---:|---:|---:|"]
for name, run in data["runs"].items():
    if "evaluation" not in run:
        continue
    aux = run["auxiliary_means"]
    lines.append(f'| {name} | {aux["gripper_sign_flips"]:.2f} | {aux["mean_action_delta_norm"]:.4f} | {run["nut_below_table_proxy_trials"]} |')
lines += ["", "这些是完整 400 步的辅助代理，可能包含成功后的行为；接触数/高度/抖动不能自动等同于已人工确认的接触错误。逐回合原始成功、首次成功步、重置误差、动作变化和耗时在每个 run 的 `evaluation.jsonl`。完整低维动作/状态 trace 为本地 `outputs/gate1/trajectories/` 的 NPZ，路径和 SHA256 随原始行记录。", "", "`paired_outcomes.csv` 保留按测试初态并排的 0/1 结果；所有训练 update 的 loss 在 `metrics.jsonl`。本地 checkpoint 路径、SHA256、配置和代码版本在各 `run.json`。模型权重、optimizer、原始 HDF5、虚拟环境和缓存均未进入 Git。", "", "![闭环成功率](closed_loop_success.png)", "", "![训练与验证去噪 loss](loss_curves.png)", "", "## 适用范围", "", "本实验使用同一个 Square PH 任务、原始相对控制命令及 16 维未改写的同步原始状态分量。训练前已排除官方 object 里缓存依赖的相对派生分量，详见时间约定及修订清单。因此不等于复现论文 23 维/绝对动作版本，也不支持 RGB 时间戳错误或真实机器人日志分布的推断。", ""]
(ROOT / "reports/gate1/baseline_results.md").write_text("\n".join(lines))
print(f"Wrote measured baseline report for {len(all_attempts)} training attempts, {len(data['runs'])} condition/seed slots, {episodes} complete policy episodes")
