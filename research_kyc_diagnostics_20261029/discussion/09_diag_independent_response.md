先读新任务书与当前冻结产物，再独立核对官方训练/评估路径；不沿用旧讨论结论。

# KYC 0/32 独立审查（DeepSeek）

**边界**：只读审查；未运行模型/仿真，未改文件。下列判断基于当前 `research_expansion_20261029` 文件与固定官方源码，不沿用旧讨论结论。

## 1. 事实与差异分开

已确认事实：C 完成 20,001 epochs / 60,003 updates（seed0，约4.57h）；最终 checkpoint 固定；10/10 专家回放成功；准确外参、**新 test camera pool** 的 dev 为 0/32，0 reach、0 grasp；正式 350 rollouts、persistent/IID、moved-stale 全部 **NOT_RUN**。`loss` 8.78→0.39、val 0.331，只证明拟合训练目标，不证明部署能力。

已确认实现差异（不等于根因）：
- 自定义可恢复 sampler 的 RNG 流与官方 DataLoader 不同（`run_experiment.py:12-24`；`frozen_training_plan.json`）。
- 训练内官方 test rollout 被关闭；官方 `train.py:120-144` 每1000 epochs 用同一 env 评估50条，会改变 env reset/RNG。
- val 相机改为 train pool（`C_config.json:9-13`）；官方 val 用 test camera（`kyc_train.py`/`paper_runs.yaml` 的 `test_cameras`）。
- 无逐 demo XML；`semantics.json` 限制；`env_version 1.4.1` vs 子模块 1.5.1。此为**上游 Dataset 路径**，不是本轮新增。
- 自定义 eval 用 `reset_from_xml_string` + 固定 root，官方 `eval.py:173-198` 用 `env.reset()` + `poses_list[episode_num]`；相机/初始状态分布不同。

## 2. H1–H4 支持、反证、排除范围

| 假设 | 支持证据 | 反对证据 | 现有证据能排除到哪 | 最小区分 |
|---|---|---|---|---|
| **H1 输入不一致** | 自定义训练/评估入口；sampler/RNG 差异；Plücker 解析检查是自一致 | `policy_input`（`experiment_lib.py:34-40`）与官方 `eval.py:160-171,206-230` 的 RGB/Plücker/qpos/extrinsics/反归一化路径逐项对应；qpos 均被 zero；extrinsics 均零；专家回放10/10；`metadata_insensitive=false` 说明 raymap 分支被用 | 只能排除“明显通道接错”；不能排除逐张量数值/相机约定差异 | 32次固定样本前向：官方 `Evaluator._image_to_tensor` 与自定义 `policy_input` 的 RGB、Plücker、qpos、extrinsics、动作块逐项 allclose |
| **H2 后验拟合、prior 部署失败** | ACT 训练/验证传入真实 actions，走 CVAE 后验；部署 `actions=None`，零 latent（`act.py:41-58`；`detr_vae.py:71-96`）；动作近常量、0 reach；val loss 0.331 不能代表 prior | KL 仅 0.009，后验可能接近 prior；loss 下降说明动作分布部分可拟合；专家动作回放成功只证明动作语义 | 未测 prior 与 posterior 的差距；不能凭 loss 判断 | 32个固定训练样本：expert action / posterior 重建 / prior 生成 / 常数动作基线，比较 L1、方向、方差 |
| **H3 训练相机有效、新相机失败** | dev 全用 test camera pool；无同 checkpoint 训练 camera 对照；官方 `eval.py:194-198` 每个 episode 用不同 test pose | 0/32 是 **0 reach/0 grasp**，不只是成功率低；若训练相机也 0，则 H3 不能解释全部；KYC 论文称条件化在 test camera 有收益 | 只能说明“新相机下失败”；不能区分训练未学会与视角泛化 | 16条闭环：8个固定 root ×（训练相机 / test相机）各1条，同 checkpoint、同初始 state |
| **H4 数据/环境/采样偏差** | sampler RNG、关闭训练内 test rollout、无逐 demo XML、版本 1.4.1/1.5.1、`original=False` | 10/10 回放、初始 XML+state 重建逐像素一致、200 demos/60k updates 与官方数量一致；未发现已证实致命错误 | 不能排除；也不能确认为主因 | 只读比较 `data_split` env_args、train/test camera 数值、sampler 顺序；无需 GPU |

**判断**：H1 目前**没有强支持**，但可用 32 次前向低成本排除或确认；H2 是**最符合“loss 下降但动作近常量”的解释**；H3 是**必须补的对照**，但 0 reach 使其不足以单独解释；H4 是未排除的背景差异，不能先验认定。

## 3. 官方复现真正要求，及几个概念边界

