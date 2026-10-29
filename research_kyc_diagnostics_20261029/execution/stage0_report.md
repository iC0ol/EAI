# Stage 0 独立只读复核

结论：**NEEDS_BOUNDED_STAGE1**。没有发现足以直接解释准确外参 0/32 的明确问题。此结论在任何本轮 CUDA、环境实例或模型前向之前落盘；机器门槛见 [stage0_gate.json](stage0_gate.json)。本阶段模型调用、仿真、优化器更新均为 0。

固定任务书 SHA256 为 `ae04cd358b7e7faa24110dbb447973e518aa739830e541e6bb5dab5c0a7c97ea`，review_gate 中 Codex 与真实 DeepSeek 均为 APPROVE。派发北京时间 2026-10-29 11:59:36，总限 19:59:36。使用当前 `research/u-gate0-v3-overnight` 分支，不建工作树。

## 来源和记录核对

11 个指定旧文件与 Git 起点 `a03f16d` 的对象逐字节相同。新独立查询官方固定 Git tree，48 个源码/配置/相机文件 blob 均与本地字节匹配，含 44 个 KYC blob 和 4 个 RoboSuite 关键文件。见 [旧来源](results/old_11_source_audit.json)、[官方来源](results/source_blob_audit.json)。KYC commit 为 `e0647105a0f3946581d253c55dc9fd1218fa0974`，RoboSuite 为 `0df3a5f5782937fa2e8fa923910d616b73310b8d`。

本次记录中有两处元信息措辞纠正，原件保留：vendor 是固定 archive 解压目录，没有自己的 `.git`，最初 `git rev-parse` 错读了 EAI 父仓库 HEAD，不能据此称 vendor 版本改变；独立 blob 核对给出实际来源。另 HDF5 不仅含 states/actions，还含无 RGB 的 obs/next_obs、rewards 等。详见 [来源纠正](results/version_provenance_correction.json)、[schema 澄清](results/schema_clarification.json)。两项不改变数值结果或阶段门槛，无重跑或新增观察。

## 八项核验

| 项目 | 代码与独立观察 | 能排除与不能排除 |
|---|---|---|
| 训练输入 | `R/scripts/run_experiment.py` 使用官方 `K/utils.py:EpisodicDataset`，256×256、9 通道共同 crop、m1/n3、200 demo、70/70/60 | 没有明显复制错误证据；尚缺同状态三入口的实际张量对照 |
| 部署输入与控制 | `K/eval.py:Evaluator` 与 `R/scripts/experiment_lib.py:policy_input` 均 flipud、RGB/255、ray 六通道、丢弃 proprio、零相机 token、BF16、动作逆归一化和 chunk30 | 源码同构不能替代数值一致性，Stage1A 检查；旧 root 恢复规则不同于官方随机 reset，不直接判因果 |
| posterior/prior | `K/models/act.py` 有 actions 即后验，`detr_vae.py` 部署 latent=0；验证 L1 的分母包括 padding | 验证 loss 不是部署误差；这是原算法路径而非已确认 bug。需要同样本 prior/posterior/常数比较 |
| 统计和动作还原 | 前 200 demo 共 20,400 帧，按官方 float32 ACT 公式重算四组统计，checkpoint/JSON 每维 bit equal；动作 roundtrip 最大约 1.49e-8 | 排除本次所查 stats 错配；drop1 qpos 确为 −mean/std 而非零，cam token 为零；不改变设置 |
| checkpoint | 845,671,886 bytes，SHA `c904a97002571d96e3ee6b66057d09162cbdcb5e926cb6ea0b660ca1390bce13`；60003 updates/20001 epochs；375 entries 全有限；args 与 JSON 无差异；optimizer 存储 step 均60003 | 没有错载 smoke 或非有限参数证据。Stage1 再对官方架构 strict load；本阶段未实例化模型 |
| 采样与恢复 | 60003 行连续，20001 个 epoch 均恰含 demo0–199 一次；每轮 batch70/70/60；36→37 更新恢复连续 | 独立 sampler generator 与官方全局 RNG、关闭训练内 eval 均改变随机流，但不是已定位原因；缺历史时刻/crop/camera，不能宣称从 seed 完整重建输入 |
| 旧动作/回放 | 32 roots+1重复共4950步，均无 success/reach/grasp；独立首动作 xyz std 约 [6.86e-5,2.58e-5,1.23e-4]m；专家10/10 | 开发条件动作集中属证据；目标增量和不是实测 EEF 位移。10回放仅限制整体动作 wrapper 解释，不证明视觉训练或策略学会任务 |
| 场景/几何 | HDF5 env_version1.4.1，固定源码1.5.1；无逐demo XML/RGB；LiftRand 某些背景位姿由 freejoint state 保存；旧初始源码 XML+完整state恢复通过 | 不证明精确采集场景相同；旧 ray 反投影仅自一致。Stage1 若能可靠使用真实 MuJoCo 可见几何则做独立投影，否则记未完成 |

R 指旧 reproduction，K 指其 vendor/kyc/policy_robosuite。逐张量、逐 epoch、逐旧 root 原始统计分别见 results/ 下 `checkpoint_*`、`normalization_audit.json`、`sampling_audit.json` 和 `old_trajectory_audit.json`。

## 官方历史渲染和行为参照

独立读取 [作者 issue1 回复](https://github.com/ripl/CamPoseOpensource/issues/1#issuecomment-3533166490) 与固定 `train.py`，确认官方在 epoch 前后检查 framebuffer，并在异常时 reset；旧适配训练没有该检查。旧训练没有逐帧 RGB 或 framebuffer 状态日志，因此**历史渲染健康性为 UNKNOWN**。当前重新渲染正常也不能追认历史正常。

[PR5](https://github.com/ripl/CamPoseOpensource/pull/5) 是未合并贡献者兼容建议；本地 MuJoCo3.3.0 满足其 >=3.3.0,<3.4，不能当既定根因。现成 torch2.6.0+cu124、torchvision0.21.0+cu124、numpy1.26.4、h5py3.12.1，未安装或更新环境。

[作者 issue2 回复](https://github.com/ripl/CamPoseOpensource/issues/2#issuecomment-3598554639) 说明论文报告 test_cameras；官方 `reproduce/paper_runs.yaml` 的 Lift 配置将 eval_start_epoch 设为10000，覆盖默认20000。`train.py` 在阈值之后每次50条，之前默认10条，不能统一称50。旧训练禁用内置评估、val相机改train池的差异保留。

本次检查官方 README、全部 issue 列表、相关 comments、releases（空），没有找到匹配 LiftRand/eef_delta/ACT 的训练完成 checkpoint 链接，不宣称全网不存在；未下载新资产或联络作者。公开一手材料摘要见 [官方证据](results/official_public_evidence.json)。

## 下一步的理由与边界

旧文件没有固定训练来源状态的 prior/posterior 输出，也没有同状态三入口张量或训练池闭环对照。只读无法区分 H1/H2/H3。双方已批准 v2 中的条件性 Stage1，无须重新确认；先完成固定 8 状态和恰至多32次前向，A 超差/不稳定或 B 预登记地板触发即停止 C。4 demo 的8状态不是8独立任务；若只凭 open-loop 停止，结论只能保留 D/IMPLEMENTATION-LIMITED，不能写成 C。无论结果如何，完整重训和新算法仍未授权。
