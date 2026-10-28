# 具身智能选题：扩展研究与条件性复现

**最终结论见[联合研究最终报告](02_联合研究最终报告.md)。** 当前无可直接进入新方法研发的合格候选。F的C训练完成，但准确外参dev0/32触发停止；实验PARTIAL / IMPLEMENTATION-LIMITED，正式误差比较NOT_RUN。研究及收尾材料已齐备。

状态见 [STATUS.md](STATUS.md)，授权见 [00_范围与授权.md](00_范围与授权.md)。

- 上一轮完整交付：[research_selection_20261028](../research_selection_20261028/README.md)
- 新检索与判断：notes/
- 真实 DeepSeek 通信：discussion/
- 两个五小时检查与任务派发：orchestration/
- 有资格对象的具体协议与复现：reproduction/

已完成本批扩展检索、五次真实DeepSeek通信、限定复现、主线程独立复核及结果纠错。累计GPU保守分配约4.642h，未追加停止后的训练/推理/rollout。

- [复现前研究判断与下一步](01_复现前研究判断.md)
- [独立初筛（冻结）](notes/01_Codex独立初筛.md)
- [核心文献与源码核查](notes/02_核心证据登记.md)
- [真实讨论纠错与保留分歧](notes/03_交叉审查与纠错.md)
- [已冻结执行协议](reproduction/PROTOCOL.md)
- [执行者最终报告与逐root结果](reproduction/FINAL_REPORT.md)
- [主线程独立结果/代码审查](notes/04_复现结果独立审查.md)
- [只读补证与恢复资格任务书](03_只读补证与恢复资格任务书.md)
- [派发、模型及双检查记录](orchestration/dispatch.json)

GPT-6.1-sol（max）任务“复现相机条件策略与持续标定误差”于01:26发布，06:26五小时续查后完成dev和收尾，一次回传主聊天；执行检查已停止。主线程01:37、06:34两次核查及最终审查已记录。全部时间为2026-10-29 Asia/Shanghai。检索前判断和冻结协议保留为历史文件，不能据其旧“待执行”状态重新启动。
