# D alignment pilot — Gate 1

单任务 Square PH 低维 Diffusion Policy 的动作日志固定时间错位证伪实验。
独立分支 `research/d-gate1`；`spatial_intervention_pilot/` 为已结束项目，保持不变。
范围与停止规则见 [预登记协议](reports/gate1/experiment_protocol.md)。

本轮结案：**Insufficient evidence / Stop at Gate 1**。六次训练已启动，五次完成；
Larger seed 43 在最后确认 42,400/50,000 更新后中断，原因未知，无最终权重。
已评估五个策略共 250 个完整回合，没有重跑或缩短回合。

| 条件 | seed 42 成功/50 | seed 43 成功/50 |
|---|---:|---:|
| Clean | 22 | 34 |
| Mixed Small Lag | 19 | 27 |
| Larger-Lag Control | 22 | 未执行测试 |

Mixed 的配对差方向一致但区间跨零；Larger 第二种子缺失。没有达到执行传统
lag 检查的预登记门槛，Q2 未评估。不建议当前进入 Gate 2；这不等于证明日志
错位无害或简单方法已解决问题。详见 [判断与限制](reports/gate1/go_no_go.md)。

## 重现入口

所有命令从 `/home/asus/EAI` 执行。独立环境、源码依赖、缓存、数据和 checkpoint
均在本目录，本地大文件不进入 Git。无需 sudo、系统 CUDA 修改或模型权重下载。

```bash
bash d_alignment_pilot/scripts/bootstrap.sh > d_alignment_pilot/reports/gate1/logs/bootstrap_reproduction.txt 2>&1
bash d_alignment_pilot/scripts/run.sh scripts/materialize_frozen_data.py
bash d_alignment_pilot/scripts/run.sh -m pytest tests -q --junitxml=reports/gate1/tests.xml
```

Git 中已有冻结 manifest，`materialize_frozen_data.py` 从记录重建被忽略的 HDF5，
不会重新抽样 delta、episode 或测试初态，并验证原始 SHA256。原始预登记创建
命令（`audit_data.py`、`d_alignment.data`、`freeze_eval.py`）见执行记录，不应在
已有 manifest 上重新抽样。XML 内含绝对资产路径，逐 byte 复现需沿用记录中的
`/home/asus/EAI` 位置与源码布局；跨位置复现应另做路径规范化审计，不能冒充原哈希。

冻结文件和已完成结果不可覆盖。重新执行完整实验应先由研究者决定如何保留已有
结果，不能直接删除重跑。训练与最终测试命令、实际状态和错误见
[执行命令](reports/gate1/commands.md)；是否应继续由 Clean gate 与预登记门槛决定。
最多六次策略训练；不会自动进入后验监督或 Gate 2。

## 证据入口

- [环境](reports/gate1/environment.md)
- [数据时间约定](reports/gate1/data_time_convention.md)
- [数据完整性](reports/gate1/dataset_integrity.md)
- [闭环基线结果](reports/gate1/baseline_results.md)
- [Go / No-Go](reports/gate1/go_no_go.md)
- [固定源码与数据版本](configs/versions.json)
