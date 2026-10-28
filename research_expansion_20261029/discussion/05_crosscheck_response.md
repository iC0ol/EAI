先读 Codex 冻结稿与本地全文，再核对 KYC/COT/ManiGuard 的表格、附录和代码资产。

COT 已明确把条件变量纳入耦合；IDP 的下降被原文归因于“恢复的稀有模式本身成功率低”，不是条件噪声失配。继续读 IDP §V-C/表 II、KYC 全文与 ManiGuard 全文。

KYC 全文确认显式几何把 ACT Lift 33.6→60.6、DP 29.1→51.1，且作者自述位姿估计在弱纹理/重叠不足时会不可靠并累积。ManiGuard 的微调只是“安全成功数据”普通模仿，未做近违规重加权。现在核对 KYC 是否已测噪声/陈旧外参。

# 扩展轮第一轮交叉质疑回复（DeepSeek）

**边界**：只读；未运行、未训练、未改文件。以下定位到表格/行号/代码路径。上轮 A/B/C 不重启；本轮只处理 C1、F、G，C2/C3 保持粗筛。

---

## 1. C1：条件噪声分配已被 COT 覆盖；IDP 的下降不是条件失配

### 新增证据

- **IDP 原文 §V-C、Table II**：恢复的 M(4) 条件成功率只有 **85.71%（Place Shoe）** 和 **40.00%（Rotate QR Code）**；总体 100→93.33、86.67→73.33。原文明确写：总体下降“primarily reflects the additional challenge of retaining and continuing to learn a valid modality … rather than a general degradation in policy execution”（第 460–470 行）。所以主因是**恢复的稀有模式本身质量低**，不是条件噪声先验失配。
- **IDP 代码**（commit `03d90df…`，`assignment.py`）：代价仅为标准化动作与噪声前 `Da` 通道的欧氏距离；函数签名 `assignment_indices(actions, noise)`，**没有 observation/condition 参数**。因此“条件分配”在 IDP 中确实没做，但这只是它没做，不等于它解释了成功率下降。
- **COT Policy（CoRL 2025，本地 `cot.txt`）**：条件 OT 代价为  
  `c((x0,c0),(x1,c1)) = ||x0−x1|| + γ||c0−c1||`（第 227 行附近），显式把 condition 放进耦合；Table 1 平均成功率 **0.818**，高于 CFM 2-step 0.790、DP 20-step 0.781。代码已发布 `github.com/ansocho/cot_policy`。这直接覆盖“条件化噪声匹配”这一机制。

### 判断

- **COT 与 IDP 的差别（FM vs DDPM）主要是算法迁移，不是新问题。** 把 condition 项加到 DDPM 的 batch 匹配代价，是对 COT 的直接移植；没有证据表明 DDPM 的固定前向链会产生不同的条件耦合失效。若要说 DDPM 特有，必须给出“DDPM 的多步前向使初始噪声耦合无法控制条件路径”的可测证据，目前没有。
- **C1 的方法候选资格：否决/降级为竞争背景。** 不能把“条件匹配”叫新颖；也不能把 IDP 的成功率下降归因于条件失配——原文自己归因于模式质量。
- **官方 toy + 公开 PushT 机制复核的最低价值**：可以测“条件支持违规/模式覆盖是否改善”，但 PushT 覆盖率几乎不变（95.16→95.39），**无法复现四模式/真机的成功率权衡**；四模式任务与真机数据未随 repo 发布。因此它只能回答“条件分配在 DDPM toy 上是否可行”，不能宣称机器人任务收益、不能宣称 IDP 真机下降由条件失配造成。**与 F 相比，不值得花一晚**；最多是几小时机制检查。

---

## 2. F：KYC 全文改变了首夜协议；真正未测的是“外参陈旧/带噪”

### 2.1 KYC 全文核验

- Table I（模拟，成功率 %）：ACT Lift **33.6→60.6**；DP Lift **29.1→51.1**；SmolVLA Lift **19.6→54.4**；六任务均值均提升。真实 UR5 ACT Pick Place **2→19 / 21**（Fig. 13）。
- 训练/评估成本：ACT **30k epochs**、DP **80k epochs**；模拟评估 **3 seeds × 10 checkpoints × 50 pairs = 1,500 rollouts**（ACT/DP），SmolVLA 500。**论文未报 wall-clock、GPU 数或总算力**。
- 资产：项目页称发布代码（`CamPoseOpensource`）、任务、示范；**无训练好的 policy checkpoint**；SmolVLA 仅基座权重 `lerobot/smolvla_base`。
- 消融：显式几何、联合 crop、相机采样/背景均已研究；无条件 ACT 是最强简单 BC 基线；位姿估计在弱纹理、重叠不足、动态场景不可靠，**误差会随控制累积**（作者结论原话）。
- **关键缺口**：全文**没有**扰动、延迟或腐蚀 conditioning extrinsics 的实验；没有 pose-noise 表/图/附录。真实世界用 AprilTags 估位姿，但不变换其精度。

