# F 最后一轮有限恢复（2026-11-03）

**本轮已获得有效数值测量，但没有建立可靠任务基线。建议暂停当前checkpoint的优先F路线。**

从 [十问主报告](02_联合验收与研究决策报告.md) 开始。16次ACT已执行；仅比强mean/median改善1.64%/1.31%的平移MAE，未达到冻结20%/3-of-4门，Stage2 **NOT_RUN**，不是0/16。总53.403545791 GPU秒，无训练。

| 阅读目的 | 文件 |
|---|---|
| 结论与边界 | [FINAL_REPORT](FINAL_REPORT.md)、[阶段决定](stage2_decision.json)、[交付状态](completion.json) |
| 原授权和冻结身份 | [任务书](00_本轮用户任务书_原文.md)、[PROTOCOL](PROTOCOL.md)、[candidate manifest](candidate_manifest.json)、[scientific freeze](scientific_freeze.json) |
| 工程预检 | [CPU报告](CPU_PREFLIGHT_REPORT.md)、[修复账本](repair_ledger.json)、[公开原件导出](publication/README.md) |
| 健康输入 | [原始4个NPZ](inputs/)、[12图/读回](results/input/)、[父审](artifacts/parent_input_acceptance.json) |
| 动作输出 | [16个原始NPZ与JSON](results/predictions/)、[完整分析](analysis.json)、[7维动作CSV](artifacts/action_chunks.csv) |
| 独立验收 | [Codex原数组重算](artifacts/parent_model_recomputation.json)、[Codex意见](notes/08_Codex模型结果独立验收.md)、[DeepSeek独立](discussion/36_model_independent_response.md)、[最终交叉](discussion/37_model_cross_response.md) |
| 执行预算 | [累计账本](recovery_state.json)、[各阶段](stages/)、[命令](commands.jsonl)、[资源采样](resources.jsonl) |
| 公开完整性 | [允许清单](final_public_allowlist.txt)、[SHA manifest](final_publication_manifest.json)、[扫描](final_secret_scan.json)、[远程核验](publication/remote_verification.json) |

协议/候选manifest/修复证据保留形成时的原文状态，不回写SHA；实际放行顺序由 engineering_gate、science_gate、input_gate 与 orchestration 派发记录证明。本目录无新运行授权，所有后续训练、修复、基线替换和F实验均待研究负责人另行决定。
