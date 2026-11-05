# 检索日志（空间理解与机器人行动）

- 检索截止日：**2026-11-05**（Asia/Shanghai）。所有入库记录 `published <= 2026-11-05`。
- 实际检索日期：2026-11-05。
- 执行者：Claude Code CLI（DeepSeek 后端）独立会话，无其他 agent。

## 检索入口与可用性

| 入口 | 状态 | 说明 |
|---|---|---|
| `https://export.arxiv.org/api/query` (Atom API) | 可用 | 全部布尔检索与元数据来源 |
| `https://export.arxiv.org/html/<id>v1` (LaTeXML) | 可用，偶发 HTTP 429 | 全文主力来源（0.1–0.6 MB/篇，适合慢链路） |
| `https://arxiv.org/pdf/<id>` | 间歇失败（SSL 35 / 000） | 前 16 篇用 PDF；后续改用 HTML |
| `api.semanticscholar.org` | HTTP 429 | **未使用**，不作为任何证据 |
| `api.openalex.org` | HTTP 429 | **未使用** |
| GitHub REST API | 可用 | 资产/许可证核查（只读） |
| 机构页面 / 项目页 | 部分可用 | 用于代码与数据入口确认 |

访问限制说明：
1. 本机对 `arxiv.org` 直连间歇性返回 `SSL_ERROR_SYSCALL`，故 PDF 仅部分获取；其余全文来自 arXiv 官方 HTML 渲染，属同一论文的官方版本，但**页码/图表编号可能与 PDF 不完全一致**，笔记中以章节标题定位为主。
2. Semantic Scholar / OpenAlex 被限流，因此**没有做跨库引文追踪**（forward/backward citation chasing）。这是本次覆盖的主要缺口，已在 `reports/SELF_AUDIT.md` 记录。
3. 9 篇 HTML 抓取遇到 429，降级为 `ABSTRACT_ONLY`，已在登记表中标注。

## 检索策略

先建立 A–F 问题图谱，再按证据筛选；不使用"先定方法再找问题"的顺序。

- **R1（38 条查询，1251 命中，去重 1093）**：A 跨视角/坐标系、B 可行动空间表示、C 时序记忆、D 主动观察、E 空间推理与行动关系、F 相邻方向（世界模型、3D 基础模型、场景图、高斯泼溅等）。
- **R2（26 条，572 命中，新增 443）**：点名核查经典与直接竞争工作（RoboPoint、RoboSpatial、SpatialVLM、VSI-Bench 等），并补 action space / 等变 / 标定 / 不确定性 / 局部修复。
- **R3（24 条，403 命中，新增 258）**：针对"知道—做到"缺口、反事实、弃权、再观察、信息价值、位姿误差。
- **R4（18 条，302 命中，新增 99 相关）**：外参误差、标定漂移、系统误差 vs 随机误差、空间干扰项、最小充分状态、误差传播。
- **R5（12 条，132 命中，新增 78）**：多模态冲突、传感器仲裁、模态缺失、因果混淆、捷径。
- **R6（12 条，198 命中，新增 101）**：容差、误差预算、精度需求、"何时有帮助"、阶段划分、扰动研究、oracle 差距。

累计去重后进入标题级筛选的记录约 **2360** 条（R1–R6 元数据合并）。标题级筛出约 300 条相关，进一步选出 **95 篇**进入结构化登记；其中 **87 篇**获得可提取全文（PDF 或 arXiv HTML），实际完整读取 33 篇、部分读取 21 篇，其余 41 篇仅读摘要（第四轮补读后）。

## 查询明细

