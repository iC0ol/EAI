# GPU预检真实结果独立验收 + Stage1最终冻结审查

继续同一真实会话；同一候选代码未改。请先独立审原始结果，**不要读notes/05_Codex预检验收及Stage1冻结.md**。不重新全文读取旧文献/大数据/全部候选，只针对实际新证据和必要代码确认。

目录 /home/asus/EAI/research_kyc_final_recovery_20261103。原件：stages/gpu-preflight.json、recovery_state.json、gpu_preflight_result.json、results/preflight_strict_load.json、results/preflight_input_provenance.json、results/gpu-preflight_readbacks/events.jsonl、logs/gpu-preflight.log、call_ledger.jsonl、resources.jsonl、model_events.jsonl、orchestration/gpu_preflight_executor_launch.json。执行者汇总artifacts/gpu_preflight_executor_verification.json仅供定位，不能代替原始证据。父审SHA/进程复算事实artifacts/parent_gpu_preflight_acceptance.json可读，但不要把父审复算声称是你的操作。

实际报告：一次worker，16.88504482805729GPU分配秒，exit0，input constructors/close成功，ACT strict-load成功，0ACT/render/read/step，科学时钟未开始。剩余总1783.114955秒。请独立核验是否够限定ENGINEERING_READY，尚缺什么不得夸大；原始事件/严格加载/计数/退出是否矛盾，停止/预算是否满足。没有图像或模型前向，不能称SCIENTIFIC_MEASURED。

然后针对同一协议与代码准确SHA审是否可批准 STAGE1_WITH_PARENT_INPUT_GATE：先s1-input12render/24read、0ACT、210秒；完全退出后父审真实12图/数组/GL/边界/文件集+源码SHA和预算签input_gate，再独立新派发s1-model固定16forward，S1合计600，总1800；无新修复、训练、重试。首次s1-input派发启动8h科学时钟。四状态/两demo、双常数、BF16、容差/筛选等既审原规则不变；此时Stage2仍不放行。

协议SHA256 3fd12394fd845a4c2df528119655af65ab1a830b55833f5aa278c0c8c004c460；manifest SHA256 bd4233fbeca8898d0145c3411ae98901897fd24b974984c3b83195cea75843ed。

给独立ACCEPT/REJECT预检及明确APPROVE/REJECT Stage1限定范围，列实际证据和限制。500汉字左右为宜，不追加重复工程测试或扩大实验；不运行、不写文件、不模拟观测。下一轮再交叉读Codex意见。
