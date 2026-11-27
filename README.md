# EAI · 机器人自适应动作块执行研究

我们研究冻结的机器人策略在什么时候值得重观察，以及观察后哪些动作值得延续。**最新双任务实验已完成 1600 回合。** 在 100 个独立叠块场景上，原版 PACE 和分量更新均成功 52 次，固定完整动作块 H=50 成功 24 次。在 100 个手机入支架场景上，三者依次成功 64、61 和 61 次。分量更新未达到预先登记的提升门槛。[项目交接与小论文目标](当前阶段的交接文档.md) · [双任务正式报告](pace_robotwin/RESULTS.md)

| 最近实验 | 设计与证据 |
| --- | --- |
| PACE / RoboTwin 2.0 双任务 | [冻结协议](pace_robotwin/PROTOCOL.md) · [1600 个回合的结果](pace_robotwin/results/episodes.jsonl) · [完整统计](pace_robotwin/results/ANALYSIS.json) · [独立审计](pace_robotwin/results/AUDIT.json) |
| Square-MH 分量更新先导 | [32 个初态、5 组的配对报告](component_commitment/results/REPORT.md) · [结果解释](component_commitment/FINDINGS.md) |

从仓库根目录运行 `python3 -B pace_robotwin/verify_public.py` 可核验公开结果并复算主比较，需要 NumPy 和 SciPy。叠块的 26 个分歧场景另提供两种方法的逐查询记录、实发动作数组和共享首帧，便于工具按场景分析。[26 对原始记录与下载入口](pace_robotwin/results/discordant_stack/README.md)

## Square-MH 早期实验

Gate B 使用 robomimic Square-MH 和官方图像 Diffusion Policy 检查固定执行步长的影响，以及插入前的几何余量能否预测短首次提交相对长首次提交的收益。B0、B1、B2 和 continuation-h4 均已完成并冻结。历史 Gate C 尚未授权。

| 阶段 | 结果 | 报告 |
| --- | --- | --- |
| B0 | 固定 `h=8`，成功 84/100 | [基线报告](gate_b_v2/reports/B0_REPORT.md) |
| B1 Pilot | 20 个初始状态、100 条记录，成功 82/100 | [Pilot 报告](gate_b_v2/reports/B1_PILOT_REPORT.md) |
| B1 Full | 100 个新初始状态、500 条记录，成功 399/500。在 `h=1,2,4,8,15` 下分别成功 66、72、81、87、93 次 | [Full 报告](gate_b_v2/reports/B1_FULL_REPORT.md) |
| B2 Discovery | 30 个状态、450 条分支。主效应 +5.57 个百分点，95% CI [−1.58, +15.64]，达到独立 Confirmation 的审查条件 | [Discovery 收尾](gate_b_v2/reports/b2_discovery_20261117/B2_DISCOVERY_CLOSEOUT.md) |
| B2 Confirmation | 30 个新状态、450 条分支。主效应 0.00 个百分点，95% CI [0.00, 0.00]。按冻结规则判定未达到 8 个百分点的实际意义阈值 | [Confirmation 收尾](gate_b_v2/reports/b2_confirmation_20261118/B2_CONFIRMATION_CLOSEOUT.md) |
| Continuation-h4 | 事后配对诊断，在 Confirmation 原状态上完成 450 个配对。后续 `h=4` 成功 430/450，原 `h=15` 成功 440/450。配对差 −2.22 个百分点，95% CI [−10.44, +3.78] | [h4 诊断报告](gate_b_v2/reports/b2_continuation_h4_20261119/B2_CONTINUATION_H4_DIAGNOSTIC_REPORT.md) |

## 协议与复核

- [Gate B 协议与 B0/B1 设计](research_spatial_action_round4_20261109/reports/GATE_B_PROTOCOL.md) · [B2 v1.1 冻结协议](research_spatial_action_round4_20261109/reports/B2_PROTOCOL_REVISION_20261116.md) · [选题背景](research_spatial_action_round4_20261109/reports/PRIMARY_TOPIC.md)
- [Gate B 实现和复核说明](gate_b_v2/README.md) · [源码包](gate_b_v2_source.tar.xz) · [源码包 CI 核验](.github/workflows/gate-b-v2-source-audit.yml)
- 工作站的环境、权重、原始运行记录、二进制快照和哈希清单留在 `gate_b_v2/`。三份离线安装源位于本地的 `gate_b_v2/assets/workstation-installers/`。公开原始记录与校验清单可从上表各报告进入。
