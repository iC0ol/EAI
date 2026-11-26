# 工作站运行与接续

本线程于 2026-11-25 获得研究者授权。复现和独立检验均在这个检出内运行。正式试验的 1600 个回合及判断规则已在本地提交 `9abb268` 冻结。[协议](PROTOCOL.md)

## 工程准备

推理端使用 `policy/`、`runtime/policy/`、`assets/policy/` 和 `vendor/Openpi-PACE/`。仿真端使用 `sim/`、`runtime/sim/`、`assets/sim/` 和 `vendor/RoboTwin-PACE/`。未修改的对照源码在 `vendor/PACE/`。分量控制器及其测试在 `controller/`。工程验收与正式采集均已结束。原小时续办任务「续办 PACE 双任务配对实验」已在结题交付后删除。[正式结果](RESULTS.md)

`bash pace_robotwin/run.sh engineer` 在用户级服务启动独立 seed 2 配对工程批次。它为每项任务在同一工程场景各执行五个方法。服务先按官方发布清单固定所有参数分片哈希。叠块模型与仿真就绪便可开始叠块工程回合，手机模型可同时下载。每一项都在投入使用前逐文件核验，正式启动还会核验全部资产。工程记录位置由 `pace_robotwin/runs/ENGINEERING_PATH.json` 指向。服务在完整工程批次结束后调用 `bash pace_robotwin/run.sh audit engineering`。主线程检查真实 TCP、计时、资源、配对与工程记录后运行 `bash pace_robotwin/run.sh accept`，生成绑定清单的验收记录。

## 正式运行

`bash pace_robotwin/run.sh start` 启动 `eai-pace-formal.service`。调度器用本地单显卡先运行两个任务的原版复现，再运行独立比较。每次启动检查科学输入，逐回合原子提交。系统服务与对话模型的用量独立。已有回合须通过哈希和身份检查才被跳过。

`bash pace_robotwin/run.sh status` 给出各任务、方法的回合数与时间。两任务的工程计时齐备后才给出总 ETA，正式回合计时会逐步取代工程估计。`pace_robotwin/runs/formal/STATUS.json` 记录当前批次及错误。模型服务、预热和模拟器日志在对应运行目录的 `sessions/`。服务状态可通过 `systemctl --user status eai-pace-formal.service` 检查。

完整回合在 `runs/formal/{reproduction,heldout}/任务/scene_NNN/方法/`。每条保留实际下发动作、原始预测、查询本体观测、执行决策和原生成功谓词的几何证据。独立复核命令为 `bash pace_robotwin/run.sh audit formal`。主线程已核对总数、配对、原始动作与哈希，Sol Max 和主线程分别从回合记录复算了结论。[结果与证据](RESULTS.md)
