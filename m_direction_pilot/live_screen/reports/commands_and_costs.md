# 命令、资源与成本

全部工作在/home/asus/EAI原checkout中，独立分支research/m-gate0-live-screen；
没有新worktree或环境安装。只读复用d_alignment_pilot/.venv：Python3.9.13、
Torch2.2.2+cu121、MuJoCo3.2.3、robomimic0.4.0、robosuite1.5.1、SciPy1.13.1。
单RTX3090、2 CPU线程、FP32确定性推理、原Clean42、native16D/chunk8/DDIM16不变。
所有新结果、代码和显式缓存留在live_screen/；权重、HDF5和Python环境不提交。

执行次序如下，列出的是本轮记录，不是授权再次运行。脚本使用exclusive输出和
append-only reservation，拒绝原槽位重跑。run_stage退出0表示完成该阶段计划，
科学Go/No-Go必须读取stage JSON中的status/continue。

```bash
bash m_direction_pilot/live_screen/run.sh m_direction_pilot/live_screen/scripts/audit_and_freeze.py
# commit 58ac609: protocol, 12 states, 160 allocations, 144 action checks
bash m_direction_pilot/live_screen/run.sh m_direction_pilot/live_screen/scripts/register.py
bash m_direction_pilot/live_screen/run.sh m_direction_pilot/live_screen/scripts/test_core.py
# preflight fix and final passing log; commit 60cf0ba: execution code
bash m_direction_pilot/live_screen/run.sh m_direction_pilot/live_screen/scripts/run_stage.py A
bash m_direction_pilot/live_screen/run.sh m_direction_pilot/live_screen/scripts/run_stage.py B1
bash m_direction_pilot/live_screen/run.sh m_direction_pilot/live_screen/scripts/run_stage.py B2
# B2 continue=false: no B3 command, fit, training or Gate1
bash m_direction_pilot/live_screen/run.sh m_direction_pilot/live_screen/scripts/export_results.py
bash m_direction_pilot/live_screen/run.sh m_direction_pilot/live_screen/scripts/test_delivery.py
```

命令stdout/stderr见reports/logs/；第一次合成优化测试失败与修复后的通过记录均保留。
每支108个JSON保存执行SHA60cf0ba510c306852e2dcfa262aa8bb53ec35bc5，protocol SHA
58ac6095d3cad406748f4ecd50340112ce4af98f。后期导出/审计脚本没有调用新仿真或推理。

| 项目 | 实际值 |
|---|---:|
| A / B1 / B2 wall | 59.186 / 725.481 / 624.138 s |
| 执行起止，Asia/Shanghai | 2026-10-23 17:27:10.888 → 17:51:11.716 |
| 从A启动到最终stage完成 | 1440.830 s（24.014 min） |
| 冻结绝对截止 | 2026-10-24 05:00:40 Asia/Shanghai |
| 完整后缀尝试 / 完成 / 未使用 | 108 / 108 / 52 |
| 前缀控制步 / 后缀控制步 | 10080 / 33120 |
| 前缀积分 / 后缀积分 | 252000 / 828000 |
| 全部控制 / 原生积分 | 43200 / 1080000 |
| 未计入完整控制步的部分积分 | 0 |
| DP推理次数 | 4178 |
| 分支wall之和 / process CPU之和 | 1369.866 / 1420.852 s |
| suffix simulation wall之和 | 493.379 s |
| inference wall之和 / CUDA Event区间之和 | 564.316 / 564.034 s |
| peak CUDA allocated / reserved | 100873216 / 111149056 bytes |

CUDA Event是推理区间的elapsed，不是设备独占核时；process CPU不能与wall相加。
execution elapsed包含模型加载与阶段之间间隔；分支计时从reservation后开始。
前缀单列成本和全部逐支原始数值见outputs/branch_costs.csv，不隐去重放前缀开销。
本轮实验远低于12小时上限，因预登记信息门槛提前停止，并非时间/预算耗尽。

训练0、额外seed/radius/task/state0、reset/cache/solver修复0、Gate1后缀0。
原113个M历史文件、原数据/权重/upstream文件SHA及5个旧分支引用全部通过交付审计。
Git差异限制在live_screen/；不修改D、spatial、inspection_robot、ROS或系统CUDA。

原始完整trace的公开CSV.GZ约45MB，逐数组与本地NPZ完全一致；全部108支的SHA索引、
12状态/160槽位分母及缺失Y均公开。图已逐张检查可读性。封存脚本最后生成
outputs/sha256_manifest.json，排除自身以及被ignore的本地NPZ/运行时/缓存/原数据/权重。
推送只针对本轮新分支；最终提交及远端HEAD通过git rev-parse / ls-remote核对后交付。
