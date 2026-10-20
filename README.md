# EAI — Spatial Intervention Pilot

用于 VLM 空间可执行性与假设场景编辑诊断的离线先导实验。**Phase 0–2 / Checkpoint B 已经研究者检查**，
已完成 Phase 3：独立部署 Qwen3-VL-4B-Instruct，并对六核心样本做固定 prompt 的推理冒烟。
不训练、不微调、不扩充研究数据集。

Phase 3 的实际结果：F_A 3/6、F_B 2/6、F_AB 1/6，完整三状态组合 0/6；JSON 解析 6/6 成功。
没有出现“F_A 与 F_B 均正确而 F_AB 错误”的样本，不能据此独立确认纯组合推理错误。
单次生成平均 4.91 秒，torch 峰值显存 8842.2MiB，没有 OOM。原 62 项几何测试及新增 13 项测试全部通过。
这只是六样本冒烟，不构成统计结论；已停止，等待研究者检查。

全部项目文件位于 [`spatial_intervention_pilot/`](spatial_intervention_pilot/)，
Python 环境独立，不修改已有 inspection_robot、ROS2、NVIDIA 驱动或系统 CUDA。

- [项目结构与重现说明](spatial_intervention_pilot/README.md)
- [Phase 3 模型实际结果与错误案例](spatial_intervention_pilot/reports/phase3/smoke_report.md)
- [六核心原始回答与结构化预测](spatial_intervention_pilot/outputs/phase3/core/predictions.jsonl)
- [75 项 Phase 3 完整测试日志](spatial_intervention_pilot/reports/phase3/logs/all_tests.log)
- [Phase 0–2 几何结果与限制（历史）](spatial_intervention_pilot/reports/pilot_summary.md)
- [工作站与环境审计](spatial_intervention_pilot/reports/environment.md)
- [62 项自动测试日志](spatial_intervention_pilot/reports/logs/tests.log)
- [六个核心实例的四状态对照图](spatial_intervention_pilot/reports/qc_core_edits.png)
- [原始模型输入](spatial_intervention_pilot/data/public_inputs.jsonl) / [几何真值](spatial_intervention_pilot/data/private_labels.jsonl)

三类各 4 个场景，共 12 个（其中 6 个核心实例）。48 个状态在 0.10 / 0.05 / 0.025m 网格上的可达标签一致；
独立重生成的 26 个数据文件逐字节一致，生成失败 0、oracle 未决 0。

| 场景类型 | NONE | A | B | A+B |
|---|---:|---:|---:|---:|
| 串联阻塞 | 0 | 0 | 0 | 1 |
| 替代路线 | 0 | 1 | 1 | 1 |
| 修改引入新阻塞 | 0 | 1 | 0 | 0 |

![12 个原始场景及几何标签](spatial_intervention_pilot/reports/qc_montage.png)

在 Linux 工作站重现：

```bash
cd /home/asus/EAI/spatial_intervention_pilot
bash scripts/bootstrap.sh   # 环境尚未建立时执行
bash scripts/run.sh all
```

随机种子为 `20261020`；Python、包版本、下载哈希、字体/GEOS 版本、生成时 Git commit 均有记录。
仓库不含 Python 运行时、venv 或缓存。“private_labels”和私有 QC 只是模型不可见的评估数据，
在本公开仓库中一并提供，禁止将它们放入 VLM 输入。

这些标签仅针对有限分辨率几何模型；F=0 不能证明连续空间不可达，编辑后可达也不等于能真实搬动物体。
12 张图含参数变化与受控旋转/镜像，尚不足以支持关于 VLM 的 H1/H2 研究结论。