| round | label | query | hits |
|---|---|---|---:|
| R1 | A_view_invariance | `all:"view-invariant" AND all:manipulation` | 16 |
| R1 | A_camera_pose | `abs:"camera pose" AND abs:policy AND abs:robot` | 40 |
| R1 | A_camera_cond | `abs:"camera-conditioned" OR abs:"camera conditioning"` | 30 |
| R1 | A_coordinate_frame | `abs:"coordinate frame" AND abs:manipulation AND abs:learning` | 14 |
| R1 | A_cross_view | `abs:"cross-view" AND abs:manipulation` | 40 |
| R1 | A_frame_reference | `abs:"frame of reference" AND abs:robot` | 19 |
| R1 | A_6dof_generalization | `abs:"6-DoF" AND abs:"generalization" AND abs:manipulation` | 30 |
| R1 | B_affordance_vla | `abs:affordance AND abs:"vision-language-action"` | 40 |
| R1 | B_3d_vla | `abs:"3D" AND abs:"vision-language-action" AND abs:manipulation` | 40 |
| R1 | B_pointcloud_policy | `abs:"point cloud" AND abs:manipulation AND abs:policy` | 40 |
| R1 | B_reachability | `abs:reachability AND abs:manipulation AND abs:learning` | 30 |
| R1 | B_spatial_rep | `abs:"spatial representation" AND abs:robot` | 40 |
| R1 | B_grasp_vlm | `abs:"grasp" AND abs:"vision-language model" AND abs:manipulation` | 40 |
| R1 | C_spatial_memory | `abs:"spatial memory" AND abs:manipulation` | 23 |
| R1 | C_object_permanence | `abs:"object permanence" AND abs:robot` | 14 |
| R1 | C_occlusion | `abs:occlusion AND abs:"manipulation" AND abs:policy` | 40 |
| R1 | C_belief_state | `abs:"belief state" AND abs:manipulation` | 20 |
| R1 | C_dynamic_manip | `abs:"dynamic scene" AND abs:manipulation AND abs:policy` | 19 |
| R1 | C_vla_memory | `abs:memory AND abs:"vision-language-action"` | 40 |
| R1 | D_active_perception | `abs:"active perception" AND abs:manipulation` | 40 |
| R1 | D_nbv | `abs:"next-best-view" AND abs:manipulation` | 22 |
| R1 | D_info_gain | `abs:"information gain" AND abs:manipulation AND abs:robot` | 30 |
| R1 | D_active_vla | `abs:"active" AND abs:"vision-language-action" AND abs:manipulation` | 40 |
| R1 | D_active_vision | `abs:"active vision" AND abs:"manipulation"` | 25 |
| R1 | E_spatial_bench | `abs:"spatial reasoning" AND abs:benchmark AND abs:"vision-language"` | 50 |
| R1 | E_spatial_intelligence | `abs:"spatial intelligence" AND abs:robot` | 40 |
| R1 | E_vlm_spatial_fail | `abs:"spatial" AND abs:"vision-language models" AND abs:"fail"` | 40 |
| R1 | E_spatial_action | `abs:"spatial reasoning" AND abs:"robot" AND abs:"action"` | 50 |
| R1 | E_grounding_action | `abs:"spatial grounding" AND abs:manipulation` | 40 |
| R1 | E_vsi | `abs:"spatial" AND abs:"video" AND abs:benchmark AND abs:reasoning AND abs:robot` | 40 |
| R1 | F_world_model | `abs:"world model" AND abs:manipulation AND abs:action` | 40 |
| R1 | F_spatial_vla | `abs:"spatial" AND abs:"vision-language-action"` | 50 |
| R1 | F_depth_vla | `abs:depth AND abs:"vision-language-action"` | 30 |
| R1 | F_3dfm | `abs:"3D foundation model" AND abs:robot` | 30 |
| R1 | F_scene_graph | `abs:"scene graph" AND abs:manipulation AND abs:policy` | 19 |
| R1 | F_spatial_prompt | `abs:"spatial prompting" OR abs:"spatial prompting"` | 20 |
| R1 | F_gaussian_splat | `abs:"Gaussian splatting" AND abs:manipulation AND abs:robot` | 30 |
| R1 | F_imitation_spatial | `abs:"imitation learning" AND abs:"spatial" AND abs:manipulation` | 40 |
| R2 | G_roboPoint | `ti:"RoboPoint"` | 1 |
| R2 | G_vsibench | `ti:"VSI-Bench"` | 0 |
| R2 | G_robospatial | `ti:"RoboSpatial"` | 2 |
| R2 | G_spatialvlm | `ti:"SpatialVLM"` | 1 |
| R2 | G_roboreferral | `ti:"spatial" AND ti:"referring"` | 20 |
| R2 | H_action_space | `abs:"action space" AND abs:"generalization" AND abs:manipulation` | 40 |
| R2 | H_relative_action | `abs:"relative action" OR abs:"delta action"` | 30 |
| R2 | H_equivariant | `abs:equivariant AND abs:policy AND abs:manipulation` | 40 |
| R2 | H_calibration | `abs:calibration AND abs:"manipulation" AND abs:"uncertainty" AND abs:policy` | 16 |
| R2 | H_uncertainty_action | `abs:uncertainty AND abs:"visuomotor" AND abs:policy` | 15 |
| R2 | H_spatial_cot | `abs:"chain-of-thought" AND abs:"spatial" AND abs:robot` | 30 |
| R2 | H_vlm_action_gap | `abs:"vision-language" AND abs:"action" AND abs:"gap" AND abs:robot` | 30 |
| R2 | H_grounding_fail | `abs:"grounding" AND abs:"failure" AND abs:"manipulation" AND abs:"vision-language"` | 30 |
| R2 | H_depth_est | `abs:"monocular depth" AND abs:"manipulation" AND abs:policy` | 5 |
| R2 | H_handeye | `abs:"hand-eye" AND abs:"calibration" AND abs:"policy"` | 3 |
| R2 | H_affordance_transfer | `abs:affordance AND abs:"generalization" AND abs:"manipulation"` | 40 |
| R2 | H_spatial_pretrain | `abs:"spatial" AND abs:"pretraining" AND abs:"robot"` | 30 |
| R2 | H_world_model_action | `abs:"world model" AND abs:"action" AND abs:"spatial" AND abs:robot` | 30 |
| R2 | H_gui_ground | `abs:"spatial" AND abs:"VLM" AND abs:"robot" AND abs:"benchmark"` | 40 |
| R2 | H_recovery | `abs:"failure recovery" AND abs:"manipulation" AND abs:"vision-language"` | 19 |
| R2 | H_interactive_perc | `abs:"interactive perception" AND abs:manipulation` | 17 |
| R2 | H_occlusion_bench | `abs:"occlusion" AND abs:"benchmark" AND abs:"robot"` | 30 |
| R2 | H_camera_intrinsics | `abs:"camera" AND abs:"calibration" AND abs:"manipulation" AND abs:"learning"` | 30 |
| R2 | H_3d_scene_graph_action | `abs:"3D scene graph" AND abs:"manipulation"` | 20 |
| R2 | H_grasp_pose_vlm | `abs:"grasp pose" AND abs:"vision-language"` | 23 |
| R2 | H_spatial_interface | `abs:"spatial interface" OR abs:"action interface" AND abs:"robot"` | 30 |
| R3 | I_knowing_doing | `abs:"knowing-doing" OR abs:"knowing doing gap"` | 16 |
| R3 | I_reasoning_action_gap | `abs:"reasoning-action gap" OR abs:"reasoning action gap"` | 1 |
| R3 | I_representation_action | `abs:"representation" AND abs:"action" AND abs:"gap" AND abs:"robot"` | 30 |
| R3 | I_vlm_action_misalignment | `abs:"VLM" AND abs:"action" AND abs:"misalignment"` | 20 |
| R3 | I_action_attribution | `abs:"attribution" AND abs:"failure" AND abs:"robot" AND abs:"manipulation"` | 22 |
| R3 | I_counterfactual_spatial | `abs:"counterfactual" AND abs:"spatial" AND abs:"robot"` | 15 |
| R3 | I_intervention | `abs:"intervention" AND abs:"spatial" AND abs:"robot" AND abs:"policy"` | 17 |
| R3 | I_abstention | `abs:"abstain" OR abs:"abstention" AND abs:"robot"` | 20 |
| R3 | I_reobserve | `abs:"re-observe" OR abs:"reobserve" OR abs:"re-look"` | 20 |
| R3 | I_information_value | `abs:"value of information" AND abs:"robot"` | 17 |
| R3 | I_spatial_uncertainty | `abs:"spatial uncertainty" AND abs:"manipulation"` | 4 |
| R3 | I_pose_error | `abs:"pose error" AND abs:"manipulation" AND abs:"policy"` | 6 |
| R3 | I_calibration_bias | `abs:"miscalibration" AND abs:"robot"` | 20 |
| R3 | I_decision_change | `abs:"decision" AND abs:"changed" AND abs:"policy" AND abs:"robot"` | 20 |
| R3 | I_attention_spatial | `abs:"attention" AND abs:"spatial" AND abs:"manipulation" AND abs:"diagnos"` | 0 |
| R3 | I_oracle_study | `abs:"oracle" AND abs:"spatial" AND abs:"manipulation"` | 12 |
| R3 | I_privileged | `abs:"privileged" AND abs:"manipulation" AND abs:"distillation"` | 25 |
| R3 | I_when_to_ask | `abs:"when to ask" OR abs:"clarification" AND abs:"robot"` | 20 |
| R3 | I_occlusion_action | `abs:"occlusion" AND abs:"action" AND abs:"polic"` | 1 |
| R3 | I_view_selection | `abs:"viewpoint selection" AND abs:"manipulation"` | 10 |
| R3 | I_3d_error_propagation | `abs:"depth" AND abs:"error" AND abs:"policy" AND abs:"manipulation"` | 17 |
| R3 | I_robot_frame | `abs:"robot frame" OR abs:"robot-centric" AND abs:"policy"` | 30 |
| R3 | I_spatial_generalization | `abs:"spatial generalization" AND abs:"manipulation"` | 30 |
| R3 | I_object_centric_action | `abs:"object-centric" AND abs:"action" AND abs:"policy"` | 30 |
| R4 | J_extrinsic_error | `abs:"extrinsic" AND abs:"error" AND abs:"manipulation"` | 13 |
| R4 | J_calibration_drift | `abs:"calibration drift" OR abs:"calibration error" AND abs:"policy"` | 25 |
| R4 | J_systematic_vs_random | `abs:"systematic" AND abs:"random" AND abs:"error" AND abs:"policy"` | 10 |
| R4 | J_sensor_bias | `abs:"bias" AND abs:"camera" AND abs:"manipulation" AND abs:"learning"` | 6 |
| R4 | J_pose_noise | `abs:"pose noise" AND abs:"policy"` | 4 |
| R4 | J_robust_calibration | `abs:"calibration-free" AND abs:"manipulation"` | 6 |
| R4 | J_spatial_distractor | `abs:"distractor" AND abs:"spatial" AND abs:"robot"` | 25 |
| R4 | J_irrelevant_spatial | `abs:"task-irrelevant" AND abs:"spatial"` | 20 |
| R4 | J_minimal_info | `abs:"minimal" AND abs:"sufficient" AND abs:"state" AND abs:"robot"` | 20 |
| R4 | J_information_bottleneck | `abs:"information bottleneck" AND abs:"manipulation"` | 20 |
| R4 | J_when_3d_helps | `abs:"3D" AND abs:"helps" AND abs:"policy" AND abs:"manipulation"` | 9 |
| R4 | J_depth_value | `abs:"depth" AND abs:"benefit" AND abs:"policy"` | 20 |
| R4 | J_negative_result | `abs:"negative result" AND abs:"robot"` | 11 |
| R4 | J_ablation_spatial | `abs:"ablation" AND abs:"spatial" AND abs:"policy" AND abs:"manipulation"` | 25 |
| R4 | J_geometry_vs_semantics | `abs:"geometry" AND abs:"semantics" AND abs:"policy" AND abs:"manipulation"` | 25 |
| R4 | J_error_propagation | `abs:"error propagation" AND abs:"manipulation"` | 18 |
| R4 | J_sensitivity_analysis | `abs:"sensitivity" AND abs:"action" AND abs:"perturbation" AND abs:"policy"` | 25 |
| R4 | J_representation_necessity | `abs:"representation" AND abs:"necessary" AND abs:"robot" AND abs:"action"` | 20 |
| R5 | K_conflict | `abs:"conflict" AND abs:"modalities" AND abs:"policy" AND abs:"robot"` | 4 |
| R5 | K_arbitration | `abs:"arbitration" AND abs:"sensor" AND abs:"robot"` | 2 |
| R5 | K_trust_sensor | `abs:"trust" AND abs:"sensor" AND abs:"manipulation"` | 20 |
| R5 | K_proprio_vision_conflict | `abs:"proprioception" AND abs:"vision" AND abs:"conflict"` | 4 |
| R5 | K_reliability_weight | `abs:"reliability" AND abs:"fusion" AND abs:"manipulation"` | 25 |
| R5 | K_modality_dropout | `abs:"modality dropout" AND abs:"robot"` | 6 |
| R5 | K_sensor_failure | `abs:"sensor failure" AND abs:"policy" AND abs:"manipulation"` | 1 |
| R5 | K_which_modality | `abs:"which modality" AND abs:"robot"` | 3 |
| R5 | K_visual_proprio | `abs:"visual" AND abs:"proprioceptive" AND abs:"policy" AND abs:"manipulation"` | 25 |
| R5 | K_state_estimation_policy | `abs:"state estimation" AND abs:"end-to-end" AND abs:"manipulation"` | 19 |
| R5 | K_causal_confusion | `abs:"causal confusion" AND abs:"imitation"` | 18 |
| R5 | K_shortcut | `abs:"shortcut" AND abs:"visuomotor"` | 5 |
| R6 | L_tolerance | `abs:"tolerance" AND abs:"pose" AND abs:"manipulation"` | 25 |
| R6 | L_error_budget | `abs:"error budget" AND abs:"robot"` | 3 |
| R6 | L_precision_requirement | `abs:"precision requirement" AND abs:"manipulation"` | 20 |
| R6 | L_when_does_help | `abs:"when does" AND abs:"help" AND abs:"robot" AND abs:"representation"` | 0 |
| R6 | L_benefit_predict | `abs:"predict" AND abs:"benefit" AND abs:"robot" AND abs:"policy"` | 25 |
| R6 | L_task_demand | `abs:"task" AND abs:"demand" AND abs:"spatial" AND abs:"robot"` | 25 |
| R6 | L_sensitivity_task | `abs:"sensitivity" AND abs:"task" AND abs:"spatial" AND abs:"manipulation"` | 25 |
| R6 | L_heterogeneous | `abs:"heterogeneous" AND abs:"benefit" AND abs:"robot"` | 20 |
| R6 | L_phase | `abs:"phase" AND abs:"spatial" AND abs:"policy" AND abs:"manipulation"` | 21 |
| R6 | L_perturbation_study | `abs:"perturbation" AND abs:"study" AND abs:"manipulation" AND abs:"policy"` | 25 |
| R6 | L_oracle_gap | `abs:"oracle" AND abs:"gap" AND abs:"policy" AND abs:"manipulation"` | 9 |
| R6 | L_representation_choice | `abs:"which representation" OR abs:"representation choice" AND abs:"robot"` | 0 |

