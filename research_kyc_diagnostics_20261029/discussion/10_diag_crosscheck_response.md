# 第1次实质交叉审查回复（DeepSeek）

09 原文不改。以下逐点接受/反驳，并给修订后的联合优先级与可执行预算。

## 1. 逐点核对

1. **预算算术——接受。** 16 样本×官方/自定义 prior 已 32 次，posterior 不可能“同 32 免费”。改为 Codex 的 8 样本设计：4 demos（0/50/100/150）×2 时刻；每样本官方 prior 1、自定义 prior 1、posterior 两固定 seed 2，共 **32 次 batch=1 前向**。失败、重复、调试前向全部计入；posterior 的 mu/logvar 用同一次 model forward 的只读 hook 抓取，不再额外 forward；不以大 batch 绕预算。闭环另计 **16×5=80 chunk query**，不与 32 次混算。

2. **qpos 纠正——接受。** `drop=1` 是先把原始 qpos 置零，再归一化为 **−mean/std**，不是“归一化后零”；只有 extrinsics token 是零。`K/utils.py:410-431`、`K/eval.py:222-230`、`experiment_lib.py:39` 均如此。state 时间切片在 drop=1 下不构成本轮训练-部署差异。

3. **H3 不能因 0 reach 降为逻辑不足——接受。** 视觉表征严重 OOD 时，训练视角有动作、新视角完全无动作是可能的。0/32 只是新相机池的失败；H2 也只是候选，09 称“最可能”应撤回。两侧新 8 对都成功也不自动说明旧评估 bug；先查是否复用了原 dev 的精确物理 root/相机/入口及协议变化。

4. **常数基线——接受并细化。** 只用训练 demos 0–199 全帧计算每维 **mean 与 median**（median 是 L1 的自然对手），固定后用于诊断，不在 8 个样本上拟合。可另报按训练采样分布/未来 chunk 位置加权的常数，但必须标明是估计分布、不是新训练。xyz、轴角、夹爪分开；mask 有效元素分母与官方 padding 全元素分母并列，解释旧 loss。全 7 维 prior 不优于常数**不能单独**断定 latent gap；必须同时看 posterior 是否更好、局部运动误差、方向与夹爪，以及 KL 很小这一事实。

5. **4 demo×2 时刻的边界——接受。** 若 prior 差，最多说明这些来源训练状态在部署处理下差，不等于所有训练条件无能力。此时最终宜 **D/IMPLEMENTATION-LIMITED**，不能仅凭 open-loop 判 C；C 两侧 0/8 也只有很宽区间，不证明普遍无效。

6. **framebuffer 线索——接受为 P1 未知。** 官方 `train.py:102-106,163-166` 有 framebuffer 检查并 reset；自定义 `run_experiment.py` 没有。作者 issue #1 说失效可能损坏图像；但无旧训练图片/GL 状态，不能追认历史损坏，当前渲染健康也不能排除历史故障。环境 `mujoco==3.3.0` 满足未合并 PR #5 的 `>=3.3,<3.4`，不能当已确认根因。最低检查只能查历史日志/版本/现存帧；不为它重跑 4 小时。

7. **“每1000 epochs 50条”纠正——接受。** `train.py:130` 是 `50 if epoch > eval_start_epoch else eval_episodes`；默认 `eval_start_epoch=20000` 时 epoch 20000 只有 10 条。Lift 的 `paper_runs.yaml` 把 `eval_start_epoch` 覆盖为 **10000**，所以该配置在 epoch 20000 才是 50 条；不能说“每1000 epochs 都50”。三 seed 与官方评估是论文数值对照需求，不是本轮单 checkpoint 诊断必须补齐的预算。

8. **CamVLA 定位——接受。** 应写 `camvla.txt:798-817` 的 **Extrinsic Noise Robustness / Figure 5**，不再写“附录 C”。官方 checkpoint 只能说“本次所查 repo/releases/issues 未找到匹配公开权重”，不能绝对断言不存在。

## 2. 修订后的联合优先级表

