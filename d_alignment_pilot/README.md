# D alignment pilot — Gate 1

单任务 Square PH 低维 Diffusion Policy 的动作日志固定时间错位证伪实验。
独立分支 `research/d-gate1`；`spatial_intervention_pilot/` 为已结束项目，保持不变。
范围与停止规则见 [预登记协议](reports/gate1/experiment_protocol.md)。

授权补跑后结案：**Insufficient evidence / Stop at Gate 1**。研究者新增授权一次
Larger seed 43 原配置重训；总计七次尝试、六个完整策略，另保留一次 42,400
更新的中断尝试。六个策略共 300 个完整回合，每回合 400 步，没有缩短评估。

| 条件 | seed 42 成功/50 | seed 43 成功/50 |
|---|---:|---:|
| Clean | 22 | 34 |
| Mixed Small Lag | 19 | 27 |
| Larger-Lag Control | 22 | 23 |

Mixed 的配对差方向一致但区间跨零。Larger seed 43 比 Clean 下降 22pp
（配对 CI [8,36]pp），两个固定种子平均下降 11pp（初态聚类 CI [1,22]pp），
存在损害信号；seed 42 的净下降为 0，未满足预登记的跨种子重复性门槛。
因此不执行 Step D，Q2 未评估，当前不进入 Gate 2；不能写成没有退化、
日志错位无害或简单方法已解决问题。详见 [判断与限制](reports/gate1/go_no_go.md)。

中断排查确认上次智能体轮次遇到 `usage_limit_exceeded`；本地训练后来停止的
直接原因仍缺少退出码。见 [额度诊断](reports/gate1/interruption_diagnosis.json)
和 [补跑授权](reports/gate1/retry_authorization.md)。原有项目保持不变。

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
原预算六次尝试；此次人工授权一次补跑，总计七次。不会自动增加第八次尝试，
也不会自动进入后验监督或 Gate 2。

## 证据入口

- [环境](reports/gate1/environment.md)
- [数据时间约定](reports/gate1/data_time_convention.md)
- [数据完整性](reports/gate1/dataset_integrity.md)
- [闭环基线结果](reports/gate1/baseline_results.md)
- [Go / No-Go](reports/gate1/go_no_go.md)
- [固定源码与数据版本](configs/versions.json)