## 发现与筛选记录

1. **R1 直接否定了"泛化式"选题**：A/B 类查询返回的 2026 年论文密度极高（跨视角 40+、3D-VLA 40+），且多数以"加一个几何/深度/点云分支"为贡献。这类工作难以在小论文层面证明独立机制。
2. **R2 确认了经典工作已进入对比基线**：RoboPoint、RoboSpatial、SpatialVLM 均为公开资产，任何"空间提示/空间 VQA"类贡献都必须以它们为基线。
3. **R3/R4 是最有价值的一轮**：它把"空间信息是否被用于决策"变成可审计的问题（反事实审计、证据使用链、误差传播），同时显示该问题已被多条线并行占据（记忆审计、测试时诊断、运行时一致性）。
4. **R5 否定了"多模态冲突/仲裁"作为新颖切口**：视觉—本体感觉冲突与阶段依赖已被 2602.12032 直接研究并给出机制（本体感觉梯度主导）与补救（GAP）。
5. **R6 找到唯一未被直接占据的构念（此判断在第二、四轮被部分修正）**：现有"tolerance"在机器人学中指**规划可行域**（2607.03758）或训练目标中的**允许偏差走廊**（2604.21241）。第一轮写"LIBERO-RIG 不估计每任务阈值"是**错误的**——其 Table 5 正是 "Tolerance per axis"。修正后的缺口是：LIBERO-RIG 的容差按扰动轴、轴间不可比，且不预测"换空间表征能挽回多少"；More Structure 已单任务证明机制；二者未被连成跨任务预测关系。

