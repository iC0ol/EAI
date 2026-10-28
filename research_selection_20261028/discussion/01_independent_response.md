我先读取任务书与历史评估文件。

任务书与三份历史报告已读。现在开始独立检索（2023—2026-10-28，重点 2025/2026），先并行扫四个不默认复活旧路线的学习问题域。

第一轮检索显示这些方向 2025–2026 竞争已很密集。继续针对“可定位缺陷”做第二轮，优先找官方 issue / 代码级证据，而不是摘要级空白。

第二轮确认：chunk 边界、latency、tokenization、动作空间都已有 2025–2026 直接竞争。再用第三轮探测三个较少被“简单修复”覆盖的缺陷面，然后打开关键页面核验表格。

现在打开关键页面核验，而不是依赖搜索摘要。先核验三组最强竞争工作与缺陷证据。

核验结果显示：RTC、LiPo、CUPID、动作量化理论都已直接覆盖对应缺陷。再核验三篇 2026 年竞争工作的作者/状态，以及状态缺失实验的原文。

# DeepSeek 独立初筛意见（候选阶段）

**日期**：2026-10-28  
**模型**：deepseek-flash（经 Claude Code 客户端调用）  
**会话状态**：原指定会话 `9be4870e-04f0-446c-9adf-24281ae34cf0` 在本机恢复失败；本轮是**新会话**，未续接旧上下文，不声称记得旧对话。以下判断仅基于本轮读取的本地文件与公开检索。  
**独立性边界**：与 Codex 共享 D/M/U 历史背景，但未查看 `notes/` 中 Codex 候选，因此只能称“候选阶段独立检索”，不是完全盲审。  
**执行边界**：本轮未运行实验、未训练/推理、未下载权重或数据、未安装环境、未修改旧代码、未写或推送分支。

---

## 0. 结论摘要

| 候选 | 问题 | 判断 |
|---|---|---|
| C1 | 推理延迟下 action-chunk 边界不连续 | **淘汰**：2025–2026 已有推理时与训练时两代直接方法，且线性混合这一最强简单基线已是已发表方法的组成部分 |
| C2 | 本体状态捷径导致空间泛化退化；可靠性门控状态融合 | **探索级保留，但不是优先对象**：缺陷证据存在关键混淆，最近 2026 工作已系统比较状态接口；仅值得一次低成本全文补证与两周仿真诊断 |
| C3 | VLA 指令盲视 / 语言-动作绑定崩塌 | **淘汰**：2026 年多条数据与机制路线直接竞争，数据修复已声称大幅解决；且 VLA 训练成本与来源透明度不适合作为首篇小论文 |

**本轮没有 PRIORITY-GO 候选，不建议现在生成工作站任务书。** 最低代价的下一步是只读补证（见 §6），不是上机训练。

---

## 1. 检索与核验条件

- **检索截止**：2026-10-28；覆盖 2023–2026，重点 2025/2026。
- **工具**：WebSearch、WebFetch；实际打开了下列关键页面。PDF 文本抽取失败一次：RSS 2026 的 Legato PDF 返回二进制流，随后 `Read` 调用本地 poppler 失败（`GLIBC_2.38 not found`），因此 Legato 只读到 RSS HTML 摘要与检索摘要，**未读全文表格**。
- **来源缺口**：任务书提到的两个 `research_direction_audit_20261021` 文件未在本机与 GitHub main 找到，未冒充已读。U 的补充界限来自本地 `U_v3_morning_report.md` 与任务书，作为待核实背景。
- **未做**：未查看 Codex 候选；未使用任何私有标签、scene JSON、QC、family 或 Phase 3 预测；未进行模型推理。

---

## 2. 候选 C1：推理延迟下的 action-chunk 边界不连续

### 问题定义
在 action-chunked flow/diffusion policy 中，当推理延迟使当前 chunk 未执行完就被新 chunk 替换时，拼接处出现位置/速度不连续，表现为停顿、jerk、模式切换；动态任务（抛掷、举重、精密插接）的任务质量下降。限定条件不是“chunk 大小”，而是**延迟 > 0 且 chunk 被异步替换**。

