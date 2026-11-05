# 对DeepSeek40最终候选意见的独立核查

DeepSeek40真实结束于2026-11-04 20:09:44，模型字段deepseek-flash，exit0/result success；完整意见给REVISE/BLOCK，未批准GPU。主审未照单全收。

直接检查本机：results和roots两个父目录实际都已存在。因此“当前候选启动必败”不成立；空目录不出现在manifest或Glob文件清单，不能据此推断不存在。干净checkout的父目录初始化风险仍值得最小修正，统一mkdir(parents=True,exist_ok=False)不弱化禁止覆盖。

四份专家reference_next_eef实际存在，形状105/102/126/97×3且分别与HDF5 next_obs/robot0_eef_pos逐位相等。它不是现有数据缺失，但CPU预检应将源头一致性显式纳入机器断言。证据artifacts/parent_review40_blocker_check.json。

C原设计同render双read提供读回一致性；两个独立进程在source/geometry/T/RNG均相同时也提供有限跨臂重复，并非完全无重复。但为直接回答同状态/相机独立render，在原每臂22样本内将demo0/1最后状态替换成各自t0重复，保留相同相机/seed/crop起点，使用不同唯一标签+repeat_of。仍10val+12train、44getitem，不增加GPU或动作预算；若故障早停导致repeat未执行则NOT_RUN，不追补。

已向指定6.1-sol/max发送仅这三项的合并CPU修订。原manifest/协议/CPU/diff保留；完成后真实CPU重新覆盖并封新SHA，再向DeepSeek交叉核查修订。尚无GPU消耗或科学时钟。旧notes05只认可旧版的限定预检条件，当前不构成放行。禁止把准备错误或改进当旧0/32根因。
