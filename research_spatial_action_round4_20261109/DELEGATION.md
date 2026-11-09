# 第四轮接续委托：必须选择唯一主选题，仍不开展实验

你继续的是同一个DeepSeek会话。用户最新要求在2026年11月9日18:00北京时间把本轮新提示词发送给你并接续前三轮上下文；现在已经到授权发送时刻。本次新任务更新此前的完成/停止状态和候选决策要求。紧随其后的完整新原文是科学任务规范，不要重做前三轮委托，也不要将上一轮的否定结论当作不可改变的规则。

## 路径和权限

唯一工作区 `/home/asus/EAI`，本轮新目录 `/home/asus/EAI/research_spatial_action_round4_20261109/`（下称ROUND4），分支 `codex/spatial-action-round4-20261109`。CLI仍在原会话工作目录 `research_spatial_action_review_20261106`，请对新输出使用正确绝对路径，避免覆盖旧报告。

先读工作区和本轮AGENTS.md。历史报告、代码审计和文献库保持只读；缺失细节从指定报告读取，不猜测上下文。新原文完整保存在ROUND4/USER_PROMPT.md，18116字节，SHA256为 `51937cece044f632e21cf386a7edff7d62beea41b7be35c1d519bb653c30bbc7`。

既有用户授权覆盖本轮原创文档提交和公开push至 `https://github.com/iC0ol/EAI`，无需再次询问权限。只修改ROUND4新增文件；不得改动main、旧报告、旧实验、系统环境、依赖、ROS/CUDA/驱动。不得提交凭据、缓存、运行环境、下载论文全文、源码仓库、大型资产或其他任务文件。

本轮只有Gate A：阅读论文、公开代码和资产元信息、理论/统计分析、研究设计、原创报告。**不运行训练、模型推理、仿真或benchmark，不下载模型/大型数据，不安装依赖，不实现算法，不启动其他Agent，不开展Gate B/C。** 论文或少量公开纯源码可下载作静态阅读，存在ignored的papers/references中，不执行其中代码。

## 新任务的关键变化

必须完整执行附件。最终**选择一个唯一主推课题**，不能用并列候选、全部不合格、继续广泛调研作为答案。若没有理想选项，就选择当前风险最低、最可快速证伪且最值得优先验证的方案，明确标注“待实验确认的主选题”。这不是允许虚构科学有效性、创新性、本地成功率、权重或实验结果。

先核查2—4个具体任务/模型组合的真实资产、动作接口、官方评估与正成功证据，再形成2—3个不同科学问题/机制，比较并主动收敛。区分作者报告、官方资产存在、第三方复现和本地已跑通，本轮没有做本地实验，不能混写。基于真实行动失败证据与强简单反例，优先考虑可执行、可验证及失败成本，不能只给宏大理论问题或把A1/C1改名。

新检索只补明确决策缺口，优先已有三轮材料。证据足以排序即停止检索。文献不能决定的量转化为授权后的最小实验问题，不无限静态调查。真实未知必须诚实标出，不把未实验的假设写成事实；无需披露内部思维过程，提供可复核的论证和来源即可。

## 新交付

只在ROUND4建立：

- `reports/FINAL_REPORT.md`：严格覆盖附件A—H；第一页给出唯一主选题。包括资产表、失败链、候选取舍、最近邻竞争、方法/强基线、Gate B、两周计划、小论文与毕业论文不同贡献、三个风险预警和转向。
- `reports/PRIMARY_TOPIC.md`：可独立阅读的主选题决定，含中英文题目、科学问题、方法、任务/模型/资产、选择理由、未验证事项和首个待授权实验。
- `reports/GATE_B_PROTOCOL.md`：冻结的第一项最小验证协议，明确前置条件、唯一核心判断、最小运行范围、统计单位、指标/日志、对照/混杂、资源/成本、通过/停止标准和无正成功率时的处理。它只是设计，不执行。
- `reports/SELF_AUDIT.md`：按附件自检，特别防止为强制选题而夸大创新、把论文结果当作本地复现、忽略强简单基线、混淆相关与因果。
- `sources/sources.jsonl`：关键论文/官方代码/资源的版本、直接链接、证据定位、读取级别（全文/部分/摘要/静态源码/官方声明/未核实）及状态。
- `notes/search_log.md`、`notes/research_state.md`：实际差量核查及进展、有限未知、下一步和恢复信息。

本轮完成标记为ROUND4的 `reports/COMPLETION.json`，不能复用前三轮标记。只在实质工作完成后写：

```json
{
  "status": "COMPLETE",
  "round": 4,
  "report_path": "reports/FINAL_REPORT.md",
  "primary_topic": "实际唯一主选题名称",
  "self_audit": {
    "unique_primary_topic_selected": true,
    "task_assets_and_success_evidence_audited": true,
    "concrete_action_failures": true,
    "nearest_competitors_and_strong_simple_baselines": true,
    "gate_b_protocol_frozen": true,
    "two_week_plan": true,
    "method_paper_and_thesis_contributions": true,
    "risks_and_pivots": true,
    "uncertainties_not_claimed_as_facts": true,
    "no_experiments_performed": true,
    "github_publication_scoped": true
  },
  "remaining_uncertainties": []
}
```

允许未实验的不确定性，不能以选题不完美为由不作选择。只有真实外部阻断使后续任务都无法进行，且尝试合理替代入口失败，才可记录 `reports/BLOCKED.json`，字段status=BLOCKED、具体reason、实际attempted_alternatives。局部论文不可访问、候选有风险或需要实验确认都不是全任务阻断。

## 发布和结束

持续完成此轮原会话的实质工作，阶段提纲不算交付，但不要为增加研究轮数重复劳动。完成后仅stage `research_spatial_action_round4_20261109/` 下明确文件，审查staged diff，禁止 `git add .` / `git add -A`。提交并push `origin codex/spatial-action-round4-20261109`，对照 `git ls-remote` 与本地HEAD验证，确保本轮成果和标记已发布、目录无遗漏修改。不得force push或改写旧内容。

交接者确认你接收后即结束，不替你做科研选择。你完成唯一主选题、报告及发布后停止，等待研究者对Gate B的单独授权。
