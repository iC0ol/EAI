# Gate 决定

**最终状态：TECHNICAL-BLOCK；停止阶段：0A。**

有限离线资源审计没有定位到指定的 LeWM PushT 权重、匹配训练数据或有可信来源的动作统计缓存。指定 HF 缓存目录不存在，已完成搜索范围没有对应名称或精确大小命中；已有环境未通过 LeWM/PushT 兼容验收。证据和覆盖局限见 [preflight](preflight.md) 与 [resource_manifest](../outputs/resource_manifest.json)。未为弥补缺失下载模型/数据或建立新环境。

这不是预算耗尽或实验负结果。磁盘余量充分；没有进入模型加载、重放、G 训练、校准或 dev，无法评价研究假设。没有实证依据使用 NO-GO-CURRENT-SCOPE、GO-MECHANISM-REVIEW，或据“不显著”作科学否定。

| 门槛 | 结果 |
|---|---|
| 0A 资源 | TECHNICAL-BLOCK |
| 0A strict load/scaler/语义/重现 | NOT_RUN |
| 0B 可信基线 | NOT_RUN |
| 32-calibration | NOT_RUN |
| 16-dev | NOT_RUN |
| dev→test 条件 1 | 未满足：0A 未通过 |
| dev→test 条件 2–6 | NOT_EVALUATED，未观察 dev |
| 64-test | NOT_RUN，未触及 |

没有建立独立实验 root/source，也没有相关候选分支。逐 root、工程重放、root manifest 均只含表头；科学指标和 δ_J 保留 null/NOT_RUN，未用 0 代替未执行结果。无候选评分、真实后继、O 或逐 root 分析。

本分支只新增 `u_consistency_pilot/` 文件。研究者已授权公开回传；提交将包含代码、协议、版本/来源 pins、资源证据、空表说明、失败原因和报告，不含数据/权重/环境/缓存/凭据。交付 commit 的父提交保留起始历史，main 和 D/M 分支不移动。

**到此停止，等待研究者将结果交给 Codex / DeepSeek 复审。** 五小时续查已取消，工具确认删除，记录在 automation_completion.json；不会自动进入 U1、追加 roots、下载 Cube、扩大实验或宣称正式可发表题目。若以后研究者提供可信本地资产位置及复审意见，需要重新核验 0A；本次报告不授权跨过该门。
