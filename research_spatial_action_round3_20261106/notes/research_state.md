# Round 3 研究状态

- 日期：2026-11-06（Asia/Shanghai）。检索截止：2026-11-06。
- 会话：接续上一轮原会话；上一轮报告作为可读历史证据，不重跑旧综述。
- 目录：`/home/asus/EAI/research_spatial_action_round3_20261106/`（ROUND3）。
- 分支：`codex/spatial-action-review-20261106`。
- 权限：只读文献/代码、理论/统计分析、方案设计、原创报告、授权发布。**未训练、未推理、未仿真、未安装/运行第三方代码、未下载模型/数据。**
- 实际执行的代码：`git clone --depth 1` MetaFine 仓库到 ignored `references/`；`pdftotext` 提取论文；arXiv API 查询；本地算术。未运行任何 MetaFine 脚本/env。

## 本轮完成

1. 读取 ROUND3 的 `USER_PROMPT.md`（SHA256 `8f233d42…8495`，19,579 字节，已核对）。
2. 回读上一轮 `reports/FINAL_REPORT.md` 的 A1 定义与 Gate A 清单。
3. 下载并读取 MetaFine 论文全文（42 页，`papers/2605.19986_metafine.txt`）。
4. `git clone` MetaFine 官方仓库（commit `9d23841684295abc3a4163c6a5918e2590555ffa`，2026-10-01，MIT），逐文件只读核查：
   - `README.md`、`core/env.py`、`core/env_mixins.py`、`core/predicates.py`、`core/skill.py`、`utils/eval_metrics.py`、`utils/eval_sweep.py`、`utils/eval_setup.py`、`utils/task_graph.py`、`utils/evaluator.py`、`core/policies/pi05/evaluate.py`、`core/policies/pi05/README.md`、`configs/*.yaml`。
   - 确认 19 个 env、21 个 skill、40 个 capabilities 资产（仓库内），与 README 一致；论文声称 431 objects/1,078 parts/4,312 grasp poses（数据集另发）。
5. 下载并读取 6 篇最近邻：2609.03142 EGR、2606.16504 APEX、2607.11167 Pix2Act、2610.02898 MixVLA、2609.33707 View Collapse、2609.39145 Blackout vs Freeze；以及上一轮已读的 2610.01626、2607.09825、2610.18843、2609.12641。
6. 重新形式化 A1 的因果链，区分：
   - 输入扰动 `δe_p`（可选、任务相关）；
   - 策略响应 `R_π = ∂a/∂e_p`；
   - 闭环传播 `P_c = ∂e_x/∂a`；
   - 任务几何余量 `c(x) = dist(φ(x), ∂A)`；
   - 策略容差 `T_π(s)`（行为量，需闭环 rollout）；
   - 任务结果 `Y`。
7. 结论：A1 原公式把 `T_π` 与 `c` 混为 `τ`、把 `R_π` 与 `P_c` 混为 `g`，存在定义循环与量纲错误；修正后的版本是**误差预算测量框架**，不是新方法机制。
8. 竞争核查结论：方法空间已被 EGR（证据门控的 invariance/sufficiency）、APEX（执行间隙）、MetaFine（编码器精度瓶颈）、ActGaze（动作接地 gaze）、Pix2Act（等变增广）、MixVLA（不变/非不变混合）、View Collapse（视角依赖）占据。
9. 决策：**选项 4**——目前所有候选都不合格，需要重新选择研究问题；A1 仅保留为测量型毕业论文章节，不作为方法型小论文。

## 已裁决的问题

- A1 是否可直接申请 Gate B？**否。** 其原始变量定义不成立；修正后是测量框架，缺独立方法机制。
- MetaFine 是否已占据 A1？**部分占据。** 它有阶段诊断、连续位姿误差、硬编码容差（2 cm/4°/3 mm）、相机扰动、配对 seed；但没有 R_π/P_c 测量、没有精度分配方法、没有论文中的多尺度编码器干预代码。
- 是否可用 MetaFine 作为 A1 平台？**可以，但不是 turnkey。** 无公开 checkpoint；论文结果需在 7 个策略上微调；任务图 stage 只对 multi_skill 生效；peg-in-hole 无 stage flags；相机扰动用未播种的全局 RNG。
- B1/B2/B3 是否更好？**否。** B1 方法空间饱和；B2 证据弱（单次 200 集，15 vs 24，两比例检验 p≈0.13 不显著）；B3 被 2602.23408（13,000+ 真机 rollouts）占据。

## 有限剩余工作（只读/决策，不实验）

1. 若研究者坚持"测量型小论文"：与导师确认论文形态；把 A1 重新表述为 error-budget 研究，不声称方法创新。
2. 若研究者坚持"方法型小论文"：需要换问题域并重做 Gate A；本轮不提供合格候选。
3. 不再扩大文献检索；本轮已覆盖最近邻与代码。

## 真实访问限制

- MetaFine 资产数据集（HF/ModelScope）未下载（大文件，未授权）；仓库内只有 40 个资产。
- 论文的 431 objects/1,078 parts 与仓库 40 assets 不一致；其余在数据集。
- 未获取任何策略 checkpoint；论文的 7 策略结果不可直接复现。
- GitHub API 仍限流；仓库用 `git clone` 只读获取。
- 未读 MetaFine 论文的每一页附录；已读方法、实验、代码相关附录。
