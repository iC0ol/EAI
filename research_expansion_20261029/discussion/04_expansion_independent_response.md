先读取联合审查主报告与纠错账本，确认哪些旧结论已被纠正，再独立扩大检索。

主报告确认上轮 A/B/C 已审，不能续命。现在独立扫新的问题面：离线 RL、测试时适应、示范噪声/监督、策略评估与低样本学习。

初步新面：离线 RL 稀有成功、测试时适应、纠正反馈/噪声标签、rollout-free 评估。继续找带原始表图/代码证据的具体缺陷。

继续核对两个较新的方向：动作保持增广/相机外参漂移，以及离线策略评估的失败偏差。只为判断是否有真实自然缺陷，不扩题。

相机外参漂移出现很强的原始数字（65.3%→6.3%），这是此前未审的新面。核验原文与直接竞争，再定三个候选。

两个候选面已成形：相机外参漂移（原文明示 65.3%→6.3%）与稀有成功离线 RL。补读其直接近邻与资产状态，再决定是否保留第三个。

安全约束这条线有具体失败率（成功 rollout 中 6–21% 违反规格），但需核实作者/状态与代码。补读 RAIL 与 ManiGuard 后再定第二候选。

# 扩大范围后的独立初筛（2026-10-29）

**边界**：只读检索与讨论，未运行实验、未安装环境、未修改文件。未查看本轮 Codex 新结论；以下为新会话独立检索。上轮 A（跨块聚合）、B（轨迹 MI 筛选）、C（本体状态）只作为竞争背景，不续命、不改条件重开；D/M/U/导航/VLM 问答不默认恢复。

**阅读范围**：CamVLA 项目页；Know Your Camera arXiv 摘要+项目页；Production-Constrained Extrinsic Drift 的 dblp/检索片段（IEEE 页返回 418，未读全文）；RAIL arXiv 摘要；ManiGuard arXiv 摘要；ACIL ICML 页；TARL ICML 页；离线 RL 综述仅得检索片段（Springer 重定向未读），Imbalanced Offline RL 与 Equivariant Offline RL 只读摘要。**摘要不等于全文查新**，下文逐项标注。

---

## 1. 扩大后的问题面与淘汰

| 扫描方向 | 代表 2025–2026 线索 | 决定 | 理由 |
|---|---|---|---|
| 相机外参漂移 / 视角捷径 | CamVLA、Know Your Camera、Production Extrinsic Drift | **保留 F** | 有原始失败数字、自然工业漂移证据、公开仿真与代码线索 |
| 成功但违反安全约束 | ManiGuard、RAIL、ACIL | **保留 G** | 6–21% 成功 rollout 违反规格，是自然基准证据 |
| 离线 RL 稀有成功 | CQL/IQL/Cal-QL、Imbalanced Offline RL、DiSA-IQL | 不保留 | 关键数字多来自综述/软体机器人；稀有成功常靠人工子采样；Cal-QL/IQL 已覆盖 |
| 测试时适应 ID/OOD | TARL、VANE、TEMPO | 不保留 | “ID 退化”多为断言，未找到量化表；KL 锚定/可靠更新已直接覆盖 |
| 段级失败示范选择 | SSDF、S2I（ICRA 2025） | 不保留 | 段级选择已是直接方法；与上轮 B 同族 |
| 纠正反馈集合监督 | CLIC、SDP | 不保留 | 点监督→集合监督已被直接提出，且需交互纠正数据 |
| 动作保持增广/等变失配 | RoCoDA、EquiForm、SEIL | 不保留 | 动作同步变换与噪声下等变失配均已有方法 |
| Rollout-free 策略评估 | RoboFQE、SurVAL、ALOE | 不保留 | 属评估而非策略学习；代码/权重未确认 |
| 持续离线 RL | CoD、HiSPO、HTAC | 不保留 | 回放/子空间/任务组合路线密集 |
| 奖励黑客 | SOLE-R1、GRM-GRPO 失败卡 | 不保留 | 证据强但多在 VLA/GRPO，3090 成本与 VLM 路线不符 |
| 目标误泛化 | Barth 等 2026、Langosco 2022 | 不保留 | 机器人证据新但以诊断为主，方法恢复依赖深度，首夜设计不稳 |

---

## 2. 候选 F：固定相机的隐式手眼映射与外参漂移

