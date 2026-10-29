继续同一真实 DeepSeek 会话，但这是用户授权的新一轮 KYC 排障，不是此前研究的重复答复。你是独立研究审查者；Codex 同时独立核查实现，在本轮交换意见前不向你提供其新意见。请先独立形成自己的证据和优先级。仅可用只读工具；不得运行实验、修改文件、下载权重或凭据。

完整用户任务：/home/asus/EAI/research_kyc_diagnostics_20261029/00_原始任务书.md。请先读。
旧实验根：/home/asus/EAI/research_expansion_20261029/。至少读 02_联合研究最终报告.md、notes/04_复现结果独立审查.md、reproduction/FINAL_REPORT.md、PROTOCOL.md、RECOVERY.md、results/dev_summary.json、results/offline_action_audit.json、manifests/C_config.json、scripts/run_experiment.py、scripts/evaluate.py、scripts/experiment_lib.py。
官方本地只读源码：reproduction/vendor/kyc（e0647105a0f3946581d253c55dc9fd1218fa0974），reproduction/vendor/robosuite（0df3a5f5782937fa2e8fa923910d616b73310b8d）。重点看 policy_robosuite/train.py、eval.py、utils.py、models/act.py、models/detr_vae.py，及 reproduce/paper_runs.yaml；确切路径用Glob定位。可查官方 https://github.com/ripl/CamPoseOpensource 与论文 https://arxiv.org/abs/2510.02268。已有缓存 sources/ 可以查，但保留真实来源和版本。

不要把旧讨论的判断当成证据，重新检查当前文件。也不需要重做 D/M/U 或全面选题调研。固定事实：60003 updates 已完成、冻结 final checkpoint；专家10/10，准确外参新相机 dev0/32；正式test未跑。你的职责是审查 H1输入不一致/H2后验拟合而部署prior失败/H3训练相机与新相机差异/H4数据环境采样偏差。请给支持与反对证据、现有证据排除范围、源码位置、未知项和最低成本区分实验。不预先认定 bug 或为了延续 F 发明网络。

必须说明：官方复现真正要求；如何区分CVAE后验验证loss与部署能力；低损失/对raymap敏感是否足够；常数动作基线如何定义才公平；少量训练视角闭环能支持什么不能支持什么；官方是否有匹配本任务/动作约定/checkpoint公开可用（有来源才说有）；恢复基线后F仍面临哪些最近研究的覆盖。已有MoVie等研究只作针对性复核，不扩大方向搜索。

本轮最高预算：固定样本前向32次，闭环16条×150步，总诊断含仿真≤1 GPUh，零优化器更新。Stage0先只读结论；Stage1只在未决问题确需运行且双方任务审查通过时。任何完整新训练仍需人类重新批准。

输出中文独立审查：1事实/差异/假说分开；2逐项证据与反证；3有限预算内最有辨识力的诊断建议并明确计数；4可停止条件和A/B/C/D决策边界；5针对性官方来源。不要写已批准未知任务或已执行新实验。
