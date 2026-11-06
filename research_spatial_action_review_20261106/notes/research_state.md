# 研究状态（本次复审，可持续恢复）

- 会话性质：全新独立会话。未继承任何此前聊天记录、角色或结论。
- 日期：2026-11-06（Asia/Shanghai）。检索截止：2026-11-06。
- 工作目录：`/home/asus/EAI/research_spatial_action_review_20261106/`
- 分支：`codex/spatial-action-review-20261106`
- 范围：只读文献复审 + 研究设计 + 原创文档 + 授权发布。**未运行任何实验、训练、GPU 推理、仿真、模型/数据下载。**
- 旧报告读取方式：`git show codex/spatial-action-survey-20261105:<path>`，按 EXECUTIVE_SUMMARY → FINAL_REPORT → SELF_AUDIT → nearest_neighbor_review 顺序实际读取。

## 已完成

1. 读完旧分支四份指定材料（摘要 688 行完整报告、268 行自检、139 行最近邻笔记）。
2. 阶段 A：建立上轮判断复审表（`reports/PRIOR_JUDGMENT_AUDIT.md`），覆盖 C1 五类疑问与门槛逻辑。
3. 阶段 B：实际核查 10 篇核心论文的全文/关键章节（本地全文来自上轮公开下载的 arXiv 文本，已复制到本目录 `papers/`，不提交）：
   - 2607.09825 More Structure（全文）
   - 2610.18843 LIBERO-RIG（正文 + Table 5 + Appendix D + Limitations）
   - 2609.12641 LIT（Table I/II、§IV-B/C/D、真实机器人段）
   - 2510.02268 KYC（Table I、§IV-C、动作空间与裁剪消融）
   - 2610.01626 action-chunk stability（摘要、§1、§4.2–4.3）
   - 2609.27247 CMA（摘要、§III–V、Table 2）
   - 2512.02902 FTM/FLA（方法、Table、§4）
   - 2606.02277 RSB（Table 3 附近与 95.92% 上下文）
   - 2610.29646 decision value（摘要、§5.1/5.4）
   - 2608.03052 proprioceptive state（引言、贡献、任务族设计）
   - 另读 2605.18746 ESI-Bench、2609.37292 A-FAR、2602.12032 GAP、2602.23408 action space、2609.28955 ActGaze、2609.16815 embodiment dependence、2609.06114 DLS 的关键段落。
4. 阶段 B 补充检索：9 组 arXiv API 查询（见 `notes/search_log.md`），新增核查 2610.12457 SpatialHarness、2609.39145 Blackout vs Freeze、2609.33707 View Collapse、2605.19986 MetaFine、2608.15938 open-loop、2607.01804 VLA-Corrector、2610.19765 RAIN、2608.27497 MAGP 等摘要。
5. 自有再分析（仅对已发表数字做算术，不是实验）：
   - LIT Table II 28 个架构×扰动单元：headroom 零模型 Δ=α(1−b) 的 R²≈0.49，corr≈−0.70。
   - KYC Table I 18 个模型×任务单元：同一零模型 R²<0，corr≈−0.17。
   - 结论：headroom 是干预/数据集依赖的强混杂，不是普遍主解释；上轮把它称为"最严重风险"属过度概括。
6. 资产只读核查：LIT 仓库（Apache-2.0，一个 checkpoint + 292 episodes 数据 + eval 脚本）、KYC 仓库（MIT，无权重，单 seed 数小时–一天）、LIBERO（MIT/CC BY 4.0，Python 3.8 + torch 1.11）、ManiSkill（Apache-2.0 代码 / CC BY-NC 资产）、ACT（MIT，两个仿真任务）。

## 关键新发现（相对上轮）

- **构造错位 1**：LIBERO-RIG 的 "tolerance per axis" 是**硬件扰动幅度容限**（模型在哪一级 rig 扰动前失效），不是任务几何容差 τ。上轮把它当作"任务容差已被操作化"的证据，属误读。
- **构造错位 2**：More Structure 的 3D oracle 是**特权目标坐标信息**（goal token），不是"空间精度/表征升级"。把它的结果外推为"精度干预只修 Near-Miss"缺少同一自变量的证据。
- **事实错误**：上轮写 No-Grasp "15/15/24 完全不变"；24 比 15 高 60%，原文只说 "not reduced"。这直接削弱"定向干预只修对应失败模式"的前提。
- **headroom 被高估**：见上，KYC 18 单元反驳了"基线越低涨得越多"的普遍性；LIT 内约一半方差。
- **KYC 自带廉价基线未被上轮排除**：随机裁剪（random cropping）在全部任务上提升成功率；上轮的"空间升级收益"没有与裁剪对齐预算比较。
- **决策价值标准的误用**：2610.29646 的 top-k 选择单元是 80 个留出语料；把它套到 5 个任务是统计上不可估计的。
- **竞争密度**：2026 年"检测—纠正/自适应计算/主动观察/遮挡记忆/安全约束"每一格都已有 5–10 篇直接工作（见 `notes/limits_and_result_differences.md` §4）。

## 当前判断（待写入最终报告）

- C1 按原表述应**放弃**：构造效度不成立、预测时点泄漏、统计单元不足、前提被自身证据反驳。
- 唯一仍值得 Gate A 只读核查的替代问题是**状态级"局部空间余量 × 误差增益"**（候选 A1），但它不是现成课题：需要先证明 τ(s)、g(s) 可测且非均匀，并且要与 2610.01626、MetaFine、SpatialHarness 等一手竞争逐篇比对。
- 本轮不建议申请 Gate B 实验授权。

## 待核查 / 下一步（只读）

1. 读全 2610.01626 的 §4 全部表格，确认 λ 的方差不只是任务难度代理。
2. 读全 2605.19986 MetaFine（目前仅摘要）：它的"局部空间结构"因果干预是否已经做了"margin×gain"的连接。
3. 读全 2610.12457 SpatialHarness（目前仅摘要）：信息充分性框架是否已覆盖候选 A1 的上界论证。
4. 读全 2608.15938：开环/闭环反应性与"空间状态更新"的边界。
5. 在 ManiSkill 任务几何上做纯 CPU 的解析容差估算（不训练、不渲染），检验 τ 是否在阶段间差 >2×；若不能，A1 直接停止。

## 真实访问限制

- GitHub REST API 被限流（403），仓库核查改用网页；未 clone、未安装。
- 部分论文只有 HTML 渲染文本，表格顺序在纯文本中错位；所有引用数字均已回到上下文人工确认。
- 未获取 LIBERO-RIG 的代码/manifests（论文称发布，但 arXiv 页与正文无 URL）。
- 未读任何私有标签、场景真值或受保护输入。
