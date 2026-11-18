# B2 v1.1 Confirmation 待审批授权模板

**NOT AUTHORIZED · 2026-11-18 · 待独立审查。** Discovery 的结论为 `DISCOVERY_UNCERTAIN_CONFIRMATION_JUSTIFIED`。95% CI 上界 `0.156406` 达到冻结协议规定的继续条件。Confirmation 需要研究者单独批准。 [Discovery 独立复核](b2_discovery_20261117/B2_DISCOVERY_CLOSEOUT.md)

## 待填写审批记录

| 字段 | 待研究者填写 |
|---|---|
| 授权人 | |
| 授权时间 | |
| 批准的 implementation commit SHA | |
| 批准的工作站 HEAD SHA | |
| 独立审查记录或审批编号 | |

## 审批范围

在 Square-MH 上使用全新的预插入物理状态，独立检验投影净空是否调节短首次动作提交相对 `h=15` 的成功率优势。按冻结规则选出 30 个独立状态，每个状态覆盖 `h ∈ {1, 2, 4, 8, 15}`，每个 Horizon 重复 3 次，共 450 条 Branch。

完整继承 B2 v1.1 的几何 Stage Gate、`h_source=8`、首次 Horizon、`h_continue=15`、最终任务成功判定、随机化及共同 policy-noise 种子、状态级分析和 `E ≥ 0.08` 的实际意义阈值。候选选择、采集条件和分析参数以冻结协议为准。 [冻结协议](../../research_spatial_action_round4_20261109/reports/B2_PROTOCOL_REVISION_20261116.md)

| 独立性约束 | 确认方式 |
|---|---|
| Confirmation 种子 | 主块 `310000–310099`，扩展块 `310100–310199`，选样种子 `20261117`。 |
| Discovery 对照 | 保留原机 Discovery 候选及 30 个正式状态作为隔离核对依据。 |
| 跨 Split 隔离 | 两个 Split 的候选池和正式状态池分别使用独立目录。启动 Branch 前检查 `source_seed`、`state_id` 和 `snapshot_sha256` 交集为空。 |
| 预留种子 | `299999` 保留给 PREFLIGHT。正式 Confirmation 仅使用上表种子块中新采集的状态和快照。 |

## 批准后的工作站授权字段

本 Markdown 用于审查。研究者明确批准后，运行器从新的 Confirmation 运行目录读取 `B2_CONFIRMATION_AUTHORIZATION.json`。

| JSON 字段 | 运行器要求 |
|---|---|
| `approved` | 研究者批准后填写 JSON 布尔值 `true`。 |
| `protocol_version` | 字符串 `B2_PROTOCOL_REVISION_20261116`。 |
| `implementation_commit` | 已批准的实现 SHA，与新目录中复制的 PREFLIGHT Summary 的 `implementation_commit` 完全一致。 |
| `preflight_summary_sha256` | 新目录内 `b2_preflight_summary.json` 的实际 SHA256。 |
| `authorized_by`、`authorized_at` | 实际授权人和授权时间，两者均为非空字符串。时间记录采用带时区的 ISO 8601。 |
| `authorized_scope` | 使用字符串 `confirmation`。 |
| `discovery_run_dir` | 指向已经完成的 Discovery 目录。代码可在缺省时查找当前目录，本计划采用独立目录，审批时显式填写。 |
| `discovery_analysis_sha256` | 对 `discovery_run_dir` 内的 `b2_discovery_analysis.json` 实际文件计算 SHA256。 |

授权同时绑定通过检查的 PREFLIGHT 证据和完整 Discovery 结果。 [执行计划与门禁核对](B2_CONFIRMATION_EXECUTION_PLAN.md)
