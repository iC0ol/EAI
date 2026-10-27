# U：真实转移残差校准的动作一致性验证

本次结论：**TECHNICAL-BLOCK，止于 0A 资源门。** 没有在已完成的搜索范围定位到指定 LeWM 权重或匹配 PushT 训练数据/可信动作统计缓存，未验证可兼容运行环境。没有进行推理、训练或仿真，也没有对 U 作科学肯定或否定。

原始协议来自研究者 2026-10-27 的指令；机器可读约束保存在 [protocol_v2.json](configs/protocol_v2.json)。其中下游方案是待执行约束，未完成语义冻结的字段明确标注 NOT_RUN/NOT_VERIFIED；不能将其视为已通过 0A 的完整可执行预登记。

- [资源审计与实际命令](reports/preflight.md)
- [动作语义未验收项](reports/action_semantics.md)
- [基线有效性状态](reports/baseline_validity.md)
- [停止决定](reports/gate_decision.md)
- [局限与未执行内容](reports/limitations.md)
- [逐 root 表](outputs/per_root_metrics.csv)：仅表头，因为未建立实验 roots
- [资源/版本清单](outputs/resource_manifest.json)、[环境包版本](outputs/environment_packages.json)、[预算](outputs/budget.json)、[摘要](outputs/summary.json)

`scripts/run_gate.py` 仅实现离线资源审计；`scripts/summarize.py` 仅校验并汇总阻塞路径。它们不实现 G 训练、校准或 dev/test。输入检查拒绝覆盖已有审计目录，避免复查时毁坏证据。实际执行命令、返回码和测量范围见 preflight；不要把未实现的阶段当成可运行命令。

所有新增文件位于此目录。旧 D/M、Spatial、main 和起始研究分支保持原状；没有新建工作区、worktree 或环境。最终交付后等待研究者复审，不自动 U1、补样或下载数据。
