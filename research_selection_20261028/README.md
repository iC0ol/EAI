# 2026-10-28 具身学习选题联合审查

**本轮决定：当前无合格候选。** 原创研究审查交付完成；新机器人实验/仿真/策略推理/训练均NOT_RUN。C“本体状态依赖”仅保留为有限只读补证对象，未获得整夜实验资格。DeepSeek主张一次问题诊断备选，Codex对其资产与预算就绪程度持异议；没有伪造一致意见。

## 阅读顺序

1. [联合审查主报告](01_联合审查主报告.md)：历史约束、5项粗筛/3项深入、直接竞争、决定及五个问题的回答。
2. [实验辨识与条件性计划](03_实验辨识与条件性计划.md)：作用路径、同接口阳性/阴性、数据独立性、统计精度、两周/三个月条件性安排。
3. [工作站Agent只读补证任务书](02_工作站Agent_只读补证任务书.md)：独立自包含、90分钟上限；不是实验执行任务书，保存并未触发执行。
4. [文献与源码登记](notes/02_文献与源码阅读登记.md)：准确来源、版本、实际阅读范围、已读代码和资产状态。
5. [真实讨论与纠错账本](notes/03_真实讨论与纠错账本.md)：两轮有证据反驳、原始错误、更正与未决分歧。

## 原始记录和复核

- [原始任务书](00_原始任务书.md)；[状态](STATUS.md)；[历史来源清单](history/manifest.json)；[两份未取得原件](history/MISSING.md)。
- [Codex交换前冻结意见](notes/01_codex_independent.md)及[hash](notes/01_codex_independent.freeze.json)。这是保留错误的初稿，最终结论以主报告为准。
- DeepSeek：[独立回复](discussion/01_independent_response.md)、[第一轮](discussion/02_crosscheck_response.md)、[第二轮](discussion/03_crosscheck_response.md)；各同名`prompt.md`/`metadata.json`保留输入与执行记录。实际模型为deepseek-flash。
- [硬件与客户端核验](artifacts/workstation_audit.json)、[五小时续查](artifacts/five_hour_checkpoint.json)、[U与数学只读复核](artifacts/readonly_arithmetic_audit.json)、[GAP静态解析](artifacts/gap_static_parse.json)。
- [可重复的标准库算术脚本](scripts/readonly_arithmetic_audit.py)；[DeepSeek只读工具包装器](scripts/run_deepseek.py)。包装器沿用本机凭据，不包含key；不会自动运行。

旧项目保留原位。`archive/historical_reports_readonly.tar.gz`仅打包本轮需要的旧报告副本，不删除/移动原实验。`sources/`为14篇公开论文及源码文本的本地阅读缓存，原始DeepSeek JSONL在`discussion/`；这些全文/工具日志不进入公开Git。原始记录可在本机核对，公开包保留原创报告、可见讨论、来源与哈希，不上传环境、缓存、模型、数据或凭据。

按EAI既有公开同步授权，仅将本轮原创交付同步到已存在的`research/u-gate0-v3-overnight`分支；不创建新实验分支、不改写main、不force-push。同步结果见`STATUS.md`和最终回复。5小时续查已触发并继续完成了本轮；无需再开始同质候选搜索。
