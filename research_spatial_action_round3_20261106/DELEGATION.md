# 第三轮接续委托：保持原会话，以明确科研决策结束

用户刚刚直接要求：“这是新一轮的提示词，发给deepseek，对话不用切换，接续上一轮的上下文，在上一轮的基础上接着调研。”

**这是上一轮原会话中的新用户任务，不是要求重建背景或重复此前综述。** 保留你上一轮科研复审的上下文；上一轮的“独立新会话”“完成后停止”等条款是上一轮的启动和结束状态，本轮用户已经明确授权继续。以紧随本委托后的完整新提示词为本轮科学要求，优先于旧委托中的任务目标。不要重跑旧委托、C1复审或旧完成检查。

## 路径与权限

- 唯一工作区 `/home/asus/EAI`；仍使用 `codex/spatial-action-review-20261106` 分支，不新建workspace/worktree。
- **本轮所有新成果只写入 `/home/asus/EAI/research_spatial_action_round3_20261106/`**，简称ROUND3。Claude当前目录仍为上一轮的 `research_spatial_action_review_20261106`，请对新文件使用正确的绝对路径，避免误覆盖旧报告。
- 新附件完整原文在 `ROUND3/USER_PROMPT.md`。保持19579字节的原文，SHA256为 `8f233d42ae80e828ccd0170f5e865e76873ad653d271507cdaa90fde1dec8495`。
- 上一轮报告 `research_spatial_action_review_20261106/reports/` 等作为实际可读的历史证据保持只读；缺少的上下文请回读文件，不能猜测。
- 之前明确授权的GitHub提交权限继续适用于本轮新报告和原创核查记录；完成后push到公开 `https://github.com/iC0ol/EAI` 当前分支。不得改写历史、force push、修改旧实验代码或其他任务目录。
- 只做文献、公开代码静态核查、理论/统计与方案分析。**不训练、不模型推理、不机器人仿真、不安装或运行第三方代码、不下载大型模型/数据、不实现算法、不派发实验Agent，不开始Gate B/C。** 不修改系统、驱动、ROS、CUDA或现有Python环境。
- 允许下载公开论文及少量必要源码作静态阅读，保存在本轮已忽略的 `papers/` 或 `references/`；不运行安装脚本、评估脚本、模型加载、notebook或测试。记录核查版本/commit、路径与行号。不得把第三方全文/源码仓库提交至GitHub。

## 如何继续研究

完整执行下附新提示词，重点是A1定义、直接竞争、MetaFine只读代码审计、最强简单方案与可能的新机制，以及可以明确裁决的科研决策，不再做开放式泛检索。最多选择另外2个具体问题与A1深入比较。文献多、引用少、README声称、代码存在、未安装等都不能独立作为结论。

MetaFine及最近邻研究的具体问题与URL已在新原文中给出。应核查官方纯源码及真实入口、版本、任务、固定状态/配对扰动接口、阶段指标、策略适配、公开阳性证据与资源限制，不能只重复README。只读审计不等于本机复现成功；也不能把尚未运行的功能全部判为不可用。

关键结论区分论文直接证据、独立推导、合理假设和当前未知。阅读全文/方法/实验/附录中真正影响决策的部分，标明读取层级与原文位置；抽象与数值不能靠摘要猜测。用有依据的数学定义区分感知误差、策略响应、控制传播、任务结果、几何余量及策略容差，不通过堆变量或不断改名制造创新。

保持用户一直强调的多研究、多思考、多阅读，但不靠论文数量、轮数、报告长度表现工作量。寻找强反例，主动推翻不成立的候选；不为赶进度开实验，也不无限收窄定义拖延决策。不需要披露内部思维过程，提供可复核的证据和论证即可。

## 新交付与完成标记

仅在ROUND3建立：

- `reports/FINAL_REPORT.md`：覆盖新原文第十节五项交付，明确因果关系、变量与测量、竞争/源码证据、解析/简单学习/潜在新机制对比、最多3候选及最终选择。
- `reports/FINAL_DECISION.md`：直接选择原文给出的四种科研决策之一并写明依据。如可申请Gate B，给出冻结的任务、基线、干预、阳性对照、停止条件、统计单元、评价与成本协议，但不执行；如需核查，仅留下有限、可直接裁决的证据缺口。
- `reports/COMPETITORS_AND_CODE_AUDIT.md`：MetaFine逐项只读核查、3—6篇最近邻对照、官方版本/文件行号/入口/资产/阳性及风险，使用VERIFIED/PARTIAL/UNKNOWN。
- `reports/SELF_AUDIT.md`：变量与因果逻辑、传统反例、创新差异、统计独立性、Gate顺序、两篇论文不同贡献、未知与权限边界自检。
- `sources/papers.jsonl`：本轮真正核查的核心论文和公开代码版本、来源、读取层级及证据定位。
- `notes/search_log.md`、`notes/research_state.md`：实际访问和阅读记录、已裁决问题、有限剩余工作及恢复信息；必要的原创全文/源码笔记另放 `notes/`。

不要复用上一轮 `reports/COMPLETION.json`。本轮实质完成后在ROUND3新建 `reports/COMPLETION.json`：

```json
{
  "status": "COMPLETE",
  "round": 3,
  "report_path": "reports/FINAL_REPORT.md",
  "self_audit": {
    "causal_and_measurement_definitions": true,
    "geometry_and_policy_tolerance_separated": true,
    "metafine_readonly_code_audit": true,
    "closest_competitors_checked": true,
    "analytical_learning_and_new_mechanism_comparison": true,
    "at_most_two_alternatives": true,
    "explicit_research_decision": true,
    "gates_and_statistics": true,
    "short_paper_thesis_distinct_contributions": true,
    "evidence_levels_and_unknowns_disclosed": true,
    "no_experiments_performed": true
  },
  "remaining_uncertainties": [],
  "decision": "用实际科研决策替换此文字"
}
```

允许真实、有限的科研未知或否定结论，不得为了标记完成编造证据。只有外部服务/访问等实际阻断使工作都无法继续、且合理替代入口也已尝试时，才写 `reports/BLOCKED.json`，字段 `status: BLOCKED`、具体 `reason` 和已实际尝试的 `attempted_alternatives`。问题难、局部全文不可访问和候选被否定不是全任务阻断。

## 发布与停止

只stage `research_spatial_action_round3_20261106/` 下明确文件，禁止 `git add .` / `git add -A`。审查staged diff，确保无其他任务文件、凭据、缓存、环境、第三方全文/代码、大文件或下载资产。提交后：

`git -C /home/asus/EAI push origin codex/spatial-action-review-20261106`

再用 `git ls-remote origin refs/heads/codex/spatial-action-review-20261106` 与本地HEAD核实，并确保本轮目录所有交付及完成标记已提交，无遗漏修改。

交接者确认本次新提示词已经被原会话接收后即结束，不替你做科研判断。你持续完成本轮实质审查和公开交付；不要只回复收到或提纲。完成后停止，等待研究者审阅，不开展实验。