### F.1 可测退化与原始证据

- **CamVLA 项目页**：15° 相机偏移使成功率从 **65.3% 降到 6.3%**；原因是固定相机策略“把 hand-eye 坐标映射记进权重”，碰撞、重装、手持相机会破坏该映射。这是作者报告，未独立复现。
- **Production-Constrained Extrinsic Drift（IEEE Access 2026）**：自然热/振动/支架漂移约 **0.3 mm**，使平均 3D 引导误差 **0.4131 mm → 1.1170 mm**，机械验收 **90/90 → 12/90**；用 50 个归档故障窗做 MAP 恢复后误差 **0.4775 mm**、验收 **83/90**。来源为 dblp/检索片段，IEEE 全文页 418，未读表。
- **Know Your Camera**：策略会利用静态背景线索推断相机位姿，几何/相机位置变化时该捷径崩溃；用逐像素 Plücker 射线条件化后，ACT、Diffusion Policy、SmolVLA 均改善。项目页未给数值表。

**自然 vs 人工**：15° 是压力测试，不是自然发生率；0.3 mm 工业漂移是自然证据但任务/机器人专用。首夜应报**剂量-反应**，不能只报最坏点。

### F.2 最直接 3 篇近邻

| 工作 | 作者/年份/状态 | 链接 | 实际读到范围 |
|---|---|---|---|
| CamVLA | Wenhao Li, Xueying Jiang, Quanhao Qian, Deli Zhao, Shijian Lu, Gongjie Zhang, Ran Xu；2026 项目页，论文链接，代码 “Coming Soon” | [项目页](https://alibaba-damo-academy.github.io/CamVLA/) | 项目页；65.3→6.3、π0 基线；未读论文/无权重 |
| Do You Know Where Your Camera Is? View-Invariant Policy Learning with Camera Conditioning | Tianchong Jiang 等 7 人；arXiv:2510.02268v1，2025-10-02；检索称 ICRA 2026 | [arXiv](https://arxiv.org/abs/2510.02268)；[项目页](https://ripl.github.io/know_your_camera/) | 摘要+项目页；代码/任务/示范发布，无权重；无数值表 |
| Production-Constrained Extrinsic Drift Recovery for Narrow-Field-of-View Vision-Guided Robotic Grasping | Mu Li, Jian Yang, Hongying Wang, Yanfeng Li, Dong Zhao；IEEE Access 14:141240–141261，2026 | [dblp 记录](https://dblp.org/pid/11/3400.html?view=by-year)；IEEE 11677037 | dblp/检索片段+摘要级；IEEE 全文 418 未读 |

补充（不作近邻计数）：DROID 2025-04 标定修复，说明大规模数据中未记录的外参变化会混淆训练；属数据 provenance 证据。

### F.3 强简单解释与最强已有修复

**解释**：不是视觉容量不足，而是策略把“相机—机器人—背景”的固定几何记成捷径；外参一变，动作坐标映射即错。**最强修复**：显式相机位姿条件化（Plücker 射线）、从单张 RGB 估计 hand-eye（CamVLA）、训练时随机相机扰动增广。三者都已是直接方法；最简单的是相机增广，若它已闭合差距，新机制无必要。

### F.4 最小创新假设与直接反例

**假设（尚未成立）**：部署时无需已知外参/标定板，用**动作条件视觉预测**自监督估计漂移——采样候选外参，将策略预测的动作 chunk 前向展开，选“最能解释下一帧”的外参，再以该外参重映射动作。

**直接反例**：CamVLA 的 Geometric Head 已从单张 RGB 估计 hand-eye；若它在同样漂移下工作，假设多余。另一个反例：简单相机增广/测试时多外参集成已匹配，则不需要新估计器。**不能因为论文没做“动作条件预测”这一具体形式，就宣布空白。**

### F.5 资产与一晚首验（3090 24GB / 32GB / 4核）

**可用程度**：
- RoboSuite、ManiSkill、LIBERO 公开；ACT、Diffusion Policy 公开实现。
- Know Your Camera：代码、任务、示范发布；**无权重**；仓库存在≠本机可跑，需 smoke test。
- CamVLA：代码 “Coming Soon”，无权重；不能作为首夜依赖。
- Production 论文：无公开代码/数据；只作自然漂移证据。

**首夜最小实验**：
- 选 1 个公开任务（Lift / Pick Place / Assembly 之一），100–200 条示范；ACT 或 DP，固定相机训练。
- 测试外参偏移 0°/5°/10°/15°（预登记），条件：无增广、相机扰动增广、（若代码可跑）相机条件化。
- 主指标：15° 成功率与完整分母；次指标：0° 成功率（ID 成本）、动作变化幅度（敏感性，不是成功阳性）。
- 3 个评估 seed；训练 seed 首夜可 1–2 个，但必须报训练方差限制。先做吞吐 pilot，**不猜训练小时数**；若一个任务训练+评估放不进一晚，降为公开 checkpoint 或停止，不硬扩。
- **停止**：相机增广已闭合 15° 差距且无 ID 成本 → 无方法必要；仿真不复现剂量效应 → 当前范围 VALID-NEGATIVE（若精度足够）或 INCONCLUSIVE；资产跑不通 → TECHNICAL-BLOCKED。

### F.6 最强反驳

这是**标定/感知工程**问题，不是学习机制；CamVLA、Know Your Camera、工业 MAP 恢复已覆盖；15° 是人工压力测试；真实自然漂移可能更小；π0 真实机器人崩溃未必在 ACT/DP 仿真复现；无公开权重；一晚训练统计功效弱。因此 F 最多是**问题验证 kill test**，不是论文创新。

---

## 3. 候选 G：成功-only 评价掩盖约束违反

### G.1 可测退化与原始证据

- **ManiGuard（arXiv:2608.17386v1，2026-08-18）**：200 个基础任务、1,000 场景、8,000 条安全标注示范、23,000+ rollouts；明确报告 **6–21% 的成功 rollout 违反规格**；微调后 safe task completion 从近 0 到 7.5–29.8%，但仍有 21–42% engaged rollouts 违反规格。来源为 arXiv 摘要，未读表。
- **RAIL（arXiv:2409.19190v1，2024-09-28；检索称 ICRA 2025，arXiv 页未标）**：一些高分策略部分靠频繁违反约束取得成绩，硬约束下显著掉性能；反向地，硬约束偶尔提升低性能策略的安全完成。摘要无数字，代码项目页检索称存在，未核实可运行。

**自然性**：ManiGuard 是基准 rollout 的自然统计，不是人工造坏；这是它比“人为污染”更强的点。

### G.2 最直接 3 篇近邻

| 工作 | 作者/年份/状态 | 链接 | 实际读到范围 |
|---|---|---|---|
| ManiGuard: A Benchmark and Data Suite for Specification-Grounded Safety Evaluation and Improvement of Robotic Manipulation | Yiyan Peng 等 14 人；arXiv:2608.17386v1，2026-08-18；无 venue | [arXiv](https://arxiv.org/abs/2608.17386) | 摘要；6–21%、8,000 示范、200 任务；未读表；未给代码链接 |
| RAIL: Reachability-Aided Imitation Learning for Safe Policy Execution | Wonsuhk Jung, Dennis Anthony, Utkarsh A. Mishra, Nadun Ranawaka Arachchige, Matthew Bronars, Danfei Xu, Shreyas Kousik；arXiv 2024；检索称 ICRA 2025 | [arXiv](https://arxiv.org/abs/2409.19190) | 摘要；无数字；代码未在 arXiv 页列出 |
| Action-Constrained Imitation Learning | Chia-Han Yeh, Tse-Sheng Nan, Risto Vuorio, Wei Hung, Hung-Yen Wu, Shao-Hua Sun, Ping-Chun Hsieh；ICML 2025 | [ICML](https://icml.cc/virtual/2025/poster/45492) | 摘要页；无数值；针对动作空间约束，不是安全违规率 |

补充：DiffOG（T-RO 2025）、TamedPUMA（L4DC 2025）为可动/几何约束修复；未读全文，仅检索片段。

### G.3 强简单解释与最强已有修复

**解释**：BC 只最大化动作似然，成功标签也不含约束；策略可以“完成任务但撞/超限/扰动环境”。**最强修复**：测试时可达性安全滤波（RAIL）、可微轨迹优化（DiffOG）、几何 fabric（TamedPUMA）。若滤波器把违规降到 0 且成功损失很小，学习侧改动就没有必要。

### G.4 最小创新假设与直接反例

**假设（尚未成立）**：把成功标签改成**约束条件化成功**，并用近违规段重标注/降权，让策略在训练时区分“成功且安全”与“成功但违规”；不改测试时控制器。

**直接反例**：RAIL 式测试时滤波已在同任务上把违规降为零且成功损失可忽略；或 ManiGuard 的违规多来自规格/标注 artifact；或简单成功+约束二分类重加权已匹配。任一成立，G 停止。

### G.5 资产与一晚首验

**可用程度**：ManiGuard 声称发布 8,000 条安全标注示范，但页面**未给代码/数据链接**；RAIL 代码项目页检索称存在，未核实；RoboSuite/ACT/DP 公开。200 任务全量不适合一晚。

**首夜最小实验**：选 ManiGuard 一个任务族/一个任务（或自建一个带关节限位/障碍的 RoboSuite 任务），训练 success-only ACT/DP；测成功率、成功 rollout 违规率、safe success；加 RAIL 滤波作对照。主指标：违规率与 safe success；次指标：滤波后的成功损失。3 个评估 seed；训练 seed 限制如实报。**停止**：滤波零违规且成功损失小 → 无学习方法必要；数据/代码不可得 → TECHNICAL-BLOCKED；违规率不复现 → MEASUREMENT-LIMITED。

### G.6 最强反驳

安全滤波是控制层修复，不是学习贡献；ManiGuard 规格可能过严/有标注噪声；RAIL 已覆盖；数据/代码链接未确认；一晚只能做一个任务，外部效度弱。G 是**备份 kill test**，不是优先论文对象。

---

## 4. 保留决定

| 候选 | 证据状态 | 首夜资格 | 投入建议 |
|---|---|---|---|
| F 相机外参漂移 | 来源事实强（65.3→6.3；0.3 mm→12/90），未独立复现 | 有，但需资产 smoke test | **优先一晚问题验证**；不宣称论文创新 |
| G 成功但违规 | 来源事实强（6–21% 成功 rollout 违规），未独立复现 | 有，但数据/代码未落实 | 备份 kill test |
| 其余扫描方向 | 多数为摘要/检索级，竞争密集 | 无 | 不投入 |

**最终**：优先 **F**，备选 **G**；不保留第三个。理由不是“领域无问题”，而是 F 同时具备：原始失败数字、自然工业漂移证据、公开仿真与代码线索、单卡小模型可测、强简单修复可杀死假设。G 证据也强，但资产与“滤波已解决”的风险更高。

---

## 5. 最愿意用一晚复现哪个

**F：固定相机外参漂移的剂量-反应与简单增广能否闭合。** 它不是复现 CamVLA 的论文，而是回答一个决定性问题：在公开仿真、ACT/DP、匹配训练/评价下，外参偏移是否产生可测成功率下降；随机相机增广是否已经解释全部收益。若增广闭合，F 停止；若不复现，F 在当前仿真范围 VALID-NEGATIVE/INCONCLUSIVE；若增广不够，才有资格讨论“动作条件自监督漂移估计”这一最小假设。**复现本身不是贡献，只买一个是否继续投入的判断。**

---

## 6. 未知与最强反驳（保留）

- **未独立复现**：CamVLA 的 65.3→6.3、Production 的 12/90、ManiGuard 的 6–21% 都是作者/基准报告；本轮没有跑任何 rollout。
- **未读全文**：CamVLA 论文、Production IEEE 全文、ManiGuard 表、RAIL 表、ACIL 表均未读；不能把摘要写成全文查新。
- **资产未知**：Know Your Camera 代码/任务/示范是否本机可跑、是否有匹配权重；ManiGuard 数据/代码链接；RAIL 代码可运行性；均未验证。仓库存在≠可运行。
- **自然性**：15° 是压力测试；0.3 mm 是自然但专用工业站；仿真剂量效应未必等同真实。
- **最强反驳 F**：这是标定工程，CamVLA/Know Your Camera 已解决；简单增广可能足够；一晚训练统计功效弱。
- **最强反驳 G**：测试时滤波已足够；规格可能 artifact；数据不可得。
- 因此本轮只给**问题验证资格**，不给论文创新资格；不把“能复现已知缺陷”包装成贡献。
