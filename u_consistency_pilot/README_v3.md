# U v3 overnight execution

v3 的用户授权允许公开资产下载、独立环境、实现/有限排障和自动 cal/dev/test。v2 记录保留在原文件；本次入口、结果和状态另存。实验目标不是获得正结果。

当前研究 run_id：`20261027T172105Z_sourcefix`。原 T0 `2026-10-27T11:54:50Z`，硬截止仍为 `2026-10-27T23:54:50Z`（北京时间次日 07:54:50）；23:09:50Z 后不启动预计不能完成的科学阶段。状态见 `outputs/v3_20261027T172105Z_sourcefix/status.json`，交付见对应报告目录。

前序 `20261027T115450Z` 在 G 训练前发现：18685条metadata轨迹实际只有185种精确初始状态，每种101条。当前版本将整个初始状态家族放入同组，并全局剔除完全相同的原始 current-state / five-control-successor-state / action-block 逆转移。旧已编码子集已标无效，不用于 G；旧0A/工程证据与所有实际资源累计延续，原 config 另存 `protocol_v3_20261027T115450Z.json`。来源家族是保守代理，未声称已经识别出原始采集者的全部谱系。此前的zstd窗口和范围推断错误、修复及自动异常快照也完整保留。

实际工程验收已执行的命令（EAI 根目录）：

```bash
python3 -B u_consistency_pilot/scripts/bootstrap_v3.py --run-id 20261027T115450Z --verify-existing
bash u_consistency_pilot/scripts/with_env_v3.sh u_consistency_pilot/scripts/check_v3.py --kind integrity
bash u_consistency_pilot/scripts/with_env_v3.sh u_consistency_pilot/scripts/check_v3.py --kind data-training
bash u_consistency_pilot/scripts/with_env_v3.sh u_consistency_pilot/scripts/check_v3.py --kind smoke
python3 -B u_consistency_pilot/scripts/run_overnight_v3.py --run-id 20261027T115450Z --self-test
```

smoke 包含真实 strict load / CUDA / 编码 / 5×2 动作预测 / 先封存再执行的 8 个工程分支。data-training 和监督器故障恢复测试使用 TEST_ONLY 私有目录，不进入研究样本。正式 0A 的数据/scaler/6 roots 重放仍由阶段入口执行，不能用工程 smoke 代替。

独立监督器的实际入口如下；同 run 的锁阻止重复启动。环境/代码准备完成后用 `--admit` 封存 hash，监督器才会进入资产校验和后续阶段。重新启动只跳过 hash 与输出校验均通过的阶段。**不要在监督器已有有效 PID 时再开第二份。**

```bash
python3 -B u_consistency_pilot/scripts/run_overnight_v3.py --run-id 20261027T172105Z_sourcefix --admit
python3 -u -B u_consistency_pilot/scripts/run_overnight_v3.py --run-id 20261027T172105Z_sourcefix
```

本机当前使用 tmux 的 `u_v3_supervisor_sourcefix`（带用户进程 sleep inhibitor）与 `u_v3_guardian_sourcefix`。实际入口分别为上述监督器及 `python3 -u -B u_consistency_pilot/scripts/resource_watch_v3.py --run-id 20261027T172105Z_sourcefix`。数据已经由独立的 `download_ranges_v3.py --run-id 20261027T115450Z --workers 16` 完成并校验；下载重试按原偏移续传。实际 argv、PID、退出码在 commands.jsonl / download_commands.jsonl；进度与资源每分钟或更频繁原子保存。截止、TERM、异常或子进程死亡都会进入独立 finalizer，保留已完成结果并普通 commit/push，不强推。自动异常快照并不意味着 agent 放弃已授权的有限修复。

资源准备实际由已记录的源码下载、runtime/torch 二进制副本和离线 wheel 安装完成；`bootstrap_v3.py --install` 是整理后的本机重建帮助入口，本次没有为了测试它而重装环境。Python3.11 / torch2.6.0+cu124 来自 EAI 内既有可运行栈的独立副本；旧环境保持原样。最终实际包锁存于本次报告目录。PYTHONPATH 被清空，防止 shell 继承的 ROS 路径污染新环境。

科学顺序由 STAGES 固定：校验资产→单文件 zstd 流式解压→语义/工程重现→按 source 分组及编码→G 训练→32 cal→cal-fit 加强 G 与常数/ridge/shuffle→16 dev 封存评分→物理执行→dev 选择→test 封存→64 test 评分/执行→root bootstrap。dev 效果正负不影响 test 启动；只有技术、可信基线和实测预算约束会阻止 test。

评分阶段拒绝已有真实结果文件，G 的采样 API 无候选 A 参数，b 的 78 维接口只有合法历史/过去动作/当前候选。真实结果/O/d_F/d_G 只在物理执行后独立合并。所有缺失项用 NOT_RUN/null。原始 data/model/runtime/外部源码/checkpoint/大缓存不提交。

最终停止等待研究者审查，不自动 U1、Cube、闭环或额外任务。

最终状态：`NO-GO-CURRENT-SCOPE`。已完成32cal/16dev/64test；报告为 `reports/v3_20261027T172105Z_sourcefix/morning_report.md`。B2与B1在64test上选择完全相同。

实际执行过的交付审查是 `.work/20261027T172105Z_sourcefix/delivery_audit.py`；同一只读代码现归档为 `scripts/audit_delivery_v3.py`，可用当前独立环境在EAI根目录运行（需要本机保留的private输出，不会训练或仿真）。它复核所有14阶段完成标记、test封存输入、80root评分哈希/时间、640图像哈希、真实J/选择、残差恒等式和5000次root bootstrap；见delivery_validation.json。
