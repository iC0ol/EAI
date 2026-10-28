先读取 Codex 冻结稿、全文抽取文本与源码，逐项核对定位。

BID 全文与 MedianTE 关键节已读。现在读 DemInf/DataMIL/状态接口全文与四份源码。

源码确认了 BID 的 positive-only 路径与 DataMIL 的 MetaWorld 预算。现在补读 State-free 全文与 NOSTRA，核验状态混淆是否被受控消融排除。

# 第一次交叉质疑回复（DeepSeek）

**本轮范围**：只读全文/源码与网页；未运行实验、未训练、未推理、未写实现。以下定位均给出章节、表号或代码行。

## 0. 判断变更总表

| 争议 | 原判断 | 新证据 | 修正 |
|---|---|---|---|
| C1 聚合 | “选完整候选、避免逐坐标混合”是残余 | BID `name='positive'` 已实现；BID Table 4 的 +Positive 接近全 BID；MedianTE Table III 已有 block/trimmed medoid | **撤回**该残余；C1 延迟接缝仍淘汰 |
| C2 数据 curation | 局部关键片段可能被整轨迹平均丢失 | DemInf §V-C 明确因“会删掉难但必要的片段”而**故意**不做逐状态过滤；附录 B 所有基线都用 S(τ)=1/T∑h | **降级**：无直接失败实证，不作候选 |
| C3 本体状态 | state-free 的收益可能被相机/动作空间混淆 | state-free Table V 在固定双腕广角+relative EEF 下只切状态：π0 0/0→.984/.584；ACT 0/.084→.933/.517；DP 0/0→.867/.533 | **撤回**“混淆使缺陷不成立”；缺陷主效应成立 |
| C3 门控创新 | 逐时间步可靠性门控是残余空白 | NOSTRA 用每模态 posterior-prior KL 做逐时间步切换，换用 imagined latent；RA-L 2026 | **降级**：机制已被覆盖，只剩窄差异 |
| 标签 | 无差距→MEASUREMENT-LIMITED | 任务方纠正 | **接受**，改为 VALID-NEGATIVE / INCONCLUSIVE / MEASUREMENT-LIMITED 三分 |

---

## 1. C1 不等于延迟接缝：我撤回“完整候选选择”这一残余

**新增证据（源码）**

- `bid_multi.py:46-50`：`topk = num_sample // num_mode + 1`，`dist_avg_pos` 取每个强策略候选到最近 top-k 个其他候选的平均距离；这是“密集邻域/medoid 型”分数，不是在坐标上拼接。
- `bid_multi.py:53-70`：`weak` 是可选参数；`name='positive'` 时 `dist_avg_neg.zero_()`，**不需要弱模型**。
- `bid_multi.py:72-80`：`argmin` 后按 index 取回**完整候选向量**，从不对坐标做混合。
- `bid_single.py:45-56`：coherence sampler 也只在完整候选上按 prior 距离排序，取单一候选。

**新增证据（论文表）**

- BID Table 4（VQ-BeT/Push-T，closed-loop）：Vanilla 38.9，+Positive **42.8**，+Negative 42.7，full BID 43.8。positive-only 已拿到大部分收益，且完全避免逐坐标拼接。这比“BID 存在”更强：它直接说明“选完整候选、不用弱模型”是**已发表的强基线**。
- MedianTE Table III（can, h=2, q=2, n=50）：deployed weighted mean 0.600，coordinate-wise median 0.880，**block medoid 0.940**，**trimmed medoid 0.960**。完整候选选择器已在同一候选集上被测试，且点估计高于逐坐标中位数（作者说彼此未显著分离）。
- MedianTE §V 明确承认逐坐标中位数会产生“an action no query proposed”：在 can h=2 q=2 的 82,432 个被污染时间步中，输出与某个候选完全一致仅 **0.03%**；但它到最近候选的距离是平均两两距离的 **0.13**（p99 0.51），且始终不超出逐坐标范围。
- MedianTE §VIII 明确：所有结果只在仿真；无硬件；无光照/视角/材质研究；固定 stride。**逐坐标包络是统计/组合保证，不是动作流形或碰撞安全保证。**

**判断**

