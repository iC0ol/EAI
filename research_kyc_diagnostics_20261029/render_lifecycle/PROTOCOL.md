# 当前RGB：资源所属上下文的生命周期修复（v2）

用户已明确要求检查原因并尝试解决当前RGB损坏。本任务仍由Codex和真实DeepSeek审查、gpt-6.1-sol/max执行。不改旧源码/系统，不重训，不把当前故障追认旧0/32；不重启任何旧terminal任务。只有本文件准确SHA获双方APPROVE才派发。

## 1. 新目录与明确范围

唯一新运行目录 `/home/asus/EAI/research_kyc_diagnostics_20261029/render_lifecycle/`。原execution、render_repair及旧复现只读。只读复用旧runtime与数据、stats、sample0（demo0/t0/camera1），256×256、seed0与既有构造顺序。所有缓存/日志/结果留新目录，不安装/下载，不动模型权重或Git index。主线程独占Git负责公开。

本任务只有一种修复：**renderer的GPU资源在它所属EGL context中释放，释放后恢复先前仍存活的其他context**。它必须从新进程初始化之前安装，不能在资源可能已损坏后靠make_current补救。不是多候选碰运气，不重建FBO、不改driver、不禁用GC、不泄漏旧renderer来躲过析构。

## 2. 先做CPU预检与冻结

先读父审notes/04、parent_render_repair_audit.json、DeepSeek18与后续交叉意见、原两份执行报告及本任务全文。复制必要自有脚本到新目录，禁止import旧worker.main引发旧目录写入。来源和原件hash、完整脚本/协议SHA、计划/计数/锁、真实机器资源与其他进程先落盘。

不创建env/GL/CUDA的CPU mock必须覆盖：NULL opaque pointer、正常context、重复/部分析构、owner不存在、前一context=owner/另一个仍活context/null、恢复失败及异常路径。不要把这些检查计成已通过真实GL修复。保留简短结果即可。

## 3. 总预算与流程

- 最多 **2个全新OS/Python worker、2次make_env、8次底层mjr_render、16次mjr_readPixels、300GPU分配秒**，包括初始化/失败/调试/cleanup；0ACT、0env.step、0rollout、0优化器更新。禁止继承CUDA/EGL的fork子任务。
- 单卡顺序，≤3CPU线程、RSS16GiB、VRAM12GiB、新磁盘200MiB。supervisor累计GPU墙钟硬限300秒，agent中断仍可停止写completion；派发+8h结束。隐式调用计入上限，若消耗额外次数就缩短计划标PARTIAL，不补齐。
- worker1为**原析构语义+遥测基线**。make_env之后、Dataset/Evaluator之前，以固定state/T做1帧早期对照；按原顺序构造Dataset/Evaluator/embedder后，Dataset/id、Evaluator、自定义入口各1帧，共最多4render/8read。
- 只有基线记录到有针对性的生命周期异常（例如旧renderer析构时另一个context当前、释放前后对象有效性改变/线程绑定被解除），才启动worker2；先保存选择理由。早期图若已坏，要看异常是否已在早期前发生，不能仅用“早期坏”否定生命周期机制；若无支持证据，则停止，不盲试。
- worker2在新Python进程、make_env前启用上述唯一安全析构修复，重复同样早期1帧+三入口3帧、相同state/T/seed/构造顺序。worker1退出码/退出时间须先于worker2启动。两个进程是**基线/修复条件**，不是同条件两次独立复验；不声称已证明长期/多视角稳定性。
- 工程错误最多1项局部修正，全部失败和名额照计，不额外创建第三worker，不重启terminal supervisor。若名额耗尽就交付PARTIAL。不要新增宽泛审查循环。

## 4. 补齐对象身份和con.free边界

原glCheckFramebufferStatus(GL_FRAMEBUFFER)只检查当前draw绑定，0x8219可来自surfaceless默认FBO0，不能直接判offFBO对象被删。

本次在构造/析构、**con.free前后**、EGL释放前后、render/readback前后记录：匿名owner/current context、GL_DRAW_FRAMEBUFFER_BINDING、GL_READ_FRAMEBUFFER_BINDING，以及可合法测量的glIsFramebuffer、相关renderbuffer有效性、当前已绑定非零FBO的状态与可用attachment信息。资源身份必须包含所属context，整数相等不等于跨context共享同一对象；不假定context间资源共享。

**按context归属隔离测量**：只有被查询renderer的owner等于实际current，才可查询其offFBO/offFBO_r及相关GL对象。owner不等于current则该owner项明确记NOT_MEASURED_WRONG_CONTEXT，不能把current中的同名ID当作owner对象。baseline在旧owner析构而新context当前时，只能记录owner/current以及新current所属活动renderer的对象；不得声称测到了旧owner对象的销毁。fix先绑定owner，在owner当前时测量owner对象，执行con.free后、gl_ctx.free前再次测量；gl_ctx.free销毁owner后不再查询其GL资源。恢复previous成功后，才能测量previous所属活动renderer的对象。原始对象ID应在con.free前以primitive形式保留，避免其字段清零造成测量目标变化。

