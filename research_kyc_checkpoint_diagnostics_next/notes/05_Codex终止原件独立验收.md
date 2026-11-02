# Codex 对本次终止的独立验收

2026-11-03，先读取原始traceback、实际command/ledger/resources、run_state、stages/input、dispatch与源码；本意见在本轮结果DeepSeek独立审查之前冻结。执行者叙述作为索引，结论由原件核验。CPU复核程序及结构化证据见scripts/parent_failure_acceptance.py、artifacts/parent_failure_acceptance.json。

## 实际结果与原因

接受 TERMINAL_STOP_INPUT_IMPORT_COLLISION 作为执行失败记录；不接受把它改称checkpoint失败。1个实验worker、退出码1、累计分配3.9268841021694243秒，计时包含导入与退出；make_env/render/readPixels/ACT/step/rollout/backward/optimizer全0。仅1条FRESH_EXEC与1条workers预留，input固定标记未删除、terminal stop已写、GPU租约为空；原worker和supervisor身份已退出。没有input_result、模型输入NPZ/PNG、模型结果或模型阶段启动记录。监督器自身退出码未单独采集，不补称exit0。采样资源峰值不是连续峰值。

因果链足够明确：input_worker顶层from common import *先缓存诊断common；第38行更改sys.path，第39行导入experiment_lib；其第2行from common import ROOT,atomic_json,utc命中前述缓存，诊断common没有ROOT和atomic_json，立即失败。错误在环境构造、实际框架入口和输入结果try/finally之前。主审只执行该条import的AST纯CPU反例，没有执行experiment_lib主体，没有导入torch、GL、环境或模型。该反例再次产生预期ImportError。改变sys.path不能说明已重新绑定common；当前错误归于本轮诊断整合，不是模型、驱动或数据结论。

40个冻结本地文件、39个来源SHA和521个旧证据size/mtime/SHA复核未变；本次审查没有修改冻结代码、重启监督器或消耗剩余实验名额。下一阶段strict load、官方/custom输入与输出等价、健康RGB动作预测、prior/posterior差距、强常数对比均NOT_RUN。旧0/32仍UNKNOWN。

## 审查责任与解释限制

此前32项准备检查、5项render门回归和30项复用生命周期mock没有覆盖这个真实导入顺序。代码和SHA双审是真实进行的，但其APPROVE没有发现命名空间冲突，不能包装成“执行者不按方案”或用测试数量淡化遗漏。Codex最终审批承担这项集成审查遗漏；不把它归咎于未修改的旧代码。DeepSeek先独立检验相同原件，再交换意见。

这次存在明确、可能低成本修正的导入原因，因此不满足“健康输入下已有checkpoint无动作能力且无明确修因”的实证暂停条件。也不能由导入问题容易解释推断其余管线可运行或checkpoint值得继续。已批准协议规定冻结后具体问题即停止，不自动恢复余量；本RUN保持终止，任何替代尝试都须另有明确范围与审批，不重写已批准manifest掩盖失败。

## 事前研究决策

1. 当前checkpoint动作能力未知；保留现有权重供审计，但不再自动投入。没有支持继续训练的证据。
2. 不具备闭环资格：健康输入+strict load+16次部署输出及常数比较均缺失。不能跳过诊断直接rollout。
3. F关键科学假设并未得到本轮新证据：先要可靠、准确标定下可完成任务的基线，然后才能比较同边际persistent与IID标定误差，以及简单pose-jitter/重标定之后是否存在可改进的残差。本轮即使成功也只覆盖训练分布两个demo四状态，不证明这些问题。
4. 最少的证据路线应分门：可靠输入与冻结动作诊断 → 极小闭环准确标定任务能力 → 配对persistent/IID对照 → 仅存在剩余差距时考虑简单基线及F机制。后一门不应在前一门失败时启动；无训练/新算法自动授权。当前连第一门尚未完成，不能宣布F Potential Go。
5. 以论文时间为目标，建议暂停当前自动F工程链，将下一笔研究时间优先用来确认一个能复现任务成功的基线。此为项目证据与机会成本的判断，不是已检索出更好具体仓库，也不是F科学No-Go。不进行新的广泛调研。若负责人仍选择挽救本checkpoint，唯一可考虑的有限例外是先在独立命名空间设计中证明整条入口的CPU导入一致性，双审新准确SHA，再另行批准一次同预算诊断；此文只是备选计划，未修代码/未派发/未开始。

必须如实报告本轮未产生所要求的动作能力证据，不能为了形式上收尾写出不存在的MAE、通过率、图像或实验阳性。最终公开须包含此失败和两方验收，以及明确的NOT_RUN；研究负责人可据此决定是否再给一次有限诊断，而不是被默认拉入下一轮排障。
