# Gate B v2.0：几何余量感知的动作块提交（CAC）

- 修订日期：2026-11-11（B0 验收后协议修订）
- 状态：**B0 已完成；协议已修订；B1 未执行，等待研究负责人授权。**
- 目标：验证平台基线、固定 horizon 的效果，以及局部几何 clearance 是否调节不同 horizon 的任务结果。**不训练 CAC，不声称方法有效。**
- 主任务：robomimic Square-MH + Diffusion Policy image CNN。
- 硬件：单卡 RTX 3090 24 GB；本地驱动、CUDA、MuJoCo 与 checkpoint 已实际验证。

---

## 0. 本版相对 v1 的关键更正

1. 官方 Square-MH image CNN checkpoint 已公开，优先走 checkpoint-first，不默认从头训练。
2. square λ=0.017 是 2610.01626 的 K=24 demonstration/rollout 任务中位数，不是 policy-chunk 通用值，也不代表最佳 horizon。
3. clearance 不再用 r_tol - d_xy 近似；必须从仿真碰撞几何/物体轮廓计算最小有符号间隙。
4. J2 不用单次 episode 的 horizon winner 直接制造 oracle 标签；采用同一保存状态上的分支评估与 horizon×clearance 交互分析。

## 0.1 2026-11-11 B0 验收后修订记录

本节是 B0 之后对协议的正式补充，**不修改任何 B0 历史数据或统计结果**。

1. **动作空间**：实际 checkpoint 是 10-D absolute action（3-D position + 6-D rotation + 1-D gripper），不是 7-D delta。实验统一使用 checkpoint-native 动作语义，经 `RotationTransformer` 等价的 6-D→axis-angle 转换送入 7-D OSC_POSE 控制器，并设置 `control_delta=false`。
2. **Horizon**：固定 prediction horizon `H=16`；`To=2`；可执行未来动作 `H_available = 16 - (2-1) = 15`。B1 的 execution horizon 正式修订为 `h ∈ {1,2,4,8,15}`；`h=16` 仍被代码拒绝。
3. **B1 设计**：Pilot 使用种子 200000–200019（20 个状态），Full 使用 200020–200119（100 个全新状态），共 120 个互不重叠的初始状态；Full 不复用 Pilot 的任何状态。Pilot 为 20×5=100 episodes，Full 为 100×5=500 episodes，记录与 Manifest 文件分离。
4. **统计**：预注册 h=8 为参照；Cochran's Q 或按初始状态聚类的配对 bootstrap；四个对照使用 Holm 校正；报告 Wilson 区间与效应量；Pilot 不用于挑选 horizon 或阈值。
5. **B0 历史**：`gate_b_v2/reports/b0_*`、`B0_REPORT.md`、`B0_STATUS.md` 和 commit `09e9ca63b89349c3905a7dc2bca9fd8e2b99844b` 全部保留，未重跑、未覆盖。

## 1. 公开资产与 checkpoint-first 路径

### 1.1 官方权重

官方实验目录列出：

- 任务：Square-MH，image，Diffusion Policy CNN
- seed/run：train_2
- checkpoint：epoch=1950-test_mean_score=1.000.ckpt
- 文件大小：约 4 GB
- 目录：https://diffusion-policy.cs.columbia.edu/data/experiments/image/square_mh/diffusion_policy_cnn/train_2/checkpoints/
- 官方 README 说明论文实验提供 config、训练/评估日志与 best/latest checkpoints：https://github.com/real-stanford/diffusion_policy#-checkout-our-experiment-logs

实际 checkpoint payload 审计（2026-11-11）：

- `horizon H=16`、`n_obs_steps To=2`、`n_action_steps=8`；可执行未来动作 **15**。
- `shape_meta.action.shape=[10]`，`abs_action=true`，`rotation_rep=rotation_6d`。
- `training.use_ema=true`，EMA state 存在；normalizer 的 36 个参数在 model/EMA state_dict 内。
- 观测：`agentview_image`、`robot0_eye_in_hand_image` 均为 `[3,84,84]`，另有 eef_pos[3]、eef_quat[4]、gripper_qpos[2]。
- checkpoint 自身 env_runner 的 `test_start_seed=4,500,000`，不是 B0/B1 的种子范围；文件名中的 `test_mean_score=1.000` 不能当作协议种子上的预期成功率。

**证据边界：** 公开目录存在不等于本地下载成功、可加载或能复现论文成功率。文件名中的 test_mean_score=1.000 也不等于在本项目的 100 个新初始状态上成功率为 100%。

