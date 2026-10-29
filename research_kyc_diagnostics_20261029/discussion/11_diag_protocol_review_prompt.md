这是本轮第2次实质交叉讨论，同时审查完整有限执行任务。请读 /home/asus/EAI/research_kyc_diagnostics_20261029/01_有限排障执行任务书.md 全文，并依据原始用户任务判断其科学有效性、预算和停止条件。你10回复保留原文不修改。

Codex反对10回复两点：
1 你建议同入口重复测噪声，但已分配8样本×4=32，没有额外重复额度。完整稿重分配为8官方prior+8自定义prior+4前t0样本官方prior重复+8posterior首seed+4前t0样本posterior第二seed=32，batch1，失败也计。posterior重复只覆盖4个，诚实报告。容差max(1e-5,2*rmax)，rmax>1e-3则停C为数值未稳定，不扩大容差。
2 你要求“posterior在6/8优于prior”才允许闭环，这不成立：prior良好、posterior接近是健康情况，也可能小KL。稿件明确撤除此门槛。只在prior XYZ既总体不优于train median且6/8不优，同时有严重输出集中或posterior明显更好时停止C；阈值只是机会成本规则，open-loop停后归D而非训练任务普遍失败。请实质反驳或接受，不能仅因Codex提出就同意。

另外：A接口必须独立，不能官方和自定义都调用同一helper形成循环验证；Dataset固定t/camera临时控制要记录，无RGB存储事实；prior绝不读actions/真值。C复用原1000–1007 XML/state/RNG与原dev相机，再配训练池indices；新的16条并非16独立roots。当前渲染健康不能证明历史训练健康。已核实YAML eval_start_epoch=10000，10回复的纠正正确，保留。

请输出：
- 对两项争议的理由和明确结论；
- 协议是否能在零优化器更新、32固定前向、16rollout、总1GPUh内执行；任何隐藏超额、泄漏、假因果、误导性C门槛或不可实现点；
- 必须修改项与可选建议分开；不扩大研究范围；
- 对该完整文件给明确科学审查结论 APPROVE / APPROVE_WITH_REQUIRED_CHANGES / REJECT，并列准确节号。如果需要修改，我会修改后再次请你核验，不把条件意见当已过门。

本轮未派发新执行线程，未运行新推理/仿真。你仍只读，不做实验/改文件。
