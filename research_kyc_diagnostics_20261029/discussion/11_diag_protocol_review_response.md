# 第2次交叉审查：有限排障任务书

## 1. 两项争议

### 1.1 重复前向预算：接受 Codex 的重分配

10 回复要求“同入口重复测噪声”，但 8×4=32 已无额外额度，这是事实。任务书 §5A（第74行）改为：8 官方 prior + 8 自定义 prior + 4 个 t0 官方 prior 重复 + 8 个 posterior 首 seed + 4 个 t0 posterior 第二 seed = **32**，batch=1，失败/调试也计。这个分配可执行，我接受；不再要求额外重复。

但有一个**未测项**必须写明：4 次重复全部是官方 prior，**自定义入口的重复噪声没有测**。因此官方 vs 自定义的差异若落在 1e-5～1e-3 之间，不能自动归为“浮点噪声”；应报告为“入口差异，噪声底未知”。要求二选一：把 4 次重复拆成 2 官方 + 2 自定义，分别算 `rmax_official/rmax_custom`；或保留现分配，但明确 `rmax` 只代表官方入口，自定义小差异不作噪声解释。不能既不给自定义重复、又把差异归噪声。

### 1.2 posterior 必须优于 prior：接受撤回

10 的“posterior 在 6/8 优于 prior 才准进 C”不成立。健康 ACT 的 prior 可以接近 posterior；小 KL 也不单独证明 latent 问题。任务书 §5B 第88行明确撤销该门槛，正确。

Codex 的停止规则（第90–94行）我基本接受：只有 prior xyz 汇总不优于训练 median、且 ≥6/8 样本不优，同时出现严重输出集中或 posterior 明显更好（≤0.5 prior），才停止 C；且这是**机会成本规则**，停止后归 D/IMPLEMENTATION-LIMITED，不声称训练任务普遍无能力。这个逻辑成立。

但规则有一处**单位/基线歧义必须修**：第91行写“prior xyz 归一化 MAE ≥ train-median xyz MAE”，未说明 median 是原始米还是归一化空间。prior 输出经反归一化，median 由原始动作计算；两者必须统一到**同一 raw 米单位**（或同一 stats 归一化），否则比较无效。另，第84行“每维 median 在所有30位置重复”是弱常数；L1 的更公平对手是**训练集 per-position median（30×7）**。应把 per-position median 作为主常数，单向量重复 median 与 mean 作附加；否则 prior 可能轻易胜过一个过弱基线，导致错误进入 C。

## 2. 科学有效性

任务书能区分 H1/H2/H3，并把 H4 历史渲染保留为 UNKNOWN，方向正确：

- **H1**：§5A 用官方 `EpisodicDataset(transform=id)`、官方 `Evaluator._render_cam_image/_image_to_tensor` 与自定义 `policy_input` 三路独立取得同状态/同相机张量；不是官方和自定义都调同一 helper，避免循环验证。RGB 逐像素、ray/qpos/extrinsics/action 分别记录；共享 crop 用 tensor-only 检查；物理投影要求真实 MuJoCo 世界点/渲染像素，不用待检 ray 造点回投。合格。
- **H2**：§5B 的 expert/prior/posterior/常数对照、有效步与 padding 分母、xyz/轴角/夹爪分单位、方向/方差、KL/mu/logvar，足以判断 prior 是否只是常数；不再要求 posterior>prior。合格。
- **H3**：§6 用旧 dev 1000–1007 的 XML/state/RNG 与原 dev 相机，再配训练池 indices 0/25/…/175；明确 16 条只有 8 个物理 root，不是 16 独立样本；训练池相机配 dev 物理 state，不等于完整训练条件。合格，且没有把 0/8 写成普遍结论。
- **H4**：§4 要求 framebuffer 历史、版本、无 per-demo XML/RGB、无历史图像即 UNKNOWN，不重跑训练追认；合格。mujoco 3.3.0 满足 PR5 区间，不能当根因；合格。
- **YAML**：`eval_start_epoch=10000` 覆盖默认 20000 已核实；早期每次 10、后期 50，不能一概写 50；§4.7 正确。

