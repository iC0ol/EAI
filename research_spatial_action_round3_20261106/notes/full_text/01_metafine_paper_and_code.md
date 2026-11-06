# MetaFine：论文与官方代码只读核查

- 论文：He-Yang Xu, Pengyuan Zhang, Zongyuan Ge, Xiaoshuai Hao, Serge Belongie, Xin Geng, Yuxin Peng, Xiu-Shen Wei. *Beyond Binary Success: A Diagnostic Meta-Evaluation Framework for Fine-Grained Manipulation.* arXiv:2605.19986v1, 2026-05-19. 42 页。
- 代码：<https://github.com/Hiangx-robotics/MetaFine>，commit `9d23841684295abc3a4163c6a5918e2590555ffa`（2026-10-01），MIT License。
- 读取层级：论文全文（方法/实验/与代码相关附录）；代码逐文件静态阅读（未安装、未运行）。

## 1. 论文声明（事实层）

- 三维诊断：Understanding（语义干预/复合指令）、Perception（几何/光度扰动 + AUSC）、Behavior（阶段成功 + 轨迹平滑）。§1、§2。
- 任务图：原子技能 + 11 类 affordance；论文称 431 objects、1,078 parts、4,312 grasp poses（§A.2，line 1085 附近）。
- 任务规格含 `tolerances: {eps_pos_mm: 3.0, eps_ang_deg: 5.0}`（Fig. A1，line 1134）；阶段验收标准独立评估（§A.3.3，line 1469）。
- 感知扰动：几何 = 相机位置/朝向偏移（3/6/12 cm、3/6/12°）；光度 = 光照强度偏移（0.10/0.25/0.40）。扰动在场景初始化后、执行前注入，全程固定（§A.4，lines 1519–1566）。
- 关键结果：peg-in-hole 上 π0.5 overall 0%，Grasp 39%、Align 0%、Insert 0%；OpenVLA-OFT 47%/19%/3%（Table B7）。作者据此说二值成功率掩盖了 Align 阶段的差异。
- 因果干预：把 π0.5 的单尺度 SigLIP 换成多尺度 cross-attention encoder，冻结 VLM 与 action head；Grasp 39%→67%，Align 0%→32%（§2.4，lines 481–487）。作者称这是"encoder 的局部空间结构是精度因果瓶颈"的证据。
- 策略：7 个（ACT、DP3、Octo、OpenVLA、OpenVLA-OFT、π0、π0.5），均在 MetaFine 演示上微调；用作者官方超参（§B，lines 1645–1665）。

## 2. 代码实际实现（逐项）

### 2.1 已实现（VERIFIED）

- 19 个 env：`grasp_part, align_to_part, stand_up, peg_in_hole, toggle_switch, toggle_switch_table, lid_opening, stack_pyramid, slide_along, plug_charger, multi_skill, draw_triangle, rotate, door_env, take_out_and_grasp_part_into_box, put_blocks_in_box_and_take_out_memory, put_blocks_into_boxes, assembling_kits, assembling_kits_metafine_letter`（`core/env.py` 的 19 个 `@register_env`）。
- 21 个 skill（`core/skill.py` 的 21 个 `@register_skill`）。
- 任务图 YAML + 阶段谓词：`utils/task_graph.py:50-66`、`utils/eval_setup.py:93-126`、`core/env.py:2025-2200`。阶段是**独立布尔谓词**，不是有序状态机；`reached_stage` 只是取最高 flag（`utils/eval_metrics.py:95-105`）。
- 感知扰动：相机位置/朝向 + 环境光（`core/env_mixins.py:47-107`；`utils/eval_sweep.py:33-90`）。AUSC 计算已实现（`utils/eval_sweep.py:43-61`）。
- 配对 seed：`core/policies/pi05/evaluate.py:784-812` 先算 `episode_seeds`，再跨 profile 复用；clean/cam/light 用同一 physical seed。这是**状态配对**，有利于 A1 的因果比较。
- 连续误差读出：`PegInHoleEnv.evaluate()` 返回 `peg_head_pos_at_hole`（`core/env.py:640-658`）；`AssemblingKitsEnv.evaluate()` 返回 `pos_diff_norm`、`rot_diff`、`in_slot`，阈值 `pos_eps=2e-2`、`rot_eps=4°`、`height_eps=3e-3`（`core/env.py:3684-3720`）。
- 多物体阶段：`PutBlocksInBox.evaluate()` 返回 `stage_id` 与阶段布尔（`core/env.py:3466-3525`）。
- π0.5 eval 支持 `--task-graph`（`core/policies/pi05/evaluate.py:204-249, 586-700`）。