### 1.2 启动顺序

1. 下载 checkpoint 和同目录发布的 config.yaml；先核对 config 与 checkpoint 对应关系。
2. 按仓库的兼容环境安装依赖；不要先升级到最新 PyTorch/MuJoCo/robosuite。
3. 加载模型，检查 observation keys、两路 84×84 RGB、proprio 维度、action normalization、动作坐标系和 gripper 语义。
4. 跑 5–10 个 smoke-test episodes，保存视频与完整日志。
5. smoke test 通过后，跑 100 个固定初始状态建立本地 baseline。
6. 只有 checkpoint 无法加载、环境接口不兼容，或本地结果经排错后仍明显偏离时，才考虑按官方 Square-MH 发布配置重训。重训前先确认实际 task config 的 epoch 数，不要直接照搬通用默认 config。

重训时才需要下载 raw Square-MH demos 并本地渲染图像。不要下载 84.8 GB 预渲染包，除非本地渲染确实失败且磁盘/带宽允许。

## 2. Gate B 的研究问题与阶段边界

**问题：在 Square 插入前的同一物理状态，较短或较长的 action commitment 对后续成功率的影响是否随几何 clearance 系统性变化？**

Gate B 分三段：

- **B0 平台与 checkpoint 验证**：证明公开资产在本地能加载并执行。
- **B1 固定 horizon 全 episode 扫描**：检验全局 horizon 是否影响任务成功率。
- **B2 共同状态分支实验**：检验局部 clearance 是否调节单次 commitment 长度的效果。

Gate B 不实现预测误差模型、不训练 CAC、不做跨任务论文实验。B0/B1/B2 完成后再决定是否进入 Gate C。

## 3. B0：平台与基线门槛

| 检查 | 最低要求 | 失败处理 |
|---|---|---|
| 环境与 checkpoint | checkpoint 可加载；依赖版本与发布 config 对齐 | 先排错；记录完整错误，不立即重训 |
| 观测接口 | 两路 RGB 84×84、proprio 键名/维度匹配 | 修正 adapter，不改变 observation 语义 |
| 动作接口 | checkpoint-native **10-D absolute action**（3-D position + 6-D rotation + 1-D gripper），经等价 6-D→axis-angle 转换送入 **7-D OSC_POSE**，`control_delta=false`；gripper 末维语义一致 | 对照发布 config、checkpoint payload 与 runner 源码 |
| 单 episode | reset、rollout、终止谓词正常；视频可检查 | 未通过不得进入 horizon 扫描 |
| 100-episode baseline | 成功率 ≥0.70 作为继续门槛 | <0.60：排错后再试；仍低则 checkpoint/config/platform BLOCKED；0.60–0.70 记录边缘基线，不宣称复现 |

2026-11-11 正式 B0（RTX 3090，种子 100000–100099，h=8，500 steps）：**84/100 = 0.84**，Wilson 95% CI 0.7558–0.8990，Clopper–Pearson 95% CI 0.7532–0.9057。达到 ≥0.70 继续门槛。16 个失败种子全部保留，未替换、未跳过。完整记录见 `gate_b_v2/reports/B0_REPORT.md`。

DP 论文报告的 0.80–0.92 是作者跨实验结果，不是本地验收值；论文脚注披露 robomimic 任务实际只使用 22 个环境初始条件，而非名义 50。公开 checkpoint 文件名的 1.000 是在其自身 `test_start_seed=4,500,000` 上测得，不是本地 baseline，也不覆盖种子 100000–100099。

## 4. B1：固定 horizon 扫描

### 4.1 设计

- 固定模型与 checkpoint；不改权重、不更换 checkpoint、不训练。
- **H 与 h 的定义必须区分**：
  - `H = 16`：模型一次预测的完整动作序列长度（prediction horizon），由 checkpoint 固定。
  - `h`：每次预测后实际执行的未来动作数量（execution horizon）。
  - `To = 2`；`H_available = H - (To - 1) = 15`。
