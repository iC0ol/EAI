# D-Q2 盲对齐必要性审计

结论：**No-Go for D posterior-supervision necessity in this setting**。ARX 112/112 恢复正确 lag，公共窗口标签逐值等于 Oracle；16 个独立来源，非 112 个独立样本。

- [预登记协议](protocol.md)
- [泄漏审计](leakage_audit.md)
- [锚点选择](anchor_model_selection.md)
- [Lag 结果](lag_recovery_results.md)
- [动作修复](action_repair_results.md)
- [歧义诊断](ambiguity_diagnostic.md)
- [正式判断](q2_go_no_go.md)
- [环境和命令](environment_and_commands.md)

保留 Gate 1 的原结案与所有文件，不进行策略训练、环境交互或下一阶段。
