# 唯一主选题：几何余量感知的动作块提交

## 0. 定位

**待实验确认的主选题。** 选择依据是"当前风险最低、最容易快速证伪、最值得优先验证"，不是声称已被证明有效。

## 1. 题目

- **中文：** 几何余量感知的动作块提交：视觉运动策略何时应停止开环执行？
- **English:** *Clearance-Aware Commitment: When Should a Visuomotor Policy Stop Acting Open-Loop?*
- **方法简称：** CAC（Clearance-Aware Commitment）。

## 2. 一句话核心问题

**在动作块（action chunk）执行中，安全的开环执行长度是否由当前任务空间的局部几何余量决定；一个用几何余量与预测误差增长来选择执行长度的策略，能否在等算力下优于固定长度、不确定性触发和始终闭环的基线？**

这是"空间信息 → 行动决策"的关系：不是让策略"看得更准"，而是让策略用当前的空间余量决定**何时停止开环、何时重新观察/规划**。

## 3. 为什么这是一个真实问题

1. **动作块固定长度的权衡已被作者报告。** Diffusion Policy 论文 §4.3：horizon 8 对多数任务最优；太长降低反应，太短损失一致性 [F 2303.04137]。这是**任务级固定选择**，不是状态级。
2. **误差传播具有状态与拟合窗口依赖性。** 2610.01626 在 robomimic 的 K=24 open-loop demonstration/rollout stamps 中报告中位 λ：can 0.009、lift 0.015、square 0.017、tool hang 0.026；这些数值不是最佳 horizon，也不是所有 policy-chunk 的统一传播率。DP policy-chunk stamps 的窗口受 8-action chunk 限制；论文强调短窗口可能高估长窗口传播，并明确说 λ 本身不能确定最优执行长度 [F 2610.01626 §4.2–4.3]。因此它只支持“全局单一传播率不足”的动机，不直接证明 CAC。
3. **精度任务的失败是具体的。** robomimic Square 是 nut-on-peg 精密插入；DP 图像策略作者报告 avg 0.80–0.92（ph/mh），即 8–20% 失败 [F 2303.04137 Table 2]。失败集中在插入对准/接触，而不是"完全不会抓"。
4. **现有自适应 horizon 方法没有用几何余量。** 2609.00908 用 action expert 的 cross-attention entropy plateau 做 training-free 截断（VLA，π0.5/X-VLA）；2607.01804 用 latent visual monitor 做反应式截断/重规划；2608.15938 分析开环 vs 闭环但无几何判据 [A/P]。**用任务空间 clearance + 预测误差增长做预测式 commitment 的工作未被直接做**（本轮有界检索）。

## 4. 方法机制

### 4.1 输入/输出

- **输入：** 当前观测（图像 + proprio，或 Gate B 的特权状态）、策略预测的 H=16 步 action chunk、当前任务空间余量 c_t（nut 坐标系下 peg 外轮廓相对 nut 内孔的最小有符号几何间隙；相对 yaw 由轮廓投影体现，轴向 d_z 单独记录）。
- **动作接口：** checkpoint-native **10-D absolute action**（3-D position + 6-D rotation + 1-D gripper）。6-D rotation 经 rotation matrix 转为 axis-angle，与 position、gripper 拼成 **7-D OSC_POSE** 环境动作，并设置 `control_delta=false`。H=16、To=2 固定；可执行未来动作 `H_available = 16 − (2−1) = 15`。
- **输出：** 本次执行的步数 `h ∈ {1,2,4,8,15}`；剩余 chunk 丢弃，下一步重新预测。`h=16` 不可执行，代码必须拒绝，不得补齐、重复或静默截断。

### 4.2 规则（文字伪代码）

```
at decision step t:
    obs   = get_obs()
    chunk = policy.predict_chunk(obs)          # H=16, 10-D absolute actions
    c     = clearance(obs)                     # task-space margin, metres
    for h in [15, 8, 4, 2, 1]:
        e_hat = error_model(state_t, chunk[:h])  # predicted max task-space error
        if e_hat < c - margin:
            execute(chunk[:h]); break
    if none: execute(chunk[:1])
```

- `error_model` 在 Gate B 先用**解析/经验模型**（当前偏移 + chunk 指令位移的线性外推）；Gate C 再用**学习到的任务空间误差动力学模型**（小 MLP/GRU，输入状态 + chunk，输出未来偏移轨迹）。
- `margin` 是安全系数；Gate C 用验证集选择，不在测试集调。
- 方法**不改变策略权重**，只改变执行长度；因此与 DP/ACT 兼容。

### 4.3 与"加模块/换门控"的区别