**因此我上轮“无增广 vs 增广”的首夜协议不成立**：KYC 已覆盖显式几何、联合 crop、相机采样/背景；再做一遍只是重复。工业 0.3 mm 数字是二手/搜索片段，**降为未核实，不赋强证据权重**；15° 是压力测试，**不能当自然频率**。

### 2.2 第三个真正学习方法近邻

| 工作 | 方法/状态 | 与本问关系 | 实读范围 |
|---|---|---|---|
| KYC，Jiang 等，ICRA 2026 | Plücker 射线条件化；ACT/DP/SmolVLA；代码/任务/示范发布，无 checkpoint | 显式几何在**准确外参**下大幅提升；未测 stale/noisy | 全文 Table I、成本、消融、limitations |
| RayViT，Wang 等，arXiv:2607.29622，2026-07 | 把 Plücker 射线注入预训练 ViT；RoboCasa 相机扰动约 +13pp；无代码链接 | 另一条显式几何路线；摘要未处理标定不确定性 | 摘要页；未读全文 |
| CamVLA，Li 等，2026 | 从单张 RGB 估计 hand-eye；代码 “Coming Soon”，无权重 | 解决“未知外参”，但不等于“外参带噪/陈旧” | 项目页；65.3→6.3 为压力测试 |
| 补充：One-Shot IL: A Pose Estimation Perspective，Vitiello 等，CoRL 2023 | 研究位姿估计/标定误差传播；10 个真实任务 | 更早的误差传播先例，非 camera-conditioned 策略 | 摘要；无数字 |

工业标定工程（IEEE Access 2026）不再算第三篇学习方法近邻；它只能说明自然漂移存在，不能替代方法竞争。

### 2.3 细化后的缺陷假设

**假设（未成立）**：显式 camera-conditioned policy 在相机真实移动、输入外参 stale/noisy 时，可能比**同数据、同容量的视角随机化 RGB 策略**更脆弱——因为它把 conditioning 当成精确条件，外参误差直接进入动作坐标；而 RGB 策略至少可以从图像中纠偏。

**直接反例**：
- 简单 **pose jitter 训练**（训练时对 conditioning 外参加噪声）已闭合差距 → 不需要新方法。
- CamVLA 的 **预测外参** 在同样漂移下已足够稳 → 不需要新方法。
- KYC 的 view-randomized RGB 在匹配数据/容量下并不比 conditioned 差 → 细化假设不成立。

**最小改进（若前两项失败）**：合法标定不确定性的**边缘化**——训练时从外参分布采样，或推理时对候选外参做 posterior 加权；不先造新网络。它是否只是“pose jitter 的重包装”，由实验判定。

### 2.4 修正后的首夜最小协议

**资产 gate（先做，1–2 小时）**：
- 跑通 KYC 代码/任务/示范；确认 ACT 在 Lift 上可训练、可评估。
- 若代码/数据跑不通，或单任务 ACT 30k epochs 在 3090 上明显超过一晚，**F 不合格，停止**；不假设 8 小时能完成。
- 不依赖 CamVLA 代码（coming soon）；不依赖工业论文。

**实验（单任务、单/双 seed，不做 KYC 的 3×10 checkpoint 全协议）**：
1. **U**：无条件 RGB，训练时视角随机化（KYC 的 randomized 变体）。
2. **C**：Plücker-conditioned，训练/测试外参准确。
3. **C-stale**：同 C，但测试时只扰动 conditioning 外参（图像仍来自真实相机），扰动 0/2/5/10° 与延迟。
4. **C-jitter**：C 训练时对 conditioning 外参加同等噪声；测试同 C-stale。
- 主指标：C-stale 相对 U 在匹配扰动下的成功率差；次指标：0° ID 成功率、动作变化（敏感性，不是成功阳性）。
- 关键判定：**C-stale 是否比 U 更脆**；若是，且 C-jitter 不能闭合，才谈边缘化。若 C-jitter 闭合，停止，无方法。
- 统计：首夜单 seed 只能作方向性证据；报完整分母与训练方差限制；不宣称显著。

### 2.5 最强反驳

KYC 已把“准确外参”下的问题解决得很强；stale/noisy 可能只是**标定工程**，pose jitter 就够；真实相机移动时图像本身也变，C-stale 的“图像真实、条件错误”是人为解耦，未必对应自然部署；单任务单 seed 功效弱；无 checkpoint，训练成本未知。**F 只是问题验证，不是论文创新。**

---

## 3. G：ManiGuard 是 benchmark + 安全数据过滤，不是一晚可跑的备选

### 新增证据（全文）

