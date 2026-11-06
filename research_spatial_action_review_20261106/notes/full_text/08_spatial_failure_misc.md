# 其它一手材料的阅读记录

## 2606.02277 RoboSemanticBench（RSB）
- 作者：Bin Yu 等 12 人；v1，2026-06-01；<https://arxiv.org/abs/2606.02277>
- 读取层级：Table 3 附近 + GSR/TSR 定义段
- 事实：QwenGR00T 在"抓取成功但任务失败"的案例中 95.92% 抓错目标；ReasoningVLA 的对比中，89.93% 是"正确 CoT、错误目标"，6.70% 是"错误 CoT、错误目标"（两者合计不是同一模型的不同分母，引用时须带模型名）。
- 意义：目标选择失败是真实且主导的行动失败，但它属于语义—空间指代，不是精度问题。该文是 benchmark，不提供修复机制。

## 2605.18746 ESI-Bench
- 作者：Yining Hong 等 8 人；v2，2026-05-25；<https://arxiv.org/abs/2605.18746>
- 读取层级：摘要 + 结果讨论段（line 476–477）+ 任务统计
- 事实：不完美 3D 重建可能比 2D 更差，几何伪影会扭曲细粒度空间关系；人类会主动寻找可证伪视角，模型过早高置信commit、重复同方向观察。
- 意义：空间信息不是单调有益；" epistemic calibration "是行动层失败（选视角/何时停止），但该文是 agentic VLM 设定，不是训练出的操作策略。

## 2609.37292 A-FAR / BAVO
- 作者：Kaijun Luo 等 6 人；v1，2026-09-29
- 读取层级：摘要 + 引言（上轮已读全文，本轮复核关键句）
- 事实：命名 acquisition–exploitation gap；移动相机下把观测表达在移动相机系会把平均成功率从 41.0% 打到 28.0%（上轮记录的原文位置，本轮未逐字复核该数字所在段落——标 PARTIAL）。

## 2602.12032 GAP (vision-proprioception)
- 作者：Jingxian Lu 等 5 人；v1，2026-02-12
- 读取层级：结果段
- 事实：Octo-VP 通常比 Octo-V 差；梯度调整后 Octo-VP† 平均 +17%，并强于 Octo-V。说明"多加一个空间通道"可能有害，融合方式才是变量。

## 2602.23408 Demystifying Action Space
- 作者：Yuchun Feng 等 8 人；v2，2026-04-23
- 读取层级：摘要 + 引言
- 事实：13,000+ 真机 rollouts、500+ 模型；结论 delta 表示一致更好，joint-space 偏控制稳定、task-space 偏泛化。动作空间轴已被大规模真机研究占据。

## 2609.28955 ActGaze
- 作者：Jinxuan Zhu 等 10 人；v1，2026-09-24
- 读取层级：方法段
- 事实：用反事实视觉干预测"哪些区域对动作预测重要"，再蒸馏成 gaze head；真实机器人四个高精度任务。即"用动作敏感性决定看哪里"已被做成方法。

## 2609.16815 Rethinking Visual Embodiment Dependence
- 作者：Hongjie Fang 等 11 人；v1，2026-09-15
- 读取层级：摘要
- 事实：构造 cue-conflict 观测，发现可见的机器人构型在特定状态会压过任务状态线索，驱动"按 embodiment 而非任务"的动作；提出 canonicalization + decorrelation。是"错误空间线索主导动作"的直接证据与修复。

## 2609.06114 Where Success Breaks (DLS)
- 作者：Yanzhe Chen 等 3 人；v3，2026-10-22
- 读取层级：摘要 + 引言
- 事实：把鲁棒适配表述为 failure-boundary learning；用特权仿真状态做 progress localization，directional boundary shaping；真机提升。是"闭环恢复训练"的强方法竞争者。

## 仅摘要级（存在性/竞争密度用，不引具体机制）
- 2610.12457 SpatialHarness：测试时用同步仿真渲染补充视角，plug insertion 26.7→66.7，Tower of Hanoi 0→100（摘要数字）。
- 2609.39145 Blackout vs Freeze：相机黑屏与冻结在相同低成功率下产生不同物理失败模式；proprioception 部分补偿；成功执行仍可能有非目标接触（摘要）。
- 2609.33707 View Collapse：对抗训练可让策略"少用"被扰动的视角而非更鲁棒地感知，称为 robustness shortcut（摘要）。
- 2605.19986 MetaFine：二元成功率可高估能力达 70%；用因果干预指出视觉编码器保留局部空间结构是细粒度精度瓶颈（摘要）。
- 2608.15938 Revisiting Open-Loop：长开环主要帮助短上下文策略模仿非马尔可夫演示；上下文足够长时最闭环的策略最好（摘要）。
- 2607.01804 VLA-Corrector / 2610.19765 RAIN：检测偏差并纠正 / 自适应细化动作 chunk（摘要）。
- 2608.27497 MAGP：相对几何的尺度任意性阻碍与真实尺度动作对齐（摘要）。
- 2610.13516 RESCUE：反事实评估 VLA 运行时监控告警是否值得行动（摘要）。