- 它改变的是**行动承诺的时序决策**（何时停止开环），不是表征、损失权重或注意力门控。
- 可以把 CAC 看作 **task-space model predictive commitment**：用策略自己的 action chunk 作为计划，用任务空间误差模型预测其后果，只在预测安全时承诺执行。这与"用内部熵/视觉偏差做事后截断"是预测式 vs 反应式的区别。
- 科学主张是：**几何余量比内部不确定性（attention entropy、denoising variance、ensemble variance）更能预测安全 horizon**。这是一个可证伪的比较，不是"再加一个 head"。
- 实现是轻量的；论文的贡献是判据 + 证据，不是架构复杂度。误差模型是实现细节，不是创新点本身。

## 5. 任务、模型、资产

| 项 | 选择 | 证据/状态 |
|---|---|---|
| 主任务 | robomimic **Square**（nut-on-peg 精密插入），mh 优先、ph 备选 | 任务定义/数据公开；DP 图像 avg 0.80–0.92 [F 2303.04137 Table 2] |
| 策略 | **Diffusion Policy（图像，CNN）** | 官方 repo MIT；checkpoint 为 `square_mh/diffusion_policy_cnn/train_2` 的 hybrid image workspace；H=16 / To=2 / n_action_steps=8；EMA |
| 动作接口 | **10-D absolute action**（3 pos + 6-D rot + 1 gripper）→ 6-D→axis-angle → **7-D OSC_POSE**；`control_delta=false` | checkpoint payload `abs_action=true`、`rotation_6d`；`actions.py` 已在 B0 验证 |
| 观测 | 2×84×84 RGB（agentview + wrist）+ eef pos/quat + gripper qpos | checkpoint `shape_meta`；已在真实环境验证 |
| 数据/权重 | 官方 Square-MH image CNN checkpoint：train_2 / epoch=1950-test_mean_score=1.000.ckpt（4.63 GB）；**本地已加载并在 RTX 3090 上完成 B0**（84/100） | 官方实验档案；checkpoint 优先；未重训；预渲染 84.8 GB 包未下载 |
| 评估 | robomimic env；success = 最终状态 nut-on-peg predicate；B0 seeds 100000–100099，h=8，500 steps | B0 报告；协议 §3–§4 |
| 硬件 | 单卡 3090 24GB；优先复用 Square-MH 官方 checkpoint；仅必要时按发布配置重训；eval 8 envs | DP 官方实验档案；config |
| 备选任务 | ToolHang（同代码/数据；DP image avg 0.73–0.84；2610.01626 的 K=24 demonstration/rollout 中位 λ 为 0.026） | DP Table 2；2610.01626 |
| 平台 fallback | ManiSkill3 PickCube + ACT（官方 baseline；正基线数字 PARTIAL） | ManiSkill3 论文；ACT README |

## 6. 强基线

1. **固定 horizon 8**（DP 原配置，也是 B1 的预注册参照）。
2. 固定 horizon 1 / 2 / 4 / 15（不再使用不可执行的 h=16）。
3. **始终 1 步闭环**（always-short）。
4. **不确定性触发**：denoising variance / ensemble variance / attention entropy（若可计算）。
5. **反应式视觉监控**：VLA-Corrector 式 latent visual deviation（作为 baseline）。
6. **Oracle horizon**：用特权状态/离线回放选每个状态的最优 h（上界）。
7. **APEX**：执行间隙适配（若兼容；作为执行侧强基线）。
8. 任务级最优固定 horizon（用验证集选）。

## 7. 为什么选它，而不是 P2/P3

- **P2（clearance-aware selection）**：采样 K 个 chunk，用 clearance 分数选；强竞争 Gated GeoBoN（depth consistency Best-of-N）与 RAIN；第一项实验需要预测器/额外采样。
- **P3（clearance auxiliary）**：把 clearance 作为辅助监督；需要重训多个变体；归因难；auxiliary 任务拥挤。
- **P1**：第一项实验只改 eval 的 `n_action_steps`，不需要新模型；能在 1–2 周内判断"horizon 是否重要、clearance 是否预测 oracle"；失败后可在同一资产上 pivot 到 P2/P3。
- **风险最低、最快证伪、资产最可靠**：这三条是用户明确的优先级。

## 8. 未验证事项（必须如实标注）

1. **本地 DP Square 正基线**：作者报告 0.80–0.92；官方 Square-MH checkpoint 已在本地 RTX 3090 加载并完成 B0：84/100 = 0.84（Wilson 95% CI 0.7558–0.8990），达到 ≥0.70 继续门槛。
2. **固定 horizon 的效应量**：DP 论文只给任务级 8 最优；Square 上不同 horizon 的差异仍未测量。B1 协议已修订，但**尚未执行**。
3. **clearance 是否预测 oracle horizon**：未有任何论文直接测；B2 测（交互检验为主，AUROC 为次级摘要），尚未执行。
4. **always-short 是否已经最好**：若最好，CAC 的成功率增益消失；B1 测。
5. **DP/robomimic 旧环境在 3090 上能否稳定运行**：已验证；驱动 580.178.04、CUDA 11.6、robomimic 0.2.0、robosuite 1.2.0 完成 GPU smoke 与 B0。
6. **本地渲染图像与 DP 论文分布是否一致**：已用官方 `image.hdf5` 状态对比；OSMesa 渲染与存储帧直接方向 corr 0.998/0.9998，平均差约 1.5/255。
7. **方法在图像观测下能否估计 clearance**：Gate C 问题；Gate B 用特权状态。
8. **与 2609.00908 的 attention entropy 相比是否更好**：Gate B/C 必比；若打平，CAC 不成立。