## 未覆盖 / 待补

- 引文网络**部分完成**（第三、四轮）：S2 取到 6 个种子（KYC 28 篇施引、2512.02902 17、LIBERO-RIG 1、CMA 1、RSB 1、2610.01626 0），Google Scholar 另做 6 条关键词查询。**未穷举**；More Structure 的 S2 施引列表仍 429，但 OpenAlex 与 Scholar 均示零引用。因此"未被研究"只能表述为"在本轮查询与 95 篇登记中未发现"。
- 未检索中文文献库（CNKI/万方）与 IEEE Xplore 全文；会议终稿与 arXiv 版本的差异未逐篇比对。
- 41 篇仅摘要级；其方法细节与实验强度未核实，报告中不据此下强结论。

## 第二轮（后台接续，同日）

目的：核查第一轮交付后仍存在的真实缺口，而不是重复检索。

1. **重试引文入口**
   - `api.semanticscholar.org/graph/v1/paper/arXiv:2510.02268` → **429**（"Too Many Requests"）。
   - `api.openalex.org/works?filter=cites:W4414928220` → **429**（"budget ... used up ($0 remaining; resets at midnight UTC)"）。
   - `api.openalex.org/works?search=...` → **429**。
   - **可用**：`api.openalex.org/works/https://doi.org/10.48550/arXiv.<id>`（单篇查询）→ 200。据此为全部 95 条补齐出版状态：11 篇为会议论文（KYC=ICRA 2026；SpatialVLA/LIBERO-X/2506.06196=RSS；SpatialVLM/RoboSpatial=CVPR；RSB/2609.07047=EMNLP Findings；2605.30161/2607.01658/2603.22876/2601.09954=LNCS），其余为 arXiv 预印本。
   - 其他替代入口也失败：`semanticscholar.org/arxiv/2510.02268` → 404；S2 内部 citations API → 404；`scite.ai` → 403。
   - 结论：**出版状态已核实，施引文献仍不可得**。这是本轮唯一未消除的检索缺口。