遥测只读，不为测量临时绑定FBO/创建对象/修复context，不调用会因绑定被删除ID而创建资源的探测。无current context跳过GL项并标null。若当前绑定0或不是欲检对象，不把其status赋给目标offFBO；相关attachment无法无副作用获得就NOT_MEASURED。预先固定GL查询及错误读取顺序，记录查询本身可产生/清除error。若不支持某查询，保存明确缺项，不临时安装扩展。

若pybind MjrContext.free不可直接包装，可在新进程使用对照的MjRenderContext.__del__窄实现，**基线逐句保持原析构顺序及释放语义**，只在self.con.free前后插事件。保存原函数源码hash和差异；修复条件仅增加owner绑定与previous恢复，不能改变清理对象清单。日志只存primitive/weakref，不能保留env/renderer/context强引用而延后析构；不主动触发GC，记录日志分配可能改变自然触发时序的限制。

正常raw与sentinel分离，沿用已审实现：正常readPixels返回及raw拷贝后，额外独立np.full(165)以同viewport/con读一次，仍在原render锁内、经持久计数；不改np.empty，不改正常rgb。保存raw/flip/tensor/NPZ/PNG及共同raw预处理比对，正常图用于健康判定，sentinel仅作辅助。三入口数据/RNG控制必须不改变算法；冻结样本不能按结果更换。

## 5. 唯一修复的所有权与错误语义

释放前保存线程当前context/display及draw/read surface句柄（公开只存代号），识别renderer所属owner。若owner有效，先将owner设为current，再执行同一con.free和原gl_ctx.free及原清理语义；最后若previous不同于已销毁owner且仍存活，恢复之前display/surfaces/context。previous=null或previous=已销毁owner时不得重新绑定已销毁句柄。验证每步实际current与restore返回值。

局部guard处理重复/部分初始化析构，避免双重free；异常记录必须可见，不能广泛吞掉binding/restore失败冒称成功。若owner缺失而con仍需释放、归属不明或恢复失败，停止该worker并报告，不能在错误context中继续free。禁止全局跳过eglReleaseThread、关闭GC或长期保留对象作为“修复”。已销毁context不能恢复；恢复前依据本次已记录创建/销毁生命周期核查存活，不凭裸整数猜测。

这是一项原子化的生命周期所有权修复；不能从整体有效自动判断两个子步骤各自贡献。若仍失败，按门停止，不追加第二修复或新buffer。

## 6. 验收与反证

要求保存释放前后对象有效性与绑定事件链、同状态原图、实际前后差异。支持资源误释放需baseline明确在**另一个context当前**时con.free前后该current所属活动renderer的真实对象有效性/附着发生变化，加上fix中owner被绑定后con.free前后的owner对象变化、previous恢复后其对象保持有效。baseline不能在错误current下测owner对象来填补证据；仅0x8219不够。若无法获得必要对象身份/归属/前后窗口，只报告局部修复效果与因果缺项，不宣称资源误删除已证。修复支持需按owner释放后活动context及其资源仍有效，真实正常raw可辨认Lift场景，三入口同state/T正常图一致或给出误差/原因，sentinel正常读回与raw一致，并由主审实际看图。

默认FBO0 undefined在非渲染检查点可能正常，不以“所有检查点status都36053”为门槛；判断真实读回使用的对象、GL错误、正常raw与健康对照。若早期控制正常、后续基线坏、修复保持正常且对象事件一致，支持局部生命周期修复；若基线无法复现、只有修复正常，则仅标有效性证据不足。若对象始终有效但raw仍坏，拒绝误删除解释并停止。

只有一个进程/条件，统计重复和长期稳定性未测；旧训练RGB/GL历史缺失仍UNKNOWN。当前成功也不自动启动ACT/rollout或新训练。

## 7. 交付与异步回传

写STATUS/status/completion、真实命令/进程/退出码、计数/GPU累计、代码与来源hash、raw图像/匿名事件/CPU分析、修复模块与明确可用范围、失败与未测项、旧目录完整性检查。只有原创代码/必要小型结果可公开，地址/完整XML/原始CLI仅local_only/logs，凭据/weights/runtime/大数据不公开。执行者不stage/commit/push。

复用6-1-sol-max检查，查询真实共享额度和reset，优先未来有效reset+120秒、最长5h；额度低保存检查点，不兑换券。运行仍受300秒独立硬限制。完成或停止后暂停自己的检查，按原人类分工与本次解决RGB授权，一次回传主聊天01a18138-0f15-76b2-b5cf-20e1722782a9，保存回执。主审独立验收、真实DeepSeek反驳后统一发布并更新中文八部分报告。
