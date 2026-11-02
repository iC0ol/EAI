# 新授权范围：只审本轮固定诊断的事前判据

用户2026-11-02正式批准上一轮GitHub 03提示词限定的健康RGB冻结checkpoint诊断。请接续真实上下文，但不要重做上一轮排障讨论或完整论文调研；只读，不运行模型/GL/代码。新目录 /home/asus/EAI/research_kyc_checkpoint_diagnostics_next 。

读取00_本轮授权.md、00_任务基础_原文.md、notes/01_Codex事前判据.md，以及orchestration/preparation_dispatch.json。执行者正在只准备可运行代码，0新GL/model；最终协议+代码准确SHA还需两审后正式RUN，当前不是执行授权。你现在仅审科学判据和资源计划，不假称已审尚未出现的实现。研究负责人非常重视尽快硕士小论文的性价比，明确无部署信号且无具体原因就倾向暂停F，过门也只交下一最小闭环计划。

重点反驳：固定4状态2demo是否足以回答真实动作预测能力到什么程度；strong constant指标是否严谨、有没有oracle/标签选择；20%改善/3of4/7维不过差作为事前投资门是否过于任意或遗漏方向/夹爪；BF16输出入口容差1e-5+1e-4是否应仅bit-consistency还是保守不确定；posterior单样本及两个入口重复如何解释；0.8–1轻微信号不自动加实验是否合理。要求预算保持16forward/12render/24read/600GPU秒/2worker，0step/rollout/训练。输入worker退出后父审可视门再模型worker，等待不得占GPU不计时。

给出必须修改的具体条款与理由，以及是否可把更新判据并入最终协议。不要增加模型调用、训练或新的实验因素；不要拿两个模型共识当科学证据。该回复不是最终code/SHA过门，后续将完整提交精确实现供你审核。
