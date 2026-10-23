# M-Gate 0-R：专家状态重建排障与后续验证方案

日期：2026-10-23。性质：**下一次独立工程诊断提案，不是既有 Gate 0 的继续运行许可，也不是科研结论**。

## 1. 已核实事实（GitHub）

- 仓库：`iC0ol/EAI`；实验分支 `research/m-gate0`；报告提交 `537e6a6db79ed1e8aa884b4bad8a44f08b17c480`。
- 预登记提交 `b2a64fb3ad2f72b945233d76f7ad1fff84c27ad6`；执行代码提交 `946091eee089a5a5ebeddc5649a4d4afda0274a5`。
- 首个状态 S00=`demo_191`、t=52，在52步专家动作前缀后被物理/观测误差容差挡住；0个完整 suffix、0个正式方向扰动、0个 DP policy 推理、0个新策略训练。
- t=2：在线物体观测误差3.829777 mm，但物体 qpos 位置误差约2.1×10^-9 m；说明早期存在观测生成/缓存时序差异。
- t=52：物体 qpos 位置误差1.778535 mm；t=48峰值2.831569 mm；t=42发生较大的自由关节角速度误差0.931849 rad/s。后期存在真实物理状态偏离，不能只通过刷新观测解决。
- 原协议前缀容差和审计结论 `Invalid / Engineering blocked` 必须保持不变。既有结果不覆盖、不删掉、不因未使用剩余预算而自动重新开始。

## 2. 要回答的唯一工程问题

**能否不改变专家动作、任务、控制器和冻结 Clean 策略，构建一个与示教记录在物理状态及策略观测语义上相容、而且可在同一状态重复分叉的仿真起点？**

本次不能用工程排障结果声称任何 M 的方向敏感性/科研创新，也不能自动重新开始120个科学后缀。

## 3. 新一次独立注册

- 从已归档的 `research/m-gate0` 最终提交新建 `research/m-gate0-replay-recovery`，或用其他不会覆盖原分支的独立新分支。
- **新的诊断协议、固定比较方案和成本上限先提交 commit，再执行任何新仿真 step**。
- 只新增 `m_direction_pilot/reports/replay_recovery/`、`m_direction_pilot/outputs/replay_recovery/` 和相应诊断脚本；历史 `gate0/` 原始文件和哈希只读。
- 不下载新数据、不训练策略、不改动旧 D 实验/ROS/CUDA/全局依赖；保持原 RoboMimic Square/robosuite/MuJoCo/OSC_POSE、原 demo/checkpoint 哈希。
- 新仿真实测上限：**最多6条完整专家前缀诊断重放**；如果前提通过，**最多4条零扰动完整闭环 suffix**。每条实际步数、CPU时间、GPU推理调用及无效尝试均记录。任何未通过不自动扩增或改扰动半径。

## 4. 分阶段诊断（先零科研扰动）

### R0. 只读证据定位，无仿真步

1. 比对本项目 `m_direction_pilot/src/m_direction/replay.py::prefix_replay` 的环境初始化与**本项目锁定版本** robomimic 官方 `run_trained_agent.py` 的 replay/reset 顺序；特别审查 `env.reset(); env.reset_to(state)` 与现有 `reset_to({model,states,ep_meta})` 是否行为相同。官方示例中确实存在为 deterministic action playback 而做的额外 reset/reset_to；但不能预先宣称这是根因。
2. 检查原 low_dim HDF5 的 `obs` 是否来自 `dataset_states_to_obs.py` 逐状态 `reset_to` 的离线提取；这类 obs 不能直接等同于在线 `env.step` 的缓存快照。分别检查记录的 `states[t]`、原始绝对物体位姿、在线采样的 absolute object 观测和直接 sim qpos。
3. 追踪上次 `prefix_fidelity_by_step.csv` 的 t=38～52：分离 qpos、qvel、物体四元数、controller goal、夹爪控制、接触 `ncon`、实际接触点和法向/冲量、sim substeps、`qacc_warmstart` 及缓存更新时间；定位首次物理偏移的转折，而不是仅报告最大扁平状态分量。
4. 记录所有机制假设与可反驳观察：初始 reset 语义、sensor cache/step 时序、控制器隐藏状态、接触数值敏感性、原示教采集版本。明确哪些信息原 HDF5 根本未保存。

### R1. 固定一条来源做最小对照

目标固定 `S00/demo_191/t=52`。至少比较以下两种初始化路径：

- `P0`：既有已封存 trace 作为原始对照；无需为它再跑一遍。
- `P1`：严格采用锁定 robomimic 版本、并审计与数据采集一致的 `env.reset()` → `env.reset_to({model,states,ep_meta})` 路径，再逐步执行相同52个专家控制命令。保持传感器访问和 ControllerTap 对控制命令的观测不改变其值。
- `P2`（仅当需要、且先在新协议明确）：在**独立诊断环境**中对比 `env.step` 返回观测和相同 sim qpos 上强制刷新得到的观测，用来证明缓存差异。强制刷新可能改变观测缓存，因此这条路径不可直接视为有效的正式控制 rollout。

每个 t 保存以下两条各自独立的对照：

`物理对照`：source flattened state 分成 `time/qpos/qvel/act` 等可解释字段，再比较 raw sim qpos、qvel、接触与角度；

