# 命令、预算和审计成本

```text
git switch -c research/m-gate0-replay-recovery 537e6a6db79ed1e8aa884b4bad8a44f08b17c480
bash m_direction_pilot/scripts/run.sh m_direction_pilot/scripts/replay_recovery/r0.py
git commit ... # cdb04a6 independent protocol
bash m_direction_pilot/scripts/run.sh m_direction_pilot/scripts/replay_recovery/register.py
bash m_direction_pilot/scripts/run.sh m_direction_pilot/scripts/replay_recovery/test_recovery.py
git commit ... # b906e6e execution code
bash m_direction_pilot/scripts/run.sh m_direction_pilot/scripts/replay_recovery/run_diagnostics.py
bash m_direction_pilot/scripts/run.sh m_direction_pilot/scripts/replay_recovery/report_recovery.py
```

实验脚本exit2是R1技术门槛失败后的计划停机。前缀2条完整、无invalid/partial尝试。
预检6项通过，3.986s，真实积分步0；一条构建/重置测试环境用于只读kinematics API验证，
未运行专家前缀或策略。R0与报告均未构造推进仿真的环境。每个integration由StepGuard计数；
构造/reset期间若有积分调用会被拒绝，本轮没有这类额外步。

| 项目 | P1 | P2 | 合计 |
|---|---:|---:|---:|
| expert control steps |52|52|104|
| integration steps |1300|1300|2600|
| prefix内部wall(s) |7.407823|5.318554|12.726377|
| prefix process CPU(s) |7.744229|5.550815|13.295044|
| GPU推理调用 |0|0|0|

整个执行循环wall=14.098774s，process CPU=14.321876s。
prefix计时包含环境构建/reset/逐子步遥测，截止最终NPZ/哈希写入前；循环计时还包含
prefix归档与gate比较，不含Python导入。终端端到端墙钟、只读报告CPU及GPU显存驻留
未另行计时，不伪造成0GPU占用小时。CPU使用2线程，process CPU可以略大于wall。
没有加载Clean网络进行续跑、没有新优化器更新。预算10个槽位均列于complete_budget_ledger.csv。
