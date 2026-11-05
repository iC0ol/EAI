# 2510.02268 — Do You Know Where Your Camera Is? View-Invariant Policy Learning with Camera Conditioning

- 作者：Tianchong Jiang, Jingtian Ji, Xiangshan Tan, Jiading Fang, Anand Bhattad, Vitor Guizilini, Matthew R. Walter（TTIC / Waymo / JHU / TRI）
- 状态：arXiv 2025-10-02；官方仓库 README 注明 **ICRA 2026**，并称获 Best Paper Award on Robot Learning。
- 读取层级：FULL_TEXT（PDF 提取，`papers/2510.02268__kyc_camera_conditioning.pdf`）
- 代码/权重/数据：<https://github.com/ripl/CamPoseOpensource>，MIT；`setup.sh` 下载数据；`reproduce/paper_runs.yaml` 按图编号复现；**仓库内未见预训练权重**。

## 方法（§III）

用逐像素 Plücker 射线图表征相机内参与外参，与 RGB 在通道维度拼接（late fusion），条件化 ACT / Diffusion Policy / SmolVLA。数据按“stair”方式采集：每条演示用 n 个相机，相邻演示共享 n−m 个位姿，逐步引入新位姿。

## 关键证据

| 位置 | 内容 | 对本题的意义 |
|---|---|---|
| Table I | 六个任务为 Lift / PickPlaceCan / AssemblySquare（RoboSuite）+ Push / LiftUpright / RollBall（ManiSkill）。ACT：33.6 / 26.7 / 10.8 / 29.9 / 22.9 / 28.7；加条件化后 60.6 / 30.9 / 18.7 / 37.5 / 34.6 / 29.7 | 增益 **+27.0 / +4.2 / +7.9 / +7.6 / +11.7 / +1.0 pp**，任务间差异极大 |
| Table I | DP：29.1→51.1 (Lift)，2.0→2.4 (AssemblySquare) | 最难的精确任务上，条件化几乎无效（+0.4 pp） |
| §IV-A.2, Fig. 6 | fixed vs randomized 背景；fixed 场景中无外参策略靠静态背景推断相机位姿 | 说明“空间捷径”确实存在，且是任务/场景依赖的 |
| §IV-A.4 | delta EEF 动作空间最好；绝对关节/绝对 EEF 明显更差；四种动作空间下条件化都有增益 | 与 2610.38104 的警告一致：动作空间是一阶变量 |
| §IV-A.5, Fig. 9 | linear projection 编码无收益；early fusion 多数不如 late fusion | “加一个位姿 token”这类最简单实现并不奏效 |
| §IV-A.7, Fig. 11 | 达到同等性能，无外参条件化需要多数倍相机 | 数据侧替代方案存在 |
| §IV-B, Fig. 13 | 真机 UR5，每设置 21 rollouts，自定义 half-success | 真机证据量很小；half-success 降低了对失败的区分度 |

## 作者未声称、但证据支持的推断

1. **“跨视角不一致”不是单一现象，而是任务/场景依赖的**：增益从 +27.0（Lift）到 +1.0（RollBall）不等。**注意方向与朴素预期相反**——按常识 Lift 是宽容差任务、AssemblySquare 是紧容差任务，但 Lift 增益最大、AssemblySquare 仅 +7.9；这提示"基线是否依赖背景捷径"是更强的解释，也是报告候选 C1 从"容差"改写为"失败模式构成 + 有效误差下降 + 捷径依赖"的直接起因。
2. 论文把失败归因于“策略用背景推断相机位姿”，但没有做误差分解（位姿估计误差 → 末端误差 → 成功/失败），也没有给出每任务的容差阈值。

## 局限（论文未设 Limitations 节，由审稿视角补充）

- 绝对成功率偏低，尤其精确任务；因此“条件化有效”是在弱基线上的相对提升。
- 真机仅 21 rollouts/设置，无置信区间。
- 只验证了 ACT/DP/SmolVLA 三家，且需自训练；仓库不提供权重。

## 对用户 F 经历的直接解释

用户自训练的 KYC-ACT checkpoint 在准确外参下 0/32。用论文 Table I 的 ACT 基线做参照：Lift 33.6%、PickPlaceCan 26.7%、AssemblySquare 10.8%。若真实成功率是 26.7%，P(0/32) = 0.733^32 ≈ 5×10⁻⁵；即便按最难的 10.8% 计算也约 2.6%。因此 **0/32 不能用“任务本来就难”解释**，更可能来自训练/评测链路问题（或用户所用任务与论文任务并不对应）。

**结论**：该 checkpoint 不能作为“科学假设被否定”的证据，也不能作为可信基线——这与用户的判断一致，且现在有可引用的量化依据。附带的方法学教训：论文不发布权重时，复现实验必须先把“基线达到论文量级”作为独立的准入检查，而不是与主实验同时进行。
