# 2610.12696 Spa-Bench 与 2606.02277 RoboSemanticBench — “行动层诊断”的两条范式

## 2610.12696 Spa-Bench（FULL_TEXT）

- 作者：Justin Tien-Smith, Matthew Pidden, Rolandos Alexandros Potamias（Imperial College London）
- 状态：arXiv 2026-10-08；会议/期刊未核实。
- 证据位置：Abstract；§VII Limitations；Fig. 11；§VI Discussion。

### 设计
SO-101 真机，6 个桌面任务（Object State / Relative Size / Referential Description / Relational Placement / Ordinal Position / Counting），4,092 episodes（1,200 遥操作 + 2,892 评测 rollout，覆盖 π0.5、MolmoAct2、GR00T-N1.7、VLA-0）。

核心是**配对场景设计**：同一个物理场景、同一个所需动作，只把“直接指令”换成“OOD 空间指令”。这样可把“空间 grounding 失败”与“根本不会做这个动作”分开。

### 关键数字
- ID 空间配置 67.5–73.3% → OOD 40.7–52.0%（三个完整评测的策略）。
- 配对直接指令相对空间指令提升 **28.3–40.0 pp**。
- 失败模式分解（Fig. 11）：No Action、Wrong Object、Grasp Failure、Control Drift、Same-category wrong instance、Incorrect Spatial Outcome、Unable to Release、Premature Release/Drop、Timeout。

### 结论与限制
作者结论：成功操作不等于空间理解；空间 grounding 不是单一标量能力，不同任务暴露不同瓶颈（是否行动、选哪个目标、能否实现关系）。限制：单一 embodiment、≤5 个物体、reset 非像素级一致、no-action 条件是 zero-shot、词表有限、模型特定的预处理使结果描述的是“完整策略系统”而非架构组件。

### 对选题的含义
- 想做“空间 grounding benchmark”的小论文 → **已被直接占据**（且同类还有 BEHAVIOR-Spatial、ESPIRE、ESI-Bench）。
- 但它没有回答：**为什么同一个策略在 Count 上全败、在 Relational Placement 上部分成功**？也没有把失败与空间误差的量级联系起来。这是候选 C1 的切口。

## 2606.02277 RoboSemanticBench（FULL_TEXT）

- 作者：Bin Yu, Yao Zhang, Haishan Liu, Shijie Lian 等（HIT / ZGCA / WHU 等）
- 状态：arXiv 2026-06-01，标注 “Work in progress”。
- 证据位置：Abstract；§6 Table 5；§7 Discussion；§8 Conclusion。
- 代码：<https://github.com/ZGC-EmbodyAI/RoboSemanticBench>（README 存在；权重/数据未核实）。

### 设计
把选择题（数学/常识）变成“抓取正确选项方块”。用 GSR（Grasp Success Rate）与 TSR（Target Selection Rate）分解，得到 nSG 分数，控制“会抓但选错”。

### 关键数字
- QwenGR00T 在“抓取成功但任务失败”的案例中，**95.92%** 是选错目标。
- ReasoningVLA 只有 **6.70%** 的此类失败伴随错误 CoT——即大多数失败是“想对了但抓错了”。

### 含义
这是“知道—做到”缺口在空间/语义目标选择上的最干净证据之一。它同时说明：**仅提升语言/语义推理不会自动改变动作**。任何新方法的卖点必须落在“动作路径是否跟随决策”。

### 与候选的关系
- 若做“空间推理→行动”的方法，RSB 是必须对比的诊断协议（GSR/TSR 分解）。
- 但它只测“选哪个方块”，不测几何精度（抓哪里、放多准），因此不与 C1 的容差问题重叠。
