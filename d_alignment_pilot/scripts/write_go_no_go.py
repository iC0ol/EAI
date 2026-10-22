"""Write the post-retry decision from measured paired results, without tuning."""
from d_alignment.io import ROOT, read_json

data = read_json(ROOT / "outputs/gate1/comparison.json")
assert len(data["runs"]) == 6
assert all(r["training"]["status"] == "completed" and r["evaluation"]["episodes"] == 50 for r in data["runs"].values())
assert data["step_d_eligible_conditions"] == [], "Execute the authorized Step D before making a decision if the frozen gate passes"
assert len(data["archived_attempts"]) == 1
labels = {"clean": "Clean", "mixed_small_lag": "Mixed Small Lag", "larger_lag": "Larger-Lag Control"}
lines = ["# D Gate 1 判断（授权补跑后）", "", "2026-10-23，Asia/Shanghai。**Insufficient evidence / Stop at Gate 1；当前不建议进入 Gate 2。**", "", "Larger seed 43 已按研究者新增授权完成一次原配置补跑及同一批 50 初态测试，原六个条件/种子结果已齐。七次训练尝试中六次完成，一次中断，未按测试表现选择候选 checkpoint。原始中断记录保存在归档中，不从资源账本扣除。", "", "## 实际闭环结果", "", "| 条件 | seed 42 | seed 43 |", "|---|---:|---:|"]
for condition, label in labels.items():
    cells = []
    for seed in (42, 43):
        ev = data["runs"][f"{condition}_seed{seed}"]["evaluation"]
        cells.append(f'{ev["successes"]}/{ev["episodes"]}，{100*ev["success_rate"]:.0f}%')
    lines.append(f'| {label} | {cells[0]} | {cells[1]} |')
lines += ["", "正差表示 Clean 更好。每个训练种子的两策略按同一测试初态配对：", "", "| 污染条件 | seed | Clean−污染 pp | 初态配对 bootstrap 95% CI pp | Clean-only / 污染-only 成功 |", "|---|---:|---:|---|---:|"]
for condition in ("mixed_small_lag", "larger_lag"):
    comp = data["comparisons"][condition]
    assert comp["all_train_seeds_available"]
    for seed, value in comp["by_train_seed"].items():
        lo, hi = value["paired_bootstrap_95ci_pp"]
        lines.append(f'| {labels[condition]} | {seed} | {value["clean_minus_corrupt_pp"]:.1f} | [{lo:.1f},{hi:.1f}] | {value["clean_only_success"]}/{value["corrupt_only_success"]} |')
lines += ["", "按共同初态聚类、先平均两个固定策略种子后的结果：", "", "| 条件 | 平均 Clean−污染 pp | 初态聚类 bootstrap 95% CI pp | 两种子均为正差 | Step D 达标 |", "|---|---:|---|---|---|"]
for condition in ("mixed_small_lag", "larger_lag"):
    comp = data["comparisons"][condition]
    lo, hi = comp["paired_initial_condition_cluster_bootstrap_95ci_pp"]
    lines.append(f'| {labels[condition]} | {comp["mean_clean_minus_corrupt_pp"]:.1f} | [{lo:.1f},{hi:.1f}] | {comp["direction_consistent"]} | {comp["step_d_eligible"]} |')
