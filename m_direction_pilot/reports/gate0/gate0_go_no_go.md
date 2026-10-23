# M-Gate 0 v2 决策：Invalid / Engineering blocked

**Gate A未通过；M科学假设尚未检验。** demo_191,t=52专家前缀重建超出预登记容差，
故在任何名义/扰动后缀前停止。不能解读为方向无效、简单基线充分、对称PSD被否定或
M有论文新意。没有No-Go或Potential Go证据，也不启动Gate1。

协议起始commit：`b2a64fb3ad2f72b945233d76f7ad1fff84c27ad6`。
真实执行代码commit：`946091eee089a5a5ebeddc5649a4d4afda0274a5`。
顺序为只读资产审计→独立协议commit→运行代码commit→首个A前缀→停止→只读诊断/报告。
所有M方向及名义终局结果都未产生；不存在事后替换预登记或把探索数据冒充盲测的问题。

保留12个候选状态，来自6个episode；dev8/4来源，held-out4/2来源，无来源交叉。
完整清单见frozen_state_manifest.csv；全部状态状态见frozen_state_status.csv。

- A：1条前缀尝试，52个control steps / 1300个integration steps，0条完整suffix。
- B：0/120条尝试，名义分支同样未执行；paired_outcomes.csv保留全部120行，Y/Delta均空缺。
- A全部24条主计划与B120条的逐条总账见all_branch_ledger.csv（144行）；另6条修复预留未使用。
- 零扰动重复对0，seed43后缀0，正负/改善/留出混合结果0。0表示计数，不是观察到失败。
- 无训练、下载、第二任务、系统/ROS/CUDA变更。D与spatial目录及旧分支未改变。

关键证据：分叉点物体观测误差2.040859mm，物理qpos位置误差1.778535mm；
前缀观测最大3.829777mm，物理qpos最大2.831569mm。
源初态与动作完全一致，时序一致，仍存在在线观测滞后与接触段物理漂移。
详细阈值、姿态角、哈希和根因局限见expert_fork_fidelity.md。

本轮交付后停止，等待研究者review；不自动使用剩余预算排错、不更换状态、不放宽阈值、
不写Gate1执行计划来启动下一轮。若后续允许继续，应另行授权可复现性修复，并保持本轮
失败记录及协议SHA不变。
