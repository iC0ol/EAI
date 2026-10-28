先核对 CamVLA 附录、KYC 源码与配置，再查 AnyCamVLA/ViewVLA/RayViT 是否已做 persistent drift。

KYC 源码确认：Lift 官方 20001 epochs、batch70、`__len__=200`、每 epoch 仅约 3 个梯度步、`num_workers=0` 且即时渲染；训练代码自带 7.5h 上限。现在核对动作/相机语义与 AnyCamVLA/ViewVLA 是否已做 persistent drift。

CamVLA 附录确认只测了每决策独立重采样的旋转噪声（1–20°、25–45°；5° 58.7%，12° 仍高于 π0 36%），未测整段持续偏差。再核 AnyCamVLA 的标定假设与资产。

# 第二轮交叉质疑回复（DeepSeek）

**边界**：只读；未运行、未训练、未改文件。以下按原文行号/代码路径定位。

---

## 1. 先更正我上轮的三处过度表述

| 我上轮说法 | 更正 |
|---|---|
| “CamVLA 未测外参误差” | **错**。CamVLA 附录 C（`camvla.txt:798–817`）已做 rotation noise：0° **64.0%**、1° **63.3%**、5° **58.7%**，12° 仍接近/高于无噪 π0 **36.0%**；每 planning step 独立重采样，明确不是整段固定偏差；translation 因 relative action 抵消而省略；几何头平均误差 **1.41°**。 |
| “带噪外参本身未覆盖” | **收窄**：IID 旋转噪声已覆盖；**整段持续偏差**未覆盖。不能再说“CamVLA 没测误差”。 |
| “IDP 下降不是条件失配，主因是稀有模式质量低” | **改为“原文解释如此，但 Table II 只做模式分解，不能排除条件失配是共同原因”**。C1 仍因 COT 覆盖与资产/价值降级，但不能说因果已被证伪。 |
| “G 全量 200 任务太大，所以单任务也不能验证” | **撤回**。降级主因是**学习新意与具体资源协议未建立**，不是把全量成本强加给首夜。 |

---

## 2. C1：COT 覆盖机制；DDPM 差异目前只是算法迁移

- **IDP Table II（`immiscible.txt:441–446`）**：M(4) 条件成功率 Place Shoe **85.71%**、Rotate QR **40.00%**；总体 100→93.33、86.67→73.33。原文第 460–470 行解释为“恢复的模态仍在学习、较不可靠”，但这是作者解释，**不是排除条件失配的独立因果检验**。我上轮把它写成“主因”过强。
- **IDP 代码**（commit `03d90df…`，`assignment.py`）：`assignment_indices(actions, noise)` 只用标准化动作与噪声前 `Da` 通道的欧氏距离，**没有 observation/condition 参数**。所以 IDP 确实没做条件分配。
- **COT（`cot.txt:227–247`）**：耦合代价 `||x0−x1|| + γ||c0−c1||`，显式把 condition 放进 OT；Table 1（`:314–324`）平均 **0.818**，高于 CFM 2-step 0.790、DP 20-step 0.781。代码已发布 `github.com/ansocho/cot_policy`。
- **判断**：把 COT 的条件代价移植到 DDPM，是**算法迁移**，不是新问题；目前没有“DDPM 多步前向使初始耦合失效”的可测证据。C1 的方法候选资格**否决**，保留为竞争背景。
- **官方 toy+PushT 机制复核的最低价值**：只能测条件支持/模式覆盖；PushT 覆盖率几乎不变（95.16→95.39），四模式/真机数据未发布，**不能宣称机器人任务收益，也不能宣称真机下降由条件失配造成**。与 F 相比不值得一晚。

---

## 3. F：KYC 源码与预算改变了可行性判断

### 3.1 KYC 源码事实（`kyc_train.py`、`kyc_utils.py`、`kyc_paper_runs.txt`）

