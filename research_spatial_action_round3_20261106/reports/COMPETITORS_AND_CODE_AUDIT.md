# 直接竞争与代码资源审计

- 审计对象：MetaFine（论文 + 官方仓库）与 6 篇最近邻。
- 方法：只读。`git clone --depth 1` 到 ignored `references/`；`pdftotext` 提取论文；逐文件阅读。**未安装、未运行、未下载模型/数据。**
- 状态：`VERIFIED` = 有直接代码/论文证据；`PARTIAL` = 部分实现/部分证据；`UNKNOWN` = 未找到或未核实；`HIGH_RISK` = 复现成本/失败概率高。

---

## 一、MetaFine 仓库事实

| 项 | 值 | 证据 |
|---|---|---|
| 仓库 | <https://github.com/Hiangx-robotics/MetaFine> | — |
| commit | `9d23841684295abc3a4163c6a5918e2590555ffa` | `git log -1`（2026-10-01 10:34 +0800） |
| 许可证 | MIT | `LICENSE` |
| tracked files | 7,139（含 assets 5,361） | `git ls-files | wc -l` |
| 仓库大小 | 170 MB（不含 .git） | `du -sh` |
| env 数 | 19 | `grep -c '@register_env' core/env.py` |
| skill 数 | 21 | `grep -c '@register_skill' core/skill.py` |
| 资产（仓库内） | 41 个 object 目录 / 40 个 capabilities.json | `find assets` |
| 论文声称资产 | 431 objects / 1,078 parts / 4,312 grasp poses | 论文 §A.2 |
| 策略 | 7 个 vendored（ACT/DP3/Octo/OpenVLA/OpenVLA-OFT/π0/π0.5） | README、`core/policies/` |
| checkpoint | **无** | `find` 无 `.pt/.pth/.safetensors/.ckpt` |

**关键差异**：仓库内只有 40 个资产的 capabilities，论文的 431 objects 需要 HF/ModelScope 数据集（未下载）。论文的 7 策略结果需要自行微调，不是拿 checkpoint 直接评测。

---

## 二、MetaFine 12 个问题逐项回答

### Q1. 官方仓库到底实现了哪些功能？

**VERIFIED（核心仿真/任务图/评测）**：
- 19 个 Gym env（`core/env.py` 的 19 个 `@register_env`）。
- 21 个 motion-planning skill（`core/skill.py`）。
- 任务图 YAML → `multi_skill` env：`utils/task_graph.py:50-66`、`utils/eval_setup.py:93-126`。
- 阶段谓词：`core/env.py:2025-2200`；阶段 flags 独立布尔；`utils/eval_metrics.py:85-105`。
- 相机/光照 DR：`core/env_mixins.py:47-107`；AUSC：`utils/eval_sweep.py:33-90`。
- 平滑度：`utils/eval_metrics.py:43-78`。
- 录演示/回放/转换：`record.py`、`utils/replay_trajectory.py`、`utils/convert_to_lerobot.py`、`utils/convert_to_rlds.py`。
- π0.5 eval 支持 `--task-graph`：`core/policies/pi05/evaluate.py:204-249, 586-700`。

**未实现（论文/README 之外的计划）**：
- 论文的多尺度 cross-attention encoder 干预（仓库**未找到**对应实现；搜索 `multi-scale`/`cross-attention encoder`/`causal intervention` 无命中）。
- peg-in-hole 的 Grasp/Align/Insert 阶段 flags（`PegInHoleEnv.evaluate()` 只返回 success + `peg_head_pos_at_hole`）。
- 结构化 tolerance schema（论文 Fig. A1 的 `eps_pos_mm/eps_ang_deg`；代码是谓词/硬编码）。
- object/target pose 扰动接口（只有 camera/light；`placed_in`/`stacked_on` 是 TODO）。
- 策略 checkpoint、AI planner、PPI leaderboard、多模态（README roadmap）。

### Q2. 哪些任务可以直接使用？

**VERIFIED（代码中存在）**：`grasp_part, align_to_part, stand_up, peg_in_hole, toggle_switch, toggle_switch_table, lid_opening, stack_pyramid, slide_along, plug_charger, multi_skill, draw_triangle, rotate, door_env, take_out_and_grasp_part_into_box, put_blocks_in_box_and_take_out_memory, put_blocks_into_boxes, assembling_kits, assembling_kits_metafine_letter`。

**精度相关**：`peg_in_hole`（连续 `peg_head_pos_at_hole`）、`assembling_kits` / `assembling_kits_metafine_letter`（连续 `pos_diff_norm`、`rot_diff`、`in_slot`；容差 2 cm/4°/3 mm）、`plug_charger`、`stack_pyramid`、`put_blocks_*`（`stage_id`）。

**注意**：`multi_skill` 只加载单个 articulated object；多物体任务（put_blocks、assembling_kits）是 bespoke env，不走统一 task-graph。

