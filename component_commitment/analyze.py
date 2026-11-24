"""Seed-paired pilot summaries. All control windows stay nested within episodes."""

import math
from pathlib import Path

import numpy as np

from study import ARMS, SEEDS, atomic_write, digest, save


def mean(values):
    return float(np.mean(values))


def capped_steps(row):
    return 500 if row["first_success_step"] is None else row["first_success_step"]


def mechanism(episodes):
    splits = releases = opportunities = material_seeds = release_seeds = eligible_seeds = 0
    incompatibility = stall = 0
    upward_mean_by_seed, lateral_mean_by_seed = [], []
    for row in episodes:
        events = [e for e in row["events"] if e["eligible"]]
        eligible_seeds += int(bool(events))
        opportunities += len(events)
        material = released = False
        for event in events:
            if event["decision"] == "split":
                splits += 1
                issued = event["issued_hole_axial_minus_new_m"]
                material |= math.sqrt(sum(v * v for v in issued) / len(issued)) >= 0.001
            if not event["admissible"]:
                incompatibility += 1
                stall += int(event["stall"])
                if row["arm"] == "adaptive":
                    released = True
                    releases += 1
        material_seeds += int(material)
        release_seeds += int(released)
        if events:
            upward_mean_by_seed.append(mean([e["actual_hole_upward_travel_m"] * 1000 for e in events]))
            lateral_mean_by_seed.append(mean([(e["actual_hole_lateral_end_m"] - e["actual_hole_lateral_start_m"])
                                              * 1000 for e in events]))
    return dict(opportunities=opportunities, eligible_seeds=eligible_seeds, split_events=splits,
                material_seeds=material_seeds, releases=releases, release_seeds=release_seeds,
                incompatible_events=incompatibility, stall_events=stall,
                mean_upward_mm=mean(upward_mean_by_seed) if upward_mean_by_seed else None,
                mean_lateral_change_mm=mean(lateral_mean_by_seed) if lateral_mean_by_seed else None)


def pairwise(ours, reference, bootstrap):
    first = np.array([capped_steps(a) - capped_steps(b) for a, b in zip(ours, reference)])
    final = np.array([int(a["success"]) - int(b["success"]) for a, b in zip(ours, reference)])
    interval = np.percentile(first[bootstrap].mean(axis=1), [2.5, 97.5]).tolist()
    success_interval = np.percentile(final[bootstrap].mean(axis=1) * 100, [2.5, 97.5]).tolist()
    return dict(mean_step_delta=mean(first), ci_steps=interval,
                final_success_delta_count=int(final.sum()), ci_success_pp=success_interval,
                adaptive_only_success=int((final == 1).sum()), reference_only_success=int((final == -1).sum()),
                adaptive_faster=int((first < 0).sum()), same_steps=int((first == 0).sum()),
                adaptive_slower=int((first > 0).sum()))


def summarize(rows):
    seeds = SEEDS["overnight"]
    grouped = {arm: [rows[seed, arm] for seed in seeds] for arm in ARMS}
    result = {}
    for arm, episodes in grouped.items():
        result[arm] = dict(n=len(seeds), ever_success=sum(r["first_success_step"] is not None for r in episodes),
                           final_success=sum(r["success"] for r in episodes),
                           mean_capped_steps=mean([capped_steps(r) for r in episodes]),
                           queries=episodes[0]["policy_queries"], samples=episodes[0]["policy_samples"],
                           mean_inference_s=mean([r["inference_seconds"] for r in episodes]),
                           mean_wall_s=mean([r["wall_seconds"] for r in episodes]), mechanism=mechanism(episodes))
    gen = np.random.RandomState(20261125)
    bootstrap = gen.randint(0, len(seeds), size=(20000, len(seeds)))
    contrasts = {arm: pairwise(grouped["adaptive"], grouped[arm], bootstrap) for arm in ARMS if arm != "adaptive"}
    primary = contrasts["refresh"]
    exposure = result["adaptive"]["mechanism"]
    enough = exposure["material_seeds"] >= 8 and exposure["release_seeds"] >= 4
    gain = (primary["mean_step_delta"] <= -10 and primary["ci_steps"][1] < 0
            and primary["final_success_delta_count"] >= -1)
    harm = ((primary["mean_step_delta"] >= 10 and primary["ci_steps"][0] > 0)
            or primary["final_success_delta_count"] <= -2)
    if not enough:
        decision = "保留或主动解除的有效机会不足，当前样本难以判断该机制。"
    elif gain:
        decision = "达到预定的先导收益门槛，支持在独立初态上验证。"
    elif harm:
        decision = "出现预定的性能损失信号，应回看不一致回合与抓持阶段。"
    else:
        decision = "本轮未达到预定的先导收益或损失门槛。"
    return dict(seed_count=len(seeds), episode_count=len(rows), control_steps=len(rows) * 500,
                arms=result, paired_contrasts=contrasts,
                interpretation=dict(decision=decision, enough_exposure=enough,
                                    meets_speed_and_final_success_criteria=gain, observed_loss_signal=harm),
                record_hashes={f"{s}_{a}": digest(r) for (s, a), r in sorted(rows.items())})


LABEL = dict(fixed15="固定 h=15", refresh="整块更新", smooth="整块平滑", always_split="满足条件即分量更新",
             adaptive="按相容性分量更新")


def display(value):
    return "—" if value is None else f"{value:.2f}"