`观测对照`：source HDF5 16D、`env.step` 返回的16D和由 raw sim 状态导出的物体绝对位置/姿态分别比较；不能把缓存差全部归入物理位移。

报告不得仅以整体 `state_max_abs` 判断“位置误差”，也不能因为某条初始化路径恰好通过单个状态就立即申请120次科学实验。

### R2. 小范围跨阶段、跨来源技术复核

仅在 R1 确认**物理重建一致性有可解释的修复路径**之后，利用剩余额度从原冻结状态中选择**不同来源、不同阶段**的至少2个代表（例如原 S02 grasp、S09 insertion；选择理由和ID必须在实际后果产生前预先记录），验证相同修复不是 demo_191 专用。

与原 Gate A 一样，**旧的严格容差作为独立比较栏保留，不能静默放宽**：EEF/物体位置≤1mm、物体/EEF姿态≤0.01rad、选中obs最大绝对差≤1e-3、仿真状态最大分量差≤0.01。若确认录制观测与在线观测语义天然不同，必须在新协议提出不同、具物理含义的验收定义，并明确不等价于原 Gate A 已通过。

只有明确验收通过的技术路径，才允许最多4条零扰动完整 suffix：从同一有效专家状态、同一专家动作、相同策略checkpoint和随机流开始，跨至少两个状态做成对重放（2状态×2次），观察完整轨迹/动作/噪声表和最终success是否一致；并且记录 nominal suffix 有无信息量。若仍有未解释物理/观测差异或zero-zero成功不稳定，就停止。

## 5. 决策

- **R-Pass（技术候选）**：存在明确、可复现、跨至少两条来源及两种阶段可信的起点恢复方式；同一状态零扰动成对闭环重放一致。只意味着可以**提交新 M-Gate0 科学实验预登记草案**，不自动启动。
- **R-Partial（观测语义障碍）**：raw qpos/qvel重建合理但录制与在线obs结构不相容；需要讨论如何使示教训练状态与反事实续跑状态可比。不能随意把原 D 缓存修订重新包装为 M 创新。
- **R-Fail/Engineering blocked**：接触段真实物理重放偏移且无法在预算内可靠解释/修复，或零分叉本身改变终局成功。停止这条 RoboMimic-专家前缀研究路径；保留 M 作为未经检验的假设，不声称方向性假设已经被推翻。
- **R-Inconclusive**：少量工程对照结果相互矛盾、成本到达上限或关键中间状态信息缺失，记录未决项，不自动扩增。

**禁止**：改写原 Gate 0 预登记、覆盖 `A_S00_repeat0`、删除失败记录、降低误差阈值后宣布旧 A 通过、换随机好看的示教episode、自动运行 B1～B4、训练40参数教师/新BC、转到其他任务或加载新模型。

## 6. 若技术复现恢复后，科学 Gate0 必须先改的点

原 v2 Gate B1 在 development 只有 xyz±，混合方向 xy/xz/yz 只在 held-out 的 S08/S09/S10 上运行。因此不能通过 dev-only 数据识别一般固定全局3×3二次度量的非对角项，也不能由 `diag` 败北直接声称“固定global metric”败北。

**建议先提出新的、结果尚未揭盲的独立矩阵供研究者审批，不在本次恢复实验执行：**

- B1：12状态 × (1 nominal + xyz三个轴×±) = 84 suffix；含8 dev、4 held-out，原6来源保持来源隔离。
- B2：从事前固定的**4个dev状态（覆盖≥2个dev来源）和2个held-out状态（覆盖2个held-out来源）**各补充 xy/xz/yz ×± = 6×6=36 suffix；合计120。
- 牺牲原B3小半径4支与B4第二策略14支，优先解决当前**可辨识性与最强固定3×3基线**问题；半径及checkpoint依赖性留到下一独立验证阶段。预算不能简单合并两个矩阵。
- 所有混合方向和来源必须在新科学实验前固定。开发集拟合固定global3×3或几何规则，真正留出集只做一次检验；即使有6方向，也仅做描述性/探索性检验，不声称12状态能够可靠估计复杂M(s)。
- 正负符号及改善型后果单独报告；对称PSD无法解释具有方向符号不对称的结果，不能事后追加非对称头来保题。

如果该矩阵被接受，需要另建明确授权的科学 Gate0 注册和运行分支；只有**R-Pass之后**才有讨论资格。

## 7. 交付物

1. `reports/replay_recovery/protocol.md`、预登记commit SHA、执行commit SHA；
2. `reports/replay_recovery/reset_and_sensor_diagnosis.md`：至少列P0/P1/(可选P2)初始化差异与t=0..52分项曲线；
3. `outputs/replay_recovery/`：逐步分项CSV、prefix清单、实际CPU/GPU/sim步账、差异来源与代码SHA；原始NPZ本地保存并记SHA；
4. `reports/replay_recovery/zero_repeat.md`：通过后才运行，包含4条后缀的完整比较；
5. `reports/replay_recovery/go_no_go.md`：明确R-Pass/R-Partial/R-Fail/R-Inconclusive，无科研Go结论；
6. push全新分支并给出最终HEAD。任何工程原因只能按证据描述，不得用“可能”写成“已证明”。