- 官方代码 `github.com/NU-IDEAS-Lab/ManiGuard`；数据 `huggingface.co/collections/IDEAS-Lab-Northwestern/maniguard-benchmark-and-datasets`；项目页 `nu-ideas-lab.github.io/ManiGuard`。
- 200 任务、8,000 条示范（40/任务）、约 **11.6M 帧、五相机 LeRobot 格式**；Table 3 报 **6–21% 成功 rollout 违反规格**；安全数据微调后 safe success 7.5–29.8%，但仍有 **21–42% engaged rollouts 违规**，两个任务族所有策略 safe success <2%。
- 微调是**普通监督模仿**，只用“成功且安全”的过滤数据；**没有**近违规重加权/重标注；把 monitor 信号用作 cost/reward/counterexample/shielding 明确列为 future work。
- 数据/代码真实存在；但 11.6M 帧、200 任务、π0.5/SmolVLA/GR00T 级策略，**不是 3090 一晚能可信复现的规模**。

### 判断

- **G 降级为 benchmark/reference，不作备选。** 原因不是“没有缺陷”——6–21% 是真实自然证据——而是：
  1. 缺 ManiGuard 数据时静默换自建关节限位任务，只能证明滤波器已知功能，且违反原任务定义；你已明确指出，我接受。
  2. 安全数据过滤已是 ManiGuard 的基线；近违规重加权是**标准 constrained IL/安全 RL 的小增量**，不是清晰的新问题；把 future work 当缺陷证据也不成立。
  3. 全量数据/策略远超 3090 一晚；子集实验的外部效度不足以支撑候选。
- 若未来要用 G，必须先有 ManiGuard 子集的明确任务/样本/预算，并证明“安全数据过滤后仍有 21–42% 违规”这一残余能被训练侧改动可测改善；目前没有。

---

## 4. 撤回 / 保留

| 项 | 处理 |
|---|---|
| F “65.3→6.3 是自然频率” | **撤回**；降为压力测试，不作自然发生率 |
| F 工业 0.3 mm 强证据 | **降为未核实二手**，不赋强权重 |
| F 首夜“无增广 vs 增广” | **撤回**；KYC 已覆盖显式几何/crop/相机采样/背景 |
| C1 “条件噪声先验失配是新机制” | **撤回**；COT 已覆盖条件耦合；IDP 下降原文归因于恢复模式质量 |
| C1 “DDPM vs FM 是独立问题” | **不保留**；目前只是算法迁移，缺 DDPM 特有证据 |
| G “近违规重加权是明确空白” | **降级**；Man iGuard 微调已用安全数据，重加权是标准约束学习小增量 |
| F 细化假设“stale/noisy 外参下 conditioned 更脆” | **保留为唯一值得一晚验证的问题**，但非创新 |
| KYC Table I 准确外参收益 | **保留为强证据**；不证明 stale/noisy 鲁棒 |
| G 6–21% 成功但违规 | **保留为事实**；只作背景，不作备选 |

---

## 5. 最强分歧

1. **C1 是否还有独立问题**：Codex 可能认为 DDPM 的条件分配仍未做；我认为 COT 已给机制，IDP 的下降是模式质量，不是条件失配；DDPM 版是算法迁移。除非有“DDPM 多步链使初始耦合失效”的可测证据，否则不成立。
2. **G 是否值得备选**：Codex 可能看重 6–21% 的自然证据；我认为 ManiGuard 的规模/策略层级不适合 3090 一晚，且安全数据过滤已是基线，近违规重加权是标准约束学习的小增量；自建任务不能替代。
3. **F 是否值得一晚**：Codex 可能认为 KYC 已解决相机几何；我认为“准确外参”与“stale/noisy 外参”是不同条件，KYC 明确没测且承认误差会累积；但简单 pose jitter 可能闭合，且训练成本未知。**这是唯一值得用一晚杀死的假设**，不是已成立的新方法。
4. **F 的成本**：KYC 全协议 3 seeds×10 checkpoints、ACT 30k/DP 80k epochs，未报 wall-clock；一晚只能单任务单 seed，功效有限。若 pilot 显示放不下，我同意停止，不硬上。

---

## 6. 最终

- **深入对象仍为 C1/F/G**；C2/C3 粗筛。
- **C1：否决为方法候选**，保留为竞争背景；官方 toy+PushT 机制检查价值低，不值得一晚。
- **G：降级为 benchmark/reference**，不作备选；不静默换自建任务。
- **F：唯一保留的一晚问题验证对象**，但必须先过资产/吞吐 pilot；首夜只测“stale/noisy 外参下 conditioned 是否比 view-randomized RGB 更脆，以及 pose jitter 是否闭合”。**不宣称论文创新；复现/诊断本身不是贡献。**
- 若 F 的 pilot 失败或 C-jitter 闭合，本轮**无实验备选**；这不是对相机几何或安全约束领域的否定，只是本轮投入决定。
