这是研究负责人2026-11-04新的正式授权，接续真实session3042c6f2-e7a1-422d-a632-2f6ad14e854b。上一轮已交付，不重做；你是DeepSeek独立审查者，不能把旧20% MAE门用于阻止本轮授权闭环。只读，不运行或修改任何实验。先独立查看新任务原文 /home/asus/EAI/research_kyc_grasp_diagnostics_20261104/00_本轮用户任务书_原文.md 和AGENTS.md。

自己读 /home/asus/EAI/research_expansion_20261029/reproduction 下官方vendor/kyc/policy_robosuite/train.py、eval.py、utils.py(EpisodicDataset)、vendor/kyc/reproduce/paper_runs.yaml，vendor/robosuite/robosuite/wrappers/action_wrapper.py，本地scripts/run_experiment.py、evaluate.py、experiment_lib.py、validate_semantics.py，results/semantics.json与dev_summary.json。必要时读之前RGB故障报告research_kyc_diagnostics_20261029/02_联合排障报告.md及最后恢复报告research_kyc_final_recovery_20261103/02_联合验收与研究决策报告.md。不读新notes中的Codex独立意见（尚未写），先冻结自己的判断。

请重点审查官方FBO检查/reset与本地的真实差异，150与通用300配置，累计eef_delta/成功判定/初态恢复是否一致；区分明确代码缺口、目前可复现训练输入污染和旧训练因果三层。提出有限可判别方案：A四个匹配专家回放+B四root训练/dev各一，共最多12条、各<=150步；C一次有限原训练Dataset动态渲染流程检查，零训练。总GPU分配建议硬上限900秒含全部初始化/预检/失败/清理，CPU<=3/RSS16GiB/整卡12GiB。

数据缺逐demo XML时如何诚实建立替代物理root与匹配专家/策略阳性？可考虑原10/10专家中的demo0..3、生成器默认seed42+i，一次冻结XML+state共享A/B；训练相机窗口内中间相机i+1与旧dev root1000+i的T配对，但不得混称旧dev物理root或原始示教场景完全重建。你可提出更有证据的替代，无结果后挑选。审查StageC如何使当前坏RGB实际进入训练预处理张量，以及无当前故障时如何限制历史因果。不要将不完整FBO单点状态、loss下降、健康修复后的图直接当历史根因证明。

只给针对性独立审查、关键混淆、最小实验/停止条件建议和预算可行性；先不批准未见的候选集成代码。输出中文，引用实际文件行号及证据。无需重开完整文献研究。