- **撤回**：我把“选完整候选、避免逐坐标混合”当作残余创新，是错的。BID positive-only 覆盖了同查询多采样情形；MedianTE Table III 的 block/trimmed medoid 覆盖了缓存重叠候选情形。
- **保留**：C1 的“延迟接缝”问题仍淘汰，但理由不是“聚合方向全关闭”，而是 RTC（NeurIPS 2025）、Legato（RSS 2026）、LiPo（2025）已分别覆盖推理时、训练时、混合+jerk 优化；线性混合是已发表方法的组成部分。
- **不宣布永久关闭**：如果未来有**自然任务失败**证据，显示 block medoid 会在陈旧模式上选错、而某种新聚合能可测改善，那才是新问题。当前只有数学上可构造的流形反例，没有自然失败率，不能当机器人缺陷。

**尚存分歧**

Codex 说 BID positive-only 已覆盖我的设想；我同意结论，但补充：BID 的候选是**同一查询的新采样**，不是跨时间缓存的旧 chunk；真正覆盖缓存情形的是 MedianTE 的 block/trimmed medoid。若 Codex 能指出一个缓存候选的观测年龄差异导致 block medoid 自然失败的案例，C1 才重新打开；否则本议题关闭。

---

## 2. C2 数据 curation：没有“局部覆盖损失”的直接证据，降级

**新增证据**

- DemInf §V-C 原文：虽然每个 state-action 对都有 MI 分数，但作者**不直接按 state-action 过滤**，理由是“would … remove all parts of a task that are inherently harder to predict, but necessary for success”，并举例：自由运动易预测，夹爪闭合时刻难预测。作者因此选择整轨迹平均。
- DemInf 附录 B：所有评分函数统一为 `S(τ)=1/T ∑ h(s_t,a_t)`；整轨迹平均是**所有基线共同的设计**，不是 DemInf 獨有的未审视缺陷。
- DataMIL：使用小规模 held-out `Dtarget` 的 BC 代理损失与 co-training（§3/§4），不是纯离线 DemInf 权限；`datamil_config.py:7-17` 是 MetaWorld `pick-place-wall` + `prior`，`datamil_config.py:27-33` 为 `num_workers=32`、`batch_size=16364`、`num_steps≈1100`；`datamil_launcher.sh:5-23` 为 `NUM_TRIALS=50`、`candidate_size 0.5`。本机 4 核上 32 workers 是 8 倍超订，16k batch 也不是“一晚可复现”的依据。

**判断**

- **降级**：没有找到“整轨迹平均过滤丢掉唯一关键片段并导致任务失败”的直接证据。DemInf 的作者不仅知道这个风险，还明确用它作为选择整轨迹的理由。把“平均可能掩盖局部”当成新机器人缺陷，是把数学可能性当实证。
- **公平比较的前提**：若要做，必须匹配权限与预算——纯离线 DemInf 不能用 target rollout；DataMIL 可以用 `Dtarget`，两者不能直接对比“局部覆盖”。同一总 demo 数、同一更新数、同一模型容量下，比较“整轨迹平均 vs 阶段分层覆盖”才有意义。
- **尚存分歧**：Codex 可能认为“阶段分层”本身是可发表的方法贡献，即使缺陷未被证实。我不同意：这会变成 method in search of a problem；除非先找到自然数据集中“平均过滤后某阶段覆盖归零且成功率下降”的案例。

---

## 3. C3 本体状态：缺陷主效应成立，但门控创新被 NOSTRA 覆盖

**新增证据（state-free 全文）**

- Table V（§V-C）：Pick Pen，双广角腕相机、relative EEF 固定，只切本体状态：
  - π0：有状态 **0 / 0** → 无状态 **.984 / .584**（height / horizontal）
  - ACT：**0 / .084** → **.933 / .517**
  - Diffusion Policy：**0 / 0** → **.867 / .533**
- Table I（§III）：普通腕相机、relative EEF，只切状态：72 cm **0/30 → 30/30**；90 cm **0/30 → 17/30**。
- 因此我此前说“0→85 不能归因于状态、可能只是相机/动作空间”**过强，撤回**。主效应在固定相机与动作空间下已被隔离。
- 但相机/动作空间的 sweep 只在 state-free 下做（Table III/IV/VII），没有 state × camera × action 的全交叉；**交互项仍未知**，这不是否定主效应的理由。

**新增证据（NOSTRA）**

- NOSTRA 对每个模态维护 closed-loop posterior 与 history-only prior，用两者 KL 判定该模态是否“gone out of distribution”，超过阈值就切换到 imagined latent；per-modality、time-varying，无需噪声训练数据；12 个 MuJoCo 任务 + 4 个真实 Franka 任务；RA-L 2026。
- 这**就是**逐时间步、逐模态的可靠性门控；我说“没有 learned gate 所以有空白”不成立——KL 信号就是 gate，且比我的“视觉可靠性”更一般。
- 差异只在：NOSTRA 面向传感器故障/缺失观测，切换到 imagined latent；我设想的是“状态干净但分布偏移、视觉仍可用”时抑制状态捷径，切换到 vision-only 分支。这个差异窄，且 NOSTRA 的 KL 很可能也会触发状态 OOD。

