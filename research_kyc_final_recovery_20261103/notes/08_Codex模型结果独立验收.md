# Codex模型结果独立验收（DeepSeek36前冻结）

**SCIENTIFIC_MEASURED / INCONCLUSIVE_MIXED_OR_WEAK_SIGNAL；Stage1数值投资门未通过，Stage2 NOT_RUN。** 本轮已经跨过工程阻塞并完成真实评估，不能再归类为未加载模型的导入失败；但仍没有可靠部署能力或Lift成功证据。

独立脚本scripts/parent_recompute_model.py不导入执行者metrics/analyze，先从16个原始NPZ与保存输入/目标、冻结统计量/常数重算float64，写artifacts/parent_model_recomputation.json后才读取执行端analysis.json作比较。核心指标完全一致。再次核对源头、输入集、16调用顺序/seed/branch/batch、输出hash、原始输入tensor hash、prior没有actions/is_pad、strict denormalization与16 policy/internal/complete事件。原始数字另无损导出review_packets/model_originals，供只读DeepSeek独立查看，不产生任何新前向。

| 四状态等权指标 | 官方prior | posterior（有动作标签） | 强mean | 强median |
|---|---:|---:|---:|---:|
| xyz normalized MAE | 0.728540 | 0.728892 | 0.740696 | 0.738244 |
| 全7维 normalized MAE | 0.539282 | 0.539603 | 0.592716 | 0.543627 |
| 平均逐状态RMSE | 0.934486 | 0.934641 | 0.883127 | 0.928284 |
| 平移方向余弦 | 0.498815 | 0.514871 | 0.480083 | 0.288077 |
| 夹爪sign准确率 | 0.675 | 0.675 | 0.675 | 0.675 |

官方/custom四状态首次输出差均0；0/1两入口自身重复差均0。未重复4/5不冒称其重复稳定。prior xyz相对mean仅改善1.641%、相对median仅1.314%；7维相对median仅改善0.799%，相对mean改善9.015%。每个状态都未同时优于两个常数：0/1输给mean，4/5输给median，因此0/4（门为至少3/4且两demo），同时20%门未过。不能只挑较弱常数或只报总体loss。方向改善与夹爪无总体退化不能覆盖这两项预登记失败；posterior单次有标签采样没有显示实质优势。

配对描述（artifacts/parent_paired_state_description.json，不是事后新放行阈值）：相同T的0→4和1→5，RGB有16.1%/17.2%像素位置变化，而prior多数动作维度变化很小；专家平移平均维差约2.4–4.9毫米，prior对应约0–1.24微米。两对专家夹爪chunk平均绝对差1.2/1.4，而预测约0.00051/0。提示在这两对训练状态中预测对任务进展反应很弱；不能据此证明全局视觉塌缩、锁定网络层原因或把两demo当独立泛化集。posterior的mu/logvar接近0和近似输出也只是有限BF16/单次采样证据，不推出更换KL、增训练轮次有效。

本阶段16.663939374秒，累计53.40354579128325 GPU秒；总16ACT/12render/24read，0训练/step/rollout，未触限。当前无证据证明入口不一致、坏图、缺失权重或数值不稳能够解释本次弱表现；没有已证实、可在剩余授权内修复的明确原因。旧0/32历史因果仍UNKNOWN。

**独立研究决定：不放行Stage2；暂停当前checkpoint的优先F路线，保留权重和证据。** 这是按有限训练状态投资门及已有高排障成本作出的选择，不是证明KYC方法无效，也不是统计意义的泛化No-Go。即使预算剩余很多也不能改门继续rollout。下一步唯一建议是由研究负责人批准另选有官方权重且已有可复验任务阳性的基线，先验证准确相机下任务行为；不自动开展新搜索、下载、训练、修复或F实验。

F核心假设仍缺可靠准确标定任务基线、独立来源配对任务结果、公平匹配边际与幅度的IID/episode-persistent两非零幅度比较，以及无真值泄漏的简单重新标定/常规鲁棒性对照。当前没有资格写F有效性论文结论或执行Stage3。本轮四训练状态/两demo也不能回答真实闭环成功率；第二基础问题必须诚实记NOT_MEASURED，不能填0/16。
