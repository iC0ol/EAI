先核对 GAP 全文与源码差异，再读 NOSTRA/CUPID/absolute-state 的关键节。只读，不执行。

# 第二次交叉质疑回复（DeepSeek）

**ID 更正**：A＝跨时间 chunk 聚合；D＝延迟接缝。上轮我把 A 与 D 混在“C1”里，现更正。本轮只深入 A/B/C；D/E 仅保留粗筛，不展开。未运行任何代码/实验。

---

## 1. A：没有自然失败率，维持“不作候选”

**新增证据（源码/表）**

- `bid_multi.py:46-50`：`dist_avg_pos` 是候选到最近 top-k 个其他候选的平均距离；`:53-70` 中 `weak` 可选，`name='positive'` 时负项置零；`:72-80` 按 index 取回**完整候选**。BID positive-only 已覆盖“同查询多采样、选完整候选、不用弱模型”。
- BID Table 4（closed-loop）：Vanilla 38.9，+Positive **42.8**，full BID 43.8。
- MedianTE Table III：deployed mean 0.600，coordinate median 0.880，**block medoid 0.940**，**trimmed medoid 0.960**。跨时间缓存候选上的“完整候选选择”也已是基线。
- MedianTE §V：逐坐标中位数在 82,432 个污染时间步中只有 **0.03%** 与某个候选完全一致；到最近候选距离为平均两两距离的 **0.13**（p99 0.51）。§VIII 明确无 manifold/碰撞安全保证。
- MedianTE 的 blank-frame 是**注入式 corruption stress test**，不是自然失败率；不能当自然缺陷证据。

**判断**：A 不作候选。完整候选 medoid 不是创新；off-support 是数学构造，当前没有自然任务失败率。**来源证据状态：NOT_RUN；基于查新的淘汰，不是 VALID-NEGATIVE 实验。** 不宣布“所有聚合方向永久关闭”；若未来有自然失败率，可重开。

---

## 2. B：无局部覆盖损失的直接实证，降级为 INCONCLUSIVE

**新增证据**

- DemInf §V-C 明确：虽然每个 state-action 都有 MI 分数，但**不按 state-action 过滤**，因为会“remove all parts of a task that are inherently harder to predict, but necessary for success”；作者因此用整轨迹平均。附录 B 中**所有方法**统一为 `S(τ)=1/T∑h`——平均是共同设计，不是 DemInf 獨有的未审视缺陷。
- CUPID §5：curation 使用 `m=100`（仿真）/`m=25`（真实）条 closed-loop rollout；评估 500/25 rollouts；§9 明确 greedy selection **忽略 demonstration 之间的交互**。它是“训练→rollout→TRAK→再训练”，不是纯离线免费预处理。
- DataMIL：`datamil_config.py:7-17` 为 MetaWorld `pick-place-wall` + `prior`；`:27-33` 为 `num_workers=32`、`batch_size=16364`、`num_steps≈1100`；`datamil_launcher.sh:5-23` 为 50 trials、`candidate_size 0.5`。本机 4 核上 32 workers 是 8 倍超订，不能无依据说一晚可复现。

**判断**：B 无“局部关键片段被整轨迹平均丢掉并导致任务失败”的直接证据；DemInf 的作者是**有意**选择整轨迹以避免逐状态过滤。**来源证据状态：NOT_RUN；INCONCLUSIVE；不作候选。** 公平比较必须匹配权限（纯离线 DemInf 不给 target rollout；DataMIL 给 `Dtarget`）与总 demo/更新预算。

---

## 3. C：缺陷真实，但方法空间已被 GAP/NOSTRA/relative encoding 覆盖

### 3.1 缺陷证据（保留）

- State-free Table V（固定双腕广角 + relative EEF，只切状态）：π0 **0/0 → .984/.584**；ACT **0/.084 → .933/.517**；DP **0/0 → .867/.533**。
- Table I（普通腕相机，只切状态）：72 cm **0/30 → 30/30**；90 cm **0/30 → 17/30**。
- 因此“状态导致空间泛化退化”在固定相机/动作空间下是成立的；我上轮的“相机/动作混淆使缺陷不成立”已撤回。相机/动作 sweep 只在 state-free 下做，**交互项仍未知**，但不影响主效应。

### 3.2 GAP 是直接竞争（保留）

- GAP Table 1：Pick-place Vision-only 91.8 / Concat 78.4 / GAP 94.2；Push-wall Vision-only 63.2 / **Mask 79.2** / GAP 73.6；Threading 43.6 / 53.0。GAP 总体最强，但**Mask 在 push-wall 反超**，说明“简单状态 mask/dropout”是强基线。
- GAP 方法 §4.3 / Eq5 / Algorithm 1：按 phase indicator ρ 削弱本体梯度，直接就是“防状态捷径”；比我的门控更接近问题。

### 3.3 GAP 代码与论文不一致（定位）

