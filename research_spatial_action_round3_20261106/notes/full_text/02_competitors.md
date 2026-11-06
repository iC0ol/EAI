# 最近邻竞争：逐篇核查

本轮只读与 A1 直接相关的 6 篇（另 4 篇上一轮已读）。层级：F=全文/关键章节；P=部分；A=摘要。

## 1. EGR 2609.03142 — Evidence-Gated Regularization

- 作者/版本：未核（v1，2026-09-02）；<https://arxiv.org/abs/2609.03142>；F（摘要、§1、§3.1–3.3）。
- 核心：VLA 多模态训练会产生 "modality entanglement"：对无信息传感器的扰动敏感（nuisance sensitivity），而单一信息模态不足时又不够用。
- 方法：per-frame、per-sensor **evidence score**（相机用目标可见面积/交互门控；触觉用接触模式）门控两个一致性目标：
  - 低 evidence → invariance（鼓励忽略）；
  - 高 evidence → single-sensor sufficiency（鼓励单独使用）。
- 与 A1 的关系：**这是"按任务相关性门控不变性 vs 敏感性"的直接实现**，只是门控信号是可见性/接触，不是几何余量。A1 的"margin-conditioned sensitivity shaping"若只换门控信号，就是 EGR 的变体。
- 证据：BEHAVIOR-1K 基准（47 skills）+ 两个真机平台；全模态 SR 12.5%→16.4%（+31%）（摘要）。
- 限制：模态级，不是状态级几何；没有测 R_π/P_c；没有精度分配。

## 2. APEX 2606.16504 — Adaptive Policy Execution

- 作者/版本：v1，2026-06-15；<https://arxiv.org/abs/2606.16504>；F（摘要、§1、方法概览）。
- 核心：策略输出的高层参考与低层控制器之间存在 **execution gap**；精度敏感任务受害最大。
- 方法：插在策略与控制器之间的 plug-and-play 适配器，重建动力学可行参考 + test-time 自适应项，有收敛保证；不改策略/控制器。
- 结果：示范回放 tracking error −41.2%；成功率 +4.8–25.8 pp；覆盖 ACT 等四类策略，PegInsertion 增益最大（摘要）。
- 与 A1 的关系：**直接占据"P_c（动作→执行）"这一因子**。若 A1 的失败被归因于执行传播，APEX 是强基线/替代方案；A1 必须证明剩余的是感知→动作响应，而不是执行间隙。
- 限制：不处理感知误差；需要低层状态反馈；对感知噪声无效。

## 3. Pix2Act 2607.11167 — 图像空间等变增广

- 作者/版本：v1，2026-07-13；<https://arxiv.org/abs/2607.11167>；A（摘要）。
- 核心：把 3D 动作表示为相机平面 2D 轨迹，用三角化恢复末端位姿；观测与动作同坐标，因此可对图像与图像空间动作做**联合等变变换**。
- 与 A1 的关系：**"等变增广"已被直接做**；A1 的 margin-aware equivariance 若只是给增广加权，会与 Pix2Act 正面竞争。
- 限制：摘要级，未核实其对精度阶段/容差的处理。

## 4. MixVLA 2610.02898 — 不变/非不变信息混合

- 作者/版本：v1，2026-10-02；<https://arxiv.org/abs/2610.02898>；A（摘要）。
- 核心：VLA 纠缠 task-relevant invariant structure 与 environment-specific non-invariant factors；AMI 随机混合非不变表示，保留不变表示。
- 与 A1 的关系：**"哪些信息该不变、哪些该保留"的另一条实现**；与 EGR 同属"信息不变性门控"家族。
- 限制：摘要级；面向 OOD 泛化，不是精度阶段。

## 5. View Collapse 2609.33707 — 视角依赖 vs 鲁棒感知

- 作者/版本：Futa Waseda, Shuhei Kurita, Isao Echizen；v1，2026-09-27；<https://arxiv.org/abs/2609.33707>；F（摘要、§1、§4）。
- 核心：对抗训练可让策略**减少使用**被扰动的视角，而不是更鲁棒地感知；称为 view collapse。
- 方法：blackout / graded blur 单视角干预，测 per-view reliance；View Swap 训练干预。
- 结果：直接 AT 改善 Camera Viewpoint/Sensor Noise，但造成 wrist-dominant reliance；View Swap 后 AT 进一步改善多轴（摘要/§4）。
- 与 A1 的关系：**"表面鲁棒性来自信息使用重分配"** 的直接证据；A1 测 R_π 时必须控制跨视角替代，否则会把"换视角"误读为"更敏感"。
- 限制：多视角 VLA；不测几何余量。

## 6. Blackout vs Freeze 2609.39145 — 物理失败模式

- 作者/版本：Heejae Suh 等 4 人；v1，2026-09-30；<https://arxiv.org/abs/2609.39145>；F（摘要、§1、指标段）。
- 核心：黑屏与冻结在同样低成功率下产生不同物理失败模式；冻结导致更极端关节行为，抓取闭合后黑屏导致更多掉落（无本体感觉时最明显）。
- 指标：success、NTC（非目标接触）、F5（>100 N 持续 5 步）、Drop、JVE、JLP；150 episodes/condition（LIBERO Spatial）+ 真机。
- 与 A1/B2 的关系：**"成功率掩盖物理副作用"已被系统做**；B2 的"空间改善导致另一阶段恶化"是它的一个更窄变体。
- 限制：相机故障，不是空间精度干预；VLA 级。

## 7. 上一轮已读、仍是最直接竞争的 4 篇

- **2610.01626**：动作误差闭环传播 λ；状态依赖；78% lift stamps 在 deadband；闭环稳定罕见。占据 `P_c` 的测量。
- **2607.09825 More Structure**：Near-Miss 31%→2.5%，No-Grasp 15/15/24；目标锚点干预。占据阶段失败分类与"精度型失败"。
- **2610.18843 LIBERO-RIG**：rig 扰动轴 + per-axis tolerance（rig 容限，不是任务 τ）；本体感觉噪声无影响。占据"硬件扰动鲁棒性"与"state 被忽略"。
- **2609.12641 LIT**：捷径接口；逐扰动增益；真实机器人三轴 +16.7/+16.7/+13.3。占据"通用 vs 定向干预"。

## 8. 竞争结论

| A1 的组成部分 | 已被谁占据 | 剩余空间 |
|---|---|---|
| 几何余量 c(x) | MetaFine（2 cm/4°/3 mm）、任务几何 | 仅剩"按状态连续读出 + 与策略响应结合" |
| 策略响应 R_π | EGR、ActGaze、View Collapse、GAP | 剩"margin-conditioned"这一门控信号 |
| 传播 P_c | 2610.01626、APEX、经典误差传播 | 剩"与感知误差连接" |
| 预测收益 | 无直接同构（有界否定） | 测量型贡献 |
| 分配方法 | RAIN、VLA-Corrector、FoveaVLA、ActGaze、EGR | 饱和 |

**判断**：A1 的每个部件都有强竞争；唯一没有被直接做的是"三者乘积 → 干预收益"的定量预测。这是测量/机制贡献，不是方法机制。
