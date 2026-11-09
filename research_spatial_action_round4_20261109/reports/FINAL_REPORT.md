# 第四轮研究报告：唯一主选题与可执行方案

- 日期：2026-11-09（Asia/Shanghai）。检索截止：2026-11-09。
- 会话：同一 DeepSeek 会话，接续前三轮；旧报告只读。
- 范围：Gate A（文献/代码/资产只读、理论/统计、方案设计、原创报告）。**未训练、未推理、未仿真、未安装、未下载模型/大型数据、未实现算法。**
- 来源登记：`sources/sources.jsonl`；访问记录：`notes/search_log.md`；状态：`notes/research_state.md`。

---

# A. 最终选题决定（第一页）

## 唯一主选题

**中文：** 几何余量感知的动作块提交：视觉运动策略何时应停止开环执行？
**English:** *Clearance-Aware Commitment: When Should a Visuomotor Policy Stop Acting Open-Loop?*
**方法简称：** CAC（Clearance-Aware Commitment）。
**定位：待实验确认的主选题。** 选择依据是"风险最低、最快证伪、资产最可靠"，不是声称已证明有效。

## 一句话科学问题

**动作块的安全开环执行长度是否由当前任务空间的局部几何余量决定；用几何余量与预测误差增长来选择执行长度的策略，能否在等算力下优于固定长度、不确定性触发和始终闭环的基线？**

## 方法机制

在每次决策点，策略预测 H=16 步 action chunk；用当前任务空间余量 `c`（nut-peg 横向偏移相对公差）与一个任务空间误差增长模型，选择最大的 `h ∈ {1,2,4,8,16}` 使得预测误差 < `c - margin`；执行 `h` 步后重新预测。**不改变策略权重，只改变"何时停止开环"的时序决策。**

## 实验平台

- 任务：robomimic **Square**（nut-on-peg 精密插入），mh 优先、ph 备选。
- 策略：**Diffusion Policy（图像 CNN）**，官方 repo/config；horizon 16，n_action_steps 8。
- 数据：raw Square ph 69 MB / mh 74 MB；本地渲染 84×84 图像（不下载 84.8 GB 预渲染包）。
- 正基线：DP 论文图像策略 Square avg **0.80–0.92**（作者报告）；Gate B 本地门槛 ≥0.70。
- 硬件：单卡 3090 24GB；训练 3000 epochs，约 1–2 天；eval 2–4 小时/500 episodes。

## 最主要风险

**始终 1 步闭环（always-short）可能已经最好**；若如此，CAC 的 success 增益消失，只剩算力效率。Gate B 的第一个实验就是测这个，失败则 pivot 到 P2/P3 或换任务。

## 为什么选它（在不完美选项中）

1. **正基线最可靠**：DP 图像 Square 有作者报告的 0.80–0.92，代码/配置/数据公开。
2. **失败具体**：8–20% 的 nut-on-peg 失败；2610.01626 测得 square 的误差传播率 0.017，状态依赖。
3. **第一项实验最便宜**：只改 eval 的 `n_action_steps`，不训练新模型；1–2 周可得到 J1/J2 的明确结论。
4. **强简单基线清楚**：固定 8、always-short、不确定性、反应式监控、oracle；方法必须全部击败或至少优于最佳固定。
5. **3090 可行**：DP 图像训练/评估在单卡范围；不需要 VLA 或大数据。
6. **失败可复用**：若 CAC 不成立，DP/robomimic/Square/渲染管线可直接用于 P2（selection）或 P3（auxiliary）。

**它不是 A1/C1 的改名**：A1 是误差预算测量，方法是敏感度塑造；CAC 是**执行 horizon 的承诺决策**，干预点是"何时停止开环"，文献与实验都不同（action chunking/receding horizon vs representation/sensitivity）。两者共享"几何余量"这一空间量，但科学问题不同。

---

# B. 实验资产核查表