- `gap_gap_gap.py:85`：`lambda = self.cfg.lambda` 是 Python 语法错误；该训练脚本无法按原样导入/执行（静态阅读即可见；未执行）。
- `:83`：`phase_p = torch.max(batch['phase']).item()` 对整个 batch 取 max，得到标量；论文 Algorithm 1 第 322 行写的是“Calculate **average** indicator ρj of Bj”。max 与 average 语义不同。
- `:86`：`coeff_p = 1 - lambda * phase_p`，再在 `:88-91` 乘到本体参数梯度；论文 Eq5 是 `ω ← ω − λ·(1−ρ)·η∇L`。代码的 `1−λρ` 与论文的 `λ(1−ρ)` 不是同一缩放。
- `gap_gap_gap.py:36-43`：train `demo_range=[0, demo_num]`，valid `[0, 0.1*demo_num]`，同一 `data_path`；`gap_gap_dataset.py:107-127` 确认验证集是训练集子集。验证/早停存在泄漏。
- `gap_gap_cfgs_task_assembly.yaml`：`demo_num: 100`、`action_shape: 4`、`pro_dim: 9`；README 只给 `environment.yml` 与训练命令，**未给权重或数据下载入口**，config 仍是 `path/to/demos_folder`。

**限定**：这些只说明**公开代码不是论文实现的忠实可运行版本**，不能推断论文实验就是这样跑的；修代码也不构成论文创新。GAP 论文的 Table 1 仍可作为方法证据。

### 3.4 NOSTRA：要拆成两个结论

- §III-B 的 AdaMLI 不是“KL 绝对值阈值”，而是 `D_KL(T) − D_KL(T−1) > f_o · r(T,k)`，`f_o=20, k_o=10, f_c=2, k_c=2`；它检测的是 **KL 的急剧变化**，不是稳态偏移。
- 因此：
  - **机制覆盖成立**：per-modality、逐时间步的可靠性切换已被 NOSTRA 覆盖；“没有 learned gate”不是空白。
  - **clean-but-shifted state 是否被覆盖，未被证明**：平稳偏移未必触发 sharp-change gate。我上轮写“NOSTRA KL 很可能也会触发干净空间 OOD”是推断，**撤回**为待核实。
- 这给 C 留了一个窄差异，但只是假设，不是已证空白；且 GAP 的训练期梯度抑制是另一条已占路径。

### 3.5 Absolute State：覆盖简单坐标重写，不是所有本体删除

- 只对线性 rail 的 0/1 维做 episode-relative state **and** action；其他关节保留绝对值（§III）。Table II：ID SR 5/50/20%，OOD 0/25/20%；按 20 episodes/条件计，OOD 的 25% 只有 5/20，样本小。
- 8×H200、2500 demos、200k updates、约 70h 数据；不能声称 3090 低成本原样复现。它直接覆盖“绝对坐标重写”这个简单修复，不是新题。

**C 判断**：缺陷真实；方法空间已被 GAP/NOSTRA/state-free/relative encoding 覆盖到很窄。**来源证据状态：NOT_RUN；source facts 支持缺陷，但无本地实验；方法覆盖是查新判断，不是 VALID-NEGATIVE。** C 不是 paper-ready 候选。

---

## 4. 是否把“创新成立”错误提前成“优先复现资格”的门槛？

**部分是。** Codex 的“当前无合格候选”对**论文优先对象**成立，但如果把“创新已被覆盖”当作**问题验证复现**的唯一门槛，就过强。任务书明确区分“优先复现对象是获得问题验证资格，不是已经确立的论文题目”。C 有真实缺陷、可测任务后果、公开仿真基座，值得一次**杀死测试**；这不等于它有论文创新。

但 C **不能**做 GAP/State-free 的忠实复现：
- GAP：公开训练脚本有语法错误，梯度语义与 Eq5/Algorithm 1 不一致，无权重/数据入口。
- State-free：无代码、无权重、无数据，只有 arXiv 与 LeRobot π0 集成示例。
- Absolute State：无公开数据/权重，8×H200。
- NOSTRA：代码未核实；即使有，也不是 clean-shift 设置。

所以第一夜只能是**新的公开仿真诊断**，不是“复现 GAP/State-free”。如果研究者目标是三个月出论文，C 的期望值低；如果目标是决定是否继续投入，这个 kill test 值一晚。

---

## 5. 若保留 C：具体待判问题、资产、基线、第一夜证据

**待判问题（不依赖新模型）**

1. 在公开仿真、预登记空间偏移下，匹配数据/更新/容量后，加入本体状态是否**提高 ID 成功率但降低 OOD 成功率**？
2. 若 Q1 成立：一个**不带 phase detector 的全局本体梯度缩放**（同一 λ）是否已匹配 GAP 的 phase-gated 调制？若匹配，GAP 的 phase 组件没有独立作用；若不匹配，才有第二阶段的方法问题。

**现成公开资产/入口**

- MetaWorld、RoboMimic：公开仿真与数据。
- ACT、Diffusion Policy：公开实现与训练入口。
- GAP repo：公开，但训练脚本不可按原样运行、无权重/数据；只能作为方法描述参考，不能作为 baseline checkpoint。
- State-free / Absolute State：无公开权重/数据；不作第一夜依赖。
- NOSTRA：代码入口未核实；不假设可运行。

**最强简单对照**

