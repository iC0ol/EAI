先读取冻结协议、训练/评估汇总与只读代码，核对“实施差异”与“机制失败”的边界。

0/32 与近乎常量动作是实施受限的核心。现在对训练/评估路径做只读代码核对，优先找“已证实差异”与“仅可疑原因”。

# 第07轮审查：实施受限，不是机制阴性

## 1. 最重要的事实纠正

| 事项 | 实际证据 | 不能宣称 |
|---|---|---|
| 训练 | C 完成 **20001 epochs / 60003 updates**，约 **4.57 h**；loss 8.779→0.393，最后1000均值 0.380，val 0.331（`training_progress.json`、`loss_summary.json`） | loss 下降≠任务学会；`loss_summary` 自己也标了 caution |
| dev | 32 独立 roots **0/32 成功、0 reach、0 grasp**；动作近常量：首动作跨 root 标准差约 1e-5 m，z≈−0.0018，夹爪≈−0.99；整段 z 位移约 −0.084 m（`dev_summary.json`、`offline_action_audit.json`） | 这不是 persistent 机制被证伪，是 **IMPLEMENTATION-LIMITED** |
| 正式 test | **350 rollouts NOT_RUN**；`test_allowed=false` | 没有 persistent vs IID 的任务证据 |
| U | **NOT_RUN**；仅随机初始化 RGB-only 接口阴性 | 没有 C vs U 系统比较 |
| 敏感性 | `metadata_insensitive=false`，C 对 raymap 有动作变化 | 只证明“分支被使用”，不证明几何正确，更不是任务阳性 |
| 语义 | 10/10 专家回放成功；`semantics.json` 只有回放行，没有独立 3D 投影/ray 验收行 | 回放验证动作/动力学语义，不等于 Plücker 几何正确 |
| 配置 | 匹配官方 LiftRand ACT 的 20001 epochs、batch70、200/10 demos、crop、late_imagenet、chunk30、use_plucker；但仅 seed0、固定末步、val 用 train 相机 pool、关闭训练内 test rollout、自定义 sampler RNG | 不是 KYC 论文数值复现；这些是**已证实协议差异**，不是已证实致因 |

`patches/README.md` 还记录：原验收在轨迹末状态用 compiled XML 失败，修复为“源码模型 XML + 初始完整 state”；原因未被证明。该修复本身合理，但说明几何恢复链并非一开始就干净。

---

## 2. 最多三个优先排查点

### P1｜训练数据的 per-demo XML / cube size 未恢复（已证实差异，未证实致因；最高优先）

- 证据：`results/semantics.json:130-133` 明确“Public HDF5 lacks per-demo XML/cube dimensions. Official generator default seed used once”；`env_version 1.4.1` 与固定子模块 1.5.1 不同。
- 代码：`scripts/experiment_lib.py:15-22` 只建一个 `make_env`；`scripts/run_experiment.py:42-43` 所有 200 demo 共用该 env；`vendor/.../utils.py:354-392` 的 `EpisodicDataset.__getitem__` 只 `set_state_from_flattened`，没有 per-demo XML/cube geom 恢复。
- 后果假设：LiftRand 的 cube size/场景 XML 与 demo 不一致时，训练图像与动作标签可能来自不同几何；策略可能学成“固定下压+闭合”的均值动作。**这是假设，不是已证明 bug。**
- 最小检查：固定一个 demo/time，比较训练渲染图与 HDF5 内保存的 observation/官方渲染；打印 `env_args` 的 `env_name`、`original`、`model_file`、cube geom size；若不一致，先修数据几何，不改网络。

### P2｜Plücker / 相机约定未独立验收（已证实 gate 缺口，未证实致因；高优先）

- 证据：`PROTOCOL.md` §4 要求 3D 点投影、ray 方向/矩、旋转左右乘、crop/raymap 同步；但 `semantics.json` 只有 10 条专家回放，没有这些行。`fixed_observation` 的 `metadata_insensitive=false` 只说明 C 对 raymap 敏感。
- 代码：`experiment_lib.py:23-29`（`camera_pose`/`render`/`intrinsics`）、`:34-40`（`policy_input`）；`kyc_utils.py:344-392`（`_set_camera_pose`、Plücker）；`kyc_eval.py:137-171`。
- 风险：cam2world vs world2cam、OpenGL→OpenCV、`np.flipud` 的 v 轴、crop 与 raymap 同步、intrinsics 任一错，都会让 C 依赖错误几何；RGB 分支仍可能学，但 C 的条件分支可能把策略拉向常量。
- 最小检查：用已知 3D 点/已知像素 ray 对照 `PluckerEmbedder` 输出；检查 `cam_quat` 顺序、`z=-forward`、flipud 后 v 轴；确认 crop 对 9 通道同步且 ray 未被错误插值。找不到 bug 就明确写“未证实”。

### P3｜训练内官方 test rollout 被关闭 + 自定义 sampler RNG（已证实差异，未证实致因；中优先）

