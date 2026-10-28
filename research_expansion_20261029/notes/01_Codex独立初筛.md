# Codex 扩展轮独立初筛

形成于读取 DeepSeek 本轮回复之前。实际新检索截止 2026-10-29；这是问题探索记录，不是创新宣言。扩展搜索涵盖离散抓手/混合动作、时间重采样与关键事件、动作归一化、离线 RL 的 chunking/stitching、生成策略模式覆盖。重复上一轮的三个主题不进入新候选。

## C1：训练噪声分配改变条件分布时，模式覆盖与任务正确性的权衡

**来源事实**：[Immiscible Diffusion Policy](https://arxiv.org/abs/2610.09369)（Zhang 等，2026-10-07 预印本）III–V、表 I/II 显示，批内 Hungarian 噪声分配改善模式比例，但 Place Shoe 成功率由 100% 到 93.33%，Rotate QR Code 86.67% 到 73.33%；两项真实任务也下降。来源是作者结果，不是本轮复现。Push-T 覆盖率几乎不变，因此“模式塌缩本身造成任务失败”尚不成立。其训练使用镜像/平衡批次和受控多模态起点，不能直接称自然分布失败频率。

**独立复核**：官方仓库 `immiscible-diffusion-policy/immiscible-diffusion-policy` 固定 `03d90df3f07d82f125981b1667d5c1306b8eb884`；README 与 `immiscible_diffusion_policy/assignment.py`。匹配代价仅使用批内标准化动作，没有观测条件；噪声池整体保持不等于每个观测的条件噪声保持。README 明示未提供论文数据/权重、镜像/模式计数器不在发布范围，GPU 训练/全新 Conda 求解未经确认；配置用固定 epoch 启动，论文的性能触发不是已实现控制器。

**假设**：跨观测的全局分配可能把绝对动作位置等观测相关量编码到噪声，训练条件先验与部署独立高斯采样出现失配；这可能与稀有模式质量不足一起解释权衡。不能从成功率下降直接认定该机制。

**最强反证**：[COT Policy](https://proceedings.mlr.press/v305/sochopoulos25a.html)（Sochopoulos 等，CoRL 2025）明确研究朴素 OT 在条件策略中的问题，使用观测参与耦合。因此“条件化噪声匹配”已不是新方法。更早 [Immiscible Diffusion](https://papers.nips.cc/paper_files/paper/2024/hash/a422a2f016c14406a01ddba731c0969a-Abstract-Conference.html) 已讨论数据条件噪声不再高斯；需区分数据条件与外生观测条件。另 [Consistency Policy](https://www.roboticsproceedings.org/rss20/p071.pdf) V 节早已说明模式减少未必损害标准 Push-T 成功。

**最小验证价值**：先在官方 COT 小例子与标准公开策略数据做条件匹配诊断，再决定是否值得正式机器人训练；不能把二维生成拟合替代机器人证据。强简单参照是独立配对、原 IDP、原 COT/合法条件匹配；新模块必须胜过这些后才谈贡献。同一噪声池、同批动作/条件、相同梯度步及 NFE，测条件支持违规和任务后果，而非只测无条件多样性。

**当前资格**：探索级，待全文竞争审查。可以为机理复核而复现既有方法；尚无新方法资格。最可能失败在：缺少原镜像数据/训练配置，或 COT/简单随机配对已解释全部改进。

## C2：示教去冗余是否损失有意义的低位移操作阶段

**来源事实**：[Improving Robotic Imitation Learning via Trajectory Standardization](https://arxiv.org/abs/2606.22907)（Yang 等，2026 预印本）II–IV、算法 1：用末端位置速度/加速度构造重采样距离，改善三项实机任务。原式与实现近似需分别核对，不能把加速度称为真实接触力。

**假设**：在末端低位移但抓手、力或物体状态改变时，仅位置的重采样指标可能删除任务关键持续时间。尚没有核验到自然示教中该缺陷的逐样本频率和真实任务损失；不能凭“可能误删”排名首选。

**直接竞争**：ISR 本身、AWE 的 waypoint 提取、HYDRA 的稀疏/密集动作切换（后两篇目前只经 ISR 引用识别，待一手全文核验）。强简单修复是保留抓手事件与最小时长；若足够解决就停止，不添加 learned event 网络。最可能失败在：原方法已保留这些信号，或时间缩放改变控制语义，使表面收益源于速度/动作表示。

**当前资格**：未具备机器人实验资格；先查数据和实际事件遗漏，优先级低于 C1 的明确方法权衡。

## C3：多时域 critic 的自适应承诺是否受估计噪声与可比性限制

**来源事实**：[Adaptive Q-Chunking](https://arxiv.org/abs/2605.05544)（Gireesh、Ju、Wang，2026 预印本）4–5 节称 raw Q 跨时域比较偏向最短块；优势归一化和低信号时长块回退已经处理该问题。近邻 QC、DQC 在其相关工作被明确比较；尚未独立读全部近邻和官方实现。

**假设**：不同 horizon 的噪声/最大值选择偏差也许导致过度乐观承诺；但论文已有 normalization/selector 理论与消融，不能将普通 uncertainty gate 再包装。强简单基线是固定最优块长、原 AQC、统一 critic 尺度校正。

**当前资格**：粗筛降级，先查全文反例及代码。训练成本、任务依赖和第三直接近邻验证均未完成；无资格立即跑长 RL。

## 其他已找到的直接覆盖

- [FAN](https://arxiv.org/abs/2609.21358) 已把持续适应中的 action normalization 坐标漂移作为核心问题；冻结合法校准集统计是必须前置的简单方案。此时不再单列“动态归一化”新题。
- [PF-DAG](https://github.com/XiaohanLei/PF-DAG)（ICLR 2026）已覆盖 coarse mode 与细动作解耦，README 明示 early access/runnability 未验证；不能泛称离散连续混合动作尚无人研究。
- [ALT](https://stanfordmsl.github.io/alt/)（ICLR 2026）将低样本 DP 的记忆性解释为有益，并有 lookup 简单基线；“记忆训练动作”本身不是必须修复的退化。
- 离线 RL stitching 已命中 MQE、LAVL、BiTrajDiff、GTRL 等；本轮尚未建立超出这些工作的具体小问题，不因标题热门增加第四候选。
