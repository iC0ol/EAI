# GPU预检交叉处理与报告勘误

Codex已阅读真实DeepSeek32b独立意见（exit0、实际response model deepseek-flash；旧32因上下文超限无效）。两边先各自形成意见，现在交叉确认；不修改候选代码、manifest、协议或任何科学阈值。

协议SHA256：3fd12394fd845a4c2df528119655af65ab1a830b55833f5aa278c0c8c004c460。manifest SHA256：bd4233fbeca8898d0145c3411ae98901897fd24b974984c3b83195cea75843ed。

1. 接受CPU lazy-import覆盖限定。最终真实CPU检验只执行实际顶层导入，input_runtime/telemetry/owned_release/lc_common会首次在GPU预检执行真实导入；这不称全链路已通过。用户明确允许将设备/仿真相关剩余路径放到限额GPU预检，本次直接用正式共享builders验证，不再扩大测试循环。CPU测试未覆盖这些模块不是科学成功证据。
2. 接受cleanup表述勘误：GPU预检用builders.close_input，S1 input有自己的manual cleanup；共享的是实际构造器，清理目的相同但不能称完全同一函数。S1必须独立确认cleanup和所有GL context已销毁。
3. 同意一个worker顺序input构造/清理，再model构造/strict-load/清理在代码上可行。DeepSeek撤回旧断言；是否实际通过由受监督运行决定。
4. 接受极端退出竞态和finally异常可能影响结果落盘的风险；不能仅依赖gpu_preflight_result。父审独立检查worker/supervisor PID+start_ticks、原始日志、call ledger、resources和分配时间；缺少终态不猜零预算或成功。若账本未完整落盘，先只读核实并保守计已分配时段，停止，不重启或补跑。
5. 冻结SHA是阶段入口检查，不是OS级只读；父审各阶段重算SHA、输入/常数/统计来源和文件集合。S2放行前再次独立检查S1原始输入/输出/分母/分析，不把分析脚本未重验SHA误当不可篡改。所有门均待实际证据，不凭自动字符串放行。
6. 本次仅批准GPU_PREFLIGHT_ONLY：单一phase一次、最多180GPU分配秒、0ACT/render/read/step、全程累计1800。两轮修复额度耗尽，失败即封存。Stage1/2未批准；科学8h未开始。Stage2研究解释阈值须在闭环数据出现前另冻，不能事后将少量阳性直接升格为Potential F。

Codex决定：APPROVE GPU_PREFLIGHT_ONLY，精确上述SHA，不要求改实验源码，不再重复CPU测试。额度已真实刷新；待DeepSeek交叉确认后正式下发。