| # | 任务 + 模型 | 官方来源 | 权重/数据 | 动作接口 | 正成功证据 | 3090 | 复现风险 | 状态 |
|---|---|---|---|---|---|---|---|---|
| 1 | **robomimic Square + DP（图像）** | DP 2303.04137；repo `real-stanford/diffusion_policy`（MIT）；`square_image.yaml` | 无 checkpoint；raw ph 69 MB / mh 74 MB；预渲染 image zip 84.8 GB（不下载） | 7-D OSC pose delta + gripper；2×84×84 RGB + proprio | **作者报告 avg 0.80–0.92**（ph/mh，3 seeds × 50 init） | 训练 1–2 天；eval 2–4 h | 旧栈（PyTorch/gym/MuJoCo）；需本地渲染；无 checkpoint | **VERIFIED（作者报告）/ 本地未跑** |
| 2 | robomimic ToolHang + DP | 同上 | 同上 | 同上 | 作者报告 avg 0.73–0.84（image） | 同上 | 任务更难、更长 | **VERIFIED（作者报告）** |
| 3 | ManiSkill3 PickCube + ACT | ManiSkill3 2410.00425；`examples/baselines/act` | 100 motion-planning demos；30k iters；无 checkpoint | pd_ee_delta_pos；RGB/state | 官方 baseline 存在；**精确成功率未在 README/正文给出** | 训练数小时–1 天；GPU 并行 eval | ACT 历史 0 成功风险；基线数字 PARTIAL | **PARTIAL** |
| 4 | MetaFine Grasp/Toggle + ACT/DP3 | MetaFine 2605.19986；repo MIT | 仓库 40 assets；演示可生成；无 checkpoint | pd_joint_delta_pos 等 | ACT 49/63/63；DP3 75/85/63（Grasp/Toggle/Press） | 可行 | **精度任务 Peg/Plug/Stack ACT/DP3 = 0%**；任务偏 coarse | **VERIFIED（作者报告）/ 不作主平台** |

**结论**：只有 #1/#2 同时满足"精度任务 + 作者报告的正基线 + 可改 horizon + 3090 + 数据可管理"。#3 是平台 fallback；#4 的精度任务无正基线，不能作主平台。

**证据分级**：
- 作者报告：DP Table 2；MetaFine Table B4。
- 官方资产存在：DP repo/config；robomimic 数据；ManiSkill ACT baseline。
- 第三方复现：未核查。
- 本地跑通：**无**（本轮未运行）。

---

# C. 真实失败证据链

## C1. 失败是什么

- **任务**：Square 要求把方形 nut 套到 peg 上；success = nut on peg；动作 7-D OSC delta；图像 84×84。
- **失败表现**：nut 未对准/未套入、掉落、接触后偏移；DP 图像策略 avg 0.80–0.92，即 8–20% 失败（作者报告）。
- **不是"完全不会抓"**：DP 在 Lift/Can 接近饱和；Square 的失败集中在精密插入/接触。

## C2. 证据（两类独立来源）

1. **DP 论文 Table 2**：Square 图像 DP-C 0.98/0.92（ph）、0.98/0.84（mh）；DP-T 1.00/0.90（ph）、0.94/0.80（mh）。失败率 8–20%。**作者报告**。
2. **2610.01626 §4.2**：robomimic 中位误差传播率 square 0.017、tool hang 0.026、lift 0.015、can 0.009；78% lift stamps 在 deadband；闭环稳定罕见。**独立测量**（同一 benchmark，不同论文）。
3. **DP 论文 §4.3**：action horizon 8 对多数任务最优；太长降低反应、太短损失一致性。**作者报告**；但只做任务级固定选择。

## C3. 机制解释（分层）

- **已支持**：固定 horizon 是任务级折中；误差传播是状态相关的；Square 是精密插入，接触阶段对误差敏感。
- **合理假设（未验证）**：在插入前 clearance 小的状态，长 horizon 会把小偏移放大/错过纠正窗口；短 horizon 更好；在自由空间，长 horizon 更好（一致性/算力）。
- **未知**：Square 的失败有多少来自 horizon，多少来自数据覆盖/多模态/控制器；Gate B 才能分解。

## C4. 反例/推翻条件

- 若固定 horizon 1/2/4/8/16 的成功率差异 <5 pp → horizon 不是有效变量，CAC 不成立。
- 若 always-short 已最好且 oracle 增益 <5 pp → 自适应无 success 空间。
- 若 clearance 与 oracle horizon 的 AUROC <0.6 → 几何余量不预测 horizon。
- 若失败主要是抓取/掉落而非插入对准 → 空间余量假设错位，换任务/机制。

## C5. 为什么不是工程 bug

- DP 是官方 baseline，Square 是标准任务；失败率在论文中报告，不是本地环境问题。
- 2610.01626 独立测得误差放大；不是单一 repo 的偶然。
- Gate B 会用同一模型/同一初始状态配对，排除渲染/种子/评估差异。

---

# D. 候选比较与淘汰理由

## D1. 三个不同科学问题