**结论**：这是一次**有界的实施诊断**，不是论文复现，也不是新方法实验；只要不把 A 的入口差异直接判 H1 因果、不把 B 的 open-loop 地板当科学阴性、不把 C 的 0/8 当普遍无能力，科学有效性成立。

## 3. 预算与隐藏超额

- 32 固定前向 = 8 官方 prior + 8 自定义 prior + 4 官方重复 + 8 posterior 首 seed + 4 第二 seed；batch=1；失败/调试计入。**数字自洽。**
- 闭环 16 条 × ≤5 query = **80**；16×150=2400 env steps；与固定 32 合计 **112 policy calls**，§3 明示两类别，不混算。**自洽。**
- 总 1 GPUh、0 optimizer update、≤2GiB 新增磁盘、无下载；Stage0 不初始化 CUDA；Stage1 ≤1h；合格。
- 隐藏超额风险：A 的官方 Dataset/Evaluator helpers 会创建 `PluckerEmbedder`/渲染，GPU 时间必须计入 3600s；C 的 reset/render 也计入；`posterior` hook 失败重跑计调用；任务书已写“失败调用、调试、重复均计”，需 supervisor 实际计数。
- 泄漏风险：prior 不读 actions/成功/真值；posterior 只用训练 action 标签、绝不进闭环；C evaluator 标签不回注 policy；任务书写明。
- 假因果风险：A 超差只记“入口/数值未解释”，不直接判 H1；B 地板只作停止预算；C 0/8 宽区间。任务书已写；保留。
- **不可实现点/需澄清**：§5B 第91行单位歧义；§5A 自定义重复噪声未测；§5B 单向量 median 过弱；§5A 官方 Dataset 固定 t/camera 的“临时控制”必须用只读 wrapper/subclass，不能改 vendor 或改变正常数值计算；需记录并恢复 RNG。任务书写了“代码/上下文管理记录”，但未指定 wrapper 形式，建议明确。

## 4. 必须修改 vs 可选

**必须修改**
1. §5B 第84、91行：常数主对手改为**训练集 per-position median（30×7）**；单向量重复 median/mean 作附加；prior 与 median 统一 raw 米单位（或同一归一化），并同时报告两种分母。否则 H2 门槛无效。
2. §5A 第74行：4 次重复拆 2 官方 + 2 自定义，分别算 `rmax`；或明确自定义噪声未测，1e-5～1e-3 差异不作噪声解释。二者选一，写入协议。
3. §5A 第76行：明确 posterior 使用哪个入口（官方还是自定义）、hook 捕获哪些张量、绝不为 posterior 额外 forward；posterior 只用于 B 诊断，不参与 C 选择。
4. §5A 第67–68行：官方 Dataset 固定 t/camera 必须是只读 wrapper/subclass 或上下文控制，记录 patch、RNG、恢复；不得修改 vendor 源码或改变正常计算。
5. §5B 第90–94行：把停止规则写成可审计伪代码，明确样本级/汇总级、raw/normalized、mask 分母、6/8 判定、posterior 平均方式；停止后只能 D/IMPLEMENTATION-LIMITED，不得写 C。
6. §6 第100行：明确 16 条不是 16 独立 root；训练池 indices 0..175 只配旧 dev 物理 state，不是完整训练条件；不得用它们估计普遍成功率。

**可选建议**
- 增加 per-position mean 作为第二常数；不增加模型前向。
- 报告 posterior 两 seed 的方差，但不把重复当独立样本。
- 若物理像素对应不可靠，明确“未完成”，不扩样本、不改 ray。
- C 的 8 对 root 报告逐 root discordance 与描述区间，不做显著性/等价性宣称。

## 5. 审查结论

**APPROVE_WITH_REQUIRED_CHANGES。**

任务书在目标、阶段、预算、停止与回传上总体可执行；32 前向 + 80 query + 1 GPUh + 0 optimizer 的框架自洽，且能区分 H1/H2/H3，保留 H4 为 UNKNOWN。但 §5B 的常数单位/基线、§5A 的自定义重复噪声与 posterior 入口、§5A 的官方 Dataset 控制方式必须先修正；否则 H2 比较可能无效，H1 差异可能被误归噪声。

修改后请再送核验；**当前不是已过门，也不是执行授权**。不扩大研究范围，不做新方法、不重训、不跑正式 test。