- 正式 execution horizon 列表：**`h ∈ {1,2,4,8,15}`**。`h=16` 不可执行，必须由代码拒绝；不得静默截断、补齐或重复最后一个动作。
- 每个 episode 全程固定执行长度 h：每次决策仍重新预测 H=16 步，只执行前 h 步，丢弃剩余动作并重新观测/预测。
- **Pilot**：20 个固定初始状态 × 5 horizons = 100 episodes，种子 **200000–200019**。目的仅为检查五种 h 是否可执行、初始状态配对、记录完整性、环境稳定性和初步 ceiling/floor；不得据 Pilot 结果挑选 horizon 或修改阈值。
- **Full**：100 个固定初始状态 × 5 horizons = 500 episodes，种子 **200020–200119**。Full 使用 100 个全新状态，**不复用 Pilot 的任何状态**。
- Pilot 和 Full 使用**不同的记录文件**（`b1_pilot_episodes.jsonl`、`b1_full_episodes.jsonl`）和**不同的 Manifest**（`b1_pilot_run.json`、`b1_full_run.json`），统计口径分离；Full 不能与 Pilot 混合成一个数据集。若 Pilot 后改变模型、动作语义、h 列表或其他参数，必须重新建立独立正式数据集。
- `B0`（100000–100099）、`B1 Pilot`（200000–200019）、`B1 Full`（200020–200119）三个区间必须完全不重叠。runner 启动前按**完整区间**校验，而不是只比较起点；任何重叠直接抛出异常。B1 共使用 120 个不同的初始状态。
- **正式完整性**：Pilot 必须恰好 20 个 seed × 5 h = 100 条记录；Full 必须恰好 100 个 seed × 5 h = 500 条记录。分析程序同时校验 JSONL 与 Manifest（phase、horizons、episodes、seed 起止、记录覆盖、h 覆盖、配对 Hash、`paired_initial_state_verified`）；任一项失败即拒绝生成统计结果。若同一目录同时存在 Pilot 和 Full，必须显式指定 `--b1-phase`，不得自动优先选择。
- **正式运行环境锁定**：B1 必须使用 B0 已验证的 checkpoint（SHA256 `adaf1785…27c6d`）、dataset（`7e589063…42887`）和 DP source tree（`aec43e20…72f21`）；`max_steps=500`、`H=16`、`To=2`、GPU `NVIDIA GeForce RTX 3090`、torch `1.12.1+cu116`/CUDA `11.6`、device `cuda:0`、policy seed offset `700000` 全部锁定。B1 CLI 不提供 checkpoint/dataset/dp-root/max-steps/config 覆盖入口；实际 Manifest 与每条 JSONL 记录必须携带实际指纹；分析门禁拒绝任何不一致。不得以警告后继续或自动替换文件的方式绕过。
- B1 的任务是固定 horizon 扫描；**不得在 B1 运行中收集 B2 状态或 snapshot**。B2 的独立实现和未启动状态保持不变。
- 同一初始状态在五个 horizon 下配对；必须验证同一 seed 的 `initial_state_sha256` 在五个 h 下完全一致。初始状态一致不代表轨迹一致：不同 h 会导致后续状态分化。
- 固定环境随机流，并记录 policy sampling seed。当前实现按 policy call index 调度随机种子，使相同 call index 在不同 h 下使用相同噪声种子；这不是整条轨迹共享随机数，报告时必须如实说明轨迹会分化。

### 4.2 主要指标

- 主指标：episode success（最终状态 nut-on-peg robomimic predicate，非 sticky success_seen）。
- 次指标：episode length、policy calls、wall-clock、碰撞/掉落/未对准/超时类别。
- 同时报 success-vs-policy-calls 与 success-vs-wall-clock；h=1 可能提高调用次数，不能只看成功率。

### 4.3 统计分析（预注册）

- 统计单位：**初始状态 seed**。五个 horizon 是同一 seed 的配对条件，不是五组独立样本；不得把 500 个 episode 当作完全独立样本。
- 分析前必须通过完整性门禁：Pilot 恰好 100 条（20×5），Full 恰好 500 条（100×5）；seed 区间、horizon 集合、记录数、Manifest 与 JSONL 必须一致；缺失、重复、越界或未配对数据一律拒绝分析。
- 分析同时校验环境指纹：checkpoint/dataset/DP-source SHA256、max_steps、H、To、GPU、torch/CUDA、device、policy seed offset、config fingerprint 必须等于 B0 锁定值；Manifest 与每条记录不一致时拒绝生成正式统计。
- 报告每个 horizon 的原始成功数、成功率及 Wilson 95% 区间。
- 五水平整体差异：**Cochran's Q** 检验；同时报告按初始状态 seed 聚类的配对 bootstrap 结果。
- **预先指定 h=8 为唯一参照组**。分别计算 h=1、2、4、15 相对 h=8 的成功率风险差，报告按 seed 聚类的配对 bootstrap 95% CI。
- 四个对照的 McNemar 精确检验 p 值使用 **Holm step-down** 多重比较校正；报告未校正与校正后的 p 值。
- 预先注册的实际意义阈值：最大 horizon 成功率差 **≥8 个百分点**（0.08）才视为存在值得继续研究的实际信号；该阈值不因 Pilot 结果调整。
- 不得仅因某个 horizon 的观测成功率最高就宣称它显著优于其他 horizon；必须同时报告全部 horizon、CI、整体检验和校正后结果。
- **Ceiling/Floor**：若所有 horizon 成功率均 ≥0.95，记录 ceiling effect；若均 ≤0.05，记录 floor effect。此时该任务/ checkpoint 对 horizon 效应缺乏可识别性，不得硬凑结论。
- Pilot 只用于执行、配对和记录完整性检查；不得用 Pilot 的成功率挑选 horizon、修改 h 列表或重新设定阈值。Full 的统计分析不因 Pilot 结果改变。

