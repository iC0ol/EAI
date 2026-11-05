# Codex 候选代码预读检查点（非最终批准）

2026-11-04 15:17 Asia/Shanghai。执行者仍在CPU准备，尚无最终candidate manifest、真实CPU最终报告、准确SHA双审或GPU派发。代码尚在改动，本记录不构成任何运行批准。

## 已完成的独立审查

主审notes/01是在读取DeepSeek38意见之前完成的源码/历史证据独立审查；notes/02为交叉质疑；notes/03为官方论文/150步配置及历史证据边界。真实DeepSeek38与39均已退出且有metadata/response；39撤回“env.reset不重建context”的错误说法。不要重复启动38/39。继续使用真实session3042c6f2-e7a1-422d-a632-2f6ad14e854b，经scripts/run_deepseek_recovery.py --resume。

已预读moving版本 common/ledger/gates/supervisor/roots/control/render_audit/builders/preflight_worker/expert_worker/policy_worker/reader_worker，以及实际官方Dataset。主要结构是预检四root+两帧+strictload，A四专家，B八条配对150步/五query，C两个各22样本的实际getitem→crop/id→default_collate审查。A+B总12轨迹、40 ACT、1800步封顶；科学阶段必须先有真实预检后内预算门。CPU准备与GPU预检不是任务行为证据。

## 已反馈执行者，最终版本需要复核

1. 使用实际env.sim.model几何/状态验证，而非reset_from_xml_string后可能陈旧的env.model模板。roots.physics当前采用实际sim几何数组摘要。
2. 150MiB目录上限包含本地讨论raw；B不重复保存40份9通道输入，C通过真实collate切片保留每item，以免无意义重复挤占证据预算。
3. 动作前EEF/物体/夹爪真实状态要明确记录。15:15版本已新增initial_EEF/initial_cube，但gripper_qpos仍有obs.get(...,[])静默缺失默认，已要求执行者补核。最终文件仍需重读。
4. 不用旧20% MAE门阻止本次B。A失败必须先识别控制/状态恢复；不能神经网络背锅。候选要求四专家阳性及reward==1/_check_success一致才允许B。
5. C两个臂目前都用相同本地训练/验证初始化，唯一差异是实际官方两个FBO/reset源码节点。它是“添加官方guard”的机制对照，不是完整官方训练复刻；官方验证test_cameras与本地train_cameras差别需单独注明。无故意wrong-context/free，无强制GC，无loss/optimizer/ACT。
6. 监测本身（GL查询、第二sentinel read）会改变运行时序，C有限当前样本没复现不能排除旧长期训练污染。若有坏图，要核原uint8→实际crop→getitem→collate完整链，不能仅凭GL错误下结论。
7. A/B种子42..45及demo0..3来自预选固定方案，不是结果后筛选。源数据缺逐demo XML；新root只建立本轮A/B一致替代物理场景，不宣称原示教XML精确重建。

## 待做

等待执行者CPU完成回传（不要重复派发准备）；对最终代码/真实CPU记录/协议和全部准确SHA完成Codex独立审查，再真实DeepSeek独立审查及必要交叉。仅精确双审后单独GPU预检派发。真实预检验收后冻结内预算与科学8h时钟；A验收后才B，C有限一次，各阶段结束不持GPU等待。

目前5h共享额度15:13实查92%、周14%。真实reset19:40:02，主/子复用检查19:42:02，之后每日04/09/14/19/23:42:02最大间隔5h。没有兑换卡。主审Git独占，N尚未公开，旧实验/源码只读。