2. **补读全文（6 篇）**
   - `2609.18514` ActiveScale、`2512.02902`、`2610.22997`、`2603.12193`、`2601.08325`、`2602.04600`。
   - 其中 `2512.02902` 改变了结论强度：4K 参数 FTM 把 LIBERO 跨视角 48.5%→87.1%，4.7M 版本超过 π0.5 LoRA（467M），构成"空间表征不足"叙事的最强反例。

3. **重读三篇 C1 依赖论文的全文**
   - `2610.18843` LIBERO-RIG：Table 5 即 "Tolerance per axis"，第一轮"无人估计阈值"的判断错误，已更正。
   - `2607.09825` More Structure：Near-Miss 31%→2.5%，No-Grasp 15/15/24 不变；StackCube 为推断性例证，未做干预对照。
   - `2610.01626`：明确指出单一全局 contraction rate 不被经验支持。

4. **修订后果**
   - C1 由"容差预测收益"收窄为"失败模式构成预测收益"，评分 4.0→3.35，判定由"优先"改为"有条件、置信中低"。
   - 实验门槛由 4 条增至 6 条，新增"同任务不同失败模式变体"与"4K 参数级对齐对照"。

## 第三轮（同日，引文追踪）

Semantic Scholar citations 端点在本轮**间歇可用**（前两轮均 429），因此补做了首次施引文献核查。

