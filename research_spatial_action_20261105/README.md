# 空间理解与机器人行动：独立文献调研

- 工作区：`/home/asus/EAI`
- 新分支：`codex/spatial-action-survey-20261105`
- 执行：Claude Code CLI，现有 DeepSeek 后端 `deepseek-flash[1M]`
- 检索截止日：2026-11-05（Asia/Shanghai）
- 原始附件：`USER_PROMPT.md`；当前委托及交付要求：`DELEGATION.md`
- 范围：文献检索、论文下载与阅读、创新性审查、未来验证设计。无实验、训练、模型/数据集下载。

`scripts/run_research.py` 由独立 tmux 会话运行，不依赖原聊天保持在线。未完成的阶段性回答会接续同一 DeepSeek 会话；遇到上下文耗尽则通过落盘研究状态继续。真实服务/权限阻断会记录原因，避免无效空转。研究完成并核实公开分支后停止。

本地运行状态和模型接收回执分别在 `orchestration/runtime/status.json`、`orchestration/runtime/dispatch_receipt.json`；原始会话日志在 `logs/`。这些运行文件及论文全文不公开提交。最终报告为 `reports/FINAL_REPORT.md`，摘要为 `reports/EXECUTIVE_SUMMARY.md`，查新、自检及来源登记随报告发布。

tmux 会话：`eai-spatial-action-20261105`。查看终端可用 `tmux attach -t eai-spatial-action-20261105`；退出查看用 tmux 的 detach 操作，避免中断研究。手动停止可先在 `orchestration/runtime/STOP` 创建文件，阻止下一轮启动，再按需中断当前会话。完成本次交接后，Codex 不主动复查研究；由研究者另行通知。
