# Codex 候选独立审查（DeepSeek 32 前冻结）

审查对象：PROTOCOL.md SHA256 `3fd12394fd845a4c2df528119655af65ab1a830b55833f5aa278c0c8c004c460`；candidate_manifest.json SHA256 `bd4233fbeca8898d0145c3411ae98901897fd24b974984c3b83195cea75843ed`。

本意见先于本候选的 DeepSeek 独立意见形成。已实际复算55个候选文件、113个只读来源和最终CPU测试代码SHA，无差异，记录在 artifacts/parent_candidate_hash_audit.json。已核对R1/R2真实结果、R2差异、最终安全分支导入及来源、共享loader、GPU构造器、计数与调用门、supervisor、输入健康门、模型/闭环入口和统计筛选代码。没有启动GPU、env、ACT或rollout。

## 决定

**APPROVE GPU_PREFLIGHT_ONLY**：批准同一worker顺序进行input_setup→close_input→model_setup(strict load)→close_model的候选；必须有新派发和完整双审证据后执行，最多180 GPU分配秒，累计总上限1800秒。任何render/readPixels/ACT/step均被该阶段的计数映射拒绝；两轮修复已用完，失败封存，不再修改/重试。此意见不是Stage1或Stage2放行。

单一进程可以顺序验证两个构造器，不需要把二者同驻或必然拆成两个worker；共享正式builders和实际退出证据比仅通过CPU安全模块导入更有价值。CPU_IMPORT_READY仅证明已观察导入和CPU数据检查，CUDA/EGL初始化、strict-load、真实清理仍须测量。每个阶段唯一attempt marker和ledger阻断重试；总GPU按worker启动到清理退出累计；外层policy和匹配internal计一次，未计划调用在底层执行前拒绝。CPU计数拒绝测试不能冒充实际ACT测试。

## 保留边界与解释风险

1. GPU预检不渲染、不验证BF16前向及闭环健康。构造器不触发这些操作是待验证事实；如实际触发则拒绝并停止，不放宽门。监控约2秒采样不是连续峰值证明。
2. GPU预检异常结果中的 actual_GPU_path=false 不能解释为没有使用GPU；任何失败均以supervisor实际分配秒、阶段记录和原始日志为准。该描述字段不控制放行、不返预算。
3. Stage1输入固定原四状态、三入口和共同canonical raw，实际Dataset完整输出也核对；模型官方/custom比较、双常数和自身重复阈值保持不变。输入成功后仍须父审实际12帧/数组/边界和退出记录。科学8小时不得在预检或等待额度时提前开始。
4. 20%改善、至少3/4且覆盖两demo只是一项投资筛选，四训练状态不能证明泛化、视觉因果依赖或任务成功。posterior是有标签上界探针，不能充当部署能力。
5. Stage2实际还未批准。准确外参8物理root的train/dev配对有意义；删除与旧未验证RGB/0成功动作强制相等的assert正确，旧差异只解释性记录。正式Stage2前还须在未看闭环结果时冻结可信基线/Potential F/不充分结果的研究决策阈值；本候选仅有0/8训练相机失败及阳性需双审，不能事后把任意一次成功称Potential Go。
6. 无论剩余预算多少，不能为凑齐结果追加phase、重试、训练或换权重。阶段失败与BASELINE_LIMITED须分开；工程失败不等同checkpoint能力阴性。

共享额度当前5h已用87%、周73%，真实reset为2026-11-03 14:57:55+08。先完成双审；需要时在reset+120秒恢复，不因额度开启无结果倒计时。
