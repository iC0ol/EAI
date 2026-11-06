# CMA 2609.27247 + Decision Value 2610.29646

## 2609.27247 Memory That Changes Action Is Not Memory That Guides It

- 作者：Jiajie Zhang 等 3 人；arXiv v1，2026-09-23
- 来源：<https://arxiv.org/abs/2609.27247>；本地全文 `papers/2609.27247__memory_changes_action_audit.txt`
- 读取层级：摘要 + §III–V + Table 2

关键：
- Put Back：64 个配对全部改变动作，但只有 20/64 在双向 × 所有动作种子下"完全可靠"；正确选择率 0.729，signed faithfulness 0.529。
- Later Swap：24 对全部改变动作，但选择分支从不改变（p=0.5, F=0）。
- 真机：9 次完成中 5 次抓错目标。
- **测量噪声关键**：动作种子间变异 0.0674 rad joint RMS，大于 memory-swap 的差异 0.0076 rad。
- 结论："reliable and predictive ≠ decision value" 的同类问题；两个 held-out 比较未显示相对强简单基线的独占预测增益。

对本复审：任何"干预后动作变化"的度量（包括 Δε）都必须先证明效应大于种子噪声；0.0076 vs 0.0674 是一个现成的量级警示。

## 2610.29646 From Association to Decision Value

- 作者：Nurmukhambetov Serikbayev 等 3 人；arXiv v1，2026-10-21
- 来源：<https://arxiv.org/abs/2610.29646>；本地全文 `papers/2610.29646__from_association_to_decision_value.txt`
- 读取层级：摘要 + §5.1/5.4 + 结论

关键：
- 单元是 **136 个独立种子语料**（56 开发 / 80 留出），任务是"选哪个示范语料训练更好"。
- 主 endpoint：proper-log-score 增量 +0.059 nats，95% bootstrap CI [−0.027, 0.133]；预设 top-20% 选择未显示增量。
- 结论：可靠、相关、能降 MAE 的诊断，仍可能没有增量决策价值。

对本复审：原则正确（必须报选择效用），但**样本单元是 80 个留出语料**。上轮把它转成"5 个任务上做 top-k 选择效用"的门槛，统计上不可估计（n=5 的 top-k 无法给出置信区间）。原则可保留，具体门槛需重写。

## 共同可用事实

- SUPPORTED：动作变化 ≠ 决策改变；配对诊断可能无决策价值。
- SUPPORTED：动作种子噪声可大于干预效应（CMA 0.0674 vs 0.0076 rad）。
- CONTRADICTED（对上轮的应用方式）：把 2610.29646 的 top-k 标准直接套到 n=5 任务。
