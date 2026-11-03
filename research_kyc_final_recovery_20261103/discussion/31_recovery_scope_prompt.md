继续既有真实DeepSeek会话，本轮用户给了新的明确授权，不沿用上一轮暂停建议来结束。请用只读工具，做简短针对性独立科学/工程审查，不重新查文献、不执行代码。

新目录/home/asus/EAI/research_kyc_final_recovery_20261103。先读00_本轮用户任务书_原文.md、01_有限恢复边界与阶段门.md。暂先不要读notes/01_Codex初始针对性审查.md，形成独立判断后可读取交叉质疑；回答标明先后。已知旧轮common导入失败、第29/30轮结论都在既有上下文，不复述历史。

需明确评估：
1. 是否同意先派发原gpt-6.1-sol/max进行有限修复和真正独立CPU入口预检（最多R1已知冲突+R2真实新错误），不再把AST/mock当运行验证？最终GPU候选与科学代码仍要两审准确SHA。
2. 1800累计GPU秒含预检/失败/init/cleanup，S1原16/12/24，S2仅过门后16rollout/2400step/80query。当前建议工程GPU≤180、S1≤600、S2剩余；GPU预检不做额外forward/render/step，至多2次。总worker候选≤5，CPU3/RSS16GiB/VRAM12GiB/输出150MiB。是否存在隐含超预算、漏计或真实预检覆盖空洞？CPU安全导入与可能触发EGL/CUDA的依赖应如何清晰记录？
3. S1沿用旧阈值，S2复用旧8root计划，但必须取消旧closed_loop对旧dev clean_RGB与0/32动作完全一致的硬断言，保留XML/state/RNG一致。请读旧/home/asus/EAI/research_kyc_diagnostics_20261029/execution/scripts/stage1.py的restore_root和closed_loop核对。此修改是否必要且不改变模型/任务指标？
4. S2的8root/2相机不能称16独立任务。Stage1数值阳性不等于任务阳性、Stage2过门也不等于F有效。下一阶段判断阈值可在S2执行前另冻，不事后选样。只Stage3方案，不执行。

你对CPU_PRE_FLIGHT_AND_REPAIR_ONLY派发给出APPROVE或具体阻碍；别把此批准写成GPU或Stage2自动放行。控制在1200中文字，优先能防止再次几秒基础错误退出的具体建议。不要开始新研究题或泛泛失效报告。
