# Gate B 冻结协议：几何余量感知的动作块提交（CAC）

- 状态：**设计，未执行**。需研究者单独授权。
- 目的：用最小实验判断"目标现象是否真实存在、平台是否有正成功率、CAC 假设是否值得继续"，**不验证 CAC 方法本身**。
- 主任务：robomimic **Square**（nut-on-peg 精密插入），图像 DP。
- 备选：Square-ph；ToolHang；ManiSkill3 PickCube + ACT（见 §10）。

---

## 1. 前置条件（不满足则不进入主实验）

| # | 条件 | 检查方式 | 失败处理 |
|---|---|---|---|
| P1 | robomimic + DP 环境可在 3090 上安装并运行 | `python -c "import robomimic, diffusion_policy"`；跑 1 个 episode | 5 个工作日内不能解决 → 平台 fallback（§10） |
| P2 | Square raw demo 可下载（ph 69 MB / mh 74 MB） | 文件校验 | 换 ph/mh 或 fallback |
| P3 | 本地渲染 84×84 图像可用 | 渲染 5 条 demo，检查图像/键名与 DP dataset 兼容 | 修复渲染脚本；否则用预渲染包（84.8 GB，需磁盘/带宽） |
| P4 | DP 图像基线训练到 ≥0.70（见 §4） | 100 episodes 评估 | <0.60 两次尝试 → 停止/fallback；0.60–0.70 边缘，记录并谨慎继续 |
| P5 | horizon 可在 eval 时改变，且不重训 | 改 `n_action_steps`；确认 policy 仍预测 16 步 | 修复 eval 封装 |

## 2. 唯一核心判断

**在 Square 上，最佳开环执行 horizon 是否是状态相关的，并且由局部几何余量（nut-peg 横向偏移相对公差）预测？**

拆成两个可观测子判断（同一实验）：
- **J1（horizon 有影响）**：固定 horizon 1/2/4/8/16 的成功率差异 ≥8 pp（配对，95% CI 排除 0）。
- **J2（clearance 可预测）**：插入前状态的 clearance 能区分"短 horizon 更好"与"长 horizon 更好"的 episode（AUROC ≥0.7，或 Spearman |ρ|≥0.5 且 CI 排除 0）。

**只有 J1 与 J2 同时成立，才进入 Gate C 训练 CAC 方法。** 若 J1 成立但 J2 不成立，CAC 的核心假设失败；可考虑改用误差增长/不确定性信号（pivot）。

## 3. 最小运行范围

| 项 | 规格 |
|---|---|
| 任务 | Square-mh（300 demos）；ph（200 demos）作复现 |
| 策略 | DP 图像 CNN（官方 `square_image.yaml`）；horizon 16；训练 3000 epochs；batch 64；1 个训练 seed（Gate B 只验证现象；Gate C 用 3 seeds） |
| 观测 | 2×84×84 RGB + eef pos/quat + gripper qpos |
| 动作 | 7-D OSC pose delta + gripper |
| 评估 | 100 个固定初始状态（seeds 100000–100099），5 个 horizon 共用同一组状态（配对） |
| Horizon | `n_action_steps ∈ {1,2,4,8,16}`；每次执行 h 步后重新预测 |
| 总 rollouts | 5 × 100 = 500 episodes（不含训练/调试） |
| 训练数据 | 本地渲染 84×84 图像；约 300 demos × 400 steps × 2 cameras ≈ 240k frames；存储约 5–10 GB |
| 训练时间 | 3090 约 1–2 天（3000 epochs；若过慢降到 2000 epochs，基线门槛不变） |
| 评估时间 | 8 envs，约 2–4 小时（500 episodes × 400 steps） |
| 显存/内存 | <24 GB GPU；建议 ≥32 GB RAM；CPU 8 核 |
| 代码改动 | 仅 eval 的 horizon 参数与日志；不改策略/训练 |

### 3.1 可选快速预检（2–3 天，建议先做）

在渲染图像/训练图像 DP 之前，用 **低维 DP Square**（`robomimic_lowdim.zip` 1.93 GB；DP 低维 avg 0.89–0.93）跑同样的 horizon 扫描（1/2/4/8/16 × 50 episodes）。目的：
- 验证 horizon eval 封装、clearance 日志、oracle 计算；
- 快速看 J1/J2 是否值得继续。

规则：
- 低维通过（J1 ≥8 pp、J2 AUROC ≥0.7）→ 直接进入图像主实验。
- 低维 J1 <5 pp：**不能据此停止**（低维接近 ceiling，可能压缩效应）；记录并进入图像主实验，但把图像训练预算控制在 1 个 seed。
- 低维 always-short 最好：记录；图像仍可能不同（视觉多模态/纹理），但提高对 CAC 的怀疑，Gate C 设计需更谨慎。

低维结果只作为管线/现象预检，不作为最终论文证据。

## 4. 指标与日志

每个 episode 记录：
- `success`（nut on peg，robomimic 谓词）；
- `episode_length`；
- 每步：`nut_pose`、`peg_pose`、横向偏移 `d_xy`、插入深度 `d_z`、`clearance = r_tol - d_xy`（`r_tol` 由任务几何/公差确定，记录定义）；
- 每步：当前 action chunk（16×7）、执行的 h、replan 次数；
- 失败模式：未对准、掉落、碰撞、超时；
- 墙钟时间、policy call 次数。