- 官方 Lift ACT：**20001 epochs**（`kyc_paper_runs.txt:1–18`），batch **70**，200 训练 demo + 10 val（`kyc_utils.py:447–448`，disjoint）。
- `__len__` 返回 **demo 数 200**（`kyc_utils.py:324–325`），每 `getitem` 随机 t 并即时渲染；所以 **1 epoch = ceil(200/70)=3 个梯度步**，20001 epochs ≈ **60k steps**，不是 20k steps。
- `num_workers=0`（`kyc_utils.py:482–496`）；渲染在 CPU，4 核是瓶颈；`kyc_train.py:159–161` 自带 **7.5h** 时间上限，可断点续训。
- `setup.sh` 下载全 folder + 两套未锁版本环境，不能照跑；必须最小化资产（单 Lift 数据 + 必要依赖/ResNet 权重）。
- `kyc_eval.py:194–198` 用 `poses_list[episode_num]` 选相机；`_image_to_tensor` 用**同一个** `cam_pose_raw` 同时渲染与生成 Plücker（`:201–207`）。要测“图像真实、条件错误”，必须做**评估侧解耦**：渲染用真 pose，Plücker 用扰动 pose。
- `kyc_utils.py:391–392` 先把 RGB 与 Plücker `torch.cat` 再统一 `RandomCrop`，crop 同步；但 `RandomCrop` 对 9 通道用 NEAREST 缩放，Plücker 射线是否仍几何一致需验收。
- `kyc_cam_utils.py:66–70` 生成 `cam_to_world` 时 `z=-forward`（OpenGL 约定）；PlückerEmbedder 若期望 OpenCV，需要转换；`np.flipud` 后 RGB 与 ray 的 v 轴也要核对。
- `prob_drop_proprio=1.`（`kyc_utils.py:412–413`）把 qpos 置零，视觉-only；这是好事，排除了本体状态混淆。

**结论**：KYC 资产存在、代码可读，但**不是“下载即跑”**；动作语义（`liftrand_eef_delta` 是相邻绝对目标 pose 差、部署累加，不是当前 EEF-relative OSC delta）、cam2world/OpenGL→OpenCV、crop/raymap 同步、左右乘旋转都必须过 gate。

### 3.2 第三直接方法

| 工作 | 状态/方法 | 是否测 persistent drift | 资产 |
|---|---|---|---|
| KYC（Jiang 等，ICRA 2026） | Plücker 条件化；ACT/DP/SmolVLA | **无**；作者只承认位姿估计在弱纹理/重叠不足时不可靠、误差会累积 | 代码/任务/示范；无训练 checkpoint |
| CamVLA（Li 等，2026） | 从 RGB 估 hand-eye；camera-frame delta | **只测 IID 每决策重采样旋转噪声**；5° 58.7，12° 仍 > π0 36 | 代码 coming soon；无权重 |
| AnyCamVLA（Heo 等，IROS 2026，arXiv 2603.05868v2） | LVSM 新视角合成；依赖 ArUco 跟踪/已知相机参数 | **无** calibration drift/stale extrinsics 测试 | 代码 repo 链接；权重未说明 |
| RayViT（Wang 等，arXiv 2607.29622，2026） | Plücker 注入预训练 ViT | 摘要**无** persistent drift 测试 | 无代码链接 |

所以“persistent bias 是否比同边际 IID 更破坏”**确实没有被这四篇直接回答**；但它是**窄 robustness 问题**，不是新学习机制。

### 3.3 这个验证问题是否只是“已知噪声换相关性”？

**一半是，一半不是。**
- 若只测“persistent vs IID 的成功率差”，它确实只是把已知噪声换成时间相关结构；审稿人会问“这为什么不等于一次鲁棒性消融”。
- 要让它成为有价值的问题，必须加**机制量**：persistent bias 是否产生**系统性动作帧旋转/偏移**并在 episode 内累积，而 IID 只增加方差；以及**真实相机移动 + stale metadata** 这一生态臂是否比“冻结图像 + 错 metadata”更糟。前者能区分“相关性结构”与“单纯噪声幅度”，后者对应真实部署。
- 若不做这两项，我同意它只是 robustness ablation，**不足以支撑论文**，只配做 kill test。

### 3.4 预算/统计/语义漏洞

