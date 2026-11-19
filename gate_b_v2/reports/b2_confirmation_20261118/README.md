# B2 v1.1 Confirmation 结果

**Confirmation COMPLETE。** 2026-11-18 19:53:35（北京时间）正常结束。主种子块产生 91 个合格候选，30 个选入快照和 450 条 Branch 均通过独立复核。 [收尾报告](B2_CONFIRMATION_CLOSEOUT.md)

主效应 **E = 0.00 个百分点**，95% 状态聚类 bootstrap 区间 **[0.00, 0.00] 个百分点**，置换 `p = 1.0000`。30 个入选状态的主对比恒为零。冻结判定为 `CONFIRMATION_NO_PRACTICALLY_MEANINGFUL_EFFECT`。 [正式统计报告](B2_REPORT.md) · [分析 JSON](b2_confirmation_analysis.json) · [净空图](b2_confirmation_clearance.png)

- 450 条 Branch 记录逐字节复制。 [Episodes JSONL](b2_confirmation_episodes.jsonl)
- 候选、入选状态和 Snapshot Validation 保留 SHA256 与逐状态复核结果。快照路径相对于工作站运行目录。 [候选清单](b2_confirmation_candidates.json) · [状态清单](b2_confirmation_state_manifest.jsonl) · [快照验证](b2_confirmation_snapshot_validation.json)
- 公开输入已复算冻结分析。分析 JSON 使用 `null` 表示因状态对比恒定而无定义的 Spearman 统计量。 [完整性复核](b2_confirmation_closeout_integrity.json) · [发布清单](PUBLICATION_MANIFEST.json)

在本目录执行 `sha256sum --check SHA256SUMS` 可核验公开文件。 [SHA256 清单](SHA256SUMS)

[冻结协议](../../../research_spatial_action_round4_20261109/reports/B2_PROTOCOL_REVISION_20261116.md) · [Discovery 结果](../b2_discovery_20261117/README.md) · [预检验收证据](../preflight_third_revision/PREFLIGHT_EVIDENCE_MANIFEST.json)