- KYC 官方 `paper_runs.yaml` 对 Lift 用 **seeds [0,1,2]**、20001 epochs、200 demos、test camera pool；`train.py:120-144` 训练中每1000 epochs 评估50条；`eval.py` 用 `reward==1`。**真正论文复现至少需要3个训练 seed + 官方评估入口 + 完整 test camera roots**；本轮只有 seed0、固定末步、无训练内 test、val 用 train pool，**不是论文数值复现**。
- **CVAE 后验 vs 部署**：验证 loss 传入 actions，是后验重建；部署 `latent=0` 是 prior 生成。二者不能互替。低 loss 可能来自动作均值/后验捷径；raymap 敏感只证明输入被使用，不证明动作正确。
- **公平常数基线**：用训练集（不含 val/test）按 chunk 位置和动作维计算 mean action，得到每样本常数 chunk；同归一化、同 L1/L2、同样本。若 prior 不优于该常数基线，H2 强；若优于，H2 减弱。另报 zero-action 基线。
- **16条闭环能支持/不能支持**：8对训练/测试相机同 root 可支持“训练相机下是否有任何任务行为”的方向性判断；不能支持成功率精确估计、训练 seed 方差、persistent/IID 机制，也不能替代 50 roots 正式 test。

## 4. 有限预算内最有辨识力的诊断

**Stage 0（只读，0 GPU）**：核对 `data_split` 的 `env_name/original`、train/test camera 数值是否重叠、sampler 顺序与官方 `load_data` 差异、checkpoint 加载路径；确认自定义 `policy_input` 与官方 `_image_to_tensor` 的 qpos/extrinsics 是否同为零。若发现明确张量/相机语义差异，直接进 A 类决策。

**Stage 1A（32次前向，0优化器更新，≤0.2 GPUh）**：
- 16个固定训练样本 × 2（官方入口/自定义入口）：比较 RGB、Plücker、qpos、extrinsics、归一化动作、生成 chunk；容差 allclose。
- 同32样本：expert / posterior / prior / 常数基线，报 L1、方向、chunk 方差。
- 这一步同时检验 H1 与 H2；若官方/自定义输入不一致 → H1；若 prior≈常数且远差于 posterior → H2。

**Stage 1C（仅当1A未定位，16×150步，≤0.8 GPUh）**：
- 8个固定 root ×（训练 camera / test camera）各1条，同 checkpoint、同初始 XML/state；记录 success、reach、grasp、动作。
- 训练相机有成功、test 0 → H3；两侧都0 → H3 不足，回 H2/H4；两侧都成功 → 当前 dev 失败是评估/相机实现问题。

**不做**：不训练、不调参、不换任务、不增加噪声条件、不把16条当正式 test。

## 5. A/B/C/D 决策边界与停止条件

- **A 明确实现问题**：1A 发现输入/相机/动作张量不等价，且能解释0/32；给最小修复与重训预算，但**不自动重训**，需人类批准。
- **B 训练相机有效、test 失败**：1C 训练相机有任务行为而 test 无；先审查是否与 KYC 冲突、是否评估偏差；不直接提新算法。
- **C 训练条件仍无能力**：1A prior≈常数或1C两侧均0，且无具体可修复原因；暂停 F，不盲目扩 seed/epoch/网络。
- **D 证据不足**：1A 输入一致、prior 优于常数，但1C两侧均0或样本太少；记 **INCONCLUSIVE/IMPLEMENTATION-LIMITED**，可因机会成本停止，不写 VALID-NEGATIVE，不自动授权两周重训。

**停止条件**：1A 已确认具体输入错误但修复需重训 → 停，待批准；1A 无错误且 prior 不优于常数 → H2 主导，停 F 基线；1C 训练相机也0 → 不把失败归因相机泛化；任何阶段超出32前向/16 rollout/1 GPUh → 停。

## 6. 针对性官方来源与 F 的后续边界

- KYC：`policy_robosuite/train.py:120-144`、`eval.py:160-230`、`utils.py:354-498`、`models/act.py:41-58`、`models/detr_vae.py:71-119`、`reproduce/paper_runs.yaml`；论文 Table I（ACT Lift 33.6→60.6）是作者结果，不是本机结果。官方 repo **未提供匹配本任务的训练 checkpoint**；只有代码与数据。
- CamVLA 附录 C：只测 IID 每决策重采样旋转噪声，5° 58.7%、12° 仍 > π0 36%；不能当 persistent 证据。
- AnyCamVLA：依赖 ArUco/已知相机参数，LVSM 回训练视角；无 calibration drift 测试。
- MoVie（NeurIPS 2023）：冻结动力学 + 测试时视觉编码器/STN 适应，fixed/moving/jitter 视角均覆盖；泛泛“动力学一致性相机适应”不是新方法。

**F 即使恢复基线**，仍面临 KYC/CamVLA/AnyCamVLA/MoVie 的直接覆盖；persistent/IID 只是窄诊断，必须先有可信 clean 能力、明确缺陷、且 simple pose-jitter/重标定不能闭合，才谈新机制。**当前无优先论文资格；本轮不运行任何新实验。**
