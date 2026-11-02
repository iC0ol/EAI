# 固定释放时点的GL生命周期修复验证（v1，待双方审核）

这是用户“检查原因并想办法解决当前RGB”授权内的一次更小验证。原render_lifecycle执行完成但因果验收PARTIAL：fix条件拍图时未发生旧owner释放，不能将健康图归因于修复。本协议只补同一受控触发与真实活previous恢复的缺项；不得重启旧terminal、沿用旧余额或自动恢复ACT/闭环/训练。只有本文件准确SHA经Codex及真实DeepSeek完整APPROVE后才能派发。

## 1. 目录、样本和角色

唯一新运行目录 `/home/asus/EAI/research_kyc_diagnostics_20261029/render_controlled/`；其他旧项目/源码/结果只读，旧runtime复用，所有新增缓存/临时文件留此。不安装、下载或改系统。仍由gpt-6.1-sol/max执行，主审只读原件和做CPU验收、独占Git index。

固定sample0（demo0/t0/camera1）、旧source_state/T、256×256、同一seed及lib.make_env(0)，相同单一lib.render+RGB转换流水线。这里不用Dataset/Evaluator触发自然GC，不新增数据或视角。两条件均保存相同state/T/XML、raw/flip/tensor/NPZ/PNG；旧三入口正常图证据仍保留，但本次不宣称复验三入口。

## 2. 预算和停止

总上限 **2个新OS/Python worker、2次make_env、4次底层mjr_render、8次mjr_readPixels、180 GPU分配秒**，包含初始化/失败/cleanup。每条件before/after各1帧，正常+独立sentinel各1次read。0ACT、0env.step、0rollout、0优化器更新。隐式调用计入上限；失败名额不退回，无第三worker。

单卡顺序，≤3CPU线程、RSS16GiB、VRAM12GiB、新盘150MiB；独立supervisor在170秒发终止并留10秒释放，派发+8h截止。记录PID/start_ticks/起止/退出，前worker退出才新exec后worker；不能继承初始化GL/CUDA的fork。最多1次不改变实验问题的工程纠错，所有失败计入既定预算，不重启terminal supervisor；无名额则PARTIAL。

## 3. CPU预检与唯一候选的必要纠错

复制既有owned_release/遥测/监督结构到新目录，记录来源和最小diff。先做CPU mock，不创建GL/CUDA/env。

修复同一owner-context释放并恢复previous事务的适配边界：**raw current context非零但registry key=None时是UNKNOWN，不是NULL。** 在任何context绑定/资源释放前可见失败并停止；raw=null与key状态矛盾也应拒绝。capture/owner/ids准备阶段的异常必须被记录并让worker停止，不能被Python析构异常忽略后继续冒称成功。不在未知context上继续清理或猜测恢复。旧模块只读，此纠错并入本次候选。

CPU检查包含真实适配器形式的非零context/key=None、NULL、正常live-other恢复、owner=previous、不认识/死亡的previous、部分/重复/重入析构、绑定/释放/恢复异常、前置capture异常，以及下节共同one-shot guard。确认unknown在bind/con.free/egl.free之前停止。CPU mock不能替代真实EGL证明。

## 4. 两条件相同的确定性fixture

**本次明确改变自然析构时点，用受控释放验证机制。** 两条件都在renderer构造wrapper中显式持有本次make_env产生的renderer，保证旧renderer不会因自然GC先释放。持有仅存在于fixture，不存在于遥测日志，不是候选修复的一部分。两条件相同的强引用和释放点必须公开，不能宣称这是自然GC复现。

make_env返回后，确认恰有两个不同、已登记存活的renderer/context：A为已退休renderer（其sim不是env.sim），B为env.sim的活动renderer，实际current=B。记录A/B来源身份及B真实GL对象。若数量/身份/current不符合预注册条件，停止该worker，不额外创建context/env或切换current来凑条件。

两条件从初始化前安装同一one-shot清理外层guard（NEW/RUNNING/DONE/ERROR，只控制重复调用；不切换context、不跳过首次con.free/gl_ctx.free）。baseline首次调用执行原析构语句/顺序，fix首次调用执行经过本节纠错的owned_release。精确记录原函数SHA和两条件差异，不能让baseline额外恢复previous。未预期自然析构或重复实质free视为偏差并停止。

