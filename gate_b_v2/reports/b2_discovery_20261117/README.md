# B2 v1.1 Discovery 结果

Square-MH Discovery 于北京时间 2026-11-18 00:42:41 完成。主种子块产生 90 个合格候选，选中的 30 个快照全部通过独立验证，450 条 Branch 记录通过完整性检查。 [收尾报告](B2_DISCOVERY_CLOSEOUT.md)

主效应 E 为 **5.57 个百分点**，95% 状态级 bootstrap 区间为 **[-1.58, 15.64] 个百分点**。区间覆盖 0 和 8 个百分点阈值，协议判定为 `DISCOVERY_UNCERTAIN_CONFIRMATION_JUSTIFIED`。 [正式统计报告](B2_REPORT.md) · [分析 JSON](b2_discovery_analysis.json) · [净空图](b2_discovery_clearance.png)

2026-11-18 的文档收尾补充了净空覆盖、成功率天花板和几何量关联。**Discovery COMPLETED**，Confirmation 已满足预注册的继续条件，状态为 **NOT AUTHORIZED**，Harvest 和 Branch 均为 **NOT STARTED**。Gate C 为 **NOT AUTHORIZED**。 [待审批授权模板](../B2_CONFIRMATION_AUTHORIZATION.md) · [独立执行计划](../B2_CONFIRMATION_EXECUTION_PLAN.md)

## 公开证据

- 450 条原始 Branch 记录逐字节复制。 [Episodes JSONL](b2_discovery_episodes.jsonl)
- 候选、状态清单和 Snapshot Validation 保留各快照的 SHA256 与独立验证结果。清单里的快照路径相对于工作站运行目录，二进制快照由工作站保存。 [候选清单](b2_discovery_candidates.json) · [选入状态](b2_discovery_state_manifest.jsonl) · [逐状态验证](b2_discovery_snapshot_validation.json)
- 公开版本将工作站路径改为相对路径，并把分析中的清单哈希指向公开版本。已用公开输入复算冻结分析，所有结果字段一致。 [发布清单](PUBLICATION_MANIFEST.json) · [完整性复核](b2_discovery_closeout_integrity.json)

在本目录执行 `sha256sum -c SHA256SUMS` 可校验公开文件。 [SHA256 清单](SHA256SUMS)

[冻结协议](../../../research_spatial_action_round4_20261109/reports/B2_PROTOCOL_REVISION_20261116.md) · [预检验收证据](../preflight_third_revision/PREFLIGHT_EVIDENCE_MANIFEST.json)
