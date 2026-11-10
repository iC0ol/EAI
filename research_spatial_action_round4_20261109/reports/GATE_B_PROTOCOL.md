# Gate B v2.0：几何余量感知的动作块提交（CAC）

- 修订日期：2026-11-10
- 状态：**协议已修订，实验未执行**。
- 目标：验证平台基线、固定 horizon 的效果，以及局部几何 clearance 是否调节不同 horizon 的任务结果。**不训练 CAC，不声称方法有效。**
- 主任务：robomimic Square-MH + Diffusion Policy image CNN。
- 硬件目标：单卡 RTX 3090 24 GB；本地硬件/环境尚未验证。

---

## 0. 本版相对 v1 的关键更正

1. 官方 Square-MH image CNN checkpoint 已公开，优先走 checkpoint-first，不默认从头训练。
2. square λ=0.017 是 2610.01626 的 K=24 demonstration/rollout 任务中位数，不是 policy-chunk 通用值，也不代表最佳 horizon。
3. clearance 不再用 r_tol - d_xy 近似；必须从仿真碰撞几何/物体轮廓计算最小有符号间隙。
4. J2 不用单次 episode 的 horizon winner 直接制造 oracle 标签；采用同一保存状态上的分支评估与 horizon×clearance 交互分析。

## 1. 公开资产与 checkpoint-first 路径

### 1.1 官方权重

官方实验目录列出：

- 任务：Square-MH，image，Diffusion Policy CNN
- seed/run：train_2
- checkpoint：epoch=1950-test_mean_score=1.000.ckpt
- 文件大小：约 4 GB
- 目录：https://diffusion-policy.cs.columbia.edu/data/experiments/image/square_mh/diffusion_policy_cnn/train_2/checkpoints/
- 官方 README 说明论文实验提供 config、训练/评估日志与 best/latest checkpoints：https://github.com/real-stanford/diffusion_policy#-checkout-our-experiment-logs

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
| 动作接口 | 7-D action、坐标系、delta/absolute、gripper scaling 一致 | 对照发布 config 与 runner 源码 |
| 单 episode | reset、rollout、终止谓词正常；视频可检查 | 未通过不得进入 horizon 扫描 |
| 100-episode baseline | 成功率 ≥0.70 作为继续门槛 | <0.60：排错后再试；仍低则 checkpoint/config/platform BLOCKED；0.60–0.70 记录边缘基线，不宣称复现 |

DP 论文报告的 0.80–0.92 是作者跨实验结果，不是本地验收值；论文脚注披露 robomimic 任务实际只使用 22 个环境初始条件，而非名义 50。公开 checkpoint 文件名的 1.000 也不是本地 baseline。

## 4. B1：固定 horizon 扫描

### 4.1 设计

- 固定模型与 checkpoint；不改权重。
- 预测 horizon 保持 H=16。
- 每个 episode 全程固定执行长度 h ∈ {1,2,4,8,16}：每次决策仍重新预测 16 步，只执行前 h 步，丢弃剩余动作并重新观测/预测。
- 先做 20 个固定初始状态 × 5 horizons 的 pilot；若环境稳定且没有明显 ceiling/floor，再扩展到 100 个初始状态 × 5 horizons。
- 同一初始状态在五个 horizon 下配对；固定环境 seed，并记录 policy sampling seed。若能实现按 decision index 管理随机数，则使用 common random numbers；否则明确记录随机流不同，不把它称为完全配对随机性。
- 总量：pilot 100 episodes；扩展后 500 episodes（不含 smoke tests）。

### 4.2 主要指标

- 主指标：episode success（nut-on-peg predicate）。
- 次指标：episode length、policy calls、wall-clock、碰撞/掉落/未对准/超时类别。
- 同时报 success-vs-policy-calls 与 success-vs-wall-clock；h=1 可能提高调用次数，不能只看成功率。

### 4.3 统计分析

- 统计单位：初始状态 seed；五个 horizon 是同一 seed 的配对重复条件，不是五组独立样本。
- 先报告五水平的整体配对检验（Cochran's Q 或配对 cluster bootstrap）。
- 预注册的成对比较以 h=8 为参照，报告风险差及按初始状态 cluster bootstrap 的 95% CI；若进行多重比较，使用 Holm 校正。
- 不用“观察到的最高成功率”单独宣称某 horizon 显著优于其他 horizon；报告全部 horizon 和不确定性。
- 如果所有 horizon 均接近 100% 或均接近 0%，该任务/ checkpoint 对 horizon 效应缺乏可识别性，记录 ceiling/floor，不得硬凑结论。

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
3. 从同一保存状态分支执行 h ∈ {1,2,4,8,16} 中的一个 commitment：重新预测 H=16，执行前 h 步；随后统一恢复 h=8 策略直到 episode 结束。
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
