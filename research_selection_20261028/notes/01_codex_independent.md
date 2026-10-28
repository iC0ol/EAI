# Codex 候选阶段独立初筛（交换前冻结）

日期：2026-10-28。共享历史背景，因此不是完全盲审。此文件形成时尚未阅读 DeepSeek 初筛结论。以下仅是待粗筛的三个具体问题，不是推荐论文题目；尚未完成全文/源码审核。

## C1：动作分块聚合是否把多峰有效动作混成不可行动作

- **来源事实**：BID（ICLR 2025）Fig.1、§3/4 已直接讨论长块反应迟缓与短步重规划多峰抖动，利用 backward coherence + forward contrast 选样。MedianTE（Jiang，2026-09 预印本）§V 已以无需训练的逐坐标中位数替代均值，并给出干净条件收益不一致、共模扰动盲区。Mazza 等（2026-05 预印本）研究 CVAE 模态坍缩与生成 transport 的桥质量/敏感度。
- 问题范围：已有多峰操作策略的重叠 chunk，在相同观测、模型和查询预算下，聚合后动作是否脱离有效模态并降低完整任务成功率。
- **假设**：从已有完整候选向量选出中位代表而非逐坐标拼接，可能避免跨模态混合；其价值很可能被 BID、TAS 或简单 medoid 覆盖。
- 最强简单对照：官方执行；最新 chunk；逐坐标 median；已有 medoid/nearest-candidate。禁止把改变 query/stride 得到的收益归于聚合器。
- **未知**：自然干净失败率、已有方法剩余缺陷、官方权重、可复现实验入口。需要比数学反例更强的自然任务证据。
- 首次证据与终止：先源码/公开数据检查动作索引与归一化；若只是 temporal ensemble 权重顺序等实现错误，或现有简单方法足够，则停止新方法方向。
- 直接近邻：[BID](https://openreview.net/forum?id=qZmn2hkuzw)、[MedianTE](https://arxiv.org/abs/2609.27167)、[Multimodal Failure](https://arxiv.org/abs/2605.22493)。额外竞争：[Implicit ensembling](https://arxiv.org/abs/2608.02547)。

## C2：整轨迹质量筛选是否压低局部关键动作片段的训练覆盖

- **来源事实**：DemInf（Hejna 等，2025）§V-C 对逐状态—动作 chunk 的 MI 分数按时间平均后过滤整轨迹。DataMIL（Dass 等，ICLR 2026）直接用任务成功的代理损失驱动数据选择。IWR（Xie 等，CoRL 2025）说明近邻距离检索忽视 prior 分布并给出密度比加权。
- 问题范围：小规模多操作者示范、固定总采样/更新预算下，轨迹平均过滤是否丢失只在少数阶段出现但任务必需的状态—动作覆盖。
- **假设**：按合法观测定义的阶段或动作事件做覆盖约束，可能减少整轨迹过滤的局部信息损失。但尚未发现独立任务结果直接证明此细分缺陷，不把“平均可能掩盖局部”当已有缺陷。
- 最强简单对照：全部数据、均匀等量抽样、episode 平衡、低成本事件分层、DemInf、IWR/DataMIL（依其输入权限判断是否同问题）。训练更新、重复采样、模型容量必须匹配。
- **未知**：三篇并非完全相同设定；DataMIL 的 co-training 与单任务 mixed-quality 过滤有差别。局部质量评分是否真的改变梯度及成功率、公开逐样本得分和训练成本待核。
- 首次证据与终止：优先读官方代码和已公开评分；如果只能构造人为污染才能显示差异，或简单等量/阶段分层已解释收益，则不进入新方法研发。
- 近邻：[DemInf](https://arxiv.org/abs/2502.08623)、[DataMIL](https://proceedings.iclr.cc/paper_files/paper/2026/hash/033d9e8dbbbc0ad90e59222cf1db0fc2-Abstract-Conference.html)、[IWR](https://arxiv.org/abs/2509.01657)。

## C3：本体状态分布偏移下的模态依赖与最小训练正则

- **来源事实**：Adapt Your Body（Kuang 等，2025）报告直接加入全部本体状态可降低性能，提出利用部署 rollout 的 Wasserstein 噪声适应。Fighting Copycat（Wen 等，2020）已讨论历史行为相关导致的动作复制。NOSTRA（Saxena 等，项目页称 RA-L 2026）以分模态 latent/history imagination 应对不可靠传感器。
- 问题范围：视觉+本体状态模仿策略，训练/部署本体分布不同而视觉仍可用时，额外状态是否诱发不适当依赖及任务退化。
- **假设**：训练期预算受限的状态组正则或条件扰动可能用更少额外 rollout 保留有用状态，同时减少不适当依赖；但“加 dropout/noise”本身没有新颖性，且不能擅自删除部署信息又称公平改善。
- 最强简单对照：不用本体状态、固定噪声、mask/dropout、Adapt Your Body、同样部署数据的适应。需要对正常条件损失和异常条件收益同时报告。
- **未知**：实际可用 checkpoint、自然 shift 是否可复现、直接竞争的后续改进；当前只是已知缺陷的可能低成本验证入口。
- 首次证据与终止：先查官方实现/附录的观测和动作定义、shift 生成及基线。若已有方法同资源解决，或所谓 shift 实为动作单位/输入预处理错误，则停止。
- 近邻：[Adapt Your Body](https://arxiv.org/abs/2506.23944)、[Fighting Copycat](https://arxiv.org/abs/2010.14876)、[NOSTRA 官方项目](https://vsaxena.com/nostra/)。这三者机制相关但不完全同设置，后续必须细分，不得以数量代替直接竞争。

## 暂定优先级

尚不选首选。C1自然失败与机制定位较清楚，但2026直接覆盖强；C2初始细分缺陷证据薄弱；C3需核验 assets 和2026竞争。不以已投入旧工程降低门槛。所有候选实验均 NOT_RUN。
