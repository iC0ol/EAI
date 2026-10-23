# 环境、预算与实际执行命令

保守起点为 2026-10-23 10:08 +08:00，报告生成时累计墙钟 0.8276 h，含阅读、开发、等待与排错；低于八小时上限。最终结案核验时间另记 `final_integrity.json`。

实际新增策略训练 **0**、仿真回合 **0**、环境步 **0**、模型/数据下载 **0**。仅拟合小型线性响应模型，使用 CPU；无神经网络对齐器。锚点拟合和盲预测时长见 `execution_summary.json`。

复用 `/home/asus/EAI/d_alignment_pilot/.venv`：Python 3.9.13、NumPy 1.26.4、SciPy 1.13.1、h5py 3.11.0、pytest 8.3.5、Matplotlib 3.9.2、bubblewrap 0.6.1。没有安装依赖或更改全局环境、ROS、驱动/CUDA。设置最多两线程，无在线 WandB。Gate 1 的固定 RoboMimic/robosuite/DP 源码版本未改，本轮没有导入模拟器或策略模块。

## 实际执行（cwd=/home/asus/EAI）

```bash
git switch -c research/d-gate1-q2 cea2502eee1dd6504035f4fcde47af1833a90b93
git commit -m "Preregister independent blind Q2 alignment and necessity audit"
bash d_alignment_pilot/scripts/run.sh -m pytest tests/test_q2_blind.py -q --junitxml=reports/q2_blind/preblind_tests.xml
bash d_alignment_pilot/scripts/run.sh scripts/q2/build_views.py anchors
bash d_alignment_pilot/scripts/run.sh scripts/q2/fit_anchors.py
bash d_alignment_pilot/scripts/run.sh -m pytest tests/test_q2_blind.py -q --junitxml=reports/q2_blind/preblind_tests_v2.xml
git commit -m "Freeze anchor-only Q2 models and tested isolated estimator before blind queries"
bash d_alignment_pilot/scripts/run.sh scripts/q2/build_views.py queries
bash d_alignment_pilot/scripts/run.sh scripts/q2/audit_blind_packets.py
bash d_alignment_pilot/scripts/run.sh scripts/q2/predict_blind.py
git commit -m "Freeze all isolated Q2 blind predictions before independent truth scoring"
bash d_alignment_pilot/scripts/run.sh scripts/q2/score_once.py
bash d_alignment_pilot/scripts/run.sh scripts/q2/report.py
bash d_alignment_pilot/scripts/run.sh scripts/q2/final_audit.py
```

所有 stdout 在本报告 `logs/`，冻结记录在 `outputs/q2_blind/`。首次测试 40 passed/1.41s；补充后 43 passed，实际 XML 与日志均保留，未把未运行检查称为通过。另有 112 包真实 schema/guard 检查、拟合和查询命名空间访问探测。

## 复现与私有工件

builder/fit/predict/score 的正式入口会拒绝覆盖既有工件。不能删除既有结果重新跑后选择较好版本。首次匿名化 seed 仅在本地 private truth；物理配置、划分、算法与评价固定。揭盲后的公开评分含匿名 ID、原 episode 和 d，可用于可信 builder 复核重建，但重建不是新的独立盲测；不能将公开结果继续用作盲选参集。

本地源数据仍为旧官方 HDF5；输入 NPZ、模型系数、私有 Oracle、沙箱代码快照和零散进程 stdout 在 `data/derived/q2_blind/`，被既有 ignore 规则排除。只提交有限结构化预测、评价、配置、测试、代码和图表，不提交任何 HDF5、模型 checkpoint、Python runtime/cache 或凭据。