Vision-only；Concat；**state mask/dropout**（GAP Table 1 的 Mask 在 push-wall 79.2 > GAP 73.6）；**全局梯度缩放**（无 phase）；state-free + relative action。所有对照匹配数据量、更新数、模型容量、评估 seeds。

**最小第一夜证据**

- 3 条件（state / no-state / state-dropout）× 2 偏移（ID / 预登记 OOD 高度或水平位置）× 3 seeds；主指标 OOD 成功率，次指标 ID 成功率。
- 敏感性诊断：zero/shuffle state 是否改变动作（确认策略确实用状态）；这与“门控能提高成功率”的阳性对照分开记录。
- 若 Q1 通过，第二阶段才加 GAP 式 phase-gated 梯度抑制与全局缩放对比；不在第一夜训练新大模型。
- **停止规则**：匹配后无可复现 OOD 差距 → 若统计精度足够则 **VALID-NEGATIVE（当前范围）**，样本不足则 **INCONCLUSIVE**；state-free/dropout 已匹配 → 停止；无法忠实重建 GAP → 只保留问题诊断，不作方法声明。

**阳性对照纠正（接受）**：oracle 只给 gate 标签，必须走相同 gate 接口、相同候选/动作空间、相同预算；任务成功改善与接口敏感性分别记录；oracle 未证明最优性，不称上界。黑屏/打乱造成动作变化只是敏感性诊断，不是门控增益的阳性对照。

---

## 6. 来源证据状态与投入建议

| 候选 | 来源证据状态 | 实验状态 | 投入建议 |
|---|---|---|---|
| A 跨时间聚合 | 查新淘汰：BID positive-only、MedianTE block/trimmed medoid 已覆盖；无自然失败率 | NOT_RUN | **不投入**；不作 VALID-NEGATIVE |
| B 局部覆盖 | 无直接实证；DemInf §V-C 有意规避；CUPID/DataMIL 权限与成本不匹配 | NOT_RUN | **不投入**；INCONCLUSIVE |
| C 状态捷径 | 缺陷真实（State-free Table V/I；GAP Table 1）；机制被 GAP/NOSTRA/relative encoding 覆盖到窄 | NOT_RUN | **仅问题验证 kill test，非论文优先**；1 备选 |
| D 延迟接缝 | RTC/Legato/LiPo 直接覆盖 | NOT_RUN | 粗筛淘汰，不扩大 |
| E 语言绑定 | 2026 多路线覆盖 | NOT_RUN | 粗筛淘汰，不扩大 |

**最终**：优先对象 **无**；备选 **C（仅问题验证资格）**。这不是“整个领域无候选”，而是本轮投入决定：A/B 没有可检验的残余，C 的方法空间太窄，只值得一次杀死测试。

---

## 7. 保留 / 撤回 / 降级

- **保留**：C 的缺陷主效应；A 的“无自然失败率”；B 的“无局部覆盖实证”。
- **撤回**：“NOSTRA KL 很可能触发 clean spatial OOD”（无证据，改为待核实）；“GAP 公开代码等同论文实现”（不成立）；“state-free 的相机/动作混淆使缺陷不成立”（已撤回）。
- **降级**：C 的“可靠性门控”创新（NOSTRA 覆盖机制，GAP 覆盖训练期抑制）；B 的“阶段分层”方向（无缺陷实证）；GAP 作为第一夜复现入口（代码/资产不足）。

---

## 8. 真实未决分歧

1. **C 是否值得一晚**：Codex 倾向全部不保留；我认为作为**问题验证 kill test** 有价值，但只在“公开仿真 + ACT/DP + 预登记偏移”范围内，且不宣称复现 GAP/State-free。若研究者只想要论文优先对象，则同意本轮无合格候选。
2. **GAP 的 phase 组件是否有独立作用**：论文 Table 1 显示 GAP 总体最强，但 Mask 在 push-wall 反超；缺“全局梯度缩放（无 phase）”对照。这是可检验的机制问题，不是新模型。
3. **NOSTRA 的 sharp-change gate 是否漏掉稳态偏移**：这是假设；需要 clean-shift 下的 KL 轨迹证据，不能先宣布失效。

---

## 9. 实际阅读范围与未找到资产

- **GAP**：README、`gap.py`、`dataset.py`、`policies/bc.py`、`inference.py`、`cfgs/gap.yaml`、`cfgs/task_assembly.yaml`；论文 §4、§5、Algorithm 1、Table 1；Table 2/4 与附录 §9/10 **未读全**。
- **State-free**：arXiv HTML Table V、Table I、§V-C；附录未全读。
- **Absolute State**：前 180 行、Table I/II、§III；附录未全读。
- **NOSTRA**：§III-B/AdaMLI、Table I 附近；完整结果/附录未全读。
- **CUPID**：§5 rollout 预算、§9 limitations；附录未全读。
- **DataMIL**：config/launcher + 全文检索段；未全读。
- **未找到/未核实**：GAP 权重与演示数据；State-free 代码/权重/数据；Absolute State 数据/权重；NOSTRA 代码入口；GAP 论文实现与公开代码的一致性。以上均不作为“可一晚复现”的假设。
