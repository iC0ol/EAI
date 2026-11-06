# 2607.09825 More Structure, Not More Capacity

- 作者：Yi Li, Alexandre Chapin, Liming Chen, Jan Peters, Alap Kshirsagar
- 版本/日期：arXiv v1，2026-07-10
- 来源：<https://arxiv.org/abs/2607.09825>；本地全文 `papers/2607.09825__more_structure_not_more_capacity.txt`
- 读取层级：**全文**（含 Table I/II、Fig. 4/5、§V-D/E、§VI 限制）

## 设计与数字（逐处核对）

- 平台：ManiSkill3 PickCube-v1，Franka；冻结 SPOT（DINO ViT-B/16 + Slot Attention），11 GB VRAM；1,000 专家演示；训练 seed 0–9,999，评估 seed ≥10,000；3×300 episodes。
- Table I：DINO Global 32.6±1.5；DINO 4×4 31.7±3.0；SPOT 55.0±2.9；Pure visual 31.0±2.8；+2D goal（近似标定）55.0±2.9；+2D goal（精确标定）58.7±3.4；+224² 68.7±4.2；3D Oracle 71.7±4.1。
- §V-D：Near-Miss 随目标条件 31% → 21% → 2.5%；No-Grasp 为 **15、15、24**（每 200 集）。
- §V-E：StackCube-v1 5.3±2.2% SR；No-Grasp 144/200 = 72%；作者归因于手臂自遮挡 + SPOT 无时序记忆。
- §VI 限制：融合对比只在无 goal token 下做；表示对比用近似标定；SPOT 无时序槽记忆。

## 对上轮使用的关键校正

1. **该文有两种干预，上轮混用了它们**。表示对比（SPOT 55.0 vs DINO 32.6）确实是表征干预，但失败分类**没有**跨表示报告；"Near-Miss 31%→2.5%"来自**目标条件**消融（pure visual → 2D goal → 3D oracle）。2D goal 与 3D oracle 都使用仿真器的**真值目标位置**，二者只差"像素 vs 世界坐标"的表示；作者明说 "differ only in how the goal is represented, not in the information they assume"（§III-B）。因此这条失败机制证据证明的是**显式目标锚点的信息价值**，不是几何精度或表征容量的价值。
2. **No-Grasp 并非"完全不变"**：15 → 24（+60%）。原文措辞是 "are not reduced"，不是"不变"。上轮报告写"完全不变"是事实错误；而且 24 的增加本身是一个未解释的行为副作用，与"干预只修对应失败模式"的分诊模型相冲突。
3. 失败分类来自**单独一次 200 集运行**，不是 3×300 的稳定性运行；比较不同 SR 条件下的失败计数时，分母虽同为 200，但进入抓取阶段的机会不同，计数差异的解释需要谨慎。
4. StackCube 的"需要时序一致性而非空间 grounding"是作者**推断**，未在该任务上做目标条件干预对照。

## 可用于本报告的事实

- SUPPORTED：显式目标锚点把 Near-Miss 从 31% 降到 2.5%（单任务、单次 200 集）。
- SUPPORTED：同一分类法下 No-Grasp 计数从 15 升到 24。
- CONTRADICTED（对上轮）："No-Grasp 完全不变"。
- UNKNOWN：若换成"提高观测几何精度"而非"给真值目标"，失败构成会如何变化——该文没有这个自变量。
