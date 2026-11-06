# 2610.18843 LIBERO-RIG

- 作者：Andrea Yaoyun Cui 等 9 人
- 版本/日期：arXiv v1，2026-10-13
- 来源：<https://arxiv.org/abs/2610.18843>；本地全文 `papers/2610.18843__libero_rig.txt`
- 读取层级：**正文 + Table 1/2/3/5 + Appendix B/D/G + Limitations**（未逐格读全部 12 张结果表）

## 设计

- 11 条"硬件/装配"扰动轴，每条 5 个严重度；4 个 LIBERO suite；9 个 VLA 模型；每条件 500 episodes；共 881,500 episodes（§1）。
- 只扰动 rig，任务、初始状态、成功判据不变；策略不获得故障元数据。
- 扰动分可观察（相机安装/光学/腕部相机）、潜在（动作帧旋转、执行增益、控制频率、本体感觉噪声）、弱可观察（夹爪垫）。
- Pooled success：0.932（nominal）→ 0.767（s3）→ 0.509（s5）。

## Table 5 到底是什么（关键校正）

- 标题："Tolerance per axis. The harshest severity level each model passes before its first failure on the axis."
- 两个判据：绝对成功率 ≥0.80，或 ≥0.90 × 该模型自身 nominal。
- 原文明确："Levels are set per axis, so the table compares models within an axis, not axes with one another."（Table 5 caption）
- 因此它是**模型对硬件扰动幅度的容限**（degrees / cm / % gain / Hz），**不是任务对末端空间误差的几何容差 τ（mm/deg）**。上轮把它当作"任务容差已被操作化"的证据，属构念错位。

## 与"空间信息是否被使用"直接相关的两处

1. **本体感觉噪声无代价**：报告给策略的 arm pose 加噪（2–50 mm, 0.5–8°）后 pooled success 0.931 vs nominal 0.932；把同样的噪声注入控制器自身状态估计则在 2 cm 时把 0.960 打到 0.470（§3 / Appendix G）。作者解释为策略主要靠视觉定位手臂。这是"可用空间状态未被用于纠错"的直接行动层证据。
2. **动作接口 × 故障的关联**：X-VLA 输出绝对位姿，对 action-frame rotation / gain error 几乎不退化（0.968 vs 0.976 nominal），作者假设绝对目标每步收缩误差、delta 策略会累积；但同段明确写 "Training data and chunk length differ too, so this is an association rather than a controlled comparison."（Appendix D）

## 限制（作者自述 + 我的补充）

- 作者：仅仿真、单一 embodiment、每次只扰动一个轴、success 为原始率、每 suite 仅 10 任务。
- 我的补充：success-only 指标看不到"成功但发生非目标接触/扰动"（该现象由 2609.39145 在相机故障下报告）；"tolerance" 的轴间不可比使跨轴统一模型不成立。
- 资产：正文称 "release the benchmark together with manifests specifying the fixed perturbation parameters"（§1、Conclusion），但 arXiv abs 页、正文均无 URL；GitHub 未能定位 → **PARTIAL**。

## 可用事实

- SUPPORTED：rig 扰动可造成大幅成功率下降，且轴间差异巨大（s3 轴均值 0.448–0.931）。
- SUPPORTED：报告的 arm pose 被加噪几乎不影响成功率；控制器状态估计被加噪则大幅影响。
- SUPPORTED（作者自述）：绝对 vs delta 的差异是关联而非受控比较。
- CONTRADICTED（对上轮）："LIBERO-RIG 已操作化任务容差 τ"。
