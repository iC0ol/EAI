# 2510.02268 Do You Know Where Your Camera Is? (KYC)

- 作者：Tianchong Jiang 等 7 人
- 版本/日期：arXiv v1，2025-10-02；仓库称 ICRA 2026
- 来源：<https://arxiv.org/abs/2510.02268>；本地全文 `papers/2510.02268__kyc_camera_conditioning.txt`
- 读取层级：**Table I 全表 + §IV-C 消融 + 动作空间/裁剪段 + 真机任务定义**

## Table I（18 个模型×任务单元，逐格核对）

| 方法 | Lift | Pick Place Can | Assembly Square | Push | Lift Upright | Roll Ball |
|---|---|---|---|---|---|---|
| ACT | 33.6 | 26.7 | 10.8 | 29.9 | 22.9 | 28.7 |
| ACT + cond | 60.6 (+27.0) | 30.9 (+4.2) | 18.7 (+7.9) | 37.5 (+7.6) | 34.6 (+11.7) | 29.7 (+1.0) |
| DP | 29.1 | 23.1 | 2.0 | 20.0 | 9.5 | 19.9 |
| DP + cond | 51.1 (+22.0) | 39.3 (+16.2) | 2.4 (+0.4) | 30.3 (+10.3) | 20.7 (+11.2) | 23.7 (+3.8) |
| SmolVLA | 19.6 | 56.0 | 22.0 | 39.0 | 23.6 | 27.6 |
| SmolVLA + cond | 54.4 (+34.8) | 70.0 (+14.0) | 26.4 (+4.4) | 43.8 (+4.8) | 33.4 (+9.8) | 30.4 (+2.8) |

## 我的再分析

- 任务平均增益：Lift +27.9、Pick Place Can +11.5、Assembly Square +4.2、Push +7.6、Lift Upright +10.9、Roll Ball +2.5。
- 任务平均 baseline：27.4 / 35.3 / 11.6 / 29.6 / 18.7 / 25.4。
- headroom 零模型 Δ=α(1−b)：corr = −0.165，过原点 R² < 0。**"基线越低涨得越多"在 KYC 18 单元上不成立**：Assembly Square 基线最低 (11.6) 但增益倒数第二 (+4.2)；Lift 基线中等但增益最高。
- DP 在 Assembly Square 的基线 2.0% —— 这是"策略根本到不了精度阶段"的地板效应，不是 headroom 的线性版本。

## 被上轮忽略的廉价基线

- §IV-C3：随机裁剪（同时作用于图像与 Plücker map，保持一一对应）**在所有任务上提升成功率**；作者解释为"等效于增加不同参数的虚拟相机"。Fig. 8。
- 上轮用 KYC 的 +1.0…+27.0 作为"空间干预收益异质性"的核心证据，但没有把裁剪这条廉价基线纳入对照。任何"几何条件化/表征升级"的净收益都必须先减去裁剪可获得的收益。
- 动作空间消融（Fig. 7）：Delta EEF 最好，Absolute Joint / Absolute EEF 明显更差；且 camera conditioning 对四种动作空间都有效。

## 限制

- 仿真 6 任务 + 3 真机任务；每设置 1,500 rollouts（SmolVLA 500）；无失败分类；无误差测量。
- 任务间差异只用成功率表达；没有机制解释。
- 仓库 MIT、**无预训练权重**、`setup.sh` 下载数据、单 seed 训练 "hours to a day"、跨机器非 bitwise 一致。

## 可用事实

- SUPPORTED：同一相机条件化干预在 6 任务上增益 +1.0…+27.0 pp（ACT）/ +0.4…+22.0（DP）/ +2.8…+34.8（SmolVLA）。
- SUPPORTED：随机裁剪在所有任务上提升成功率（未与条件化交叉）。
- SUPPORTED（我的算术）：headroom 线性模型在这 18 单元上无解释力。