### 2.2 未实现 / 仅部分实现（PARTIAL）

- **论文的多尺度 cross-attention encoder 干预**：仓库中搜不到 `multi-scale`/`cross-attention encoder`/`causal intervention` 的实现；7 个 vendored 策略是原始架构。论文的因果干预结果无法从公开代码直接复现。
- **peg-in-hole 的 Grasp/Align/Insert 阶段 flags**：`PegInHoleEnv.evaluate()` 只返回 overall success + `peg_head_pos_at_hole`；没有阶段布尔。Table B7 的阶段数字需要额外脚本/谓词，仓库未提供。
- **结构化 tolerance schema**：论文 Fig. A1 的 `eps_pos_mm/eps_ang_deg` 是任务描述格式；代码中 tolerance 是谓词/环境里的硬编码阈值（`pose_near` 的 0.06 m、`pos_eps=2e-2` 等），`assets/*/capabilities.json` 只有 affordances，无 tolerance 字段。
- **局部空间偏移接口**：只有相机/光照扰动；没有 object pose、target pose、action offset 的内置注入接口。`placed_in`/`stacked_on` 是 TODO（`core/predicates.py:118-124`）。
- **paired perturbation manifest**：没有固定扰动清单；相机扰动在 `_default_sensor_configs` 用 `np.random.uniform` 采样，且 env 每 episode 重建（`pi05/evaluate.py:801`），扰动方向/幅度不随 episode seed 固定。
- **策略 checkpoint**：仓库内无 `.pt/.pth/.safetensors/.ckpt`；π0.5 eval 需要用户 `--policy-path`（`core/policies/pi05/README.md`）。论文的 7 策略结果需自行微调。
- **资产规模**：仓库 41 个 object 目录 / 40 个 capabilities；论文声称 431 objects / 1,078 parts。其余在 HF/ModelScope 数据集（未下载）。
- **专家演示的 grasp 成功判定**：`core/skill.py:184` 用 Qwen-VL API（`utils/evaluator.py`，需 `DASHSCOPE_API_KEY`）判 grasp 成功；这是外部 API 依赖，不是本地几何判定。

### 2.3 风险

- 相机扰动不可复现：`np.random.uniform` 未显式播种；同一 seed 的 clean/perturbed 物理初态配对，但相机偏移每次 env 重建都不同。
- 阶段谓词独立：一个 episode 可以"跳过"前一阶段而满足后一阶段；`reached_stage` 的解释需谨慎。
- 任务图 `multi_skill` 只加载单个 articulated object；多物体任务（put_blocks、assembling_kits）是 bespoke env，不走统一 task-graph。
- VLA 微调成本高：7 个策略、官方超参；3090 上 ACT/DP3 可行，π0.5/OpenVLA 不现实。
- 论文的"431 objects"与仓库 40 assets 的差距会影响任务多样性。

## 3. 对 A1 的可用性判断

- **可用**：`assembling_kits`/`metafine_letter` 提供连续位姿误差 + 硬容差（2 cm/4°/3 mm）+ 多物体干扰 + 相机扰动 + 配对 seed；`peg_in_hole` 提供 `peg_head_pos_at_hole`；`put_blocks` 提供 `stage_id`。这些足以构建 A1 的 `c(x)`（几何余量）与阶段暴露。
- **不可直接用**：`R_π`（策略对受控空间扰动的响应）与 `P_c`（动作误差到任务误差的闭环传播）没有内置接口；需要自写扰动注入与配对评估（Gate B/C 代码）。
- **结论**：MetaFine 是 A1 的**平台候选**，不是 A1 的**实现**。它已经占据"阶段级精度诊断 + 编码器因果干预"的一部分创新空间，但没有做 A1 的误差预算/预测/分配。