| seed | 施引数 | 参考文献数 | 结果 |
|---|---:|---:|---|
| 2510.02268 KYC | 28 | 57 | 全部为视角/相机鲁棒性变体；无“空间升级收益预测”研究 |
| 2512.02902 | 17 | 42 | 对齐/适配类；无收益预测 |
| 2610.18843 LIBERO-RIG | 1 | 28 | 无 tolerance × intervention 研究 |
| 2609.27247 CMA | 1 | 29 | 发现 2602.17659（已补读） |
| 2606.02277 RSB | 1 | 29 | 发现 2610.29646（已补读） |
| 2607.09825 More Structure | — | — | **四次重试（30–60s 间隔）与 batch POST 均 429，未取到** |
| 2610.01626 | 0 | — | 取到：**0 篇施引**（新近发表，尚无索引引用） |

引文追踪新发现两篇关键工作并已登记：
- `2610.29646` From Association to Decision Value：证明“可靠且与下游相关”的诊断可能只有 +0.059 nats 的增量决策价值（CI 跨零），因此 C1 必须以**选择效用**评估。
- `2602.17659` When Vision Overrides Language：LIBERO-CF 反事实基准 + CAG 双分支动作选择，直接与 C2 竞争。

工具状态：OpenAlex `filter=cites:` 仍 429（共享 IP 日预算）；S2 web `/arxiv/<id>` 404、S2 旧 citations API 404、scite 403、Crossref（arXiv DOI）404。

