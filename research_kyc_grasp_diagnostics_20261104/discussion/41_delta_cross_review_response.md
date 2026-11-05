**撤回/保留40阻断**

40说“当前 `results/`、`roots/` 不存在，预检必然启动失败”——**撤回**。`artifacts/parent_review40_blocker_check.json` 显示两目录实际存在；manifest 不列空目录不能证明目录不存在。我的表述把“空目录未列出”误当成“不存在”，该阻断不成立。

保留的只是**干净树父目录风险**：两处 `mkdir` 已改为 `parents=True,exist_ok=False`（`render_audit.py:14`、`roots.py:40`），当前 CPU 结果中的 `production_mkdir_contracts` 实际执行了生产语句，验证缺失父目录可创建、第二次因已存在被 `FileExistsError` 拒绝且 marker 未变。该风险已被修订消除，不再阻断。

**三项修订核查**

1. **两处 mkdir**：`change.diff` 与当前代码一致；CPU 生产表达式测试通过；未见覆盖既有 evidence。满足。
2. **reference_next_eef**：`cpu_preflight.py:42-50` 现在断言 key 存在、shape=(steps,3)、有限且与 HDF5 `next_obs/robot0_eef_pos` 逐值相等；`cpu_preflight/result.json` 四个 expert 均为 `present/shape/finite/HDF5_exact=true`。满足；A 的 `expert_worker.py:22` 可读取该数组。
3. **C within-arm repeat**：`sample_plan.json` 仍为每臂22/总44；demo0/1 原末状态槽位被 `train_d0_t0_repeat`/`train_d1_t0_repeat` 替代，`t=0`、相机1/2、seed 20261104/20261204 与各自 original 相同；`reader_worker.py:34-45` 的 `within_arm_repeats` 比较 source state/geometry/T/camera/seed/crop/raw/postcrop/collate；未执行项输出 `NOT_RUN`，不追补；CPU `C_repeat_plan` 通过。未增加 getitem/render/read。满足。

**是否还有具体阻断下一GPU预检的问题**

未发现新的具体代码阻断。保留两项**限制**，不影响预检授权：

- 预检只做4 root生成/2帧4读/模型strict-load，**不调用 `roots.restore`**；A 是第一次真实 restore/control 路径，若 A 的 `restore` 或控制器恢复失败必须停止，不能据此归因网络，也不能把预检当A/B行为通过。
- notes07 的周期评估边界成立：官方周期评估与训练共用 env，评估 `reset()` 会重建 model/sim/context；本地 `run_experiment` 只有 Dataset validation，无该评估 reset。这是源码差异和场景/渲染分布混淆，C 的两处 guard 审计不能代表完整官方训练生命周期；没有历史逐帧证据，不能据此证明0/32因果。不扩展任务。

**结论**

**APPROVE_GPU_PREFLIGHT_ONLY**，仅针对以下精确版本，单次预检≤90 GPU分配秒、总≤900、0 ACT/step/rollout/getitem，正式 `engineering_gate`+新 dispatch 绑定同一 SHA 后方可执行；失败即停，不重试。**不提前批准A/B/C**，不宣称任何行为或科学时钟通过。

- `candidate_manifest.json`：`3179c07a0cf77758d4dff01d57ffebcca1af0c11bc4034a0753b32610f40b530`
- `PROTOCOL_CANDIDATE.md`：`8773f4b7733335898d2bed5803f0d7729798896892abe6bdefd604a1f71a8ed8`