1. **8 GPUh 对两个 60k-step 模型很可能不够**：2×60,003=120,006 steps；8 GPUh=28,800 GPU-s，要求 **4.17 steps/s**。每步 batch70、单相机 256×256、CPU 4 核即时渲染，0.24s/step 是乐观值；KYC 代码自身允许单次跑到 7.5h。**先 pilot 测 steps/s；若 <4.17，两个完整模型不可能在 8 GPUh 内完成。** 此时只能 C-only 或截断，并标 PARTIAL/预算诊断。
2. **单训练 seed**：within-C persistent vs IID 是配对比较，可控制 seed；但不能外推到其他训练 seed。50 test roots 是评估精度，不是训练方差。
3. **50 roots 对高二值成功率可能欠功效**：若 baseline ~90%，discordant pairs 少，5–10pp 差异未必可检出。预登记 MDE 和 exact McNemar/paired bootstrap；否则只能报方向与 CI。
4. **C vs U 架构混淆**：C 多一个 Plücker 分支；只能做系统级比较，不能称“conditioning 的因果效应”。**主对比应是 within-C persistent vs IID**；C vs U 是次要的应用问题。
5. **评估解耦未实现**：当前 `_image_to_tensor` 用同一 pose 渲染与条件；必须改成 render_pose / condition_pose 两个参数，并验证 accurate condition 与官方一致。
6. **动作/相机语义未验收**：KYC delta EEF 与 CamVLA camera-frame delta 公式不同；`env.set_init_action()`、`np.flipud`、OpenGL/OpenCV、crop/raymap 同步，任何一个错都会制造假效应。必须先做已知动作/已知像素射线测试。
7. **敏感性/阳性/阴性对照**：
   - 阳性：C + accurate extrinsics 应复现 KYC Lift ACT ~60.6%（至少同量级）。
   - 阴性：U 在 metadata 扰动下应**严格不变**（代码路径确认不用 extrinsics）。
   - 敏感性：shuffle/zero Plücker 应改变动作；若不变，C 根本没使用几何，实验 MEASUREMENT-LIMITED。
8. **多重比较**：0/5/10° × persistent/IID × C/U × real-move，条件很多；预登记唯一主对比（C, 10°, persistent vs IID），其余为次要/探索，Holm 或分层报告。
9. **真实移动臂**：相机移动会同时改变图像与 metadata；必须分 (a) 移动+正确 metadata、(b) 移动+stale metadata、(c) 冻结图像+stale metadata。否则无法区分视觉 OOD 与标定错误。

### 3.5 修正后的首夜协议

**Gate（≤90 min，不通过则停）**：
- 最小资产：单 Lift HDF5 + 必要依赖/ResNet 权重；不跑 `setup.sh` 全量。
- 语义：已知 delta 动作方向、cam2world/OpenGL→OpenCV、crop/raymap 同步、Plücker 敏感性。
- 吞吐：测 steps/s；若两模型 <4.17 steps/s，改为 **C-only** 或截断；截断只称预算诊断。
- 阳性/阴性：C accurate ≈ KYC 量级；U metadata 扰动不变。

**Stage 1（主问题，优先 C-only）**：
- 训练 C（官方 Plücker）单 seed、固定预算；最终 checkpoint 预登记，不看 test 择优。
- 50 个独立 state-camera roots；0/5/10°；persistent（每 root 一个固定旋转，整段保持）vs IID（每决策从同一分布重采样）；只扰动 conditioning，图像/物理状态冻结。
- 主指标：10° persistent vs IID 成功率差；次指标：动作帧偏置（mean action rotation error）、episode 内累积、0° 参考。
- 若 C-only 预算都不够，停止；不硬上 U。

**Stage 2（仅当 Stage 1 完成且有预算）**：
- 训练 U（RGB-only，随机视角）同数据/步数；比较 C vs U 在 accurate/persistent 下的系统级差异；明确架构混淆。
- 真实移动 + correct/stale metadata 作为生态臂，不与冻结图像臂混算。

**Stage 3（下一阶段，不在首夜）**：
- pose-jitter 训练作为强简单基线；若它闭合 persistent 差距，停止，不称新方法必要。