## 9. 实验进度与待授权实验

- **B0：已完成**（种子 100000–100099，h=8，500 steps）：84/100 = 0.84，Wilson 95% CI 0.7558–0.8990。
- **B1：未执行。** 协议已修订为 `h ∈ {1,2,4,8,15}`；Pilot 使用 200000–200019（20 状态），Full 使用 200020–200119（100 个全新状态），共 120 个互不重叠的初始状态；Pilot/Full 记录、Manifest 和分析分离；统计方案已预注册。须等待独立审查和明确授权后才启动。
- **B2：未执行。** 插入阶段窗口未冻结，snapshot/restore 未验证；未收集 B2 状态。
- 只有 checkpoint 不兼容/分布明显不符时才按官方配置重训。**不训练 CAC 方法。**

## 10. 一句话

**如果实验证明"几何余量能预测安全 horizon，且 CAC 在等算力下优于固定/不确定性基线"，这就是一篇方法型小论文；如果不能，Gate B 会在两周内给出干净的否定，并把资产留给 P2/P3。**


## 11. 2026-11-10 修订

- 官方 Square-MH image CNN checkpoint 存在：train_2/checkpoints/epoch=1950-test_mean_score=1.000.ckpt，约 4 GB。该文件名中的分数是发布实验记录，不是本地复现结果；本地加载与评估仍待验证。
- 2610.01626 的 square λ=0.017 是 K=24 demonstration/rollout 统计中的任务中位数；不能写成 policy-chunk 的通用传播率，也不能据此推出最优 horizon。
- Gate B 的 clearance 采用仿真几何的最小有符号间隙，不再使用简单 r_tol - d_xy；yaw 纳入轮廓投影，d_z 独立记录。
- J2 改为共同状态分支实验和 horizon×clearance 交互分析；单次 episode 的 winner 不再直接作为无噪声 oracle 标签。


- DP 论文评估口径补充：虽然正文说明名义上 3 个训练 seed × 50 个环境初始条件，但脚注披露 robomimic 任务因评估代码 bug 实际只使用 22 个初始条件；本地 Gate B 的 100 个初始状态是独立新评估，不将论文名义数量当作本地基线。

> 2026-11-12 注：本节是历史修订记录，保留原文。其中“本地加载与评估仍待验证”已由 B0 完成（84/100，见 §12 与 `gate_b_v2/reports/B0_REPORT.md`）；旧动作空间/旧 horizon 描述已被 §12 取代。

## 12. 2026-11-12 第二次修订（B0 验收后）

- **动作空间统一为 checkpoint-native 10-D absolute action**：3-D position + 6-D rotation + 1-D gripper；经 6-D→axis-angle 转换送入 7-D OSC_POSE，`control_delta=false`。B0/B1/B2 必须使用同一 checkpoint 和同一转换逻辑，不描述为 7-D delta 实验。
- **Horizon 定义统一**：prediction horizon `H=16`、`To=2`、可执行未来动作 15；execution horizon 正式为 `h ∈ {1,2,4,8,15}`，`h=16` 由代码拒绝。
- **B1 种子完全分离**：B0 100000–100099；Pilot 200000–200019（20 个状态）；Full 200020–200119（100 个全新状态）。Full 不复用 Pilot，B1 共 120 个不同初始状态；runner 按完整区间检查重叠。
- **Pilot/Full 分离与完整性**：Pilot 固定 20×5=100 条，Full 固定 100×5=500 条；记录与 Manifest 分文件；分析前强制校验 seed 区间、horizon 集合、记录数、Manifest、phase 与配对 Hash；Pilot+Full 同时存在时必须显式指定 phase。
- **B1/B2 阶段隔离**：B1 CLI 和 `run_b1()` 不再提供 B2 状态收集；B2 独立实现保留但未启动。
- **B0 历史数据未改动**：12/12 证据文件与 commit `09e9ca6` 字节一致；本修订只新增说明和代码/配置/测试。
- 详见 `gate_b_v2/reports/B1_SECOND_REVISION_REPORT.md` 与 `gate_b_v2/reports/B1_PROTOCOL_AMENDMENT.md`。
