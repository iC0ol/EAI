# Codex独立GPU预检验收及Stage1冻结意见

本意见在读取DeepSeek对本次GPU原始结果的验收前形成。实际独立复算见artifacts/parent_gpu_preflight_acceptance.json；已直接读取stages/gpu-preflight、recovery_state、strict_load、原始log、call_ledger、48条GL事件、model_events和resources。不是复述执行者结论。

## 预检验收

**ACCEPT ENGINEERING_READY_INPUT_AND_STRICT_LOAD，科学观测仍0。** 2026-11-03 15:08:33至15:08:49单worker完成，单调时钟计16.88504482805729 GPU分配秒；epoch差16.885208秒，仅计时读取时差。worker与supervisor原PID/start_ticks已失活，exit0/EXITED、lease空、无terminal_stop/fatal，无science_clock。账本只有worker1、make_env1，所有ACT/render/read/step/rollout/训练均0。9次采样峰值RSS约2.05GiB、整设备VRAM1191MiB，非连续峰值保证。

真实日志显示Dataset200、1000个相机姿态资源已读；模型构造到70.43M参数。strict load missing/unexpected均空，固定checkpoint与缓存SHA相符，无optimizer创建/状态加载。代码的375项有限张量与参数检查全部在返回strict_load之前，结合exit0支持本次严格加载通过。48事件中登记两个context、两次成功destroy；最后CLEANUP的current为空，owned_release_DONE与无fatal相符。这里没有渲染/像素证据，不能称输入已健康，也没有BF16或动作能力证据。

我再次独立复算55个候选文件、113个来源、26个真实CPU快照代码及执行者列出的原始证据SHA，全部一致。源码构造与资源预检所限定的工程路径已真实打通，known common冲突不再阻塞。

## Stage1科学冻结决定

**APPROVE STAGE1_WITH_PARENT_INPUT_GATE**，仅针对以下精确版本：

- PROTOCOL.md：3fd12394fd845a4c2df528119655af65ab1a830b55833f5aa278c0c8c004c460
- candidate_manifest.json：bd4233fbeca8898d0145c3411ae98901897fd24b974984c3b83195cea75843ed

理由：两轮工程修复已完整留证；真实CPU导入、GPU共享构造/加载/清理完成；后续输入及模型的关键预算/强常数/判定规则已经在相同版本审查。没有改变模型、样本、metric、阈值或架构。下一步应采集本轮核心科学证据，避免继续消耗预算做重复工程测试。

此意见须真实DeepSeek独立验收与交叉确认后写入science_gate。然后**只先派发s1-input**，12render/24read、0ACT、最多210 GPU秒；S1合计600，模型至少留390；全scope1800，预检已用16.885044828。首次S1正式dispatch才启动8h，后续stage不延长。每phase一次，两轮修复已用完，失败不修/补跑。

input退出后我必须实际看12张图并核对所有原始数组、normal/sentinel一致性、GL与保存边界、四固定状态/源代码/输入文件哈希/进程预算，再签input_gate与新的s1-model派发；预检健康不代替这个门。模型只使用保存的健康输入，固定16调用、BF16/数值容差/双常数/逐维及方向夹爪/多样性，posterior不作部署能力证据。四训练状态两demo不做泛化、显著性或视觉因果结论。

Stage2此刻不放行。只有S1实际证据通过预登记筛选、双方独立验收再交叉，冻结闭环解释边界后才条件执行。Stage3永远只计划。本次运行未改任何冻结文件，主审只增加验收记录与阶段门。