1. 保持A/B强引用，在B当前下恢复固定state/T，保存健康before帧和对象身份；该帧须正常读回、sentinel=raw，且正常RGB像素与此前已实际验看的render_lifecycle/results/worker_1_baseline/early.png逐像素一致（像素SHA256=688297023a217d9874c347fdd0a6821def4d0a57d6abc8899014c63860976c37；冻结时另记录参考文件SHA）。不一致则STOP_BEFORE_CONTROL_MISMATCH，不调阈值或换参考，不把噪点熵高当健康。不可先释放再采before。
2. 在同一预定点持有原 `_MjSim_render_lock`，显式调用A的已安装one-shot析构入口一次。两条件采用同一调用路径，仅内部释放事务不同。不是gc.collect，不禁用GC，不删除A的字段来假装已释放。
3. baseline按原语义在B current时释放A；fix绑定A，在A current中释放A的GPU资源/EGL，然后恢复先前仍活的B。不重建FBO，不跳过eglReleaseThread，不额外make_current补救。
4. 记录释放完成后实际current与资源；恢复相同state/T并保存after帧。采after前不得修复绑定或重建资源；baseline预期坏图，但仍保存实际结果，不将未复现伪装成通过。
5. 从fixture移除已释放A的强引用，清理B并释放所有fixture引用。自然再次析构只允许guard跳过已经DONE的入口，不能再次free；记录exactly-once计数。不能因保留资源而得到正常图，cleanup/退出全部计预算。

worker1为baseline。只有受控释放A时确认B资源失效/解绑、before健康而after异常，才启动worker2；否则STOP_BASELINE_NOT_REPRODUCED，不盲试或反复等待自然时序。worker2为fix，完整重复同一确定性fixture与释放点。每条件只有1进程，非统计重复，不做长期稳定性主张。

## 5. 观测与通过门

复用按owner=current测量规则；baseline不能测A对象而只能测当前B对象。fix在con.free前后、gl_ctx.free前测A对象；在B恢复成功后测B对象。保留ID primitive，不把清零字段当测量。记录current/owner、同namespace FBO/RBO glIs、当前draw/read绑定/合法attachment、事件顺序。查询不为测量绑定FBO/context，未知或错误context明确NOT_MEASURED；默认FBO0状态不能冒充offFBO失效。

所有正常和sentinel分别计数并在原render锁内；sentinel为额外独立np.full(165)，不能替换正常np.empty。资源事件和normal raw均保存，已知健康场景中的自然165像素不算残留失败。

局部受控修复PASS须同时满足：两before健康；baseline在指定唯一释放中B对象从有效变无效/被解除且after坏；fix实际发生A≠previous=B、owner绑定/正确释放、**真实previous_restored到B**，A销毁而B所测原对象保持有效，after正常且与本条件before逐像素一致，sentinel=raw，GL读回无错误；B资源/图像不能通过重建或新context替代。state/T/XML一致，guard首次清理确实执行且未发生实质二次free。

若before不健康、身份不清、活previous恢复没有实际发生、对象身份丢失、基线不复现、after异常或任何门不满足，按对应PARTIAL/FAIL停止，不追加候选、第三worker或图像。不把仅“图像健康”或CPU mock当通过。

通过只证明**固定fixture、固定sample0、受控释放时点**的一项局部工程修复，不能证明自然GC发生率、多视角/长期/线程稳定性，也不能追认旧checkpoint训练0/32根因。仍不恢复模型/闭环，不把工程修复当论文创新。

## 6. 交付与异步续办

首次GL前冻结完整协议/代码/CPU mock/来源/样本/预算/进程锁SHA。保存真实命令、计数、原数组/匿名对象事件、完整性、FINAL_REPORT/STATUS/status/completion、明确未测项与可用范围。完整地址/XML/raw CLI仅local_only/logs；只交原创代码/必要小结果允许清单，秘密扫描；Git主审独占。

账户额度共享，按未来有效reset+120秒、最长5h复用6-1-sol-max；低额度先保存CPU/实现检查点，不能以额度理由延长GPU硬限，不兑换券、不忙轮询。完成/停止后按人类既有明确回传授权一次通知主线程01a18138-0f15-76b2-b5cf-20e1722782a9，保存回执，暂停子检查；主审独立数组/代码/实际看图与真实DeepSeek反驳后才宣布验收并统一发布。