## 第四轮（Google Scholar 通道）

前几轮只用了 arXiv API。本轮确认 `scholar.google.com/scholar` 可直接抓取（HTTP 200），因此补了一个非 arXiv 的检索通道，用于找措辞不同或发表在非 arXiv  venue 的工作。

查询（全部为 2026-11-05）：
- `"failure mode composition" robot manipulation`
- `"spatial tolerance" robot policy success`
- `"near-miss" "no-grasp" manipulation failure taxonomy`
- `predict "which tasks" "spatial representation" robot benefit`
- `"representation upgrade" robot manipulation benefit`
- `"More Structure, Not More Capacity"`（精确标题，用于确认施引数）

发现：
1. **没有**任何结果把“失败模式构成”作为预测表征收益的自变量；命中的是 Spa-Bench（基准）、More Structure（机制）与一篇 SO-101 失败/恢复基准（2606.08881，已补读登记）。
2. “spatial tolerance robot policy success” 的命中全部是定位/导航/执行相关，无 tolerance 作为任务属性预测收益的工作。
3. More Structure 的精确标题仅 1 条结果，页面**没有 "Cited by N"**，与 OpenAlex 的 cited_by=0 一致——其施引列表很可能本来就是空的，S2 的 429 因此不再是实质缺口。
4. 新发现 2606.08881：低成本 SO-101 真机上“执行不稳定”是主导失败源，已写入报告的失败模式与 C1 风险。

局限：Scholar 每次只返回前 10–20 条，且不做布尔完备检索；本通道用于“反向证伪”（找是否存在），不用于穷举。