### Q3. 能否获取固定物理初态、目标位姿、末端位姿和阶段成功状态？

| 量 | 状态 | 证据 |
|---|---|---|
| 固定物理初态 | **VERIFIED（seed + set_state_dict）** | `core/policies/pi05/evaluate.py:784-812`；`utils/replay_trajectory.py:194-332` |
| 目标位姿 | **VERIFIED（env 内）** | `core/env.py:635-638`（`goal_pose`）；`3707-3730`（`goal_pos`） |
| 末端位姿 | **VERIFIED** | `self.agent.tcp.pose`（如 `core/predicates.py:108`） |
| 阶段成功 | **VERIFIED（布尔）/ PARTIAL（连续）** | `core/env.py:2130-2200`；`utils/eval_metrics.py:85-105`；连续误差见 `3684-3720` |

### Q4. 能否在相同初态下做配对扰动？

**PARTIAL。**
- `pi05/evaluate.py:784-812` 先算 `episode_seeds`，跨 clean/cam/light profile 复用 → **同一物理初态**。
- 但相机扰动在 `_default_sensor_configs` 用 `np.random.uniform`（`core/env_mixins.py:56-84`），env 每 episode 重建（`pi05/evaluate.py:801`），**扰动方向/幅度不随 episode seed 固定**，也不可复现（未显式播种全局 RNG）。
- 没有固定扰动 manifest。要做严格的配对扰动，需要自写：固定 seed、固定扰动方向/幅度、同一初态、clean/perturbed 成对。

### Q5. 能否通过代码实现局部空间偏移？

**PARTIAL/UNKNOWN。**
- 没有内置的 object/target pose 或 action offset 注入接口。
- 可以修改 `_initialize_episode`/`set_state_dict` 或任务谓词的目标坐标来实现，但这是自写代码，不是 API。
- `pose_near` 的目标是**绝对坐标**（`core/predicates.py:93-115`）；改它等于改任务，不是改观测。
- `placed_in`/`stacked_on` 未实现（`core/predicates.py:118-124`）。

### Q6. 是否已有阶段级容差、视觉扰动或动作误差相关评测？

| 项 | 状态 | 证据 |
|---|---|---|
| 阶段级容差 | **PARTIAL** | `pos_eps=2e-2`、`rot_eps=4°`、`height_eps=3e-3`（`core/env.py:3684-3705`）；`pose_near` tolerance；论文 Fig. A1 `eps_pos_mm/eps_ang_deg` |
| 视觉扰动 | **VERIFIED（camera/light）** | `core/env_mixins.py`；`utils/eval_sweep.py` |
| 动作误差评测 | **缺** | 只有 success、stage flags、smoothness；无 action error vs expert、无 tracking error |

### Q7. 哪些已实现，哪些只是计划？

| 功能 | 状态 |
|---|---|
| 19 env / 21 skill / 任务图 / 阶段谓词 | 已实现 |
| 相机/光照 DR + AUSC | 已实现 |
| 连续位姿误差（peg/assembling） | 已实现（部分 env） |
| 结构化 tolerance（论文 schema） | 部分（硬编码/谓词） |
| object/target pose 扰动 | 未实现 |
| 论文 encoder 干预 | 未实现 |
| peg 三阶段 flags | 未实现 |
| checkpoint / 7 策略结果 | 未提供 |
| AI planner / PPI / 多模态 | roadmap |

### Q8. ACT/DP3 适配到什么程度？

**PARTIAL。**
- `core/policies/act/` 有 ACT 训练/评估代码；`train.py` 有 `enable_dr_eval`（camera/light AUSC），`core/policies/act/train.py:131, 550-580`。
- `core/policies/diffusion_policy_3d/` 有 DP3 配置/模型。
- README 说 "training is verified via the LeRobot and StarVLA paths, and π0.5 closed-loop inference is verified"；**ACT/DP3 是否在本版本跑通，未见公开证据**。
- 无 checkpoint。需要自训。

### Q9. 公开策略、示教和评估结果是否足以建立任务阳性？

**PARTIAL。**
- 论文报告了 7 策略的成功率/阶段率；HF 有 `MetaFine_CoRL26` 的 π0 baseline demos（T1–T5）。
- 没有策略 checkpoint；论文结果需自行微调 7 个策略（VLA 级算力）。
- 对 3090 用户：ACT/DP3 可自训，可能达到任务阳性；π0.5/OpenVLA 不现实。
- "任务阳性"不能从论文数字直接继承；必须在自己的环境里重训/评测。

### Q10. RTX 3090 24GB 是否合理？

**VERIFIED（仿真）/ PARTIAL（策略）。**
- README：≥8 GB VRAM、Python 3.10/3.11、SAPIEN 3.0+、ManiSkill 3.0+；仓库 170 MB。
- ACT/DP3 训练在 3090 可行；VLA 微调（π0.5/OpenVLA）不在 24GB 的现实范围。
- 数据集（431 objects）需下载；未评估磁盘/时间。