### 可定位缺陷证据（来源事实）
- **RTC**（NeurIPS 2025）：摘要明确说 action chunking “does not solve latency”，会产生 “pauses or out-of-distribution jerky movements at chunk boundaries”；实验为 12 个 Kinetix 仿真任务 + 6 个真实双臂任务。**摘要页未给数字与基线名**。
- **LiPo**（arXiv:2506.05165，2025-06-05）：摘要说 “discrete action chunking … introduces discontinuities at chunk boundaries”，会 “degrade motion quality”，动态任务中尤其影响动量传递与系统稳定；页面仅有 7 图 1 表，**未给具体数值**。
- **Legato**（RSS 2026）：批评 RTC 是策略外部修补，会造成 “spurious switches between modes” 与 “paths that are not inherently smooth”；在 5 个真实操作任务上相对 RTC 报告约 **10%** 的平滑度与完成时间改进。

### 最直接 3 篇近邻

| 工作 | 作者/年份/状态 | 链接 | 实际读到范围 |
|---|---|---|---|
| Real-Time Execution of Action Chunking Flow Policies（RTC） | Black, Galliker, Levine；NeurIPS 2025 | [NeurIPS page](https://papers.neurips.cc/paper_files/paper/2025/hash/300ccb2187dedd4edcc07f7e76d8e553-Abstract-Conference.html) | 摘要页；无数字、无基线名 |
| LiPo: Lightweight Post-optimization Framework for Smoothing Action Chunks | Son & Park；arXiv 2506.05165，2025；检索另称 IJCAS 2025，未在 arXiv 页核实 | [arXiv](https://arxiv.org/abs/2506.05165) | 摘要页；未读表格 |
| Learning Native Continuation for Action Chunking Flow Policies（Legato） | Liu, Yu, Zhao 等 12 人；RSS 2026 | [RSS page](https://www.roboticsproceedings.org/rss22/p058.html) | RSS HTML 摘要；PDF 全文抽取失败 |

补充检索到但未打开全文的近邻：Adaptive Action Chunking via Multi-Chunk Q Value Estimation（arXiv:2605.10044）、PACE（phase-aware chunk execution）。仅作覆盖提示，不作证据。

### 最强简单基线
**重叠 chunk + 线性混合**（LiPo 的第 2 个组件），或 ACT 的 temporal ensembling，或直接降低重规划频率。若线性混合已把 seam jerk 降到 chunk 中段水平且任务成功率不变，则新机制没有剩余空间。

### 最小机制假设
边界不连续主要来自“新 chunk 以过期观测为条件、且未约束与已执行动作的连续性”；在 seam 处做有界 jerk 优化或训练时连续性正则，可降低 jerk 而不改变策略。**但该假设已被 LiPo 的组件 2+3 与 Legato 的训练时 continuation 分别覆盖**，不能称为新机制。

### 任务后果
jerk、停顿、模式切换；动态任务中可能掉物或失败。RTC 摘要声称在极端延迟下仍能完成“点火柴”这类精密任务。

### 资源/代码/权重/数据
ACT、Diffusion Policy 官方代码公开，3090 可跑小规模；Kinetix 与 RTC 官方实现、LiPo 代码、Legato 代码的公开状态**本轮未逐一核实**。真实双臂平台不具备。

### 最强反证
- RTC 已覆盖推理时异步执行；Legato 已覆盖训练时 continuation；LiPo 已覆盖混合 + jerk 优化。
- 线性混合是极低成本的基线；若它已足够，C1 只剩工程实现。
- “jerk 降低”不等于任务成功率提升；若没有任务后果，属于测量问题。

### 两周首次证据与停止条件
在公开 chunked policy 上注入可控推理延迟，测 seam jerk vs chunk 中段 jerk；加线性混合。**停止条件**：线性混合使 seam jerk 接近中段，或任务成功率对 seam 不连续不敏感（阳性对照：人为注入大不连续，成功率不降）。出现任一即停止，不扩展新模块。

### 判断
**淘汰。** 2025–2026 已有推理时与训练时两代直接竞争，最强简单基线是已发表方法的组成部分；剩余空间是工程优化，不是可发表的学习机制。

---

## 3. 候选 C2：本体状态捷径与空间泛化；可靠性门控状态融合

### 问题定义
在视觉运动策略中，本体状态输入在训练分布内提升精度/接触任务，但在空间分布偏移（物体高度、水平位置变化）下可能成为 shortcut，使策略依赖“状态-动作轨迹记忆”而忽略视觉。问题是：是否存在一种仅依赖合法观测的**可靠性门控**，让状态在接触/精密阶段可用、在视觉可靠时不被过度依赖，从而同时保留分布内精度与空间 OOD？

### 可定位缺陷证据（来源事实 + 独立复核）
- **State-free Policy**（arXiv:2509.18644，2025-09）：作者报告包含状态会使策略“overly reliant”并“overfitting to training trajectories”，空间泛化下降；高度泛化平均成功率 **0% → 85%**，水平泛化 **6% → 64%**。方法同时去掉状态、改用 relative end-effector action、双广角腕相机。
- **独立复核（项目页）**：作者自述“removing the overhead camera improved spatial generalization”。这意味着**状态移除、相机配置、动作空间三者没有完全解耦**；0→85 不能单独归因于“状态捷径”。这是 C2 的关键内部混淆，不是论文原话的结论。
- **How Should VLA Models Use Proprioceptive State?**（arXiv:2608.03052，2026-08）：45 个原子任务、20 个组合任务、历史 1–96 帧。无状态基线 **54.6%**；五种状态接口点估计均更高（+1.1 到 +3.1），仅 state prompt **57.7%** 的置信区间排除零 **[0.2, 6.1]**。重排列偏好 state prompt（**68.7%，+7.0**）；articulation 偏好 VLM prefix（**68.8%，+6.1**）；精密旋钮/开关偏好 state expert（**42.8%，+3.3**），VLM prefix 反而低于基线（**38.3%，−1.2**）。结论是“没有 task-agnostic 最佳接口”；8 帧历史是实用点；**没有学习型门控，也没有空间泛化实验**；多数比较单训练 seed。
- **Blackout vs. Freeze**（arXiv:2609.39145，2026-09）：π0.5 与 GR00T 在相机黑屏/冻结下，本体状态可部分补偿缺失的机器人自身视觉，但**无法在腕部物体信息缺失时恢复成功率**；夹爪闭合后腕部黑屏会显著增加掉物，尤其无本体状态时。这说明状态是有用的，简单压制状态会伤害接触任务。

### 最直接 3 篇近邻

| 工作 | 作者/年份/状态 | 链接 | 实际读到范围 |
|---|---|---|---|
| Do You Need Proprioceptive States in Visuomotor Policies?（State-free Policy） | Zhao 等 13 人；arXiv 2509.18644v2，2025 | [arXiv](https://arxiv.org/abs/2509.18644)；[项目页](https://statefreepolicy.github.io/) | 摘要 + 项目页；未读全文消融 |
| How Should Vision-Language-Action Models Use Proprioceptive State? | Y. Zhao 等 8 人；arXiv 2608.03052v1，2026-08 | [arXiv](https://arxiv.org/abs/2608.03052) | ar5iv 结果/结论段；读了主要数字 |
| Blackout vs. Freeze: Analyzing Physical Failure Modes of VLAs under Camera Faults | Suh, Han, Gholami, Jo；arXiv 2609.39145v1，2026-09 | [arXiv](https://arxiv.org/abs/2609.39145) | 摘要；无成功率数字 |

### 最强简单基线
**State-free**（直接去掉状态）与 **state dropout**（训练时随机屏蔽状态）。此外，2026 接口论文的 **feature modulation** 已是一种软条件化；若它与门控同效，门控没有独立价值。最强基线是“state-free + 双腕相机 + relative action”这一组合。

### 最小机制假设
逐时间步门控 `g_t = f(视觉可靠性/接触阶段)`，动作由状态条件分支与纯视觉分支加权；训练时配合 state dropout 与空间偏移增广；推理只用合法观测。关键不是“加一个 gate”，而是验证门控是否在**空间偏移**下改变动作排序/决策，且不牺牲接触精度。该假设与 feature modulation 的差别仅在“逐时间步可靠性选择”，属于窄增量。

### 任务后果
空间 OOD 成功率 vs 分布内精密/接触成功率之间的权衡；若门控只改善辅助损失而不改变动作，任务无后果。

### 资源/代码/权重/数据
LIBERO、Robomimic、ACT、Diffusion Policy 公开，3090 可完成小规模训练；State-free 项目页**未发布代码、权重或数据**，只给 arXiv 与 LeRobot π0 集成示例；2026 接口论文代码状态未核实；Blackout 使用 π0.5/GR00T，成本高，但 C2 的两周诊断不需要复现它。真实机器人不可用。

### 最强反证
1. **混淆**：state-free 的收益可能主要来自双广角腕相机与 relative action，而非去状态；若控制相机与动作空间后空间差距消失，C2 的前提不成立。
2. **直接竞争**：2026 接口论文已系统比较五种状态接口，结论是“没有通用最佳接口”，并给出路由规则；逐时间步门控可能只是 feature modulation 的变体。
3. **测量**：仿真中的本体状态通常低噪声、近似真值；真实本体状态的噪声/延迟结构可能不同，仿真缺陷未必复现。
4. **单 seed**：接口论文多数比较单训练 seed，效应量（+1.1 到 +3.1）较小，门控的增益可能落在噪声内。

### 两周首次证据与停止条件
先做**受控 2×2**：状态有无 × 相机配置（原配置/双腕广角），在公开仿真任务上使用预登记的空间偏移（物体高度/水平位置），3 seeds；主指标为偏移条件下的成功率，次指标为分布内成功率与状态消融敏感度。**阳性对照**：注入状态噪声/打乱状态，确认策略确实使用状态。若控制相机与动作空间后没有可复现的空间差距，停止（MEASUREMENT-LIMITED）。若有差距，再比较 state dropout 与门控；若两者在所有条件下同效，停止。样本量不预设，先按基准方差与最小可检测效应估算。

### 判断
**探索级保留，不是优先对象。** 缺陷线索可核验，但被相机/动作空间混淆；最近 2026 工作已覆盖接口空间，门控只剩窄增量。只有全文补证确认“无门控、无空间泛化实验、且 state-free 消融未解耦相机”后，才值得一次两周仿真诊断；**当前不具备工作站任务书资格**。

---

## 4. 候选 C3：VLA 指令盲视与语言-动作绑定崩塌

### 问题定义
VLA 在标准基准上成功率高，但目标物体在演示中总出现在固定位置，指令可由视觉单独预测；测试时改名目标，策略仍抓习惯位置，说明语言-动作条件互信息坍缩。问题是：能否用合法的最小干预恢复指令-动作绑定，而不全量重训 VLA？

### 可定位缺陷证据（来源事实）
- **Galahad**（匿名仓库，under review）：基础策略在 LIBERO object 任务 **198/200** 成功；把指令替换为 `"xxx"` 后仍有 **89/200** 完成，抓向惯常位置。反事实测试中命名物体到达 **57/160**，随机运动下限 **12%**。去混淆数据 + rank-32 更新后报告 **97.7%**。但基础策略未命名、权重不发布、早期数字已被作者声明作废——**来源透明度弱**。
- **LangForce**（ICML 2026）：把缺陷定义为 “Information Collapse”：goal-driven 数据使指令可由图像预测，指令-动作条件互信息消失；用 Bayesian decomposition + latent action queries，报告 OOD SimplerEnv **+11.3%**。
- **LIBERO-Gen**（ICML 2026）：Pi0.5 在 Spatial-CG **64.0%**、Task-CG **21.2%**；识别出 “action binding collapse”（指令-动作错配）与感知不稳定。
- 补充：CofactVLA（NeurIPS 2026，检索页称 vision-override，+52.3% absolute OOD）、DISC（arXiv:2605.20856，observation leakage）——仅检索摘要，未打开全文。

### 最直接 3 篇近邻

| 工作 | 作者/年份/状态 | 链接 | 实际读到范围 |
|---|---|---|---|
| LangForce: Bayesian Decomposition of VLAs via Latent Action Queries | Lian 等 9 人；ICML 2026 poster | [ICML page](https://icml.cc/virtual/2026/poster/65457) | 摘要页；读了缺陷定义与 11.3% |
| Dismantling the Illusion of VLA Competence via Explicit Distributional Shifts（LIBERO-Gen） | Zhou 等 10 人；ICML 2026 poster | [ICML page](https://icml.cc/virtual/2026/poster/64080) | 摘要页；读了 64.0/21.2 |
| Galahad: Instruction Blindness in VLA Policies | 匿名；under review，2026 | [GitHub](https://github.com/phi-monster/Galahad) | README/项目页；数字为作者声明，未独立复现 |

### 最强简单基线
**反事实指令增广 / 去混淆数据配方**（Galahad 的数据侧做法），以及 paraphrase/negation 增广、instruction dropout。若数据侧修复已把改名到达率从 57/160 提到 97.7%，则新机制的必要性不成立。

### 最小机制假设
在 action head 侧加指令-动作对比/PMI 辅助目标，配合反事实指令对训练，阻止 action head 忽略语言；不全量重训 VLM。**但 LangForce 已做 Bayesian 分解与 PMI，CofactVLA 已做去混淆，Galahad 已做数据 + rank-32**；机制空间基本被占满。

### 任务后果
改名后抓错物体，是安全相关的真实后果；0–1% 的改名正确率是强缺陷信号（若来源可信）。

### 资源/代码/权重/数据
LIBERO 仿真公开；OpenVLA-7B LoRA 在 3090 上可勉强运行但慢；SmolVLA 更可行；Galahad 权重/数据承诺审稿后释放，当前不可用；LangForce 代码状态未核实；4×4090 未核验。对首篇硕士论文，VLA 训练与评测成本偏高。

### 最强反证
- 数据侧修复已声称解决大部分问题；若属实，缺陷是数据分布问题，不是需要新机制的架构问题。
- LangForce / CofactVLA 已在机制层给出直接方案。
- Galahad 来源匿名、基础模型未命名、早期数字作废；“xxx”测试也可能混合了 prompt 分布偏移，而非纯粹指令盲视。
- 标准 LIBERO 的改名测试可能被位置先验主导，换 benchmark 后效应量未知。

### 两周首次证据与停止条件
在公开 VLA checkpoint（优先 SmolVLA/OpenVLA-LoRA）上复现改名测试：原指令 vs 改名指令的命名物体到达率。若差距 <10 个百分点，缺陷未复现，停止；若差距大，再比较指令增广 vs 小型辅助损失。**停止条件**：增广已闭合差距，或基础模型本身已能跟随改名，或 3090 无法在预算内完成一次可解释的评测。

### 判断
**淘汰。** 2026 年直接竞争密集，数据修复已给出强简单基线，VLA 成本高且关键来源不透明；不适合作为当前首篇小论文的主线。

---

## 5. 已扫描但未立候选的方向

| 方向 | 代表 2025–2026 工作（检索层） | 淘汰理由 |
|---|---|---|
| 演示子集选择 / 数据 curation | CUPID（CoRL 2025，<33% 数据）、PROSE（NeurIPS 2026）、SIEVE（2026）、DataMIL（ICLR 2026）、COLLAGE（CoRL 2025） | 已有影响函数、覆盖度、结构先验多条路线；CUPID 已报告分布偏移下的鲁棒策略识别；简单基线（全量/随机）明确 |
| 动作 tokenization / 量化 | OAT（2026）、ProAct（2026）、CAP（2026）、TOAST（2026）、BAAT（2026）、Understanding BC with Action Quantization（2026） | 2026 年已从压缩、顺序、可预测性、鲁棒性、理论误差传播多角度覆盖；理论文已给量化误差沿 horizon 传播的样本复杂度 |
| 动作空间设计 | Demystifying Action Space Design（ICML 2026，13,000+ 真实 rollout、500+ 模型） | 已系统比较 delta/absolute、joint/task space；简单结论已明确，难以再立新题 |
| 相机故障 / 缺失模态 | Blackout vs. Freeze（2026）、DisDP（RLC 2025）、RL4IL（2026） | 黑屏/冻结、腕部/场景、有无本体状态已被系统测试；黑屏训练与嵌入替换已有缓解 |
| 持续学习 / 顺序微调 | REGEN（2026）、D2R（2026，LoRA 崩塌到 11.7%）、FAGR（RA-L 2025）、TOPIC（2025） | 生成回放、世界模型回放、适配器多条路线；直接竞争密集 |
| 跨具身协同训练负迁移 | X-Diffusion（ICRA 2026）、Co-training 系统研究（2026）、OPFA（2026） | 数据筛选、噪声时间步、共享几何 latent 已覆盖 |
| 数据多样性 / 速率偏差 | Is Diversity All You Need（2026）、OXE-AugE（ICML 2026） | 场景多样性、动作速率去偏已有大规模实证 |

这些方向共同说明：**2025–2026 的“缺陷发现”速度很快，很多看似空白的问题在半年内已被数据侧或推理时方法覆盖。** 这也解释了为什么本轮不应为了凑数保留候选。

---

## 6. 最终排序与建议

1. **C2（探索级，唯一保留）**：唯一还有可检验残余的问题是“逐时间步可靠性门控能否在空间偏移下保留状态带来的接触精度”。但前提未清：state-free 的收益与相机/动作空间混淆；2026 接口论文已覆盖大部分接口空间。**先做只读全文补证，不生成工作站任务书。**
2. **C1（淘汰）**：推理时与训练时两代方法 + 线性混合基线，剩余空间是工程。
3. **C3（淘汰）**：数据修复 + 多条机制路线 + 高算力 + 来源不透明。

**为什么没有优先对象**：三个候选都满足“有缺陷线索”，但都不满足“最小机制尚未被 2025–2026 直接工作覆盖，且两周内可在 3090 上产生判别性证据”。C2 最接近，但它的缺陷证据本身需要先被解耦；在解耦之前投入训练，会重复 M/U 的教训——把测量/实现问题误当成机制问题。

---

## 7. 最低代价补证清单（只读，不上机）

| 优先级 | 补证 | 目的 | 预计成本 |
|---|---|---|---|
| 1 | 读 2608.03052 全文附录，确认是否有学习型 gate、空间偏移实验、state dropout 训练 | 判断 C2 是否已被覆盖 | 2–3 小时 |
| 2 | 读 2509.18644 全文消融，确认 state 移除是否与相机/动作空间解耦 | 判断 C2 缺陷是否真实 | 2–3 小时 |
| 3 | 读 RTC、Legato、LiPo 全文，确认线性混合是否已作为独立消融、是否测任务成功率而非仅 jerk | 关闭 C1 | 2–3 小时 |
| 4 | 读 LangForce、LIBERO-Gen、CofactVLA 全文，确认指令增广是否已是基线、改名测试是否饱和 | 关闭 C3 | 3–5 小时 |

若第 1、2 项发现 C2 已被覆盖或缺陷不可解耦，则本轮**全部淘汰**，输出“当前无合格候选”，不进入工作站阶段。

---

## 8. 建议的下一轮交叉质疑（三个具体争议）

1. **C1**：请 Codex 查 RTC/Legato/LiPo 的代码与消融，回答“线性混合单独是否已把 seam jerk 降到中段水平；jerk 与任务成功率是否有相关性”。若答案是“是”，C1 永久关闭。
2. **C2**：请 Codex 查 state-free 的消融与 2026 接口论文附录，回答“state 移除是否与双腕相机/relative action 解耦；仿真中 ACT/DP 能否复现 state 引起的空间差距”。若不能，C2 降为 MEASUREMENT-LIMITED。
3. **C3**：请 Codex 查公开 VLA checkpoint 的改名测试与指令增广基线，回答“改名差距是否在公开模型上可复现；数据增广是否已闭合”。若已闭合，C3 无方法论文空间。

我保留的分歧点：C2 是否只是 feature modulation 的变体；如果 Codex 能证明 2026 接口论文的 feature modulation 已实现逐时间步可靠性选择，我将撤回 C2 的“残余空白”判断。

---

## 9. 来源（本轮实际访问）

- [RTC, NeurIPS 2025](https://papers.neurips.cc/paper_files/paper/2025/hash/300ccb2187dedd4edcc07f7e76d8e553-Abstract-Conference.html)
- [LiPo, arXiv:2506.05165](https://arxiv.org/abs/2506.05165)
- [Legato, RSS 2026](https://www.roboticsproceedings.org/rss22/p058.html)
- [State-free Policy, arXiv:2509.18644](https://arxiv.org/abs/2509.18644) / [项目页](https://statefreepolicy.github.io/)
- [How Should VLA Models Use Proprioceptive State?, arXiv:2608.03052](https://arxiv.org/abs/2608.03052) / [ar5iv](https://ar5iv.labs.arxiv.org/html/2608.03052)
- [Blackout vs. Freeze, arXiv:2609.39145](https://arxiv.org/abs/2609.39145)
- [LangForce, ICML 2026](https://icml.cc/virtual/2026/poster/65457)
- [LIBERO-Gen, ICML 2026](https://icml.cc/virtual/2026/poster/64080)
- [Galahad, GitHub](https://github.com/phi-monster/Galahad)
- [CUPID, arXiv:2506.19121](https://arxiv.org/abs/2506.19121)
- [Understanding Behavior Cloning with Action Quantization, arXiv:2603.20538](https://arxiv.org/abs/2603.20538)
- [Demystifying Action Space Design, ICML 2026](https://icml.cc/virtual/2026/poster/65967)

**记录**：RSS PDF 文本抽取失败（poppler `GLIBC_2.38` 缺失），Legato 未读全文表格；其余页面为摘要/项目页/HTML 结果段，未读全文的均已在表中标注“实际读到范围”。