**不能宣称**：新方法、自然发生率、真实部署普遍性、训练 seed 方差、C vs U 因果、persistent bias 是真实失败主因（除非 real-move 臂支持）。

---

## 4. G：降级理由修正，仍不开实验

- ManiGuard 代码/数据**真实存在**：`github.com/NU-IDEAS-Lab/ManiGuard`；HF collection；200 任务、8,000 示范、约 11.6M 帧、五相机；Table 3 报 **6–21% 成功 rollout 违规**；安全数据微调后 safe success 7.5–29.8%，仍有 **21–42% engaged 违规**。
- 微调是**普通监督模仿**，只用“成功且安全”过滤数据；**没有**近违规重加权/重标注；monitor 信号作 cost/reward/shielding 明确是 future work。
- 所以 G 的“训练侧利用 monitor 信号”不是已被覆盖，但也**不是已证缺陷**；它是标准 constrained IL/安全 RL 的小增量，且没有具体任务/样本/预算协议。
- **降级理由改为**：学习新意未建立 + 具体资源协议未建立；**不是**“全量 200 任务太大所以单任务不能验证”。不静默换自建关节限位任务；G 只作 benchmark/reference。

---

## 5. 是否足以启动限定复现

**结论：F 可作为一次“条件性问题验证”，但当前协议不能按原样冻结；先过 gate，且优先 C-only。**

- **足以启动的部分**：KYC 官方 LiftRand/ACT 配置、20001 epochs、200/10 数据、代码/示范、精确 Table I；问题可证伪；不需要新算法；单 3090 可承载一个小 ACT。
- **不足以直接启动的部分**：
  1. 8 GPUh / 12h 对两个完整 60k-step 模型**未证明可行**；4.17 steps/s 是硬门槛，CPU 渲染很可能达不到。
  2. `setup.sh` 未锁版本/全量下载；最小资产未验证。
  3. 动作/相机/Plücker 语义未验收；评估解耦未实现。
  4. 单 seed、50 roots、高二值成功率 → 只能做大效应方向性证据，不能做精确比较。
  5. C vs U 架构混淆；主问题应 within-C persistent vs IID。
- **必须前置的强反例**：
  - C accurate 不能复现 KYC 量级 → 实现/语义错，停。
  - Plücker shuffle/zero 不改变动作 → C 未用几何，MEASUREMENT-LIMITED。
  - U 在 metadata 扰动下变化 → 代码泄漏，停。
  - persistent 10° 成功率下降 <5pp 或与 IID 无差 → 问题在当前范围 VALID-NEGATIVE（若精度足够）或 INCONCLUSIVE。
  - 真实移动臂显示效应由视觉 OOD 主导 → 标定错误不是主因。

---

## 6. 最强分歧

1. **persistent vs IID 是否是科学问题，还是鲁棒性消融**：我认为只有加上动作帧偏置机制与 real-move/stale 生态臂，才超过“已知噪声换相关性”；否则只是 kill test，不足以论文。
2. **C vs U 是否必要**：我认为主对比应是 within-C；C vs U 受架构混淆，只能系统级解释。Codex 若坚持 C vs U 作为主问题，需要承认它不是因果比较。
3. **8 GPUh 是否可行**：按 120k steps 计算需 4.17 steps/s；KYC 的 CPU 即时渲染很可能达不到。若 Codex 有本机吞吐数据，请给出；否则不能冻结 20001×2。
4. **G 是否还有备选价值**：我同意暂不开；但降级理由是学习新意/协议，不是数据规模。

---

## 7. 最终

- **C1 否决为方法候选**；COT 覆盖机制，IDP 因果未证伪但不再支撑新题；toy+PushT 不值一晚。
- **G 降级为 benchmark/reference**；不开实验，不换自建任务。
- **F 保留为唯一条件性问题验证**：先 gate；优先 C-only within-model persistent vs IID + 动作偏置；U 仅在预算允许时作系统级参照；pose-jitter 训练留到下一阶段。
- **不宣称创新；不把复现当贡献；不在未过 gate 前承诺 8 小时作业。** 若 gate 失败或效应为零，本轮无实验备选。