**统计单位：** episode（同一初始状态的 5 个 horizon 为配对）；训练 seed 是方差来源，Gate B 只用 1 个；报告配对差值 + bootstrap CI（按 episode 重采样）。

## 5. 对照与混杂

| 混杂 | 控制 |
|---|---|
| 初始状态不同 | 5 个 horizon 共用同一组 100 个 seeds；`reset_to` 确认状态一致 |
| 训练 seed | Gate B 固定 1 个 seed；Gate C 用 3 个 |
| 动作随机性 | DP 采样固定 noise seed；或报告均值/方差 |
| 图像渲染差异 | 同一渲染脚本/分辨率；与 DP 论文的 84×84 对齐 |
| horizon 改变 episode 长度 | 报告 success 与 episode length；必要时按步数分层 |
| 选择偏差 | 不用成功轨迹估 clearance；用全部 episodes，条件在"到达插入前状态" |
| 多 horizon 比较 | 配对 McNemar / bootstrap；不把 5 个 horizon 当独立样本 |

## 6. 通过/停止标准

### 通过（进入 Gate C）
- P4：基线 ≥0.70；
- J1：max horizon 成功率差 ≥8 pp，95% CI 排除 0；
- J2：clearance 对 oracle horizon 的 AUROC ≥0.70（或 Spearman |ρ|≥0.5，CI 排除 0）；
- Oracle 上界：per-episode oracle horizon 比最佳固定 horizon 高 ≥8 pp（说明有自适应空间）。

### 停止/转向
- 基线 <0.60（两次尝试）→ 平台/任务问题，fallback（§10）。
- J1 差 <5 pp → horizon 不是有效变量，停止 CAC；可在同一平台转 P2（selection）或 P3（auxiliary）。
- J2 AUROC <0.60 → 几何余量不预测 horizon；停止 CAC 的几何版本；可试误差增长/不确定性信号（但那是另一个问题）。
- Always-short（h=1）已是最佳，且 oracle 增益 <5 pp → 自适应 horizon 无 success 空间；CAC 只剩算力效率，降级或不立项。
- 环境/渲染 5 个工作日不能跑通 → 平台 fallback，不训练方法。

## 7. 无正成功率时的处理

1. 先检查数据/渲染/动作归一化/eval 谓词，排除工程 bug；
2. 换 ph↔mh，或降低训练 epoch/ batch；
3. 若仍 <0.60：改用 **低维 DP Square**（`robomimic_lowdim.zip` 1.93 GB；DP 低维 avg 0.89–0.93）验证 horizon 现象；低维成功后再回到图像；
4. 若低维也失败：改用 **ManiSkill3 PickCube + ACT**（官方 baseline；正基线数字 PARTIAL，Gate B 重新确认）；
5. 若两个平台都无正基线：记录 BLOCKED 的具体证据，停止本轮课题，不训练 CAC。

## 8. 资源与成本

- 下载：raw Square 69/74 MB；DP/robomimic 代码 <1 GB；本地渲染存储 5–10 GB；**不下载 84.8 GB 预渲染包**（除非渲染失败且磁盘/带宽允许）。
- 训练：1–2 天 × 1 seed；Gate C 3 seeds 约 3–6 天。
- 评估：2–4 小时/500 episodes。
- 失败成本：若 J1/J2 失败，损失约 1–2 周 + 一次训练；资产（DP/robomimic/Square 数据/渲染管线）可复用于 P2/P3。

## 9. 与 Gate C 的边界

- Gate B **不训练** error model、不实现 CAC 规则、不做多任务。
- Gate C 才训练 task-space error dynamics model，做 2 任务 × 3 seeds × 100 episodes，比较 fixed/always-short/uncertainty/CAC/APEX/oracle，等 policy-call 预算。
- Gate B 的任何结果都不写成"方法有效"；只写"现象是否存在/可测"。

## 10. 平台 fallback

| fallback | 触发 | 资产 | 风险 |
|---|---|---|---|
| Square-ph | mh 数据/渲染问题 | 69 MB raw；DP ph | 基线略高（0.90–0.98 max） |
| 低维 DP Square | 图像渲染/训练失败 | 1.93 GB lowdim zip | 状态基，空间感知弱；基线接近 ceiling |
| ToolHang image | Square 太饱和/失败模式不清 | 同 DP/robomimic；DP avg 0.73–0.84 | 任务更难，训练更久 |
| ManiSkill3 PickCube + ACT | DP/robomimic 环境不可用 | 官方 ACT baseline；100 demos；30k iters | 正基线数字 PARTIAL；ACT 曾出现 0 成功历史 |

## 11. 授权后第一天要做的三件事

1. 安装/验证 robomimic + DP 环境；跑通 1 个 Square episode。
2. 下载 raw Square mh；渲染 5 条 demo，检查键名/图像与 `robomimic_replay_image_dataset` 兼容。
3. 启动 DP 训练（3000 epochs），同时写 horizon eval 封装与日志。
