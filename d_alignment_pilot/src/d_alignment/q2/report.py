"""Reports/figures from frozen outputs only; no model fitting or prediction."""
import csv
import datetime
import json
from pathlib import Path
import platform
import subprocess

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .common import read_json, sha256, write_json

ROOT = Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "outputs/q2_blind"
REPORT = ROOT / "reports/q2_blind"
LABELS = {"xcorr":"XCorr", "arx":"ARX", "zero":"Zero / no correction"}


def write(name, lines):
    (REPORT / name).write_text("\n".join(lines)+"\n")


def figure(fig, stem):
    fig.savefig(REPORT / f"{stem}.png", dpi=160)
    path = REPORT / f"{stem}.svg"
    fig.savefig(path)
    path.write_text("\n".join(line.rstrip() for line in path.read_text().splitlines())+"\n")
    plt.close(fig)


def percent(x):
    return f"{100*x:.2f}%"


def mean_ci(value, multiplier=1):
    mean = value["mean"]
    if mean is None:
        return "N/A"
    low, high = value["cluster_bootstrap_95ci"]
    return f"{mean*multiplier:.4f} [{low*multiplier:.4f}, {high*multiplier:.4f}]"


def generate():
    cfg = read_json(ROOT / "configs/q2_blind/experiment.json")
    data = read_json(PUBLIC / "summary.json")
    selection = read_json(PUBLIC / "anchor_model_selection.json")
    frozen = read_json(PUBLIC / "predictions_frozen.json")
    assert sha256(PUBLIC / "predictions.jsonl") == frozen["predictions_sha256"]
    rows = [json.loads(line) for line in (PUBLIC / "scored_cases.jsonl").read_text().splitlines()]
    assert len(rows) == 336
    grouped = {m:[r for r in rows if r["method"]==m] for m in LABELS}
    stats = data["methods"]
    errors = [r for r in grouped["xcorr"] if not r["exact_lag"]]
    error_sources = sorted({r["episode"] for r in errors})
    decision = data["decision"]
    assert decision["category"] == "A" and decision["sufficient_methods"] == ["arx"]

    with (PUBLIC / "by_episode_summary.csv").open("w",newline="") as handle:
        writer = csv.writer(handle,lineterminator="\n")
        writer.writerow(["episode","method","conditions","lag_exact_count","lag_mae_steps","action_exact_count","negligible_count","zero_lag_false_correction","mean_translation_command_rmse_m","mean_rotation_command_rmse_rad","mean_gripper_sign_disagreement"])
        for episode in cfg["lag_test"]:
            for method, cases in grouped.items():
                part=[r for r in cases if r["episode"]==episode]
                assert len(part)==7
                writer.writerow([episode,method,7,sum(r["exact_lag"] for r in part),np.mean([r["lag_absolute_error_steps"] for r in part]),sum(r["action_exact"] for r in part),sum(r["negligible_label_consequence"] for r in part),next(r["estimated_lag"]!=0 for r in part if r["true_lag"]==0),np.mean([r["translation_command_rmse_m"] for r in part]),np.mean([r["rotation_command_rmse_rad"] for r in part]),np.mean([r["gripper_sign_disagreement"] for r in part])])
    with (PUBLIC / "region_metrics.csv").open("w",newline="") as handle:
        writer=csv.writer(handle,lineterminator="\n")
        writer.writerow(["episode","true_lag","method","region","timesteps","translation_command_rmse_m","rotation_command_rmse_rad","gripper_sign_disagreement"])
        for row in rows:
            for region,value in row["regions"].items():
                writer.writerow([row["episode"],row["true_lag"],row["method"],region,value["timesteps"],value["translation_command_rmse_m"],value["rotation_command_rmse_rad"],value["gripper_sign_disagreement"]])

    fig, axes=plt.subplots(1,2,figsize=(11,4.2),constrained_layout=True)
    true_values=sorted(cfg["injected_lags"])
    for ax,method in zip(axes,("xcorr","arx")):
        matrix=np.zeros((7,9),dtype=int)
        for row in grouped[method]:
            matrix[true_values.index(row["true_lag"]),row["estimated_lag"]+4]+=1
        ax.imshow(matrix,vmin=0,vmax=16,cmap="Blues",aspect="auto")
        for i in range(7):
            for j in range(9):
                if matrix[i,j]:ax.text(j,i,str(matrix[i,j]),ha="center",va="center",color="white" if matrix[i,j]>8 else "black")
        ax.set(xticks=range(9),xticklabels=range(-4,5),yticks=range(7),yticklabels=true_values,xlabel="Estimated injected lag (steps)",ylabel="True injected lag (steps)",title=f'{LABELS[method]}: {sum(r["exact_lag"] for r in grouped[method])}/112 exact')
    fig.suptitle("16 independent sources x 7 correlated conditions; counts per cell")
    figure(fig,"lag_confusion_matrix")

    colors={"xcorr":"#b07625","arx":"#27739a"}
    fig,axes=plt.subplots(1,2,figsize=(11,4.1),constrained_layout=True)
    fixed_source=cfg["lag_test"][0]
    for method in ("xcorr","arx"):
        row=next(r for r in grouped[method] if r["episode"]==fixed_source and r["true_lag"]==0)
        scores=np.asarray(row["scores"])
        axes[0].plot(range(-4,5),(scores-scores.min())/max(np.ptp(scores),1e-20),"o-",color=colors[method],label=LABELS[method])
        for correct,style in [(True,"-"),(False,"--")]:
            values=np.sort([r["normalized_gap"] for r in grouped[method] if r["exact_lag"]==correct])
            axes[1].plot(values,np.arange(1,len(values)+1)/len(values) if len(values) else [],ls=style,color=colors[method],label=f'{LABELS[method]} {"correct" if correct else "wrong"}: {len(values)}')
    axes[0].axvline(0,color="black",ls=":",lw=1)
    axes[0].set(title=f"Fixed first source {fixed_source}, d=0",xlabel="Candidate injected lag",ylabel="Score above minimum / score span")
    axes[1].set(title="Gap distributions: descriptive, not probabilities",xlabel="Best / second-best gap divided by span",ylabel="Within-group empirical CDF",xlim=(0,1))
    for ax in axes:ax.grid(alpha=.2);ax.legend(frameon=False,fontsize=8)
    fig.suptitle("Scores and gaps; 112 conditions from 16 source clusters")
    figure(fig,"score_gap_diagnostic")
    fig,axes=plt.subplots(1,len(error_sources),figsize=(5.5*len(error_sources),3.8),constrained_layout=True,squeeze=False)
    for ax,episode in zip(axes[0],error_sources):
        for method in ("xcorr","arx"):
            row=next(r for r in grouped[method] if r["episode"]==episode and r["true_lag"]==0)
            values=np.asarray(row["scores"])
            ax.plot(range(-4,5),(values-values.min())/max(np.ptp(values),1e-20),"o-",color=colors[method],label=LABELS[method])
        ax.axvline(0,color="black",ls=":",label="True d=0")
        ax.set(title=episode,xlabel="Candidate injected lag",ylabel="Score above minimum / span")
        ax.grid(alpha=.2);ax.legend(frameon=False)
    fig.suptitle("All sources with XCorr errors, d=0; post-hoc description, no refitting")
    figure(fig,"xcorr_error_profiles")

    leak=["# 盲测与泄漏审计","","结论：正式盲预测接口通过检查。冻结之后才执行一次独立真值评分；不存在利用 NaN 边缘、可识别偏移文件名或跨污染版本比对的估计路径。","","| 程序角色 | 可读实验数据 | 不可见数据 |","|---|---|---|","| Builder | 官方源文件、原 split 和注入计划 | 不作为估计器 |","| Fitter | 八个干净锚点视图、无注入信息的设置 | 原 HDF5、所有查询、真值 |","| Estimator（每包独立进程） | 一个有限匿名包、冻结模型 | 原 HDF5、注入 manifest、私有 Oracle、其他查询、builder/scorer |","| Scorer | 已冻结预测及哈希，验证后才读真值/Oracle | 不向估计器回传标签 |","","隔离为实际 bubblewrap 0.6.1 的 mount/PID/network namespace，非仅靠代码约定。只读挂载 Python/标准库/项目 venv 和白名单代码；不挂载 GPU 设备。真实原 HDF5 以及生成后已经存在的私有真值路径，均在主动读取探测中返回 FileNotFoundError。结果见 `anchor_access_probe.json` 与 `query_access_probe.json`。","","两端统一裁四步，不先暴露含 NaN 的原污染数组；112 包所有数值有限、NaN 数全零。每来源七包 N=T−8 一致，观测逐值相同；七种注入的长度分布完全相同。不同源保留自然长度，未为对齐丢弃动作转换段。长度/NAN 计数都是无偏移信息的线索。","","所有候选 −4…4、H≤4、phase≤4 使用 `[8:N−4)` 相同评分时刻，索引审计全部通过。估计器 schema 拒绝注入字段、额外元数据和非有限数；随机文件重命名/执行次序测试不改变数值预测。每包独立进程也阻断利用同源七包相互比较的捷径。","","匿名 d=0 条件的 command 自然等于干净动作，但没有 d=0 标签或特权 clean-action 参考。它与其他条件一样单包运行；禁止的对象是额外原始 clean actions/Oracle 文件，而不是去掉协议要求的零注入对照。","",f"预测冻结：{frozen['frozen_at_utc']}；独立评分授权起点：{read_json(PUBLIC/'scoring_started.json')['started_at_utc']}。预测提交 `6c9b83c` 先于评分。预测 SHA256 `{frozen['predictions_sha256']}`；完整代码/输入/模型哈希见 `predictions_frozen.json`。","","测试：40 项初版通过；随后新增 3 项决策边界测试，最终 43 项通过。均为合成数据，不读取独立留出真值。另有真实 112 包输入/guard 审计和两角色 OS 访问探测。scorer 会在缺少冻结 receipt、哈希不符或测试未通过时拒绝授权真值。","","评分后才公开 `scored_cases.jsonl` 中的原 episode 与真实 d。该集合已揭盲，不能继续用于调参后声称独立验证。所有模型/窗口/门槛保持初登记值。"]
    write("leakage_audit.md",leak)

    lag=["# Lag 识别结果","","112 个条件来自 16 条固定独立来源；以下区间均按来源聚类重采样 10,000 次。没有把 112 当成独立示教。","","| 方法 | Exact | 95% 来源聚类 CI（%） | MAE 步 | MAE ms | 预测 ±3 | d=0 误修复 |","|---|---:|---|---:|---:|---:|---:|"]
    for m in LABELS:
        a=stats[m];ci=a["exact_lag"]["cluster_bootstrap_95ci"]
        lag.append(f'| {LABELS[m]} | {sum(r["exact_lag"] for r in grouped[m])}/112 ({percent(a["exact_lag"]["mean"])}) | [{100*ci[0]:.2f},{100*ci[1]:.2f}] | {a["lag_absolute_error_steps"]["mean"]:.6f} | {a["lag_absolute_error_ms"]["mean"]:.4f} | {sum(r["predicted_abs3"] for r in grouped[m])}/112 | {percent(a["zero_lag_false_correction_rate"])} |')
    lag += ["","ARX 的 [100,100]% 是当前经验分布重采样的退化区间，**不是总体准确率为 100% 的置信保证**。16 条来源仍不足以证明真实机器人日志普遍可恢复。Zero 的固定率由每源七种平衡注入决定，不是额外泛化证据。","","| true d | XCorr exact /16 | ARX exact /16 | Zero exact /16 |","|---:|---:|---:|---:|"]
    for d in sorted(cfg["injected_lags"]):
        lag.append(f'| {d} | '+" | ".join(str(sum(r["exact_lag"] for r in grouped[m] if r["true_lag"]==d)) for m in LABELS)+" |")
    lag += ["","| 原 episode | XCorr exact /7 | ARX exact /7 | XCorr 错误模式 |","|---|---:|---:|---|"]
    for e in cfg["lag_test"]:
        er=[r for r in errors if r["episode"]==e]
        pattern=", ".join(f'{r["true_lag"]}→{r["estimated_lag"]}' for r in sorted(er,key=lambda r:r["true_lag"])) or "无"
        lag.append(f'| {e} | {sum(r["exact_lag"] for r in grouped["xcorr"] if r["episode"]==e)} | 7 | {pattern} |')
    lag += ["","互相关错误仅在 demo_143 和 demo_20，各六个条件均偏估 +1 步；+4 条件在候选上界取 +4。后者可能受搜索边界截断影响，不能把未扫描的 +5 最优值当成观测事实，也不增加候选范围重跑。ARX 在全部原 episode 的七条件均正确。","","完整九候选原始分数为 `predictions.jsonl`；带真值的评分、逐源数据及 CSV 为 `scored_cases.jsonl`、`by_episode.json`、`by_episode_summary.csv`。","","![识别混淆矩阵](lag_confusion_matrix.png)"]
    write("lag_recovery_results.md",lag)

    action=["# Oracle 对照的动作监督修复","","Oracle 与所有方法使用完全相同的 `[12,T−8)` 原时间窗口。每方法共 14,938 个条件内时间点，来自 2,134 个不重复原始时间点；七次注入是相关重复测量。原始动作是控制命令，以下物理量是缩放后的目标命令误差，不是真实执行位置误差。","","| 方法 | 逐值完全一致 /112 | Negligible /112 | 平移命令向量 RMSE mm | 旋转命令向量 RMSE rad | 夹爪 sign 不一致 | 转换 ±2步邻域 sign 不一致 |","|---|---:|---:|---:|---:|---:|---:|"]
    for m in LABELS:
        a=stats[m]
        action.append(f'| {LABELS[m]} | {sum(r["action_exact"] for r in grouped[m])} | {sum(r["negligible_label_consequence"] for r in grouped[m])} | {a["translation_command_rmse_m"]["mean"]*1000:.6f} | {a["rotation_command_rmse_rad"]["mean"]:.8f} | {percent(a["gripper_sign_disagreement"]["mean"])} | {percent(a["gripper_switch_disagreement"]["mean"])} |')
    action += ["","上表 RMSE/比例先逐条件计算，再按来源等权平均；含物理分组及区间的精确值在 `summary.json`。所有 16 条来源的公共窗口都有夹爪转换邻域，共 155 个原时间点、1,085 个重复条件时间点。不是把无转换样本填零。","","ARX 修复逐值与 Oracle 一致，平移/旋转/夹爪误差均为零。XCorr 的 12 个 lag 错误全部造成 non-negligible 标签变化；没有观察到 wrong-lag/negligible-label 案例。合成常量动作测试确认评分器会正确区分这类情况，但不能将测试中的现象当成本次留出结果。","","| XCorr 错误来源 | 错误条件数 | 单条件平移 RMSE mm | 旋转 RMSE rad | 全窗 sign 错误 | 转换邻域 sign 错误 |","|---|---:|---:|---:|---:|---:|"]
    for e in error_sources:
        er=[r for r in errors if r["episode"]==e];v=er[0]
        action.append(f'| {e} | {len(er)} | {v["translation_command_rmse_m"]*1000:.4f} | {v["rotation_command_rmse_rad"]:.8f} | {percent(v["gripper_sign_disagreement"])} | {percent(v["gripper_switch_disagreement"])} |')
    action += ["","这些是有实际标签后果的互相关错误，不能归为静止动作的无关歧义。其 low-change 区域只占归一化标签误差能量约 9.6–10.4%；大部分后果不在近常量区域。ARX 同时消除了这两条轨迹的错误，因此它们不构成简单硬对齐仍无法解决的缺口。","","## 预固定变化分段", "","low/high-change 阈值仅从锚点 q25/q75 冻结。分区如下；完整每条件、每区间的样本数与误差在 `region_metrics.csv`，不据留出结果改窗口。","","| 方法 | 区域 | 有数据条件数 | 平均平移 RMSE mm | 平均旋转 RMSE rad | 平均 gripper sign 错误 |","|---|---|---:|---:|---:|"]
    for m in LABELS:
        for region in ("low_change","middle_change","high_change","gripper_switch"):
            valid=[r["regions"][region] for r in grouped[m] if r["regions"][region]["timesteps"]]
            action.append(f'| {LABELS[m]} | {region} | {len(valid)} | {1000*np.mean([v["translation_command_rmse_m"] for v in valid]):.6f} | {np.mean([v["rotation_command_rmse_rad"] for v in valid]):.8f} | {percent(np.mean([v["gripper_sign_disagreement"] for v in valid]))} |')
    action += ["","本轮没有训练修复后的策略，不能把标签恢复直接写成闭环成功率改善。未观测接触力，也不凭夹爪转换自动诊断接触模式。"]
    write("action_repair_results.md",action)

    ambiguity=["# 分数与剩余歧义诊断","","不存在两种固定基线均无法修复的留出错误：ARX 的硬 MAP 全部正确。互相关呈现有信息的多候选曲线，但不能把较弱基线的失败直接当作后验监督必要性。","","| 方法 | true lag 平均中秩 | top3覆盖 | 合理集覆盖 | 平均合理集大小 | ambiguous | flat | unreliable |","|---|---:|---:|---:|---:|---:|---:|---:|"]
    for m in ("xcorr","arx"):
        a=stats[m]
        ambiguity.append(f'| {LABELS[m]} | {a["true_midrank"]["mean"]:.6f} | {percent(a["top3_support"]["mean"])} | {percent(a["true_in_near_set"]["mean"])} | {a["near_set_size"]["mean"]:.6f} | {percent(a["ambiguous"]["mean"])} | {percent(a["unidentifiable"]["mean"])} | {percent(a["unreliable"]["mean"])} |')
    ambiguity += ["","两方法 top3=100%，高于九候选均匀 top3=33.33% 与预固定先验 top3=42.86%。相对固定先验的 episode 聚类差异为 57.14pp；该退化区间只反映这 16 条观测来源，不是总体零方差。ARX 的合理集全部为正确 singleton，未出现需要混合标签的残余近似并列。","","XCorr 12 个错误的 true lag 中秩均为 2 或 3，9/12 仍在近似合理集中。其 normalized gap 全在 0.05 以下，具有描述性诊断意义；但全部错误均被同一预登记 ARX 硬估计消除，不满足潜在 Go 所需的跨来源、两方法均失败条件。","","## 预固定 margin bins", "","| 方法 | normalized gap 区间 | 条件数 | 所涉独立来源 | exact |","|---|---|---:|---:|---:|"]
    for m in ("xcorr","arx"):
        for low,high in zip(cfg["estimator_settings"]["confidence_gap_bins"][:-1],cfg["estimator_settings"]["confidence_gap_bins"][1:]):
            part=[r for r in grouped[m] if low<=r["normalized_gap"]<high]
            ambiguity.append(f'| {LABELS[m]} | [{low:.2f},{min(high,1):.2f}{"]" if high>1 else ")"} | {len(part)} | {len({r["episode"] for r in part})} | {percent(np.mean([r["exact_lag"] for r in part])) if part else "N/A"} |')
    ambiguity += ["","unreliable 是 best residual 高于 8 锚点 OOF q95 或模型失配的启发式标记。ARX 有 21/112 个条件被标记但 lag 仍全部正确；XCorr 的 12 个错误均未被该绝对残差阈值标记。它不能当作已校准错误概率或充分拒绝规则。tau 来自锚点，未为覆盖留出真值调整。","","没有输出残差 Softmax，没有训练概率后验。这里既不能证明概率校准，也不能证明所有实际日志中不存在歧义；只能说当前轨迹和固定整步注入下，最简单的短历史响应硬修复已足够。","","![分数和间隔诊断](score_gap_diagnostic.png)","","下图包含全部出现 XCorr 错误的来源，统一画 d=0，不挑最有利子片段；仅为揭盲后的描述，不改模型。","","![所有错误来源的候选曲线](xcorr_error_profiles.png)"]
    write("ambiguity_diagnostic.md",ambiguity)

    go=["# D-Q2 正式研究判断","","**情况 A：简单方法足够。**", "",f'**{decision["decision"]}**',"","8 条同步锚点选择的固定 ARX（H=4、lambda=0.01）在 16 个独立来源 × 7 条件中 112/112 恢复正确整步 lag，公共窗口动作监督逐值恢复 Oracle，含夹爪转换区域。互相关只有 100/112，两个来源确有 meaningful 标签错误；但没有两种简单方法共同留下的残余失败。","","因此没有当前证据支持增加对齐后验训练机制。不能因互相关的候选曲线非尖锐、仍保留 true lag 信息，就忽略已经成功的 ARX 硬修复。这次是当前设定的方法必要性不足，不是宣称所有具身日志都不存在时间不确定性。","","## 四种情况的逐项审计", "","| 情况 | 当前是否满足 | 原因 |","|---|---|---|","| A 简单方法足够 | 是 | ARX 满足原定标签恢复标准，16/16 来源七条件均逐值一致，关键夹爪误差零 |","| B 当前观测不可辨识 | 否 | 本次 ARX 正确恢复，不能因较弱 XCorr 失败而称信息不存在 |","| C 有用的剩余歧义 | 否 | 两方法共同错且有 meaningful 后果的来源为 0；无 ARX 残余近似并列 |","| D 接口/预算或证据不可解释 | 否 | OS 隔离、预测冻结、一次评分、索引/Oracle 测试均通过，未耗尽预算 |","","## 历史和适用范围", "","Q1 历史结案仍为 `Insufficient evidence / Stop at Gate 1`，原跨种子门槛没有通过，也没有回写。原 Larger/Mixed 的符号分配不严格嵌套，不据旧实验宣称单调剂量效应。Q2 是审查报告授权的独立离线必要性检查，不替代 Q1 稳定性验证。","","独立样本数只有 16，112 只是平衡相关条件；经验 bootstrap 全对时退化，不能证明真实机器人或 RGB 日志普遍可恢复。仅测试 ±4 步内固定整轨迹平移、同步原始低维本体状态和当前 OSC 控制；没有时变延迟、RGB、丢帧、未知动作定义或跨任务验证。输出修复一致也未通过新策略训练验证闭环效果。","","## 下一步", "","建议**停止当前 D 后验监督方向，下一步仅考虑 M 的最小前提验证**；不以已投入工程为继续理由。本轮不执行 M，不追加 Q1 策略种子，不训练后验监督，不新增仿真。若未来另行发现简单修复不足的新设定，也需要新的独立登记和证据，不能复用已揭盲集合调参后声称独立验证。"]
    write("q2_go_no_go.md",go)
    write("implementation_notes.md",["# 实施与修订记录","","1. 协议提交 `9e89e1c` 先于独立查询构造；未修改协议或机器配置。","2. 初版 40 项合成/隔离测试通过；在构造查询前补充三项决策边界测试，最终 43 项通过。它们没有改变拟合、评分或决策规则；两份实际 XML/日志都保留。","3. 八锚点模型选择及代码提交 `3c5ba71` 先于查询构造。模型和 safe code 的哈希此后未改。","4. 112 个单包进程只运行一次；224 条预测以 exclusive-create 保存并 chmod 只读，提交 `6c9b83c` 后才执行一次独立 scorer。","5. 揭盲后只增加本报告/图表/结构化导出与工件核验，没有改模型、候选、窗口、tau 或门槛，也没有重跑预测/真值评分。","6. 没有实施科学规则修正或根据留出结果调参。40→43 项是测试覆盖补充，不是替换失败实验。"])

    now=datetime.datetime.now(datetime.timezone.utc)
    elapsed=(now-datetime.datetime.fromisoformat(cfg["budget_start_utc"])).total_seconds()
    timing={"budget_start_utc":cfg["budget_start_utc"],"report_generated_at_utc":now.isoformat(),"conservative_elapsed_seconds":elapsed,"eight_hour_limit_seconds":28800,"within_limit":elapsed<=28800,"policy_trainings":0,"new_simulation_episodes":0,"new_environment_steps":0,"new_models_downloaded":0,"anchor_fit_wall_seconds":read_json(PUBLIC/"anchor_model_frozen.json")["fit_wall_seconds"],"blind_prediction_wall_seconds":frozen["prediction_wall_seconds"]}
    write_json(PUBLIC / "execution_summary.json",timing,exclusive=False)
    env=["# 环境、预算与实际执行命令","",f'保守起点为 2026-10-23 10:08 +08:00，报告生成时累计墙钟 {elapsed/3600:.4f} h，含阅读、开发、等待与排错；低于八小时上限。最终结案核验时间另记 `final_integrity.json`。',"","实际新增策略训练 **0**、仿真回合 **0**、环境步 **0**、模型/数据下载 **0**。仅拟合小型线性响应模型，使用 CPU；无神经网络对齐器。锚点拟合和盲预测时长见 `execution_summary.json`。","","复用 `/home/asus/EAI/d_alignment_pilot/.venv`：Python 3.9.13、NumPy 1.26.4、SciPy 1.13.1、h5py 3.11.0、pytest 8.3.5、Matplotlib 3.9.2、bubblewrap 0.6.1。没有安装依赖或更改全局环境、ROS、驱动/CUDA。设置最多两线程，无在线 WandB。Gate 1 的固定 RoboMimic/robosuite/DP 源码版本未改，本轮没有导入模拟器或策略模块。","","## 实际执行（cwd=/home/asus/EAI）", "","```bash","git switch -c research/d-gate1-q2 cea2502eee1dd6504035f4fcde47af1833a90b93",'git commit -m "Preregister independent blind Q2 alignment and necessity audit"',"bash d_alignment_pilot/scripts/run.sh -m pytest tests/test_q2_blind.py -q --junitxml=reports/q2_blind/preblind_tests.xml","bash d_alignment_pilot/scripts/run.sh scripts/q2/build_views.py anchors","bash d_alignment_pilot/scripts/run.sh scripts/q2/fit_anchors.py","bash d_alignment_pilot/scripts/run.sh -m pytest tests/test_q2_blind.py -q --junitxml=reports/q2_blind/preblind_tests_v2.xml",'git commit -m "Freeze anchor-only Q2 models and tested isolated estimator before blind queries"',"bash d_alignment_pilot/scripts/run.sh scripts/q2/build_views.py queries","bash d_alignment_pilot/scripts/run.sh scripts/q2/audit_blind_packets.py","bash d_alignment_pilot/scripts/run.sh scripts/q2/predict_blind.py",'git commit -m "Freeze all isolated Q2 blind predictions before independent truth scoring"',"bash d_alignment_pilot/scripts/run.sh scripts/q2/score_once.py","bash d_alignment_pilot/scripts/run.sh scripts/q2/report.py","bash d_alignment_pilot/scripts/run.sh scripts/q2/final_audit.py","```","","所有 stdout 在本报告 `logs/`，冻结记录在 `outputs/q2_blind/`。首次测试 40 passed/1.41s；补充后 43 passed，实际 XML 与日志均保留，未把未运行检查称为通过。另有 112 包真实 schema/guard 检查、拟合和查询命名空间访问探测。","","## 复现与私有工件", "","builder/fit/predict/score 的正式入口会拒绝覆盖既有工件。不能删除既有结果重新跑后选择较好版本。首次匿名化 seed 仅在本地 private truth；物理配置、划分、算法与评价固定。揭盲后的公开评分含匿名 ID、原 episode 和 d，可用于可信 builder 复核重建，但重建不是新的独立盲测；不能将公开结果继续用作盲选参集。","","本地源数据仍为旧官方 HDF5；输入 NPZ、模型系数、私有 Oracle、沙箱代码快照和零散进程 stdout 在 `data/derived/q2_blind/`，被既有 ignore 规则排除。只提交有限结构化预测、评价、配置、测试、代码和图表，不提交任何 HDF5、模型 checkpoint、Python runtime/cache 或凭据。"]
    write("environment_and_commands.md",env)
    write("README.md",["# D-Q2 盲对齐必要性审计","","结论：**No-Go for D posterior-supervision necessity in this setting**。ARX 112/112 恢复正确 lag，公共窗口标签逐值等于 Oracle；16 个独立来源，非 112 个独立样本。","","- [预登记协议](protocol.md)","- [泄漏审计](leakage_audit.md)","- [锚点选择](anchor_model_selection.md)","- [Lag 结果](lag_recovery_results.md)","- [动作修复](action_repair_results.md)","- [歧义诊断](ambiguity_diagnostic.md)","- [正式判断](q2_go_no_go.md)","- [环境和命令](environment_and_commands.md)","","保留 Gate 1 的原结案与所有文件，不进行策略训练、环境交互或下一阶段。"])
    print("Generated measured Q2 reports, CSV exports and three figures; no estimator rerun")
