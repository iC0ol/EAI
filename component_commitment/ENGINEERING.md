# 夜间运行与复核

正式实验按 [预先冻结的协议](PROTOCOL.md) 执行。运行环境为工作站 RTX 3090 和 Gate B 现有 Python 3.9 环境。

## 配对初态的工程修正

2026-11-25 在正式采样前检查了 robosuite 1.2 的 Panda 夹爪。设备采用软重置。`SingleArm.reset` 还原夹爪关节位置，`PandaGripper.format_action` 通过累积 `current_action` 生成手指目标。MuJoCo 物理状态哈希未包含这个 Python 状态。首版工程记录单独保存在 `runs/engineering_pre_reset_audit_ce443a1/`。

新入口在每回合开始记录软重置后的累积指令，随后将其恢复至 Panda 构造时的零值。在所有组共享的前六个物理控制步结束时，另存物理状态、双帧策略观测和两指累积指令。配对验收要求同一初态的五组在这三项上完全一致，四个中途更新组第六步采到的两个动作候选还须分别相同。这次修正涉及每回合的初始化和审计字段，注册阈值与统计判据见原始协议提交 `da4f0d1`。

## 工作站入口

- `./run.sh status` 显示工程验收与正式实验的最近状态。每个完整回合以独立文件原子保存，包含物理状态、查询时刻、样本哈希、每步官方成功谓词和中途动作轨迹的数值证据。
- `./run.sh start` 在工程验收通过后启动或续接同一项后台实验。已有服务运行时直接返回。使用工作站用户级服务 `eai-component-pilot.service`，可用 `journalctl --user -u eai-component-pilot.service` 查看服务生命周期，策略运行日志在 `runs/overnight/worker.log`。
- 正式结束后，`runs/overnight/REPORT.md` 提供中文结果。独立审计从逐步成功标记重算初次和终态成功，再检查配对、预算、实发动作和主指标区间。`./run.sh verify` 可从保存好的回合重新生成统计和报告。