**判断**

- **保留**：state 导致空间泛化退化的缺陷是真实的（Table V/I），不是混淆造成的。
- **撤回**：把“可靠性门控”当作新机制。NOSTRA 已覆盖 per-modality KL gate；2026 接口论文也系统比较了 state prompt/VLM prefix/action prefix/state expert/feature modulation（Table 1：无状态 54.6%，sp 57.7% CI [0.2,6.1]；precision 家族 se 42.8% +3.3，vp 38.3% −1.2），并明确“没有 task-agnostic best interface”。
- **降级**：C3 只剩一个窄问题——在“状态干净但空间偏移、NOSTRA 的 KL 不触发”的条件下，是否存在 state-specific gate 的增益。这是假设，不是已证空白；没有证据前不作优先对象。
- **标签纠正（接受）**：若受控比较、测量与基线通过、统计精度足够而无差距 → **VALID-NEGATIVE（当前范围）**；样本太少 → **INCONCLUSIVE**；接口本身无辨识力（如策略根本不用状态、敏感性诊断失败）→ **MEASUREMENT-LIMITED**。黑屏/打乱导致动作变化只是**敏感性诊断**，不是“门控能提高成功率”的阳性对照；真正的阳性对照应使用 oracle 可靠性标签，或先制造一个确实降低成功率的状态损坏，再证明门控恢复。
- **措辞纠正**：把“永久关闭”“机制空间基本被占满”改为“本研究投入决定”；不排除未来有新证据重开。

---

## 4. Adapt Your Body 撤回状态

我初筛未引用 Adapt Your Body（2506.23944），我的 C3 依据是 state-free、2026 接口论文、Blackout vs. Freeze。接受 Codex 的撤回更正：不再把它当作有效独立支持；也不从“撤回”推断其技术错误。后续若引用，只写“v2 于 2025-07-01 撤回，备注 Need further modification，状态待核实”。

---

## 5. 修正后的候选状态

| 候选 | 状态 | 理由 |
|---|---|---|
| C1 延迟接缝 | **淘汰** | RTC / Legato / LiPo 直接覆盖；线性混合是已发表组件 |
| C1 完整候选聚合 | **撤回为残余** | BID positive-only + MedianTE block/trimmed medoid 已覆盖；流形问题只是 scope limitation |
| C2 数据 curation | **降级，不作候选** | DemInf §V-C 明确规避逐状态过滤；无自然失败实证；DataMIL 权限/成本不匹配 |
| C3 本体状态 | **缺陷保留，机制降级** | Table V/I 证明主效应；NOSTRA + 2026 接口论文覆盖门控/接口空间；只剩窄假设 |
| 语言绑定 | **粗筛淘汰，不扩大** | 按本轮指示，不展开 |

**结论**：本轮仍**没有 PRIORITY-GO 候选**。C3 是唯一有真实缺陷证据的方向，但“可靠性门控”已不是空白；若继续，只能做一个很窄的诊断：在 clean-but-shifted state 下，NOSTRA 的 KL 是否漏检、state-specific gate 是否还有独立增益。这个诊断的价值取决于能否先找到 NOSTRA 失效的自然条件，目前没有。

---

## 6. 尚存分歧与下一步最低证据

1. **C1 缓存候选**：若 Codex 能给出 block medoid 在缓存重叠候选上自然选错模式、导致任务失败的案例，C1 聚合方向可重开；否则关闭。数学反例不算。
2. **C3 状态门控**：若能在公开仿真中构造“状态干净但空间偏移、NOSTRA KL 不触发、state-specific gate 提升成功率”的受控案例，C3 才有独立机制；否则 NOSTRA 已覆盖。注意阳性对照必须是“成功率提升”，不是动作变化。
3. **C2 数据 curation**：若能在自然多操作者数据中找到“整轨迹平均过滤后某阶段覆盖归零且成功率下降”的直接证据，再谈阶段分层；否则不做。

我保留的方法论立场只有一条：**先有自然失败证据，再谈新聚合/新门控；数学上能构造的反例只用于界定保证范围，不用于宣称机器人缺陷。**
