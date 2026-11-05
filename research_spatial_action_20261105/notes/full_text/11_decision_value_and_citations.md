# 决策价值与引文审计：2610.29646 + Semantic Scholar 追踪结果

## 2610.29646 — From Association to Decision Value

- 读取层级：PARTIAL_TEXT（摘要 + Fig. 1 + held-out 协议），arXiv HTML。
- 作者：未在本次摘录中完整记录，登记表保留 arXiv 元数据。

### 它做了什么
把"诊断指标好不好"从"与平均表现相关"改成"能否保住下游**选择**"。具体构造是 **paired instruction dependence**：同一观测、只换目标，测演示者是否改变**第一个决策**。在 136 个独立种子的四足导航语料上，56 个开发 / 80 个留出。

### 关键结果（摘要原文数字）
- 审计可靠，且与下游 paired correctness 相关；
- 加入 correctness-aware 基线后降低 MAE；
- 但主要 proper-log-score 增量仅 **+0.059 nats，95% 语料 bootstrap CI [−0.027, 0.133]**；
- 预设的 top-20% 选择比较**未建立增量选择增益**；
- 探索性分解提示：把 both-correct 与 both-wrong 分开，比无符号 switch 统计更有留出增益。

### 为什么它决定 C1 的评估方式
这是对"做一个诊断/预测指标"最直接的方法学警告：**可靠 + 相关 ≠ 有决策价值**。C1 若只报告 b 与 Δsuccess 的相关系数，会落进同一陷阱。因此报告第 7.6 节把"选择效用（top-k 选择优于随机/按难度）"列为硬门槛。

## 引文审计（Semantic Scholar，2026-11-05）

| 种子 | 施引数 | 性质 |
|---|---:|---|
| 2510.02268 KYC | 28 | 约 24/28 为视角/相机鲁棒性变体，其余 4 篇为手眼标定、动作空间 grounding、分布偏移等（VersaCamVLA、Fisheye-VLA、RayViT、AxisGuide、Cross-View Action Consistency、Selective Cross-View Consistency、OC-VLA++、SeeR-VLA、CamVLA、GP^A 等） |
| 2512.02902 | 17 | 对齐/轻量适配类 |
| 2610.18843 LIBERO-RIG | 1 | SEAR（自演化 agentic robotics），与本问题无关 |
| 2609.27247 CMA | 1 | Artifact-to-Capability（能力形成诊断） |
| 2606.02277 RSB | 1 | From Association to Decision Value（即 2610.29646） |
| 2610.01626 | 0 | 尚无索引引用 |
| 2607.09825 More Structure | — | S2 持续 429；OpenAlex cited_by=0；Google Scholar 精确标题无 "Cited by" |

### 审计结论
1. **没有任何检索到的施引工作**研究"失败模式构成 → 表征收益"的预测关系。
2. KYC 的 28 篇施引是 A 类饱和的最强证据（不是"仍有挑战"，而是"每周新变体"）。
3. 由此发现的两篇新工作（2602.17659 CAG、2610.29646）分别削弱 C2 与提高 C1 的评估门槛。

## 仍未闭合
- More Structure 的 S2 施引列表（429），但三方证据（OpenAlex 0、Scholar 无 Cited by、论文发表仅数月）一致指向零引用。
- 该审计只覆盖 7 个种子，不是全领域引文图。