| | **P1（选中）CAC：承诺 horizon** | **P2：clearance-aware selection** | **P3：clearance auxiliary** |
|---|---|---|---|
| 科学问题 | 安全开环长度是否由局部几何余量决定？ | 几何余量能否比策略似然更好地选择采样 chunk？ | 用 clearance 辅助监督能否塑造更好的空间表征？ |
| 机制 | 用 clearance + 预测误差增长选执行长度 | 采样 K 个 chunk，用 clearance 分数选一个 | 训练时加 clearance 预测头，改变编码器 |
| 干预点 | **何时停止开环**（时序决策） | **选哪个动作**（测试时选择） | **学什么表征**（训练信号） |
| 最近邻 | 2609.00908（attention entropy）、2607.01804（visual monitor）、2608.15938 | Gated GeoBoN 2607.17454、RAIN 2610.19765、CAG 2602.17659 | EGR 2609.03142、auxiliary 任务、MetaFine encoder |
| 强简单基线 | 固定 8、always-short、不确定性、oracle | best-of-K by likelihood/ensemble、DP average | depth/pose auxiliary、无辅助、EGR |
| 第一项实验 | horizon 扫描 + clearance/oracle 相关（**最便宜**） | 采样 K chunk 的 clearance 分数 vs 成功（需采样/预测器） | 重训 3 个辅助变体（**最贵**） |
| 3090 | 低（不改模型） | 中（K× 采样 + 预测器） | 中高（多次训练） |
| 小论文潜力 | 中（决策规则 + 证据） | 中（选择准则 + 证据） | 中低（辅助任务易被视为 trick） |
| 最大风险 | always-short 已最好；2609.00908 已覆盖 | Gated GeoBoN/RAIN 已覆盖；best-of-K 强 | 归因难；增益来自参数/训练量 |

## D2. 为什么选 P1

- **最快证伪**：horizon 扫描不需要新模型；1–2 周可判断 J1/J2。
- **资产最可靠**：DP Square 有作者报告的正基线；P2/P3 也用它，但 P1 的第一实验更轻。
- **失败可复用**：若 P1 失败，DP/robomimic/渲染管线可直接用于 P2/P3；不浪费资产。
- **科学问题具体**："何时停止开环"是 action chunking 的核心决策，不是泛泛的"空间很重要"。
- **强基线清楚**：固定/always-short/不确定性/oracle；方法必须正面击败。

## D3. 为什么不选 P2/P3

- P2：Gated GeoBoN 已用几何一致性做 Best-of-N；RAIN 已用 action error 做 refine；clearance 选择是相邻变体；第一实验需要预测器/额外采样，成本更高。
- P3：辅助任务（depth/pose/affordance）很多；clearance 辅助的归因难；容易被审稿人视为"再加一个 head"；训练成本最高。
- 两者都保留为 pivot，不作为主选题。

---

# E. 最近邻竞争与创新性审查

| 工作 | 做到哪一步 | 与 CAC 的实质差异 | 能否直接替代 CAC？ |
|---|---|---|---|
| **2609.00908** Knowing When to Stop | 用 action expert 的 cross-attention entropy plateau 做 training-free 截断；π0.5/X-VLA；RoboTwin/LIBERO/真机 | 信号是**内部 attention 熵**，不是任务几何余量；VLA 级；不预测任务空间误差 | **可能**：若 entropy 在 Square/DP 上同样预测 horizon，CAC 的几何判据无增量 → Gate B/C 必比 |
| **2607.01804** VLA-Corrector | latent visual monitor 检测偏差 → 截断/重规划 | **反应式**（看已发生的偏差），不是**预测式**（看未来误差 vs clearance）；VLA | 不能完全替代：它不回答"执行前该多长" |
| **2608.15938** Open-Loop Revisited | 分析长开环主要帮助非马尔可夫演示；上下文足够长时闭环最好 | 任务级机制分析；无 clearance/状态级规则 | 不能替代：没有方法 |
| **2607.17454** Gated GeoBoN | Best-of-N 用 cross-view depth consistency 选 chunk；N=8 +1.7–2.1 pp | **选择** chunk，不是**决定 horizon**；几何一致性 vs clearance | 不能替代 P1（不同干预），但可替代 P2 |
| **2610.19765** RAIN | 预测 action error 决定 refine 程度 | refine 动作，不是 horizon；无几何余量 | 不能替代 |
| **2606.16504** APEX | 执行间隙适配；tracking error −41.2%；success +4.8–25.8 pp | 修**执行**误差，不决定**承诺长度** | 不能替代；是 Gate C 的强基线 |
| **2610.01626** Stability Assumption | 测 λ；发现状态依赖；建议显式反应性训练 | 测量/分析，无方法 | 不能替代；提供 CAC 的动机 |

**创新性判断**：CAC 的新意是**用任务空间几何余量 + 预测误差增长做承诺决策**，而不是 attention/visual deviation 触发。这个差异是**可证伪的**：Gate B/C 直接比较 geometry vs entropy vs visual monitor。若 geometry 不优于 entropy，CAC 不成立——这是诚实的风险。

