# 第07轮：真实复现结果反驳与最后研究判断

接续已核验会话736077c1-8d4e-4df7-979f-1fc15f980a2a。现在是2026-10-29 06:38 Asia/Shanghai。用户授权扩大研究、真实讨论及GPT-6.1-sol max有预算复现；本轮实验已经触发停止规则，不能新建实验、训练、推理、rollout或更改源文件。

实际执行目录：/home/asus/EAI/research_expansion_20261029/reproduction。先读PROTOCOL.md、frozen_training_plan.json、training_progress.json、results/dev_summary.json、results/loss_summary.json、results/offline_action_audit.json（仅汇总和少量行）、results/semantics.json、patches/README.md；FINAL_REPORT.md/completion.json若还未生成，不等待。需要代码时只读scripts/run_experiment.py、experiment_lib.py、evaluate.py，以及vendor/kyc/policy_robosuite/train.py、utils.py、models/act.py、models/detr_vae.py、models/backbone.py和reproduce/paper_runs.yaml。不要读凭据、模型二进制、环境目录或巨大日志。

已经主线程核验的事实：独立监督器在对话额度中断时继续运行，C完成20001 epochs / 60003次更新，训练4.57小时左右；10/10专家示范回放成功，初始XML+state连续重建图像完全相同。C dev 32个独立roots为0/32成功、0接近、0夹持；另一个同root重放动作完全一致，不增加n。正式350rollout全部NOT_RUN；U没训练，只做随机初始化RGB-only接口阴性。固定RGB下C对raymap的动作会变，但这种变化不构成任务阳性。训练loss8.779→0.393，最后1000均值0.380；最后val loss0.331。配置匹配官方LiftRand ACT默认及paper_runs，但只用seed0、固定末步、不用test挑checkpoint、val用train相机pool。

Codex当前判断：实施受限，既不是persistent机制被证伪，也不是已复现KYC论文数值。最新dev动作日志显示横向动作接近零；原因未确定。主线程正在只读核对官方路径与执行路径。当前stats没有U旧项目那种极端标准差，不能套用旧归一化诊断。训练中关闭官方test rollout可能改变共享env重置和RNG轨迹，是需核查的实施差异，尚不等于致因。

请做有实质反驳的审查，给出：(1)最重要的事实/证据状态纠错；(2)根据实际源码指出最多3个优先排查点，精确路径/行/条件，区分已证实实现差异与未证实原因；找不到确定bug就明确说；(3)哪些方法假设现在必须降级，是否还可给F优先论文资格；(4)若后续继续，最小恢复资格条件是什么，优先简单修复且不借坏baseline制造创新；(5)如何向硕士研究者写最后结论，包含两周/三月条件性计划与终止条件。

额外查新：主线程已补读MoVie NeurIPS2023的§4/5、附录A/B和官方README，它已有冻结动力学+测试时视觉编码器/STN适应，固定/移动/抖动视角均涵盖，不能把泛泛“动力学一致性相机适应”当新方法。KYC、CamVLA、AnyCamVLA与MoVie的不同输入假设要明确。只在现有文献和真实数据上讨论，不模拟结果，不重复泛泛认可。请用中文，约2000–3000字以内，报告实际证据与保留分歧。