### Q11. 能否作为 A1 或其他空间—行动问题的可靠实验平台？

**有条件可以。**
- 优点：连续位姿误差、硬容差、多物体干扰、相机扰动、配对 seed、阶段状态；ACT/DP3 可训。
- 缺点：无 R_π/P_c 接口；无 checkpoint；相机扰动不可复现；peg 阶段 flags 缺失；任务图单物体；VLA 微调重。
- 对 A1：可作为**测量平台**，但需要自写扰动/传播脚本；不能直接产生方法论文。

### Q12. MetaFine 本身是否已经占据了 A1 的部分创新空间？

**是，部分占据。**
- 已占：阶段级精度诊断、几何容差、视觉编码器作为精度瓶颈的因果干预、AUSC 鲁棒性曲线。
- 未占：R_π（策略响应）与 P_c（闭环传播）的测量、三因子乘积的预测、精度分配方法。
- 影响：A1 的"平台 + 阶段诊断 + 几何容差"不再新；A1 只剩"误差预算预测"这一测量贡献。

---

## 三、MetaFine 复现风险清单

| 风险 | 证据 | 影响 |
|---|---|---|
| 无 checkpoint | `find` 无权重 | 论文 7 策略结果不可直接复现 |
| 论文 encoder 干预无代码 | 仓库无 multi-scale/cross-attention 干预 | 论文的核心因果声明不可复现 |
| peg 阶段 flags 缺失 | `PegInHoleEnv.evaluate()` 只返回 success + peg_head_pos | Table B7 不可直接复现 |
| 相机扰动不可复现 | `np.random.uniform` 未显式播种；env 每 episode 重建 | 配对扰动需自写固定 seed/方向 |
| 资产规模差异 | 仓库 40 capabilities vs 论文 431 objects | 任务多样性需下载数据集 |
| VLM 判定依赖外部 API | `core/skill.py:184`、`utils/evaluator.py:24-35` | 录演示需要 `DASHSCOPE_API_KEY`；单帧判定有噪声 |
| 阶段谓词独立 | `core/env.py:2130-2200` | 可"跳过"前一阶段；`reached_stage` 解释需谨慎 |
| 多物体任务不走统一 task-graph | `multi_skill` 单物体；`put_blocks`/`assembling_kits` bespoke | 跨任务阶段协议不一致 |

---

## 四、6 篇最近邻对照

| 论文 | 做到哪一步 | 未做到（相对 A1） | 证据位置 | 状态 |
|---|---|---|---|---|
| **EGR** 2609.03142 | per-frame/per-sensor evidence 门控 invariance vs sufficiency；BEHAVIOR-1K 47 skills + 真机；SR 12.5→16.4 | 门控是可见性/接触，不是几何余量；无 R_π/P_c；无分配 | 摘要、§1、§3.1–3.3 | PARTIAL（未读全部附录） |
| **APEX** 2606.16504 | 执行间隙适配器；tracking error −41.2%；success +4.8–25.8 pp；含 ACT | 不处理感知误差；不测 R_π；不预测精度收益 | 摘要、§1、方法概览 | PARTIAL |
| **Pix2Act** 2607.11167 | 图像空间动作 + 联合等变增广；精度/相机扰动 | 等变增广已被做；未按余量门控 | 摘要 | ABSTRACT_ONLY |
| **MixVLA** 2610.02898 | 不变/非不变信息分离与混合；LIBERO/LIBERO-Plus/RoboTwin/真机 | 面向 OOD 泛化，不是精度阶段；无余量 | 摘要 | ABSTRACT_ONLY |
| **View Collapse** 2609.33707 | blackout/blur 单视角干预测 reliance；AT 造成 wrist-dominant collapse；View Swap | 多视角 VLA；不测几何余量；但它是 R_π 测量的混杂 | 摘要、§1、§4、Fig.1/3 | FULL_TEXT |
| **Blackout vs Freeze** 2609.39145 | 相机故障下的物理失败模式；NTC/F5/Drop/JVE/JLP；proprio 部分补偿 | 故障而非精度干预；VLA 级；B2 的最强竞争 | 摘要、§1、指标段 | FULL_TEXT |

**结论**：A1 的每个部件都有一篇强竞争；唯一未直接做的是"三因子乘积 → 收益"的定量预测。这不是方法机制。

---

## 五、总判定

- MetaFine 是**可用的测量平台**，不是 A1 的实现，也不是 turnkey 复现包。
- A1 的**测量**部分有有限新意；**方法**部分与 EGR/APEX/MetaFine/ActGaze 同族，不构成独立机制。
- 因此：A1 不作为方法型小论文；MetaFine 可作为测量型毕业论文的平台（若导师接受）。
