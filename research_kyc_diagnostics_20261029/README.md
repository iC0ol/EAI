# KYC 基线失败：联合审查与有限排障

本轮解释冻结 KYC ACT 在准确外参开发条件下 0/32 的原因，并决定是否值得再投入。原始授权见 [任务书](00_原始任务书.md)。2026-10-29用户进一步要求定位并尝试解决新发现的RGB损坏，新增范围见 [渲染修复](render_repair/00_授权与范围.md)。不自动重训。

旧证据：`../research_expansion_20261029/`，GitHub 分支 `research/u-gate0-v3-overnight`，起点提交 `a03f16da9110f219be49a0994140c7617a6b45ff`。旧目录保持只读。

分工：Codex 与真实 DeepSeek 独立审查、交叉讨论和验收；GPT-6.1-sol / max 执行双方审定的有限诊断。任务发布前先形成完整任务文本和 DeepSeek 审核记录。

进度入口：[STATUS.md](STATUS.md)。额度与自动检查：[orchestration/clocks.json](orchestration/clocks.json)；派发记录：[orchestration/dispatch.json](orchestration/dispatch.json)。

原有限诊断已受控结束，见 [执行报告](execution/FINAL_REPORT.md)、[Codex独立验收](notes/03_Codex执行结果独立验收.md)、[真实DeepSeek交叉验收](discussion/14_diag_acceptance_cross_response.md)。当前远端结果提交为2d42000；旧执行报告中的同步失败为当时记录，后续成功见 [发布回执](orchestration/publication.json)。原结果不覆盖，新微诊断另立协议和运行记录。

所有时间以 Asia/Shanghai 明示。通过账户实时 resetsAt 安排重置后两分钟续办，最长五小时核查作为兜底；完成回传可提前唤醒主任务。主研究与执行任务使用共享账户额度。没有调用额度兑换工具。
