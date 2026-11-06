# 2610.01626 Measuring the Stability Assumption Behind Action Chunking

- 作者：Aryan Goyal（单作者）
- 版本/日期：arXiv v1，2026-10-01
- 来源：<https://arxiv.org/abs/2610.01626>；本地全文 `papers/2610.01626__action_chunking_stability.txt`
- 读取层级：**摘要 + §1 + §4.1–4.3 + 结论**（未逐格读附录建模细节）

## 方法

在每个状态注入一个小动作误差，测其随后的增长率 λ：
- 开环：chunk 剩余部分不重规划直接回放；
- 闭环：扰动后策略重新规划。

用对数偏差拟合 λ；用放大阈值与不确定度门控把状态分为 contracting / expanding / unresolved（deadband）。

## 关键数字

- robomimic 中位传播率：can 0.009 → lift 0.015 → square 0.017 → tool hang 0.026；作者说这与"接触敏感、精度要求高"的趋势一致，但明确"这些中位数不证明任务难度导致增大"。
- lift 的 2,485 个演示 stamp 中只有 543 个通过 Gate 1；78% 的 |λ| < 0.0289（即大部分状态处于 deadband）。
- 闭环稳定标签比被动收缩更罕见；m=2 时每任务 stable 类仅 3–88 个 stamp。
- 结论句：既不被动开环、也不重规划能可靠收缩注入误差；重规划很少把开环放大转为可信收缩。

## 为什么对本复审重要

1. 这是目前最直接的"空间/动作误差在闭环中是否被吸收"的定量测量；λ 随任务与状态变化，支持"同一误差在不同任务/阶段有不同行动后果"。
2. 但它测的是**动作误差**的传播，不是**空间估计误差**（目标位姿/深度/外参）到任务误差的传播。两者之间隔着感知→动作映射。
3. 作者建议显式训练闭环反应性（perturbation- and tree-coverage-oriented training）。这不是空白：DLS（2609.06114）已做 failure-boundary learning，DAgger/DART 是经典强基线。

## 限制

- 大量状态落在 deadband，λ 的可分辨性有限；用不同拟合窗会改变结论（作者自述前载放大）。
- 单作者、arXiv 预印本；未见公开代码入口。
- 任务为 robomimic/MimicGen/RoboCasa 的演示与 rollout；不是 VLA。

## 可用事实

- SUPPORTED：λ 中位数随任务从 0.009 到 0.026；大多数状态不可分辨；闭环稳定罕见。
- HYPOTHESIS：λ 可作为"空间精度是否值得提升"的中介量——**该文未检验**。