## 5. Clearance 的操作定义

### 5.1 不采用的近似

不把 clearance = r_tol - d_xy 作为最终几何定义。单纯横向距离会忽略 Square 插入中的相对 yaw、孔/peg 轮廓和轴向位置，可能把几何上不可插入的状态误标为“余量充足”。

### 5.2 主定义

在插入前的预先定义阶段，使用仿真器的真实碰撞几何或物体轮廓，在 nut 坐标系中计算 peg 外轮廓相对 nut 内孔的最小有符号间隙：

c_xy(t) = min over n in N_hole of [ b_hole(n) - n^T p(t) - h_peg(R(theta_t)^T n) ]

其中：

- N_hole：nut 内孔边界的外法向集合（至少包含四个面及其反向）；
- b_hole(n)：内孔沿 n 方向的边界支持值；
- p(t)：peg 中心相对 nut 孔中心的位置，表达在 nut 坐标系；
- h_peg：peg 碰撞轮廓的支持函数；
- R(theta_t)：peg 相对 nut 的平面旋转。

c_xy > 0 表示投影轮廓仍有正间隙，c_xy = 0 表示临界接触，c_xy < 0 表示投影轮廓已违反至少一个孔边界约束。若实际碰撞几何不是理想方形，必须直接使用仿真几何/碰撞查询，不得套用理想方形公式。

轴向位置/插入深度 d_z、接触状态和阶段事件独立记录，不混进 c_xy。J2 只在预先定义的“插入前、轴向处于指定窗口”决策点比较；阶段窗口必须在看结果前冻结。

### 5.3 几何读取的阻塞条件

- 必须核对 nut、peg 的实际 collision geom、尺寸、局部坐标系和 yaw 定义。
- 若环境只暴露 visual mesh 而没有可靠 collision geom，需先验证二者差异。
- 若无法得到可靠有符号间隙，B2 标记为 BLOCKED；可以报告 dx, dy, yaw, dz 向量，但不能将其冒称为 clearance 标量。

## 6. B2：共同状态分支实验（J2 主检验）

### 6.1 取样与分支

1. 从固定的 h=8 rollout 中，按预先定义的插入前阶段抽取 decision states；每个 episode 最多取一个 state，初始 discovery 集至少 30 个不同初始状态，覆盖成功与失败轨迹，不只选成功状态。若 B1 pilot 只有 20 个 h=8 episode，则额外补足至少 10 个独立初始状态。
2. 对每个 state 保存完整 simulator state、robot state、object state、observation 和随机数状态；验证恢复后能重现同一状态。
3. 从同一保存状态分支执行 h ∈ {1,2,4,8,15} 中的一个 commitment：重新预测 H=16，执行前 h 步；随后统一恢复 h=8 策略直到 episode 结束。
4. discovery 集每个 state × h 先跑 3 个 policy sampling seeds。若 discovery 显示方向一致且值得继续，再额外收集至少 30 个不同初始状态作为独立 confirmation 集；confirmation 集不用于选 clearance 阈值或改分析定义。若要提高每个状态成功概率估计精度，再增加随机重复数。
5. 如果 robosuite/robomimic 无法可靠 snapshot/restore，则用相同 reset seed 与确定性 replay 重建状态；若仍无法复现，B2 不得以“配对状态”名义继续。

### 6.2 主要统计问题

J2 不再定义为“每个 episode 哪个 horizon 赢了”再直接计算 AUROC。主要检验是：

success ~ categorical(h) + c_xy + categorical(h):c_xy

