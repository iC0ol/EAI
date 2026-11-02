# 最终协议与代码独立审核（必须读实现，不能仅据报告）

根目录 /home/asus/EAI/research_kyc_checkpoint_diagnostics_next 。人类已正式批准原03限定实验，仍须Codex与你双审准确SHA后才正式RUN。准备线程已回传PREPARATION_READY_NO_GPU，无新GL/ACT/forward。请只读审查，不运行代码/模型/GL，不写文件，不重做论文调研或旧轮讨论。

候选PROTOCOL.md SHA ddbfbc0b4ad45fd3d380a2984c9ef0591d461429817af8c6b9cd9dc2da428381；candidate_manifest.json SHA dcf61668dc0d5789c313d9afd759b99a8c610a43b8a9fbd16f2405470c670ee7。完整读取协议、manifest、PREPARATION_REPORT、notes/02判据交叉处理、call/sample plan、source_map；务必逐个读scripts/common.py,gates.py,runtime_safety.py,input_runtime.py,input_worker.py,call_guard.py,model_worker.py,metrics.py,analyze.py,supervisor.py，核对复制owned_release/telemetry实际SHA。可以定向读原官方/旧适配器代码，不导入或执行。不要先看Codex本轮代码审稿（尚未给出），本次独立形成意见。

重点：自然A释放的安装/注册时点与原有锁、raw/sentinel同锁/计数、没有HELD/额外GC；完整同raw预处理和Dataset真实输出比对；frame保存/strict-load/NoOptimizer torch proxy与只读ResNet缓存适配是否有错误；内部forward票据是否既不漏也不双计；输入worker退出与父审核验+RUN_MODEL是否真的不可绕过；两worker跨supervisor累计600秒与210子限/15秒收尾/8h总截止是否可信；无新训练/rollout/下载/旧路径写入。

核对metrics是否落实notes/02：双常数同mask/单位、repeat/posterior不混入能力均值、16calls、sample4/5不借噪声、方向/夹爪退化、无信号/混合/计划信号分界。对26“取整体最低常数”的选择争议：现在显式要求同时胜两个完整常数，主MAE锚点median，不拼样本/坐标；相当于对policy更严格，不靠选择提升policy。20%仅投资门。

请输出：最终APPROVE或REVISE（指明准确两个SHA），逐个具体阻塞问题及源码位置/最小修改，已审核的实际文件，哪些风险只能正式运行才知但不阻塞一次有限诊断。CPU mock不能算真实验证。不要因有停止门就忽略静态可发现的必败问题；也不要为假设性风险无限增加工程/实验。本次只是代码双审，新的运行/截止由主线程单独派发。
