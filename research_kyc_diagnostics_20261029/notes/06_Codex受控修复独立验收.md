# Codex受控释放修复独立验收

2026-11-02 15:03后，先于读取DeepSeek23意见冻结。主审完整阅读释放事务、共同guard、worker、supervisor、冻结manifest与启动前修订，实际看了四图montage，独立核验保存数组及原始事件。未运行新GL/仿真/模型。

结论：**LOCAL_CONTROLLED_PASS，限定固定sample0与受控释放fixture。** 两before均匹配冻结健康参考，baseline在31→32中owner=A/current=B，B的3FBO+4RBO同namespace/ID由有效变无效，A明确NOT_MEASURED_WRONG_CONTEXT，随后解绑。fix33→34在A当前释放A，真实native restore事件46返回true，47恢复仍活B，52确认A销毁且B原对象全部有效；随后after与before逐像素相同，正常raw=sentinel、GL读回codes=[0]。释放退出至after结束没有新context/renderer或额外绑定，源码没有重建资源补救。

两条件同样持有A/B并在同一锁内显式一次释放，区别为释放事务；fix实际经历目标窗口，补上上轮缺项。每renderer首次con.free和成功原生context destroy各一次；DONE guard只抑制后续重复，首次未跳过。cleanup所有context销毁、fixture引用0。当前验证不依赖泄漏资源保持好图。

数组证据：4帧×5边界20项精确一致，8次原始readback数组文件及内容哈希一致，state/T/XML一致。三张健康图匹配参考688297…；baseline after有54.22%通道变化且无有效新读回，虽然视觉仍像场景、近似翻转，也不能当健康。它不精确等于before垂直翻转；未测内存来源，不能断言具体缓存复用路径。

预算/完整性：2新worker、2make_env、4renders、8readPixels、19.2856587232GPU秒、0ACT/step/rollout/更新；前者退出才启动后者，均exit0，主审核实原PID/start_ticks退出。295旧文件size/mtime/SHA与冻结脚本/来源SHA均匹配。启动前显存监控加入全设备保守上界，在workers=0时完成并重新冻结，无GPU运行后修改，资源上限未扩大。

父审重新执行纯CPU反例：非空raw context且key=None在新事务中可见拒绝，bind/con.free/egl.free全部未发生，错误状态可见，补上上轮遗漏。30/30原mock属于软件路径验证，不冒称实GL30次。详细独立证据见artifacts/parent_render_controlled_audit.json与scripts/verify_render_controlled_cpu.py。

限制：修复是owner释放+previous恢复的整体事务，未分离两子步骤贡献；只有固定状态、一个进程/条件、受控显式析构。未证明自然GC频率、多视角/长期/线程安全，也未复验三入口。修复模块只在隔离harness中生效，旧源码/训练环境未部署改变。旧checkpoint训练期输入历史仍缺，旧0/32仍UNKNOWN，整体研究决策仍D/IMPLEMENTATION-LIMITED；当前RGB子问题则有明确工程原因与受控局部修复证据。

投入判断：不建议新完整训练，也没有足够资格开展F算法实验。若继续，仅值得另行审定一份短小、零更新、冻结checkpoint的输入/先验后验诊断，以回答已有权重是否有可恢复的训练样本部署能力；不是使用本轮剩余预算自动续跑。该下一阶段提示词与结果交付后，按原任务书“生成任务书不等于自动获得执行授权”交研究负责人决定。当前RGB故障范围不需要继续盲目增加渲染重复。
