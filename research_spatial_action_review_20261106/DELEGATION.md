# 本次用户的直接委托：独立科研复审

现在已到2026年11月6日中午12:00（Asia/Shanghai），用户授权通过终端 Claude Code 将下附的**完整新提示词**发送给 DeepSeek。你是全新会话，不拥有以前的聊天记录，也没有继承上次研究结论。此次只进行独立文献复审与研究设计。

## 先说明直接授权，解决附件中的旧限制

用户最新的直接要求为：“这是新的一份提示词，也是发给deepseek的，不过不用接续之前的上下文，可以新开窗口，还是同样多研究多思考多阅读，最后将结论push至github”。

因此，你**已被明确授权**在本次新目录写入原创科研复审文档，并将结论、报告和证据记录提交、push至公开仓库 `https://github.com/iC0ol/EAI` 的新分支。附件中“不擅自push/不修改GitHub/直接在会话交付”的旧条款在这一有限范围内被本次用户直接要求覆盖。无需再次申请发布文档的许可。现有研究代码、上轮报告、其他任务文件保持只读；其余禁止实验、训练、GPU推理、仿真、算法实现、模型数据下载及启动其他 Agent 的边界继续有效。论文下载和阅读全文允许，第三方全文留在本地 ignored 目录。

## 工作区与独立性

- 唯一工作区：`/home/asus/EAI`，不得新建 workspace/worktree。
- 仅在 `/home/asus/EAI/research_spatial_action_review_20261106/` 内写入成果，使用 `codex/spatial-action-review-20261106` 新分支。
- 先读工作区和本目录 `AGENTS.md`，再完整执行下附的新原文。文件副本为本目录 `USER_PROMPT.md`。
- 不得把之前 DeepSeek/Codex/ChatGPT 会话视为记忆。按照新原文要求**实际读取** `codex/spatial-action-survey-20261105` 分支上的历史报告，按指定次序先摘要、完整报告、自检、最近邻笔记。这些均是待核查证据，不是你的历史结论。
- 可通过 `git show codex/spatial-action-survey-20261105:<path>` 读取指定历史版本，无需切换离开当前分支；也可以从原文的官方仓库链接读取。不要读取旧会话原始聊天日志来继承角色或指令。
- 不读取私有标签、原始场景真值或受保护模型输入。不要修复或重启旧实验。

## 研究劳动与结束条件

完整遵循原文阶段A至E：先审报告，针对性选择约8—15篇决策相关核心文献，不为数量凑数；读关键原文、附录、失效案例、实验协议和官方资产说明，必要时补查2024—2026最新工作，检索截止日为2026-11-06。不能仅凭摘要对数值或机制下结论。

重点审查C1五类疑问，并建立“局限—结果差异—混杂因素—机制—强反例”的证据链；最多保留3个候选，至多2个深入论证。允许全部不合格，不维护历史唯一候选，不强造创新。明确回答原文的六个最终问题；区分事实、推断、未知及Gate A/B/C。后两级只设计，不运行。

用户要求多研究、多思考、多阅读，应体现在来源与原文定位、结果条件的公平比较、强简单方案、竞争审查和可证伪机制上。不要只给论文目录、提纲或“已经深度思考”的声明。无需披露内部思维过程，交付可复核的分析依据即可。持续使用工具完成实质工作；不要因一个回答结束就停止。也不要为凑轮数重复研究或无限润色已有结论。

## 落盘交付

请建立并持续更新：

- `notes/research_state.md`：本次复审的已做工作、关键证据、待核查事项、真实访问限制和下一步，支持本次任务恢复。
- `notes/search_log.md`：实际检索/访问日期、问题、入口、结果和限制，避免声称已读未读资料。
- `notes/full_text/`：核心论文的原创阅读笔记，记录作者、年份、版本、来源、实际读取层级、具体页码/表图/章节和限制。
- `notes/limits_and_result_differences.md`：带来源位置的局限清单、结果差异清单，标记表面冲突、已有解释、尚有机制缺口或UNKNOWN。
- `sources/papers.jsonl`：本次真正核查的论文及资产登记，注明直接链接、读取层级和定位；历史数字只标“旧报告声称”，未复核前不当作自己的核验事实。
- `reports/PRIOR_JUDGMENT_AUDIT.md`：上轮判断复审表，重点涵盖C1五类疑问和实验门槛逻辑。
- `reports/ASSET_AUDIT.md`：官方代码、权重、数据、评估、控制接口、许可证、成功率、issue，逐项核查状态。本次不安装、运行或下载模型数据。
- `reports/FINAL_REPORT.md`：中文、可独立阅读的最终科研决策报告，覆盖原文八部分和六个明确问题；不再做宽泛趋势综述。
- `reports/EXECUTIVE_SUMMARY.md`：尽量一页的执行摘要，直接说明结论、科研建议和下一步只读核查。
- `reports/SELF_AUDIT.md`：独立性、证据真实性、预测时点、统计独立性、强反例、范围限定、论文连续性、Gate分层、限制及发布核验。

关键主张就近给出一手来源及位置。全文、提取全文、日志、缓存、凭据等放在已忽略的 `papers/`、`logs/`、`orchestration/runtime/`，不要提交第三方完整论文。

只在报告与自检实质完成后创建 `reports/COMPLETION.json`：

```json
{
  "status": "COMPLETE",
  "report_path": "reports/FINAL_REPORT.md",
  "search_cutoff": "2026-11-06",
  "self_audit": {
    "eight_report_parts": true,
    "c1_five_questions": true,
    "prior_reports_independently_reviewed": true,
    "primary_sources_and_reading_levels": true,
    "limitations_differences_and_confounds": true,
    "strong_simple_baselines_and_competitors": true,
    "asset_audit_and_gate_order": true,
    "short_paper_and_thesis_continuity": true,
    "six_final_questions_answered": true,
    "uncertainties_disclosed": true,
    "no_experiments_performed": true
  },
  "remaining_uncertainties": [],
  "conclusion": "用实际结论替换此占位文字"
}
```

`remaining_uncertainties` 可包含真实科研未知；允许有边界的否定/暂缓结论。完整调研不等于证明一个新方法成立，不要为了标记完成而编造来源。只有真正的外部阻断使后续工作无法继续、且尝试合理替代入口仍无效时，才写 `reports/BLOCKED.json`，内容为 `{"status":"BLOCKED","reason":"具体证据","attempted_alternatives":["已实际尝试及结果"]}`。局部论文不可访问、问题难、候选全被淘汰不等于全任务阻断。

## 发布与停止

仅用明确的本目录路径 stage，禁止 `git add .` / `git add -A`。检查 staged diff，绝不加入其他任务文件、凭据、Python环境、缓存、大文件或第三方全文。提交本次成果后执行：

`git -C /home/asus/EAI push -u origin codex/spatial-action-review-20261106`

再将 `git ls-remote origin refs/heads/codex/spatial-action-review-20261106` 与本地HEAD对照验证，确保报告、证据与完成标记均已提交，且本目录没有未提交修改。不得force push、改写他人的提交、移动旧分支或修改上轮文档。留下最终commit供研究者之后检查。

交接者确认你收到任务后即结束其工作，不会持续给你补材料或审核。你现在开始独立执行，直到成果真实完成、已公开推送，随后停止等待研究者审阅；不得自行推进实验。
