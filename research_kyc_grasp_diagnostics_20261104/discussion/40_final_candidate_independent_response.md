**准确SHA**
- `candidate_manifest.json`：`5323928a81b4d335827bdc779ec9ac57fae2def2b92daeba896a0be4bd59072b`
- `PROTOCOL_CANDIDATE.md`：`f6f2a0b1a42b7d1f729ae1118db2b0cacc79b1864d16f4672233ec9e499a6014`
（manifest 内 `protocol_sha256` 与后者一致；我未启动进程重算 manifest SHA。）

**实际阅读**
协议、candidate_manifest、root/rollout/call/sample/phase plans、SOURCE_AUDIT、CPU_PREPARATION_REPORT、`cpu_preflight/result.json`/`process.json`、`parent_initial_source_data_audit.json`、`STORAGE_AND_STOP_PLAN.md`；代码 `gates/supervisor/ledger/roots/control/builders/preflight_worker/expert_worker/policy_worker/reader_worker/render_audit/owned_release/telemetry/model_runtime/call_guard/runtime_safety/common/cli/loader`。未读 notes/05。

## 发现的具体GPU前阻断

**BLOCK 1：`RenderAudit.__init__` 不创建 `P/results` 父目录。**
`kyc_grasp/render_audit.py:14` 为 `self.out=P/('results/'+self.stage); self.out.mkdir(exist_ok=False)`，没有 `parents=True`。候选目录与 manifest 中没有 `results/`。`preflight_worker.py:14` 在 `try` 之前构造 `RenderAudit`，因此在干净候选树上会先抛 `FileNotFoundError`，连 `gpu_preflight_result.json` 都不会写；这不是可解释的工程预检结果，而是必然启动失败。C 的 `reader_worker` 也复用该构造，同样受影响。

**BLOCK 2：`roots.freeze_one` 不创建 `P/roots` 父目录。**
`kyc_grasp/roots.py:40` 为 `directory=P/('roots/root_'+str(...)); directory.mkdir(exist_ok=False)`，无 `parents=True`；`P/roots` 不在候选 manifest 中，代码之前也没有创建。即使 `RenderAudit` 的父目录问题修好，`preflight_worker.py:19` 在第一个 root 仍会因缺少 `roots/` 失败。

这两个是**具体、可触发的启动阻断**，不是科学解释问题；必须修复后重新生成 candidate manifest/protocol exact SHA 并重新双审。修复前不能消耗唯一一次 GPU 预检。

## 其余关键核对

- **150步/eef_delta**：`rollout_plan.json` 的 B 为 8条×150步/5 query，`call_plan` 40 ACT；A 为原始 105/102/126/97；`control.StepRecorder` 保留原 wrapper 的六维累加、夹爪不累计，并检查底层绝对目标；`model_runtime.execute_denormalize` 为官方 float32 乘加。代码未改变语义。
- **A/B物理状态**：`roots.restore` 检查 XML/state/physics/controller/RNG exact；`root_plan` 明确 `source_demo_XML_available=false`、`original_demonstrator_XML_reconstruction=false`；dev T 只借 1000+i 相机，不混称旧 dev 物理root。**但 `preflight_worker` 只 freeze roots，不调用 `restore`**；A 是第一次真实 restore，因此不能把预检当A/B行为通过。A若 restore/控制失败必须停止，不得归因网络。
- **动作前真实EEF/夹爪**：`control.StepRecorder.__init__` 保存 initial EEF/cube/gripper；`gripper_state` 用实际命名关节索引并交叉 obs；符合要求。
- **policy返回/internal/float32**：`model_runtime.call` 强制 policy 返回与 internal normalized_chunk 逐位一致，并检查 raw float32 有限；符合要求。
- **C验证故障后的train split**：`reader_worker.py:51-108` 先validation后train；validation首故障后break仅当前split，接着执行第二guard并进入原12个train sample，无新增重试；逐split保存items/batch/first fault；符合要求。
- **GL故障≠坏像素**：`reader_worker` 记录 GL health、normal/sentinel、crop参数/后tensor；`normal_sentinel_nondeterminism_survives_actual_crop` 与 `...actual_train_tensor` 区分；符合要求。**但同一state/camera没有独立重复render**：22个sample均为唯一状态，normal/sentinel只是同一render的两次读回；因此“same-state/camera重复”证据不足，最多支持读回重复，不支持render重复。应在22个getitem内加入同state/camera重复（或明确收窄声明），否则C不能回答该问题。
- **A专家文件**：CPU只核对了source state/actions/starting_abs_action；A还读取`reference_next_eef`，但代码/CPU未见该key断言。A前应断言其存在、长度与HDF5 next_obs一致；不阻断本次预检，但阻断A有效性。
- **预算/停止**：900s总、预检90、phase caps、0训练/optimizer、PDEATHSIG/alarm/supervisor终止均存在；除上述目录创建外，未见预算硬停代码阻断。
- **历史因果**：C源码明确记`history_of_training_corruption='UNPROVEN_NO_HISTORIC_RGB_FBO_LOGS'`；旧dev1000初始图正常、后续诊断坏图不能外推旧训练全程；符合边界。不能把缺失FBO守卫或单点GL异常追认为0/32根因。

## 结论

**REVISE/BLOCK 下一次GPU预检。** 当前候选不具备可安全消耗唯一预检的状态：`render_audit.py:14` 与 `roots.py:40` 的父目录缺失会在启动时失败，且可能不留下完整预检结果。修复后必须重新冻结 candidate manifest、protocol SHA，并重新双审；本轮不批准A/B/C，不宣称任何行为通过。

修复后预检的最低证据条件：4个root真实生成、root0 train/dev两帧 normal+sentinel（2render/4read）、模型实际构造与375项strict load、0 ACT/step/rollout/getitem、完整root manifest与进程/预算记录；父审独立验收后再决定A。A需4/4专家阳性、`reward==1`与`_check_success`一致、实际EEF/夹爪恢复通过；B须在A通过后另派发；C须补same-state/camera独立重复并保存真实crop/collate链。
