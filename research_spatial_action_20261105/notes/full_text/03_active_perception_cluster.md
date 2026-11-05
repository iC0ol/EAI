# 主动观察（D 类）关键证据：2609.37292 / 2610.23891 / 2609.24124 / 2610.23378 / 2603.12193

## 2609.37292 Recovering the View（FULL_TEXT）

- 作者：Kaijun Luo, Yudi Huang, Qijun Zhong, Xinshuai Song, Yang Liu, Liang Lin（中山大学 / 电子科大 / 鹏城 / X-Era）
- 证据位置：Abstract；§4 “acquisition–exploitation gap”；Table 2（SR/CVG）；§5.4 消融；§5.5 真机。

### 设计
BAVO-Bench：双臂主动视觉基准，三种条件 Clean / Stage Occlusion / Random-time Occlusion；A-FAR 用“机器人中心 3D 坐标 + 4D 关系蒸馏”联合视角与操作。

### 关键数字与结论
- 视角稳定化是前提：把观测表达在移动相机坐标系，平均 SR 从 41.0% 掉到 28.0%（ManiFlow），从 44.7% 掉到 27.0%（A-FAR）。**没有共享基座标系，A-FAR 的优势消失。**
- “可见性恢复 ≠ 任务成功”：π0.5 的 CVG 高但 Random-time SR 低，作者称之为 acquisition–exploitation gap。
- A-FAR 平均 Joint score 5.78，ManiFlow 4.42，ACT 2.97，π0.5 1.41。

### 对选题的含义
- “让机器人多看一眼”本身不是贡献；“看到之后有没有用上”才是，而且已被明确命名。
- 但它只在一个双臂平台、5 个任务上给出该现象，没有给出通用的“证据使用”度量或修复机制。

## 2610.23891 When to Make a Decision（FULL_TEXT，无实验）

- 作者：Mariana da Silva Barros, Matthias Kerzel, Cornelius Weber, Stefan Wermter（Hamburg）
- 这是**立场/架构提案**：object-centric belief state + 符号决策层，判断“剩余不确定性是否值得继续采集”。全文没有结果，评估全部用将来时。
- 价值：证明“证据何时足够”被公认为开放问题；不能作为任何经验结论的依据。

## 2609.24124 ActiveArena（FULL_TEXT）

- 证据位置：Abstract；Table 8；Table 9；§4.3。
- 35 任务、5 类，强调多轮证据获取 + 记忆。
- 关键数字：本体感觉输入使 ID 50.86→62.97、OOD 16.86→47.60；动作头 OFT/GR00T/FAST = 62.97/40.00/22.34。
- 结论：均匀时间采样比事件触发写入更 OOD 稳健；记忆更大不一定更好；显式 planner 管理记忆可用稀疏记忆接近最佳。
- 含义：**动作头与状态输入的效应量大于多数“空间模块”**，任何方法论文必须固定这些变量。

## 2610.23378 Look Before You Act / 2603.12193 SaPaVe（FULL_TEXT，略读）

- 两者都把主动观察接入 VLA：前者用 observation-aligned data adaptation，后者把主动感知与操作联合建模。
- 与 2601.08325 ActiveVLA、2609.18514 ActiveScale、2602.04600 Act, Sense, Act、2506.15666 Vision in Action 构成一个至少 8 篇的 2026 集群。
- 判断：**“给 VLA 加主动观察”作为方法贡献已被占满**；剩余空间只在“证据是否被使用”的机制层，而该层已有 A-FAR 与 2609.22299。

## 综合判断（D 类）

| 问题 | 已解决程度 | 证据 |
|---|---|---|
| 机器人能否学会移动视角获取被遮挡信息 | 部分解决（多个 2026 系统可做到） | 2609.37292、2601.08325、2603.12193、2609.18514 |
| 如何评测主动观察 | 已解决（基准饱和） | 2609.37292 BAVO、2609.24124 ActiveArena、2609.18514 |
| 获取到的证据是否改变决策 | **未解决，且已有多处反证** | 2609.37292（acquisition–exploitation gap）、2609.22299（trace informative but unused）、2609.27247（memory changes action but not choice） |
| 如何修复“用不上” | 证据不足；已有局部方案（4D 先验、运行时一致性、梯度调制）但无通用机制 | 2609.37292、2607.29169、2602.12032 |
