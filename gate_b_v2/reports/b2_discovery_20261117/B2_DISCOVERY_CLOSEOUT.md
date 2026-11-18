# B2 v1.1 Discovery 收尾报告

**Discovery COMPLETE**。Launcher 于北京时间 2026-11-18 00:42:41 正常退出，退出码为 0。从 11 月 17 日 15:36:16 起共用时 **9 小时 06 分 25 秒**，其中 Harvest 1 小时 24 分 50 秒，Branch 阶段 7 小时 41 分 35 秒。

运行目录为 `b2_discovery_20261117T153523`。启动 HEAD 为 `f1e63c5fc79718d4ca859d71de656a57e62a7a45`，实现提交为 `2f1a495e495d926a91a317948c80184eccfc464d`。资产、环境、源码指纹和本次授权均通过复核。 [发布清单](PUBLICATION_MANIFEST.json)

## 数据完整性

- 主种子块 300000–300099 产生 90 个合格候选。候选快照的 SHA256、源参考和 Stage Gate 记录均核对通过。按种子 20261116 重算得到完全一致的 30 个选入状态。
- 全部 30 个选入快照的独立验证通过，模拟器状态、几何长度、Yaw、策略历史及 Replay A/B 的最大误差均为零。新渲染观测的最大 MAE 为 `0.0002106399`，低于 `1e-3`。
- 450 条 Branch 记录覆盖 30 个状态 × 5 个 Horizon × 3 次重复。完整性门禁、实际 JSONL 行序、快照指纹与共同噪声种子调度核对通过。
- 109 个原始输入与运行证据文件在分析前后逐个核对 SHA256。

逐项结果见 [完整性复核 JSON](b2_discovery_closeout_integrity.json)、[Harvest Summary](b2_discovery_harvest_summary.json)、[Snapshot Validation](b2_discovery_snapshot_validation.json) 和 [Branch Summary](b2_discovery_summary.json)。

## 冻结分析与协议判定

在项目现有环境中执行 `python -u -m gate_b_v2.cli analyze --run-dir runs/b2_discovery_20261117T153523`。从原始记录独立复算主效应、5,000 次状态级 bootstrap 的区间和 100,000 次置换检验，结果与正式分析一致。

主效应 **E = 5.57 个百分点**，95% 状态聚类 bootstrap 区间 **[-1.58, 15.64] 个百分点**，置换 `p = 0.3439`。点估计低于 8 个百分点的实际意义阈值，区间同时覆盖 0 和 8 个百分点。

冻结规则判定为 **`DISCOVERY_UNCERTAIN_CONFIRMATION_JUSTIFIED`**。Discovery 结论不确定，达到提交独立 Confirmation 审查的门槛。Confirmation 运行需要单独的研究者授权。

| 首次 Horizon | 成功 / 90 | 成功率 |
|---:|---:|---:|
| 1 | 84 / 90 | 93.33% |
| 2 | 85 / 90 | 94.44% |
| 4 | 85 / 90 | 94.44% |
| 8 | 85 / 90 | 94.44% |
| 15 | 84 / 90 | 93.33% |

## 2026-11-18 独立复核与研究局限

**B2 Discovery COMPLETED。** 重新读取已发布的候选、状态、快照验证与 Branch 明细，按 `20261116` 复算得到相同的 30 个入选状态。450 条记录的状态 × Horizon × 重复组合均唯一齐全，快照验证 30/30 PASS。450 条记录都在 episode 总步数 500 终止，最终任务判定均返回布尔值，`success_error` 均为空。由 Branch 原始记录独立拟合得到斜率 `-1.197244 / m`，用冻结的 5,000 次状态聚类 bootstrap 和 100,000 次置换复算得到发布的区间和 `p = 0.343857`。 [Branch 原始记录](b2_discovery_episodes.jsonl) · [快照验证](b2_discovery_snapshot_validation.json) · [分析 JSON](b2_discovery_analysis.json)

- **净空覆盖。** 90 个候选中有 89 个负净空、1 个正净空。随机选入的 30 个状态全部为负投影净空，范围为 `−52.708` 至 `−0.348 mm`。本次证据覆盖不同程度的负净空，延伸到正净空仍需相应的样本。 [候选清单](b2_discovery_candidates.json) · [净空分布与对比图](b2_discovery_clearance.png)
- **成功率天花板。** 各 Horizon 的成功率为 93.33%–94.44%。30 个状态中，26 个状态的 `Δ_s` 恰为零，4 个状态出现非零对比。高成功率压缩了状态间可观测的差异，斜率对少数发生分化的状态较敏感。按 30 个状态聚类得到的区间同时跨 0 和实际意义阈值。 [状态清单](b2_discovery_state_manifest.jsonl) · [净空分布与对比图](b2_discovery_clearance.png)
- **几何量关联。** 在这 30 个状态中，Clearance 与 XY 中心距离 `d_xy_m` 的 Pearson `r = −0.977183`，与 Axial Gap `z_gap_m` 的 Pearson `r = 0.648548`。投影净空与平面偏差、轴向间隙同时变化，当前设计无法识别 XY 净空的独立作用。覆盖正净空并让这几个几何量有更独立的变化，可作为另行设计的研究方向。 [状态清单](b2_discovery_state_manifest.jsonl)

Confirmation 已满足 Discovery 的预注册继续条件，正式授权为 **NOT AUTHORIZED**，Harvest 和 Branch 均为 **NOT STARTED**。Gate C 为 **NOT AUTHORIZED**。 [待审批授权模板](../B2_CONFIRMATION_AUTHORIZATION.md) · [独立执行计划](../B2_CONFIRMATION_EXECUTION_PLAN.md)

[正式统计报告](B2_REPORT.md) · [完整分析 JSON](b2_discovery_analysis.json)

## 发布文件校验

在本目录运行 `sha256sum -c SHA256SUMS` 可复核公开文件。2026-11-18 的文档版校验保留原机 SHA256 和此前发布版的校验锚点。 [SHA256 清单](SHA256SUMS) · [发布清单](PUBLICATION_MANIFEST.json)

收尾核验记录于 `2026-11-18T09:04:33+08:00`。