def render(result):
    arms = result["arms"]
    contrasts = result["paired_contrasts"]
    p = contrasts["refresh"]
    n = result["seed_count"]
    e = arms["adaptive"]["mechanism"]
    lines = [
        "# Square-MH 分量动作块夜间先导结果", "",
        f"完成 {n} 个独立初态、{result['episode_count']} 个完整回合，共 {result['control_steps']:,} 个模拟控制步。"
        "同一初态的五组通过初始物理状态和首块预测哈希配对。独立工程验收数据单独存放。",
        "", f"**{result['interpretation']['decision']}** "
        f"相对同预算整块更新，自适应分量执行的首次成功截断步数平均差为 {p['mean_step_delta']:+.2f} 步"
        f"（按初态配对的 95% bootstrap 区间 [{p['ci_steps'][0]:+.2f}, {p['ci_steps'][1]:+.2f}]）。"
        f"前者最终成功 {arms['adaptive']['final_success']}/{n}，后者 {arms['refresh']['final_success']}/{n}。",
        "", "## 任务结果和实测成本", "",
        "| 方法 | 首次成功回合 | 最终成功回合 | 平均截断步数 | 查询 / 策略样本 | 平均推理秒 | 平均墙钟秒 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for arm, r in arms.items():
        lines.append(f"| {LABEL[arm]} | {r['ever_success']}/{n} | {r['final_success']}/{n} | "
                     f"{r['mean_capped_steps']:.2f} | {r['queries']} / {r['samples']} | "
                     f"{r['mean_inference_s']:.2f} | {r['mean_wall_s']:.2f} |")
    lines += ["", "查询表示使用一个新观察时刻，策略样本表示一次完整的动作块生成。"
              "四种中途更新方法在同一物理时刻使用相同数量的候选。模拟控制频率为 20 Hz。"
              "到 500 步仍未首次成功的回合按 500 计，因此步数反映整个初态集合。", "",
              "## 配对结果", "",
              "负步数差表示分量自适应更快。成功的两列列出同一个初态上只有其中一组最终成功的个数。",
              "", "| 对照 | 自适应减对照的平均步数 | 95% 区间 | 仅自适应成功 | 仅对照成功 | 更快 / 相同 / 更慢 |",
              "| --- | ---: | --- | ---: | ---: | ---: |"]
    for arm in ("refresh", "smooth", "always_split", "fixed15"):
        c = contrasts[arm]
        lines.append(f"| {LABEL[arm]} | {c['mean_step_delta']:+.2f} | "
                     f"[{c['ci_steps'][0]:+.2f}, {c['ci_steps'][1]:+.2f}] | {c['adaptive_only_success']} | "
                     f"{c['reference_only_success']} | {c['adaptive_faster']} / {c['same_steps']} / {c['adaptive_slower']} |")
    lines += ["", "## 动作是否真正改变", "",
              f"自适应组在 {e['eligible_seeds']}/{n} 个初态出现过介入机会，共 {e['opportunities']} 个窗口。"
              f"其中 {e['split_events']} 次实际沿用旧孔心轴向轨迹，{e['releases']} 次在可介入时释放约束。"
              f"产生至少 1 mm 实发轴向变化的初态为 {e['material_seeds']}/{n}，发生主动释放的初态为 "
              f"{e['release_seeds']}/{n}。预设的可辨识性门槛分别为 8 和 4 个初态。", "",
              "| 方法 | 可介入种子 / 窗口 | 保留窗口 | 不相容窗口（含受阻） | 其中受阻 | 平均实测上移 mm | 平均横距变化 mm |",
              "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for arm in ("refresh", "smooth", "always_split", "adaptive"):
        m = arms[arm]["mechanism"]
        lines.append(f"| {LABEL[arm]} | {m['eligible_seeds']} / {m['opportunities']} | {m['split_events']} | "
                     f"{m['incompatible_events']} | {m['stall_events']} | {display(m['mean_upward_mm'])} | "
                     f"{display(m['mean_lateral_change_mm'])} |")
    lines += ["", "窗口描述量先在每个有机会的初态内平均，再对初态取均值。上移累计窗口中每一步的正向轴移，"
              "横距变化为末值减起值。不同组可能进入不同窗口，上移或退出本身也可能是正确操作。",
              "", "## 结论适用范围", "",
              "本轮研究的是固定重观察时刻下，选择保留何种运动分量的作用。外层控制器使用了模拟器的两指抓持、"
              "柱轴和孔心位姿真值，并在首次满足官方成功谓词后结束局部更新。固定 h=15 的采样预算较低，"
              "与它的比较同时反映查询频度和执行方式。正式样本为一个任务、一份策略权重和 32 个配对初态。"
              "检查终态成功率的稀少不一致回合时应同时查看表中的实际计数。可变查询时刻、纯视觉部署和跨任务表现仍待检验。",
              "", "实验设计见 [冻结协议](../../PROTOCOL.md)，逐初态结果摘要见 [统计文件](ANALYSIS.json)，"
              "各回合完整事件见 [原始记录目录](records/)，从逐步谓词独立重算的结果和原始文件哈希见 [核验清单](AUDIT.json)。", ""]
    return "\n".join(lines)


def deliver(directory: Path, rows):
    from audit import audit
    result = summarize(rows)
    verification = audit(directory, SEEDS["overnight"], result)
    save(directory / "AUDIT.json", verification)
    save(directory / "ANALYSIS.json", result)
    atomic_write(directory / "REPORT.md", render(result).encode("utf-8"))