采用按初始 episode/state_id 聚类的 bootstrap 或合适的 mixed-effects logistic model；discovery 与 confirmation 按 episode 分离；检验 horizon × clearance 交互项，并画出不同 clearance 区间内各 horizon 的预测成功率与置信区间。

- 若 clearance 越紧时短 horizon 的相对收益越大、clearance 越宽时较长 horizon 的收益/调用效率更好，且交互在 held-out states 上保持，才支持 CAC 的核心现象。
- 用每个 state × h 的重复 rollout 估计成功概率；只有 best-vs-next 差异超过预先设定的实际意义阈值且不确定性足够小时，才给出 oracle horizon 标签。
- oracle horizon、AUROC/Spearman 是次级摘要，不取代交互检验；并列、全成功、全失败或低置信状态标记为 ambiguous，不强行分类。
- 所有阈值在看 held-out 结果前冻结；验证集用于选阈值，测试集只用于最终报告。

## 7. 通过、停止与转向

### 进入 Gate C 的最低证据

1. B0 通过：checkpoint/环境可用，100-episode 本地 baseline 达到预设门槛。
2. B1 显示 horizon 扫描不是完全无效/ceiling/floor；报告配对效应量和 CI。
3. B2 在 held-out states 上出现可重复的 horizon × clearance 交互；不能只靠训练/取样状态上的相关性。
4. 以 clearance 选择 horizon 的 oracle/可达上界相对最佳固定 horizon 有实际收益；同时报告额外 policy calls 和 wall-clock 成本。
5. 若 B1 的全局差异小但 B2 的状态交互明确，不自动判失败；这可能是不同状态效应相互抵消，需根据 B2 的 held-out 结果判断。

### 停止/转向

- B0 经排错仍无法加载或评估：先解决平台，不训练 CAC。
- B1/B2 都没有可识别的 horizon 效应，或 B2 交互 CI 覆盖零且效应上界很小：停止 CAC。
- h=1 全局最好且 state-level oracle 相对最佳固定 h 没有实际收益：停止 CAC 的成功率主张；如有明确调用成本收益，只能另行评估效率型问题。
- clearance 不产生增量预测能力：放弃几何版本；不得仅靠改名保留 CAC。
- 几何量读取不可靠或状态恢复不一致：B2 标记 BLOCKED，不做虚假 AUROC。

## 8. 与 Gate C 的边界

Gate B 不训练 error model、不实现完整 CAC、不做第二任务、不宣称方法有效。

只有 Gate B 通过后，Gate C 才：
- 训练任务空间误差动力学预测器；
- 设计视觉 clearance 估计；
- 比较 fixed / always-short / uncertainty / reactive monitor / CAC / oracle；
- 在 Square 与 ToolHang 等第二任务上做多 seed、消融和等调用预算评估。

## 9. 资源估算与第一天清单

- Checkpoint：约 4 GB；本地下载与加载时间取决于网络/磁盘。
- B1：pilot 100 episodes；扩展 500 episodes。
- B2：discovery 至少 30 states × 5 horizons × 3 stochastic repeats = 450 branch episodes；若信号存在，再收集至少 30 个独立 confirmation states（另 450 branch episodes）。
- 训练：checkpoint-first 默认不训练；若必须重训，按发布 config 实测，不预先承诺 3000 epochs 或 1–2 天。
- 不下载 84.8 GB 预渲染图像包。

第一天：
1. 核对 checkpoint、config、依赖版本和 GPU；
2. 加载 checkpoint，验证 observation/action schema；
3. 跑 5–10 个 smoke-test episodes 并保存视频；
4. 记录是否通过 B0，不启动 CAC 训练。

## 10. 当前执行状态（2026-11-11）

| 阶段 | 状态 | 说明 |
|---|---|---|
| B0 | **COMPLETED** | RTX 3090，种子 100000–100099，h=8，500 steps；84/100 = 0.84，Wilson 95% CI 0.7558–0.8990。历史数据未改动。 |
| B1 | **未执行** | 协议已修订为 h∈{1,2,4,8,15}；Pilot 200000–200019、Full 200020–200119（120 个互不重叠状态）；Pilot/Full 记录与 Manifest 分离；完整性门禁与统计方案预注册；等待研究负责人独立验收与明确启动授权。 |
| B2 | **未执行** | 插入阶段窗口未冻结；snapshot/restore 确定性 replay 未完成；未收集 B2 状态。 |

B0 通过不等于整个 Gate B 通过；B1 不证明 CAC 有效，不得提前开展 B2 分支实验。
