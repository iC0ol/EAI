# D Gate 1 预登记协议

登记日期：2026-10-22（Asia/Shanghai）。执行范围为 Square PH、低维状态输入，
动作日志整 episode 固定平移。配置的机器可读权威来源是
[`configs/gate1.json`](../../configs/gate1.json)。训练前写入冻结清单和 Git 提交。

## 科学对象与边界

Q1 是训练动作标签的索引错误是否损害正常闭环执行；Q2 是这些索引错误能否由
传统方法识别。原始动作是控制命令，既不是已经实现的末端位移，也不是下一时刻的
绝对目标状态。正常控制器动力学和响应滞后保持不变。推理同步暂停仿真，不施加
计算耗时对应的额外控制步延迟，`n_latency_steps=0`。

这次合成污染不能证明真实机器人的日志误差分布，也不能支持 RGB 时间错误的结论。
不实施后验监督、复杂对齐器、大模型、额外任务、训练结果驱动的调参或样本重选。

## 数据划分和条件

保留官方 20 个 valid episodes 原样。对官方 180 个 train episodes 用 NumPy
`default_rng(20261022)` 排序后排列，依次隔离 8 个同步锚点和 16 个独立 lag
诊断 episodes，剩余 156 个用于策略训练。最终闭环测试使用另外生成并提前冻结的
50 个正常环境初态（100000–100049），不使用训练轨迹初始化。

污染 RNG 为 731902。在策略训练 156 条中固定选择 78 条（50%），两个污染条件
共用这组 episode。Mixed 的六种 delta 各 13 条；Larger 的 ±4 各 39 条。
Clean 全部 delta=0。随机规则与每条标签保存在 `injection_truth.json`，训练器
只读取派生 actions，不读取这个文件。观测直接读取原始只读 HDF5。

定义 `C[t]=A[t+delta]`，正号表示将后来的控制命令提前写到当前观测对应的标签，
负号表示使用更早的命令。不是让环境实际提前或延后执行。在确认控制频率前，
不把步数换算成固定毫秒数；实际频率和换算写入时间约定报告。

每条完整标签序列的越界边缘设为 NaN，禁止循环移位或端点复制。三组训练都只
使用 `[4,T−4)` 内完整 16 步窗口，即起始索引 `4 … T−4−16`（含端点）。
训练无 observation/action padding；不能采到 NaN 边缘。不因 delta 调整采样起点。
完整派生标签保留 guard 区，因此对共同窗口验证 `C[t−delta]=A[t]`，无需复制边缘。
验证集未污染，三组采用相同完整序列规则。原始 HDF5 的 SHA256 必须吻合官方值。

## 策略和预算

官方 DP 的 ConditionalUnet1D，[128,256,512] 通道，扩散步嵌入 128，kernel=5，
GroupNorm=8，global observation conditioning。低维输入 16，原始相对动作 7。
训练前状态恢复审计发现官方 v1.5.1 `object` 前 7 维依赖可变 observation cache。
因此只选取原始 `object[7:14]`（世界系物体位置/四元数）及原始 eef pos/quat、
gripper qpos，所有选取值保持原样，三组采用相同列选择，不重算/修复观测。
这是训练前依据部署审计的设计修订，不涉及模型结果，也不改变污染定义、episode
集合或任何 delta；证据见 `observation_cache_summary.json` 与修订清单。
这些结果不能与原论文 23 维/绝对动作 10 维的 DP 数值直接比较。
observation horizon=2、prediction horizon=16、action horizon=8；采用官方
`oa_step_convention=True`，当前动作从预测索引 1 开始。控制器和环境元数据不改。

100 个训练扩散噪声时间步，cosine beta，epsilon MSE；评估 DDIM 16 步、eta=0。
动作已是归一化 OSC 控制命令，采用官方 relative-action 分支的 identity 归一化。
观测采用 Clean 训练公共窗口的逐维 min/max，所有条件复用同一统计量，不接触
验证、锚点、lag test 或最终测试状态来拟合统计量。

每次固定 50,000 optimizer updates、batch=256、AdamW(lr=1e−4,
betas=[.95,.999], eps=1e−8, weight_decay=1e−6)，500 步 warmup 后 cosine decay。
EMA power=.75。均匀有放回采样同一完整窗口集合；同一训练种子使用相同窗口
索引随机流。训练种子 42、43，最多六次训练（失败尝试也单独记录，不覆盖）。
每 1,000 步对同一批 clean valid 窗口进行固定噪声的去噪损失评估。
只评估最终 EMA，不按闭环测试选 checkpoint；不调参、不追加训练。

先执行 Clean seed 42 的训练与完整 50 回合评估。若成功数 ≤5/50、≥48/50，
或训练/环境故障，停止；中间区间才继续 Clean seed 43 及相同检查。
这两个阈值仅是本次管线的 failure/ceiling 操作标准，并不是理论性能阈值。
如果 loss 非有限或优化中断，直接报告管线失败。之后依次运行两污染条件各两种子。

每个策略 50 个 **完整 400 控制步** 的闭环 episodes，首次成功后也继续到 400。
成功为任一步官方 `env.is_success()['task']` 为真，并保存首次成功时间。测试初始
history 重复初始观测，只用于填满过去的观测历史，不复制动作标签。
只有 1 个仿真环境，Torch/BLAS/Numba 限制 2 线程；不启动 WandB。
如吞吐无法承担，不静默减少 50 回合，明确记录未完成及预算瓶颈。

## 评分与进入 Step D 的门槛

每个训练种子分别报告成功率、逐测试初态成功/失败、Clean−污染的配对差，
以及初态层面的 paired bootstrap 95% CI（10,000 重采样，seed 9012）。
同时报告配对 discordant counts 和两种子方向；跨种子报告共同初态的聚类重采样
区间。两个种子无法稳健估计训练随机性的总体方差，CI 仅反映本次固定策略的
测试初态不确定性，不能用它假装解决低种子数限制。

某个污染条件在两个种子均下降至少 10 个百分点，且每种子的上述配对区间下界
均大于零，才将其视为值得执行 Step D 的可重复实质退化。若仅 Larger 达标，
不能据此宣称 Mixed Small Lag 有实质损害。小点估计差异不能证明没有效应。

辅助记录 gripper 符号翻转、动作相邻差、nut 高度、接触数、局部完整动作/状态
trace。接触数和高度异常是代理量，不自动等同于人工确认的接触错误。
分别记录训练去噪 loss、clean validation 去噪 loss 与闭环成功率；不相互替代。
记录训练 GPU 占用墙钟小时和峰值分配显存，评估的仿真/重置 CPU 墙钟与推理墙钟。

只有门槛达标才实现/执行传统离线 lag 检查；不训练新策略。响应关系只从 8 个
同步锚点拟合，待估计输入不含真实 delta。16 个独立留出 episodes 可用于估计器
诊断，人工注入 truth 由单独事后评分读取。不得用这 16 条来拟合响应模型或
根据标签挑选超参数。若未运行，不创建 `lag_identification.md`。

## 决策

Q1 无可信可重复差异：`Insufficient evidence / Stop at Gate 1`。
简单方法可靠恢复且修复输入/标签与 Oracle 公共窗口一致：
`No-Go for posterior-supervision necessity in this setting`。
存在有用但传统硬对齐不可靠、非尖锐的不确定性，才可建议
`Potential Go to Gate 2`，且不能宣称后验监督更优。
部署失败、训练失败、统计证据不足、方法前提被否定分别列出。
Gate 1 交付后停止，等待研究者审查。
