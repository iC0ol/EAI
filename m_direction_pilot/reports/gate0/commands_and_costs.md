# 命令与实际成本

实际运行（均在/home/asus/EAI；没有执行D实验脚本）：

```text
git switch -c research/m-gate0 cea2502eee1dd6504035f4fcde47af1833a90b93
bash m_direction_pilot/scripts/run.sh m_direction_pilot/scripts/audit_assets.py
git commit ...  # b2a64fb：独立协议/冻结矩阵
bash m_direction_pilot/scripts/run.sh m_direction_pilot/tests/test_gate0.py
bash m_direction_pilot/scripts/run.sh m_direction_pilot/scripts/freeze_registration.py
git commit ...  # 946091e：执行代码
bash m_direction_pilot/scripts/run.sh m_direction_pilot/scripts/validate_demo_fork.py > m_direction_pilot/reports/gate0/logs/gate_a.txt 2>&1
bash m_direction_pilot/scripts/run.sh m_direction_pilot/scripts/report_gate0.py
```

Gate A命令exit2是事前检查触发的工程停机；没有运行run_gate0.py。首次GPU沙箱访问失败，
沙箱外同一nvidia-smi成功；首次Git索引写入只读失败后使用已批准的元数据访问。没有系统修复。
另外的只读内联命令仅读取HDF5/源码/已保存NPZ做检查，无额外模拟步。

| 成本 | 实测 |
|---|---:|
| 资产审计内部wall | 3.514487s |
| 专家前缀wall，含环境构建/初态恢复 | 11.081581s |
| 专家前缀process CPU | 10.490548s |
| 分支wall，含保存 | 11.308673s |
| 分支process CPU | 10.628200s |
| A执行循环wall，含最终JSON/哈希 | 11.517199s |
| prefix control / integration steps | 52 / 1300 |
| prefix模拟时间 | 2.6s |
| 完整suffix / suffix steps | 0 / 0 |
| DP续跑推理调用 / GPU推理时间 | 0 / 0ms |
| CUDA峰值allocated / reserved | 66219008 / 77594624 bytes |

模型已加载3090，尚无真实DP forward；不能把模型驻留显存解释成完成了推理验证。
上述分支/循环计时不含Python导入和策略加载；它们没有单独计时，也没有伪造端到端墙钟或
GPU占用小时。CPU为process_time，GPU时间只针对真正推理调用；本次调用数为0。
9项单元测试首轮0.393s通过，使用本地checkpoint，无训练；真实零扰动同态检查尚未进行。

每次尝试先写append-only attempt_ledger.jsonl，分支JSON与本地NPZ均独占创建。
本轮预算保守按1次A reservation记账；完整suffix实际上为0，远低于A30/B120/总150上限。
未使用额度不构成继续实验的理由。所有成果仅M目录；Git排除原始HDF5、权重、环境、缓存和NPZ。