**与上一轮结论的关系**：上一轮把"检测—纠正/自适应 chunk"列为饱和，并把 2609.00908 列为直接竞争。本轮选择 CAC 不是绕过该结论，而是把问题收窄到一个上一轮没有裁决的具体判据：**几何余量是否比内部熵/视觉偏差更能预测安全 horizon**。若 Gate B/C 显示几何判据没有增量，则上一轮的饱和结论成立，CAC 停止；这正是 Gate B 的停止条件。若几何判据有增量，它就是一个简单、可解释的替代判据，而不是"又一个自适应 chunk 系统"。

---

# F. 主选题完整方案

## F1. 方法设计

**输入：** 观测（图像 + proprio；Gate B 用特权状态）、H=16 action chunk、当前 clearance `c_t`。
**输出：** 执行步数 `h`。
**规则：** 选最大 `h` 使预测误差 `e_hat(h) < c_t - margin`；否则 h=1。
**误差模型（Gate C）：** 小 MLP/GRU，输入当前 nut-peg 偏移、速度、gripper、chunk 的前 h 步指令；输出未来 h 步的偏移轨迹；在 DP 的 rollouts 上训练（输入状态 + 实际执行 chunk，标签为实际偏移）。
**测试时：** 不需要特权状态时，用视觉/pose 估计 clearance（Gate C 的第二阶段；Gate B 先用特权状态验证现象）。
**与 DP 的关系：** 不改 DP 权重；CAC 是外层 commitment policy。

## F2. 强基线

- 固定 8（原配置）、固定 1/2/4/16；
- always-short（1）；
- 不确定性：denoising variance / ensemble variance；若用 ACT，attention entropy（2609.00908 式）；
- 反应式 visual monitor（VLA-Corrector 式）；
- APEX（执行间隙）；
- oracle horizon（特权，上界）；
- 任务级最优固定 horizon（验证集选）。

## F3. 评价指标

- 主：success（nut on peg）；
- 次：clearance violation rate、replan 次数、policy call 数、episode length、wall-clock；
- 失败模式：未对准/掉落/碰撞/超时；
- 等算力：固定 policy-call 预算下的 success；或 success vs calls 曲线。

## F4. Gate B（最小验证，未执行）

见 `reports/GATE_B_PROTOCOL.md`。核心：
- 训练 DP Square 图像基线 ≥0.70；
- 5 个 horizon × 100 episodes（配对）；
- J1：horizon 差异 ≥8 pp；
- J2：clearance 预测 oracle horizon AUROC ≥0.7；
- 通过 → Gate C；失败 → pivot。

## F5. 停止标准

- 基线 <0.60（两次尝试）；
- J1 <5 pp；
- J2 AUROC <0.6；
- always-short 最好且 oracle 增益 <5 pp；
- 环境/渲染 5 个工作日不能跑通。

## F6. 前两周计划

**第 1 周（平台与基线）**
- Day 1–2：安装 robomimic + DP；跑通 1 个 Square episode；确认 3090/驱动/依赖。
- Day 3：下载 raw Square mh（74 MB）；渲染 5 条 demo；检查键名/图像与 DP dataset 兼容。
- Day 4–5：渲染全量图像（5–10 GB）；启动 DP 训练（3000 epochs）。
- Day 6–7：训练监控；准备 horizon eval 封装与日志（clearance、chunk、replan）。
- **周末门槛**：基线 eval 100 episodes ≥0.70；若 <0.60，进入 fallback（ph/低维/ManiSkill）。

> 可选：若图像渲染/训练风险高，先用**低维 DP Square**（1.93 GB，小时级训练）做 2–3 天预检（见 `GATE_B_PROTOCOL.md` §3.1）；低维只验证管线和现象，不作为最终证据。

**第 2 周（现象验证）**
- Day 8：horizon 扫描 1/2/4/8/16 × 100 episodes（配对）；记录 success/clearance/失败模式。
- Day 9：补跑异常 horizon；检查 episode length/动作噪声。
- Day 10：计算 J1（配对 McNemar/bootstrap）；计算 oracle horizon。
- Day 11：计算 J2（AUROC/Spearman，按 episode bootstrap）；分层（ph/mh、成功/失败）。
- Day 12：决策：pass → 写 Gate C 方案；fail → pivot 评估（P2/P3/平台 fallback）。
- Day 13–14：写 Gate B 报告；不训练 CAC 方法。

## F7. 小论文与毕业论文

