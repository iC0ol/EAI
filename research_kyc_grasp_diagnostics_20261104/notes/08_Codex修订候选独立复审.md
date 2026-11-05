# Codex修订候选独立复审（先于DeepSeek41）

结论：**APPROVE_GPU_PREFLIGHT_ONLY**。
manifest SHA256 `3179c07a0cf77758d4dff01d57ffebcca1af0c11bc4034a0753b32610f40b530`；protocol SHA256 `8773f4b7733335898d2bed5803f0d7729798896892abe6bdefd604a1f71a8ed8`。

已逐项读repairs/review40_delta/change.diff及新within_arm_repeats函数、计划和CPU证据。仅五个运行文件变化，对应授权的三项修订：两个mkdir允许创建父目录仍拒绝已有输出；真实CPU校验四份专家reference_next_eef与HDF5值完全相同；C原22槽位内两个t0重复保留相机/seed，逐臂记录source/geometry/T/crop/raw/postcrop，缺项NOT_RUN不补跑。A/B root、控制动作、成功规则、最大调用/时间预算没有变化。

全部81候选、396只读来源、26实际CPU代码与快照SHA重新核验一致；来源catalog与旧版逐项相同。真实CPU exit0，14.183402秒，CUDA/GL/ACT/env未运行。两处实际mkdir语句在CPU创建缺失父目录并拒绝重入，源头EEF断言全部通过。原件/diff和原manifest已归档，未篡改旧实验。

40意见中当前目录不存在的推断已被主审实目录证据纠正；此次仍加强干净目录启动可靠性。两个独立重复是原配额内部替换，尚无结果、没有事后筛选。新的同状态比较对不完整数据只记NOT_RUN；双read不能冒充独立render。

沿用notes05的科学边界与限定预检条件，仅允许双审及RUN之后一次90秒预检，0ACT/step/rollout/getitem。科学内预算/A/B/C仍需实际预检与阶段证据，不提前放行。源码补充notes07提醒官方周期评估改变共享env生命周期/几何，C不等同完整官方训练，历史0/32原因仍UNKNOWN。
