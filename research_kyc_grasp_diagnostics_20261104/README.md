# KYC 0/32 专项抓取诊断

2026-11-05完成全部授权实验和Codex / 真实DeepSeek独立验收、交叉讨论。工作站执行者为GPT-6.1-sol / max。详见[完整中文报告](02_联合根因报告.md)。

匹配的4个替代物理初态上，专家4/4成功；冻结checkpoint在训练相机和开发相机下各0/4，均无reach/grasp。两臂训练reader的44个实际item短时健康。累计367.712573 GPU分配秒（6.13分钟），40 ACT、12条轨迹、1630步，0训练。

**决策：停止当前checkpoint恢复，暂停依赖它的F实验。旧0/32的历史根因仍未唯一定位，F的一般科学假设也未被证伪。** 当前证据不支持继续盲目增加epoch或修复模块；本轮没有后续实验授权。

## 阅读顺序

1. [用户任务书](00_本轮用户任务书_原文.md)、[冻结协议](PROTOCOL_CANDIDATE.md)、[准确候选SHA](candidate_manifest.json)。本轮使用新的抓取行为诊断授权，不采用旧20% MAE门。
2. [源码审查](SOURCE_AUDIT.md)、[训练生命周期差异](notes/07_训练循环差异补充.md)。作者Lift配置150步；本地缺两处FBO检查和周期评估是代码事实，不是历史污染证明。
3. [逐root指标](artifacts/behavior_by_root.csv)、[行为图](figures/expert_policy_behavior.png)、[专家帧](figures/expert_a_contact_sheet.png)、[策略帧](figures/policy_b_contact_sheet.png)、[实际训练batch图](figures/c-local_actual_collate_RGB.png)。
4. [Codex独立六问](notes/17_Codex最终独立验收与六问.md)、[DeepSeek独立六问](discussion/50_final_independent_response.md)、[最终交叉与勘误](discussion/51_final_cross_response.md)、[勘误落实](notes/18_最终交叉验收与报告勘误.md)。审查38–51的请求和原回复按时间保留，被后续撤回的意见不是最终结论。
5. [最终预算和来源核验](artifacts/parent_final_execution_integrity.json)、[公开文件SHA清单](publication/manifest.json)、[发布检查](publication/scan.json)。

## 证据与复核边界

results/保留所有12条逐步轨迹、40个预测块及执行值、必要读回/相机/实际batch和代表帧；roots/保留状态与物理指纹。完整原示教XML并不存在，本轮新冻结XML和RNG快照仅留本地，其哈希在根清单中。四个root是有来源依据的替代场景，不能声称完全恢复原示教或旧32个开发场景。

scripts/parent_recompute_trajectories.py、parent_audit_policy.py、parent_audit_reader.py为纯CPU原件复核；plot_grasp_diagnostics.py由保存轨迹生成静态行为图。复核需要既有本地HDF5/统计及依赖；本公开包不捆绑环境、模型权重或完整数据，不承诺脱离原工作站即可一键复现。完整实际post-crop batch已公开，C每臂6组raw留存、16组只保留运行健康记录；不能把它描述成全部raw重算。

Codex实际解码并重算NPZ/HDF5。DeepSeek读取原JSON、日志、图像和带SHA的动作逐值转写，没有独立执行NPZ解码；真实调用的[脱敏回执](publication/deepseek_review_receipts.json)保留模型字段、起止时间、退出状态和输入/输出SHA。

13个含地址长度线程标识的JSON/JSONL以publication/redacted/下的公开副本提供；仅将线程标识替换成稳定标签，动作、状态、图像和统计不变。[原件—副本对照](publication/redactions.json)记录两侧SHA及替换字段数。原始文件完整留在本地，未为发布而改写。

PROTOCOL_CANDIDATE、CPU_PREPARATION和阶段completion保留当时状态，便于追溯；其中“等待审查”等历史文字不会覆盖本README及最终报告。所有科学阶段已结束，运行入口只作代码证据，不能将留存的dispatch误当作新运行授权。

公开允许清单不包含XML、原生地址映射、DeepSeek原始CLI、自动检查/额度资料、环境缓存或凭据。发布时只暂存本轮允许清单，旧项目保持原样。
