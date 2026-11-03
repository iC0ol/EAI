旧真实Claude/DeepSeek会话736077c1-8d4e-4df7-979f-1fc15f980a2a在本轮32因1052755>1048576 tokens被拒绝，未形成评审。本次新真实会话继承文件检查点。请先读本目录discussion/32_context_handoff.md，然后进行下列独立审查。

# 真实独立候选审查：最后一次有限恢复

继续本真实会话，禁止执行代码/GL/模型/写文件，禁止宽泛重查文献。本轮用户已授权最后有限恢复，CPU准备完成。先独立审查以下实际材料，**先不要读取 notes/03_Codex候选独立审查.md**，你的第一份意见不得被Codex结论锚定。无需重复旧轮研究结论。

目录 /home/asus/EAI/research_kyc_final_recovery_20261103 。精确候选：PROTOCOL.md SHA256 3fd12394fd845a4c2df528119655af65ab1a830b55833f5aa278c0c8c004c460；candidate_manifest.json SHA256 bd4233fbeca8898d0145c3411ae98901897fd24b974984c3b83195cea75843ed。

请读本目录00_本轮用户任务书_原文.md、PROTOCOL.md、CPU_PREFLIGHT_REPORT.md、repair_ledger.json、cpu_preflight/final/result.json、artifacts/parent_candidate_hash_audit.json、候选manifest及必要diff，重点实际读取kyc_recovery/loader.py、builders.py、gpu_preflight.py、gates.py、supervisor.py、common.py、runtime_safety.py、model_runtime.py、call_guard.py以及input_runtime/input_worker/model_worker/closed_worker/metrics相关关键处。按实际代码审查，不仅看执行者报告。

独立回答：
1. 真实CPU预检是否确实隔离旧common冲突、同一入口真实导入？其局限是否被正确陈述？R1/R2已消耗2/2，后续不得第三轮修复。
2. GPU预检候选同一个worker先input_setup→close_input，再model_setup(strict load)→close_model；共享正式构造器、无ACT/render/read/step、180秒含初始化清理、总1800。你上轮说一个worker不能覆盖两路径，请按当前具体代码验证是否成立，避免仅凭先前断言。若有具体阻断指出源码位置；不要要求额外实验来证明未授权内容。
3. 实际计数、唯一phase、提前停止、异步退出/无人等待占GPU、旧源只读和SHA门有没有必须拒绝的问题？预算5worker外上限但只有4唯一phase、两轮已用完，不准第五次重试。
4. Stage1固定16/12/24、强常数、先健康输入后模型及结果解释是否符合授权？Stage2仍要S1实际通过后独立验收/交叉审查，8root配对，不自动批准。
5. 针对本精确SHA，给出明确 APPROVE GPU_PREFLIGHT_ONLY 或 REJECT，列出必须修改的问题与仅报告限制的区别。不给Stage1/Stage2偷渡批准。不要把静态阅读称GPU实际成功。

之后我们再交叉质疑；现在只输出你的独立意见，精简但证据具体。只读权限，不启动任何进程或更改旧/新代码。