**小论文（方法型）**
- 题目：*Clearance-Aware Commitment for Action-Chunked Visuomotor Policies*。
- 贡献：一个任务空间 clearance + 误差增长的 commitment 规则/模型；证明它比固定/不确定性/反应式基线在等算力下更好；2 个精度任务（Square、ToolHang）+ 3 seeds + 100 episodes + 消融。
- 最低证据：Gate B 通过 + Gate C 的 2 任务对比；若只在 Square 有效，降级为 workshop/短文。
- 不是"再加一个模块"：主张是几何判据的预测力，消融直接比较 geometry vs entropy vs visual monitor。

**毕业论文（新问题）**
- 题目：*Online Spatial Commitment: Estimating Clearance and Switching Costs without Privileged State*。
- 新问题：**在线**估计 clearance/误差动力学（无特权状态）；切换成本（重规划延迟、时序一致性、观测中断）如何改变最优 horizon；多阶段长程任务。
- 为什么不是"离线变在线"：在线引入部分可观测、模型漂移、切换成本；需要新的估计/控制方法，而不是把 Gate B 的规则搬过去。
- 与新论文的区别：小论文用特权状态离线验证判据；毕业论文必须回答"部署时怎么知道"，并处理切换成本。
- 风险隔离：若小论文判据不成立，毕业论文可转向"在线 clearance 估计"的测量/估计问题，但仍依赖同一资产。

---

# G. 风险与转向方案

| # | 最可能失败原因 | 可观察预警信号 | 处理 |
|---|---|---|---|
| 1 | **always-short 已最好**，CAC 无 success 增益 | Gate B 中 h=1 成功率 ≥ 所有其他 horizon，oracle 增益 <5 pp | 停止 CAC 的 success 主张；转 P2（clearance-aware selection）或 P3（auxiliary）；或换长程任务（ToolHang/LIBERO）让 commitment 有价值 |
| 2 | **clearance 不预测 horizon** | J2 AUROC <0.6；clearance 与 oracle h 无单调关系 | 放弃几何版本；试误差增长/不确定性混合；若仍无效，停止 horizon 线，用同一资产做 P2/P3 |
| 3 | **平台/基线失败**（DP 训练 <0.60、渲染/旧栈问题） | 两次训练 <0.60；5 个工作日不能跑通 | fallback：Square-ph → 低维 DP → ManiSkill3 PickCube+ACT；若都失败，记录 BLOCKED 证据，换平台重做 Gate A |

**保留资产**：DP/robomimic/Square 数据、渲染管线、horizon eval 封装、clearance 日志；即使 CAC 失败，P2/P3 可直接复用。

---

# H. Sources、自检与完成

## H1. 关键来源（详见 `sources/sources.jsonl`）

- DP 2303.04137 [F]：Table 2 Square image 0.80–0.92；§4.3 horizon 8；§5 3000 epochs。
- DP repo [静态源码]：`square_image.yaml`；horizon 16/n_action_steps 8；MIT。
- robomimic 数据 [元信息]：Square ph 69 MB / mh 74 MB；PH 200/MH 300。
- 2610.01626 [F，上一轮]：square λ 0.017；状态依赖；deadband。
- 2609.00908 [A]：attention entropy 自适应截断。
- 2607.01804 [A]：VLA-Corrector 反应式截断。
- 2608.15938 [A]：开环/闭环分析。
- 2607.17454 [A]：Gated GeoBoN Best-of-N。
- 2610.19765 [A]：RAIN refine。
- 2606.16504 [P]：APEX 执行间隙。
- 2607.09825 [F，上一轮]：Near-Miss/No-Grasp 失败分类。
- ManiSkill3 2410.00425 [P]；ACT baseline README [静态源码]；MetaFine 2605.19986 [F，上一轮]。

## H2. 自检（摘要，详见 `reports/SELF_AUDIT.md`）

- 未把作者报告当本地复现；未把代码存在当跑通；未把相关性当因果；未忽略 always-short/固定 horizon 强基线；未为强制选题夸大创新；未虚构权重/数据/结果。
- 唯一主选题已选；Gate B 已冻结；两周计划已给；小论文/毕业论文贡献已分开；三个风险与转向已列。

## H3. 完成标记

`reports/COMPLETION.json`（round 4）。

---

## 附：为什么不是"又一份没有决定的报告"

- 本轮给了一个唯一主选题、一个可执行的平台、一个 1–2 周的第一实验、明确的通过/停止标准。
- 不保证方法有效；但保证失败时能在两周内知道，并保留资产转向。
- 若 Gate B 显示 horizon 无效或 always-short 最好，报告会明确建议 pivot，而不是继续给 CAC 改名。