- 证据：`PROTOCOL.md` §5 明确禁用训练内 test rollouts；`frozen_training_plan.json` 写 `sampler` 为独立 `torch.Generator(seed0)`，与官方 DataLoader RNG 流不同；`run_experiment.py:12-24` 自定义 `Loader`，`:61-62` 只 validation，无官方 test eval。
- 对照：官方 `vendor/.../train.py:107-141` 每 10 epochs validation、每 1000 epochs 用同一 env 做 test rollout；会改变 env reset、XML/state、RNG 和后续训练相机采样。
- 判断：这是**确认的实施差异**，但不足以单独解释 0/32；它改变数据顺序/RNG，不会让一个本可学会的策略必然均值塌缩。先查 P1/P2，再决定是否用官方 `train.py` 仅加日志重跑；现在不能新开实验。

**结论：读过的代码里没有一行能确定为 0/32 的唯一 bug。** 最可疑的是 P1/P2；P3 是已证实差异但优先级较低。

---

## 3. 方法假设降级与 F 资格

- **F 的 persistent vs IID 假设：未测试。** C 连 clean dev 都 0/32，不能比较噪声相关性；当前证据既不支持也不否定。
- **“C 学会了显式几何”不成立。** 0 reach/0 grasp 与近常量动作说明 baseline 未学会；`metadata_insensitive=false` 只是接口敏感性，不是任务能力。
- **C vs U 不成立。** U NOT_RUN；没有系统比较，不能谈“几何收益是否被抵消”。
- **F 不能获得优先论文资格。** 它现在只是 **IMPLEMENTATION-LIMITED 的基线失败**；即使修好，也只是窄 robustness 问题，且 KYC/CamVLA/AnyCamVLA/MoVie 已覆盖大部分相机适应空间。**不把复现/诊断包装成贡献。**
- 可保留的只有：**问题验证资格**，且必须先过基线 gate；不是论文资格。

---

## 4. 若后续继续：最小恢复资格

1. **一次有界修复，不改网络/任务/阈值**：P1 数据几何 + P2 Plücker/相机约定；最多两项修复，保存补丁与验收。
2. **基线 gate**：C clean dev 至少 **4/32**（协议原门槛），且有跨 root 动作方差；仍 0–3/32 则停，不进入噪声科学判定。
3. **语义 gate 补齐**：已知 3D 点投影、ray 方向、crop 同步、动作增量/累加、专家回放 10/10；缺一项不训练。
4. **只有 C 通过后才做**：C-only persistent vs IID / moved-stale；50 roots；固定末步；不按 test 选 checkpoint。
5. **U 仅在剩余预算能完成同等训练步时**才训练；否则明确 NOT_RUN，不拿短 U 比较。
6. **pose-jitter 训练是下一阶段强基线**；首夜不训练，不据此声称新方法必要。
7. 不借坏 baseline 制造创新；不因 0/32 改小网络、减 demo、换任务或降低门槛。

---

## 5. 给硕士研究者的最后结论

**当前状态：IMPLEMENTATION-LIMITED，COMPLETE 的训练 + NOT_RUN 的正式 test，不是 VALID-NEGATIVE。** 这次运行没有回答“persistent 是否比 IID 更破坏”，只暴露了 C 基线未学会。最重要的下一步不是加模块，而是做一次数据几何/Plücker 语义的只读补证与有界修复。

**两周条件性计划**：
- 第1–3天：P1/P2 核查；固定 demo/time 图像对照、ray 投影对照、env_args/XML 核对。
- 第4–6天：最多两项修复；C clean dev 32 roots；≥4/32 才继续。
- 第7–10天：C-only persistent/IID 5°/10° + moved-correct/stale；50 roots；报告配对区间。
- 第11–14天：统计与停止决定；若 0–3/32、ray 不敏感、或 persistent/IID 无差别，封存 F。

**三个月条件性计划**：仅当两周 gate 通过且效应可辨；再加入 U（若算力允许）、第二个任务/相机、pose-jitter 与标定校正强基线。只有新方法稳定胜过这些简单基线，才谈论文；否则停。

**终止条件**：两次有界修复后仍 0–3/32；P1/P2 无法验收；C 对合理 raymap 扰动不敏感；persistent vs IID 无 20pp 量级差异且区间宽；pose-jitter 已解释全部收益；资产/预算不足。任一出现即停，不追加条件。

---

## 6. 文献边界（只基于已读）

- **MoVie（NeurIPS 2023）**：冻结动力学 + 测试时视觉编码器/STN 适应，覆盖 fixed/moving/jitter 视角；因此“动力学一致的相机适应”不是新方法。
- **KYC（ICRA 2026）**：测试时假设**准确/已知外参**，Plücker 条件化；没有 calibration noise/drift 实验。
- **CamVLA（2026）**：从 RGB 预测 hand-eye，camera-frame delta；只测 **IID 每决策重采样**旋转噪声（5° 58.7%，12° 仍 > π0 36%），未测 persistent；translation 因相对动作抵消。
- **AnyCamVLA（IROS 2026）**：依赖 ArUco/已知相机跟踪，用 LVSM 把测试视角渲染回训练视角；未测 calibration drift/stale extrinsics。
- 所以 F 的“persistent vs IID on explicit Plücker”没有被这四篇直接回答，但整个相机适应空间很拥挤；F 是窄诊断，不是新论文题。

**保留分歧**：Codex 认为先修 P1/P2 再决定；我同意，但强调 `semantics.json` 的 gate 不完整，不能把 10/10 回放当作几何验收。若 P1/P2 修好后 C 仍 0/32，应直接封存 F，不再用“persistent 机制”续命。