attempts = list(data["runs"].values()) + data["archived_attempts"]
complete_gpu = sum(r["training"].get("gpu_allocated_wall_hours", 0) for r in attempts)
partial_gpu = sum(r["training"].get("gpu_allocated_wall_hours_lower_bound", 0) for r in attempts)
sim = sum(r["evaluation"]["simulation_cpu_wall_seconds"] for r in data["runs"].values())
infer = sum(r["evaluation"]["inference_wall_seconds"] for r in data["runs"].values())
lines += ["", f"合计 **300 个完整回合 / 120,000 控制步**。六次完整训练 GPU 占用墙钟 {complete_gpu:.4f} h，旧中断尝试 ≥{partial_gpu:.4f} h，总计 **≥{complete_gpu+partial_gpu:.4f} h**。正式评估仿真及 reset CPU 墙钟 {sim:.1f} s、推理墙钟 {infer:.1f} s。耗时定义和逐回合结果见 [闭环报告](baseline_results.md)。", "", "## Q1：实质影响的证据", "", "**Insufficient evidence / Stop at Gate 1。** Mixed 两种子下降方向一致，但两个种子的配对区间都跨零；不能把 6/14pp 点估计写成已经确认的实质损害。Larger 第二种子现已补齐，但仍未达到同一污染条件两个种子均下降至少 10pp、且每种子配对区间下界大于零的原门槛。补跑消除了此前强错位对照缺失的问题，未提供可重复实质退化的充分证据。", "", "Larger seed 43 的下降为 22pp，配对 CI [8,36]pp，是这个固定策略比较中的实质损害信号。两种子平均下降 11pp，按初态聚类的 CI 为 [1,22]pp，也偏向损害；但这个区间条件于两组已训练策略，不能覆盖训练种子总体的不确定性。不能把它当作两个训练种子均已重复出退化，或临时用平均值取代原门槛。本轮应表述为“出现损害信号，但未达到预登记的跨种子重复性要求”，不能写成没有退化。", "", "Larger seed 42 的总成功数与 Clean 相同，但有 9 个 Clean-only 和 9 个污染-only 成功；成功率相等不表示逐回合行为相同。不得用统计未达标宣称错位无害，区间仍允许实质损害。没有更换任务、改变污染、追加种子或挑早期 checkpoint。", "", "Clean 44%/68% 通过预先固定的近失败/天花板门槛，但相差 24pp，说明训练随机性不可忽略。训练 noise MSE 约 0.011、EMA clean-valid 先降后升至约 0.21，存在明显过拟合。训练 loss 的收敛不是闭环成功证据，也不保证足够统计功效。50 初态和两个种子不能排除 1–3pp 小效应；当前区间条件于已训练策略，不能估计训练总体方差。", "", "## Q2：传统方法能否完成对齐", "", "**未评估：Step C 未达到预登记 Step D 门槛。** 没有执行互相关、ARX、轻量时间序列对齐或置信度估计，无 lag recovery 准确率、误差、多解率或分段结果可报告；不创建 `lag_identification.md`。8 条同步锚点和 16 条独立 lag test 留出继续隔离。", "", "已知真值逆移的完整性测试只证明生成器及 Oracle 公共窗口定义正确，不是盲 lag 估计器的恢复证据。当前不能判断简单方法是否已解决问题，不能给出 `No-Go for posterior-supervision necessity in this setting`，也不能宣称存在可靠的非尖锐后验或仍然有用的模糊示教。", "", "## 中断排查与停止原因", "", "| 类别 | 补跑后的证据 |", "|---|---|", "| 官方环境/数据部署失败 | 否；固定版本正常运行，六个策略均完成闭环 |", "| 原始执行中断 | 保留；补跑已补齐该条件，但旧进程直接终止原因仍未知 |", "| 智能体额度问题 | 同一会话明确记录 `usage_limit_exceeded`，5 小时额度达到 100%，智能体轮次因此结束 |", "| 统计证据不足 | 是；按原门槛没有可重复的实质退化证据 |", "| 简单基线否定后验机制必要性 | 未检验 |", "| 数据/模型条件限制 | 已在训练前排除缓存相对 object 分量；仍有过拟合与低种子数限制 |", "", "额度错误发生于 2026-10-22 22:53:21 +08:00，本地训练仍运行到 23:28:08。不能把智能体轮次结束与本地训练进程随后退出的直接因果关系混为一谈。当前续办起始额度可用，未兑换重置券。最少化、去账户标识的证据见 `interruption_diagnosis.json`，授权范围见 `retry_authorization.md`。", "", "## 边界和 Gate 2", "", "本实验仍为一个 Square PH 任务、16 维原始同步状态、相对 OSC 命令；20Hz，每步 50ms。`C[t]=A[t+delta]`，±1/2/4 步为 ±50/100/200ms。只改变训练标签，正常控制器响应、仿真和测试推理时轴未改变。原始相对 object 缓存问题及选择证据见 [时间约定](data_time_convention.md)。结果不支持 RGB 时间戳错误或真实机器人日志分布的推断。", "", "**当前不 Go to Gate 2，理由为研究前提的证据不足；不是后验监督被否定。** 此次授权补跑已完成，停止实验并推送报告，不自动重训其他种子、调参、扩大任务或训练后验监督策略。", ""]
(ROOT / "reports/gate1/go_no_go.md").write_text("\n".join(lines))
print("Wrote measured post-retry Gate 1 decision; Step D not triggered")
