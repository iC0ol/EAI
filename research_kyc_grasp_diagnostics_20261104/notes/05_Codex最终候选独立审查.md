# Codex 最终候选独立审查（先于DeepSeek40）

结论：**APPROVE_GPU_PREFLIGHT_ONLY**。不批准A/B/C科学运行，不批准训练。当前候选manifest SHA256 `5323928a81b4d335827bdc779ec9ac57fae2def2b92daeba896a0be4bd59072b`；协议SHA256 `f6f2a0b1a42b7d1f729ae1118db2b0cacc79b1864d16f4672233ec9e499a6014`。review绑定仅这两个准确版本。

本轮依据用户新的抓取诊断授权，旧20% MAE门不再适用。已读完整协议及实际实现，包括root冻结/恢复、原wrapper/base.step观测、policy实际返回/float32反归一化、源Dataset/crop/collate与官方guard、normal/sentinel、owner释放、独立supervisor/账本/阶段门。396个只读来源、61个候选文件与26个实际CPU覆盖代码全部SHA一致，独立校验见artifacts/parent_candidate_exact_SHA_check.json。真实CPU最终exit0，原进程已失活，实际CPU源码快照一致，没有CUDA/GL/ACT/make_env尝试；失败夹具及后续准备修订已保留。CPU不是物理阳性或GPU strict-load。

准许的下一步仅一次≤90 GPU分配秒预检：4个替代root、root0两相机2render/4read、实际模型375张量strict-load及完整cleanup，0ACT/step/rollout/getitem/训练。全部计入新scope900秒，失败不能自动重试。真正运行仍需DeepSeek对准确版本批准和新RUN_PHASE派发。

选择依据：原始demo0..3/seed42..45固定且有旧回放依据；新增共享XML/state/controller/global RNG及actual sim物理指纹防止跨环境借用阳性；模型保留375原张量，参数不改。A每条原动作长度合计430步，B训练/dev配对8条各150/5query，不按成功提前停；C两个有限臂共44getitem，不强制错误。输出需要最终原数组复核而不是仅相信executor verdict。

准备期修订已逐项检查：动作前EEF/物体/真实命名关节gripper状态；执行float32乘加与官方原表达式CPU逐位一致；prior policy实际返回等于internal捕获；C validation首次健康故障不会阻断预定train/crop/collate样本。父审另在纯CPU验证53种官方nearest裁剪尺寸映射及两段提取guard的分支契约（模拟env/GL，仅CPU，非真实故障复现），见artifacts/parent_cpu_transform_guard_contract.json。

保留边界：
- 无逐demo原XML，新root是有依据的替代场景；同批A/B匹配不能改称旧dev32root或原收集场景。
- 预检通过后必须看两张原图/数组与实际GL/cleanup/roots，再双审冻结实际内秒额和科学8h钟。不能沿用候选180/360/135/135直接开跑。B还需本轮A4/4独立验收。
- C是添加官方两处guard的机制对照，保留相同本地数据初始化；不是完整官方训练复现。guard可能重置几何，必须核actual sim指纹。GL健康/读回一致不等于视觉健康；条纹、空帧、重复还需独立图像检查。
- 不保证150MiB容纳未压缩全量，实际写前压缩字节检查/146MiB与supervisor150MiB终止是硬约束。不得因此舍弃失败证据或扩大。当前批次体积约束可在实际预检后再核。
- 当前或之后自然异常不直接证明旧4.57h训练污染；旧dev1000存留初/末图看起来清晰，旧训练没有逐帧日志。旧0/32原因仍UNKNOWN。

目前没有活动GPU账本/派发/科学时钟。本意见用于engineering_gate，其他阶段需实际证据后另审。
