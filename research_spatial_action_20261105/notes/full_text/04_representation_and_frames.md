# 表征与坐标框架：2607.09825 / 2607.11498 / 2609.32762 / 2607.05396 / 2610.24674

## 2607.09825 More Structure, Not More Capacity（FULL_TEXT）

- 作者：Yi Li, Alexandre Chapin, Liming Chen, Jan Peters, Alap Kshirsagar（TU Darmstadt / Centrale Lyon / IIT Delhi-Abu Dhabi）
- 证据：Abstract；贡献列表；ManiSkill3 PickCube-v1。
- 数字：冻结编码器下，SPOT 物体槽表示 **55.0±2.9%** vs 稠密 DINO 全局特征 **32.6±1.5%**（+22.4%）；加显式 2D 空间目标 + 原分辨率渲染 → **68.7±4.2%**，接近特权 3D oracle 上界 **71.7±4.1%**。
- 关键方法学：自动运动学失败分类，把 Near-Miss（空间精度）与 No-Grasp（物体跟踪）分开；空间 grounding 降低 Near-Miss，**不改变 No-Grasp**。
- 对 C1 的价值：这是最接近“oracle 上界 + 失败模式归因”的小规模范本；也说明**距离 oracle 只差 3 pp** 时，继续提升表征的边际收益可能已饱和——正是“容差/饱和”问题。
- 局限：单任务（PickCube-v1）、单策略、无真机。

## 2607.11498 See like a Robot（FULL_TEXT）

- 作者：Byungkun Lee, Dongyoon Hwang, Dongjin Kim, Hojoon Lee, Hyunseung Kim, Jaegul Choo, Minho Park（KAIST / Holiday Robotics / KRAFTON）
- 证据：Abstract；§I。
- 方法：depth → pointmap → 变换到“末端执行器原点 + 基座对齐轴”的机器人中心系；pointmap 特征加到对应 RGB token，不增加 token 数。
- 数字：24 个 RoboCasa 任务平均 +6.4 pp（vs RGB-only π0.5），4 个真机任务 **+32.5 pp**；比 PointVLA 高 3.5 / 23.7 pp。
- 含义：坐标框架选择本身就能带来两位数提升；相机系 vs 基座系 vs 末端系的差异是可测的。**这使“跨坐标系不一致”作为科学问题基本失效**——它是工程选择问题，已有明确答案。

## 2609.32762 What Matters for Viewpoint-Generalizable Policies（FULL_TEXT）

- 作者：Mino Nakura, Sriram Krishna, Yufei Wang, Shubham Tulsiani, Zackory Erickson, David Held（CMU）
- 方法：GP^A，作者明说“**deliberately not a new architecture**”；三个已知成分：保留稠密视觉 token、几何基础模型骨干、把视觉/本体/动作全部用旋转位置编码落到机器人坐标系。
- 结论：在随机相机下优于 2D 与 3D 替代方案，接近固定相机性能；sim→real 零样本迁移。
- 含义：跨视角泛化的“配方”已被拆解并公开；新模块很难主张独立科学贡献。

## 2607.05396 CamVLA（FULL_TEXT）

- 预测“相机系末端动作 + 6-DoF 手眼矩阵”，确定性复合为基座系动作；calibration-free、depth-free、单目。
- 含义：连“外参从哪来”都被绕开了；以“外参误差”为核心的方法必须解释为何优于“根本不需要外参”。

## 2610.24674 NISE（FULL_TEXT）

- 证据：Abstract；Fig. 4（真机，每任务每方法 N=30）。
- 现象：**depth-noise cliff**——即便用匹配的噪声深度训练，3D 策略仍在真实深度损坏下骤降。
- 方法：几何跨视角自监督 + 高斯边缘化 3D 注意力，把位置不确定性带入注意力。
- 残留失败：多视角一致的“错误表面”（透明物体）无法修复。
- 含义：几何表征不是免费的；其可靠性本身是一个可研究的量。与 C1 的“有效空间误差”概念直接相关。

## 2512.02902 VLA Models Are More Generalizable Than You Think（全文，第二轮补读）

- 主张：VLA 在novel viewpoint 下的脆弱性主要来自 **Spatial Modeling 的错位**，而非 Physical Modeling。
- 数字：Feature Token Modulation（**仅 4K 参数**）把 LIBERO viewpoint 成功率从 **48.5% → 87.1%**；Feature Linear Adaptation（4.7M 参数）到 **90.8%**，超过 π0.5 LoRA（467M 参数）。
- 含义（对本题极重要）：
  1. 若 4K 参数的全局仿射变换就能恢复大部分跨视角性能，那么“空间表征缺失”更可能是**对齐问题**而非信息缺失；
  2. 任何以“更强的空间表征”为卖点的工作，都必须先排除“只需一个轻量对齐/调制”的解释；
  3. 这也解释了为什么不同论文的“空间模块”收益差异巨大——它们可能在不同程度上做了同一件对齐的事。

## 综合

| 主张 | 状态 | 直接来源 |
|---|---|---|
| 相机系表达导致跨视角不一致 | 已解决（用机器人/基座系或末端系） | 2607.11498、2609.32762、2510.02268 |
| 需要显式外参 | 已被绕开（可预测/可无参） | 2607.05396 |
| 稠密 token 优于池化 | 已解决 | 2609.32762、2607.09825 |
| 3D 表征总是更好 | **被反驳**：损坏深度下可能更差 | 2610.24674、2605.18746（imperfect 3D worse than 2D） |
| 表征提升的收益是否可预测 | 未解决 | 各文增益差异 1–32 pp，无统一解释 |
| “空间表征不足”是否只是对齐问题 | **部分被证实**：4K 参数即可 48.5→87.1 | 2512.02902 |
