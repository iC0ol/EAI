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

30 个选入状态的净空范围为 `-52.708` 至 `-0.348` mm，均为负净空。分组图用于描述这次样本覆盖。 [净空分布与对比图](b2_discovery_clearance.png)

[正式统计报告](B2_REPORT.md) · [完整分析 JSON](b2_discovery_analysis.json)

## 发布文件校验

在本目录运行 `sha256sum -c SHA256SUMS` 可复核公开文件。原机文件的哈希见发布清单和完整性复核。 [SHA256 清单](SHA256SUMS)

收尾核验记录于 `2026-11-18T09:04:33+08:00`。
