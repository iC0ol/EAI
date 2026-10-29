请对完整任务书v2作最终科学过门核验：/home/asus/EAI/research_kyc_diagnostics_20261029/01_有限排障执行任务书.md。v1原文保留artifacts/protocol_v1_draft.md，11真实回复不改。当前还没有发布执行线程或运行实验。

已落实11六项：
1 4重复拆样本0/1官方、2/3自定义，分开rmax，合计仍32；只称经验容差一致，不说所有差异噪声。
2 主常数变为训练0–199均匀demo/均匀start采样下每chunk位置k的加权median30×7。每合法a[d,t+k]权重1/(200 Ld)，padding排除；raw值和prior均用同checkpoint action_std比较。原单向量常数作为补充。这个公式匹配训练采样和官方按全部padding元素平均的训练目标；实际诊断报告有效步和padding分母两种。
3 posterior明确官方Dataset(id)+官方ACT路径，仅一次forward hook捕获a_hat/mu/logvar/is_pad_hat；不当闭环控制器、不选root/camera/seed/checkpoint。
4 固定Dataset t/camera仅新wrapper/subclass或窄上下文，保存并恢复RNG，不改vendor。
5 已写停止伪代码，明确每样本有效元素误差、按种子先平均误差不平均预测、按有效xyz元素汇总、6/8、raw方差、近零分母保护。停后D不是C。
6 §6本来已有16条8roots、旧dev物理状态不等同完整训练条件、宽区间/不得普遍结论，保留。

需要你明确一个措辞：11说“posterior不参与C选择”，但你同时认可posterior_gap是停止C预算的附加异常。这两句若按字面矛盾。v2明确posterior仅参与预登记的停止预算规则，不作为C的控制策略或挑选任何样本/权重/修复。这是否满足你的科学意图？请实质回答。

请读取最终全文，给 APPROVE / APPROVE_WITH_REQUIRED_CHANGES / REJECT。若APPROVE，明确认可仅执行冻结Stage0和有条件Stage1、32固定前向/16rollout/1GPUh/零更新，不能自动新完整训练。不要将未来工作说成已执行。
