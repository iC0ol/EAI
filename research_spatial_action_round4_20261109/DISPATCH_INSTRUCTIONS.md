# 第四轮：2026年11月9日18:00单次定时发送

## 用户要求

“这是新一轮的提示词，接续之前的上下文，在今天下午18:00的时候，定时发送给deepseek，让他开始任务。”

仅准备文件并保存调度时，不发送、不调用模型、不开展研究。实际发送不得早于 **2026-11-09 18:00 Asia/Shanghai（10:00 UTC）**。调度如稍迟，则在实际唤醒时完成单次交接并记录真实时间；不改为次日任务。

## 原文和原会话

- 新提示词：`/home/asus/EAI/research_spatial_action_round4_20261109/USER_PROMPT.md`。
- 原始附件：`/home/asus/.codex/attachments/fecbe36a-a549-47fb-bb67-5693b6f6f27c/writing-block.md`。
- 大小18116字节，SHA256 `51937cece044f632e21cf386a7edff7d62beea41b7be35c1d519bb653c30bbc7`。
- 原会话ID：`eb3d3477-5c3f-43c8-88a5-6fb3e2342597`。
- Claude原工作目录：`/home/asus/EAI/research_spatial_action_review_20261106`。
- 使用 `claude -p --resume <原ID>`；不得新建会话、fork、continue到不确定的最近会话，或静默丢弃旧上下文。此前原会话启动/完成条款由本次明确继续授权更新。

## 到点执行

1. **先停用触发本消息的单次自动化任务后续触发**，使用 automation_update，保留原配置其他字段。这仅停用调度，不停止本次执行或DeepSeek后台研究。不要创建额外周期任务。此前COUNT=1规则曾在次日仍触发，因此不只依赖规则计数。
2. 读取工作区及本目录AGENTS.md，检查本轮 `orchestration/runtime/dispatch_receipt.json`。若已存在原会话ID及真实DeepSeek响应的成功回执，则结束，禁止重复派发。当前仍有本轮后台进程时也不要再启动第二份。
3. 核验提示词hash和原会话日志存在，确认原会话没有并发进程。不得打印认证信息。未到指定时刻则不得发送。
4. 在同一 `/home/asus/EAI` 工作区创建/使用 `codex/spatial-action-round4-20261109`，保留其他任务所有文件及staging状态。不得另建workspace/worktree、清理旧文件或改写历史。
5. 使用本目录准备好的 `scripts/run_research.py`（仅交接设施，无实验内容）在独立tmux中启动。它固定resume原会话、使用原cwd、将完整新原文连同本次DELEGATION发送；不得误启动前三轮runner，不得复用前三轮的完成标记。
6. 若需先提交本轮提示词/交接设施，只stage本目录明确路径，检查无凭据、缓存和其他任务文件后提交/push。此阶段不审阅研究内容、不代替DeepSeek选题。
7. 核对真实DeepSeek模型响应或工具活动、CLI实际session ID与原ID一致，记录实际发送时间、hash、模型、ID、目录/分支及日志回执。确认交接后结束本次定时发送，DeepSeek后台继续。

## 本轮任务重点

完整新原文优先，尤其要求：在已有三轮基础上做有限差量核查，先确认2—4个具体任务/模型资产组合和真实行动失败，再比较2—3个不同机制，必须选择**唯一主选题**。证据不完美时选最值得快速证伪的候选，并诚实标为“待实验确认”；不得再以所有候选不合格或继续泛检索收尾，也不得虚构已有效。

按附件A—H交付：第一页明确主选题、资产/失败证据、竞争与强简单基线、完整方法方案、Gate B冻结最小实验、两周计划、两层论文贡献、三个风险及转向、Sources/SELF_AUDIT/COMPLETION。只设计Gate B，不执行。成果仅写本轮新目录，沿用既有公开GitHub权限push本轮新分支并核对远程后停止，等待研究者授权。
