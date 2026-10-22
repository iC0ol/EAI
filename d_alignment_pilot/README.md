# D alignment pilot — Gate 1

单任务 Square PH 低维 Diffusion Policy 的动作日志固定时间错位证伪实验。
独立分支 `research/d-gate1`；`spatial_intervention_pilot/` 为已结束项目，保持不变。
范围与停止规则见 [预登记协议](reports/gate1/experiment_protocol.md)。

## 重现入口

所有命令从 `/home/asus/EAI` 执行。独立环境、源码依赖、缓存、数据和 checkpoint
均在本目录，本地大文件不进入 Git。无需 sudo、系统 CUDA 修改或模型权重下载。

```bash
bash d_alignment_pilot/scripts/bootstrap.sh > d_alignment_pilot/reports/gate1/logs/bootstrap_reproduction.txt 2>&1
bash d_alignment_pilot/scripts/run.sh scripts/audit_data.py
bash d_alignment_pilot/scripts/run.sh -m d_alignment.data
bash d_alignment_pilot/scripts/run.sh -m pytest tests -q --junitxml=reports/gate1/tests.xml
bash d_alignment_pilot/scripts/run.sh scripts/freeze_eval.py
```

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
