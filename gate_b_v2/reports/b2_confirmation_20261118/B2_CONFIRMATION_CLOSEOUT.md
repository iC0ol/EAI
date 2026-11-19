# B2 v1.1 Confirmation 收尾报告

**Confirmation COMPLETE。** Launcher 于北京时间 2026-11-18 19:53:35 正常退出，退出码为 0。运行总用时 **8 小时 46 分 11 秒**，其中 Harvest 用时 1 小时 23 分 01 秒，Branch 阶段用时 7 小时 23 分 10 秒。运行目录标识为 `b2_confirmation_20261118T110331`。 [工作站执行记录](../WORKSTATION_EXECUTION_LOG.md) · [发布清单](PUBLICATION_MANIFEST.json)

## 数据完整性与独立验收

- 复核了工作站实际运行环境、资产指纹、PREFLIGHT、正式授权及其 Discovery 证据绑定。Discovery 原始校验清单的 116 项全部通过。 [授权记录](../B2_CONFIRMATION_AUTHORIZATION.md) · [完整性复核 JSON](b2_confirmation_closeout_integrity.json)
- 主种子块 310000–310099 产生 91 个合格候选，满足选样要求。用冻结种子 `20261117` 独立重算，得到完全相同的 30 个选入状态。Discovery 与 Confirmation 的候选和入选状态在源种子、状态 ID、快照 SHA256 上均无交集。 [Harvest Summary](b2_confirmation_harvest_summary.json) · [候选清单](b2_confirmation_candidates.json) · [状态清单](b2_confirmation_state_manifest.jsonl)
- 91 个候选快照的文件 SHA256 均与清单一致。30 个入选快照全部通过独立恢复验证。最大模拟器状态误差和几何误差均为 0，最大观测 MAE 为 `0.00017544`，低于 `0.001`。 [逐状态验证](b2_confirmation_snapshot_validation.json)
- 450 条 Branch 覆盖 30 个状态 × 5 个 Horizon × 3 次重复，完整性、实际行序和共同噪声种子均通过核对。全部在 episode 总步数 500 时终止，最终任务判定均为布尔值，`success_error` 为 0 条。分析前后，111 个原始运行文件逐一通过 SHA256 校验。 [Branch Summary](b2_confirmation_summary.json) · [Branch JSONL](b2_confirmation_episodes.jsonl)

## 冻结统计与协议判定

按预注册计划独立分析 Confirmation。以 30 个物理状态为独立单位，从原始结果重算每个状态的主对比 `Δ_s = 0.5 × (p_s(1) + p_s(2)) − p_s(15)`。重新执行 5,000 次状态聚类 bootstrap 和 100,000 次状态级置换，所得主效应、区间、置换 p 值及判定与冻结分析一致。 [正式统计报告](B2_REPORT.md) · [分析 JSON](b2_confirmation_analysis.json)

| 指标 | Confirmation |
|---|---:|
| 主效应 E | 0.00 个百分点 |
| 95% 状态聚类 bootstrap 区间 | [0.00, 0.00] 个百分点 |
| 双侧置换 p | 1.0000 |
| 预注册实际意义阈值 | 8.00 个百分点 |

区间上界为 0 个百分点，低于预注册的 8 个百分点阈值。冻结协议判定为 **`CONFIRMATION_NO_PRACTICALLY_MEANINGFUL_EFFECT`**。 [冻结判定规则](../../../research_spatial_action_round4_20261109/reports/B2_PROTOCOL_REVISION_20261116.md#73-discovery-and-confirmation-decision)

| 首次 Horizon | 成功 / 90 | 成功率 |
|---:|---:|---:|
| 1 | 89 / 90 | 98.89% |
| 2 | 87 / 90 | 96.67% |
| 4 | 87 / 90 | 96.67% |
| 8 | 89 / 90 | 98.89% |
| 15 | 88 / 90 | 97.78% |

## 解释范围

- **主对比退化。** 30 个状态的 `Δ_s` 都恰为零。对这组常数重采样得到 `[0, 0]` 区间，净空与 `Δ_s` 的 Spearman 相关无定义。28 个状态的 15 条 Branch 全部成功，各 Horizon 的成功率为 96.67%–98.89%，呈现明显的成功率天花板。 [净空图](b2_confirmation_clearance.png) · [完整性与统计复核](b2_confirmation_closeout_integrity.json)
- **净空覆盖。** 91 个候选中有 89 个负净空和 2 个正净空。冻结随机抽样得到的 30 个状态均为负净空，范围为 −56.951 至 −3.891 mm。结论适用于本次采样覆盖的预插入状态。 [候选清单](b2_confirmation_candidates.json) · [状态清单](b2_confirmation_state_manifest.jsonl)
- **几何量关联。** 在 30 个入选状态中，投影净空与 XY 中心距离的 Pearson `r = −0.9678`，与轴向间隙的 `r = 0.4095`。本次状态分布中这些几何量共同变化，协议判定针对其中观察到的净空与主对比关系。 [独立统计复核](b2_confirmation_closeout_integrity.json)

B2 Discovery 与 Confirmation 均已完成，两组结果分别报告。Gate C 的状态为 **NOT AUTHORIZED**。 [Discovery 收尾](../b2_discovery_20261117/B2_DISCOVERY_CLOSEOUT.md) · [Gate B 状态](../../README.md)

## 公开产物复核

公开 Branch JSONL 与原机逐字节一致。公开清单采用相对路径，分析 JSON 绑定公开运行清单，并用 `null` 记录无定义的 Spearman 值。已用公开输入复算冻结分析，统计结果一致。二进制快照及正式授权原件由工作站保管，发布清单记录原始哈希。 [发布清单](PUBLICATION_MANIFEST.json)

在本目录执行 `sha256sum --check SHA256SUMS` 可验证公开产物。 [SHA256 清单](SHA256SUMS)