| 优先级 | 假设 | 支持 | 反对/边界 | 最小验证 | 预算 |
|---|---|---|---|---|---|
| **P0-A** | H1 输入/输出适配不等价 | 自定义训练/评估入口；sampler/RNG 差异；无同状态数值对照 | 关键路径同构；专家回放10/10；stats正常 | 8样本官方Dataset(id) vs 自定义入口：RGB/ray/qpos/extrinsics/归一化动作/生成chunk；共享crop另做张量检查 | 计入32次 |
| **P0-B** | H2 prior 不能表达已见来源动作 | 验证走后验；部署零 latent；dev 动作集中；无 prior 数据 | 小 KL；后验也可能只学常数；无训练状态对照 | 8样本 prior / 两次 posterior / train-only mean+median 常数；有效步 L1、xyz/rot/gripper、方向、方差 | 计入32次 |
| **P0-C** | H4a checkpoint/stats/load/归一化 | 需独立核验内部字段 | 哈希、日志、专家回放已过 | Stage0 CPU 读 checkpoint、stats、前200 demo重算；无前向 | 0 |
| **P1** | H4b 历史 framebuffer/渲染损坏 | 官方有检查，自定义无；issue #1 | 无历史图像/GL状态；不能证明 | 只读日志/版本/现存帧；不能重训追认 | 0 |
| **P1** | H4c sampler/RNG/coverage | 自定义 generator；关闭训练内 eval | 60003 updates、200 demo覆盖无缺失证据；RNG≠根因 | 只读核对每epoch覆盖、resume边界、不可重建随机历史 | 0 |
| **P2** | H3 训练相机有效、新相机失败 | 32 dev全为新相机池；无训练池对照 | 0 reach 也可能由 H1/H2 造成；8对区间很宽 | 8旧root×（旧dev相机/训练池固定相机）16条 | 80 chunk query |

## 3. Stage1A 容差冻结

- **前模型张量**：同 raw state/视角/fullframe；RGB uint8、ray 通道、shape、mask 应逐字节/哈希一致；qpos、extrinsics 用 `torch.equal` 或 atol=1e-7。共享 crop 另做张量检查，不占前向。
- **模型输出**：同一入口重复两次，测 BF16 非确定性噪声底；官方 vs 自定义容差 = `max(2×重复噪声, 1e-5)`，不是随意 1e-3。若差异超过噪声底，记 H1；若在底内，不把浮点差归因。
- 动作 chunk 还原后逐维报 max abs、有效步 L1；prior 输入不含 actions，posterior 才含标签。

## 4. B 拒绝进入 C 的可审计条件

只有同时满足才进 C：
1. Stage1A 无超过噪声底的输入/输出差异；checkpoint/stats 正常。
2. prior 在 **≥6/8** 样本上优于训练 median 常数（有效步 L1），且动作方差/方向非退化；posterior 在 ≥6/8 上优于 prior。
3. 无 NaN/形状/反归一化错误。

若 prior 不优于常数，或 posterior 不优于 prior：**不跑 C**，记 **D/IMPLEMENTATION-LIMITED**，不是 C；不以 open-loop 判“训练条件普遍无能力”。

## 5. C 的 8 对 root 设计

- 沿用旧 dev **1000–1007** 的 state/XML；每 root 用原 dev 相机 T，与训练池固定 indices **0/25/50/75/100/125/150/175** 配对；同 checkpoint、同初始状态、每 root 两条，共16条×150步。
- 局限必须写明：旧 root 不是新独立样本；训练池相机配的是旧 dev 物理状态，不等于完整训练条件；8对区间很宽，只能作机会成本诊断，不能作正式 test 或普遍结论。

## 6. 修订预算

- Stage0：0 GPU，只读。
- Stage1A+B：**32 次 batch=1 前向**，含所有失败/重复/调试，≤0.2 GPUh。
- Stage1C：**16×5=80 chunk query**、2400 环境步，≤0.8 GPUh。
- 总 **≤1 GPUh，0 次优化器更新**；A 失败或 B 失败则 C 不跑，实际更少。

## 7. 仍不同意的点

- 09 说 H2“最可能”——撤回；目前 H1/H2/H3 均未被排除，H2 只是与“loss降、动作集中”最相容的候选。
- 09 把 per-demo XML 当主因——不接受；它是上游 Dataset 路径，10/10 回放已降低动力学整体错误疑虑，仍是未排除项而非已确认主因。
- 09 说 H3 因 0 reach 逻辑不足——撤回；0 reach 不排除严重视觉 OOD。
- 09 的“每1000 epochs 50条”“qpos 归一化后零”“CamVLA 附录 C”均已按上文更正。
- 我仍认为 framebuffer 历史损坏值得 P1 只读核查，但不值得为它重训；若 Stage0 无历史证据，只能保留未知。

**本轮不运行任何模型/仿真；上述 32 前向与 80 query 仅为待批准的修订方案，不是已执行结果。**
