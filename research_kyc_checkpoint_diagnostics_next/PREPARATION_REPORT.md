# 冻结 checkpoint 诊断准备交付

**PREPARATION_READY_NO_GPU；不是实验派发，也不是最终双审通过。** 已提供两阶段可运行候选源码、协议、样本/调用清单、精确来源映射与差异、CPU 检查、门模板。没有导入实际实验入口运行，没有构造 GL、ACT 或执行 forward，也没有启动 supervisor/实验 worker。checkpoint strict load、真实采图、自然释放窗口和 ACT 输出均 NOT_RUN。

协议 SHA256：`ddbfbc0b4ad45fd3d380a2984c9ef0591d461429817af8c6b9cd9dc2da428381`。候选 manifest SHA256：`dcf61668dc0d5789c313d9afd759b99a8c610a43b8a9fbd16f2405470c670ee7`。manifest 绑定38个本目录文件和39个只读来源；两个审核者必须同时批准协议及该 manifest 的准确 SHA。文件仍为 candidate，主审修改任何受绑定文件后须重新运行 CPU 检查/prepare 并针对新 SHA 审核。此目录没有正式 dispatch.json、review_gate.json、input_gate.json 或 run_state.json。

纯 CPU 检查 **30+32=62 项通过**。生命周期30项为已审模块复用；新增32项覆盖逻辑/内部调用一次计账、隐式/额外调用与 prior 标签拒绝、协议/输入/最终审核失配、输入未退出/租约未清、晚发析构 fatal、累计上限、实际强常数算术、方向/夹爪否决和重复噪声。AST 编译16个脚本未执行函数体；没有用 mock 代替真实 EGL/strict load/模型验证。四个实际目标的两个常数 MAE/RMSE与父审 CPU 原件对齐到13位小数，未拟合常数。

`input_worker.py` 保留旧 stage1 的 make_env→Dataset→Evaluator→embedder 构造与 Dataset→Evaluator→custom 采图顺序。自然释放安装在初始化前，无 HELD/强制析构/额外 GC；输入 worker 只让上游 env.close/MjSim.free 按原语义清理。未观测到目标自然释放窗口会独立记 NOT_REPRODUCED。三个入口图像审计与统一模型输入比较分开：official/custom 对同一已保存 Dataset raw 做纯预处理，实际 Dataset 输出也验证；保存全部边界和 raw/sentinel，任何不健康立即停止。

`model_worker.py` 只读冻结 NPZ，严格加载已有375项 checkpoint，全程 eval/inference_mode。精度为原部署 BF16 autocast，FP32参数、TF32关闭；固定16次清单和逐样本旧seed，不 warmup或调试重跑。ACTPolicy原字典 in-place ImageNet normalize 只操作 clone。两个需要重点审查的新适配是：只读 ResNet 缓存 URL 映射；仅 models.detr_vae 内的 torch proxy 将 AdamW 构建变为 inert sentinel，其余属性委托原 torch，不建立真实 optimizer。完整 strict load 未实际执行，不能保证它一定通过。

`gates.py` 绑定双方准确代码/协议审核、执行者/model声明和新 RUN id/累计预算。模型阶段还需父审实际看图与 CPU 原件的证据 SHA，所有输入及源头 SHA、已退出 input stage 的进程/计数记录，以及明确 RUN_MODEL。晚发 fatal 或额外/改变文件拒绝。`supervisor.py` 每次只 fresh-exec 一个 worker；两个 stage 共享持久化计数/600秒，总两 worker，exclusive started marker 不删除。input分配210秒，model至少保留390秒；距本阶段截止15秒终止，子进程另有 parent-death 与默认 alarm 备份。等待输入审核时没有 GPU worker。CPU三核亲和性、数值库线程上限3；这不声称 OS 总线程数只有3。RSS/全卡显存是采样监控，未冒称连续峰值。

分析实现对应 notes/02：首次官方 prior 的四状态等权 xyz与7维 MAE，分别对完整 mean/median；RMSE明确 pooled 与 mean-state，另报 demo/chunk/7维/方向/夹爪/多样性。sample0/1使用本状态两重复 maxabs公式且1e-3硬上限；4/5只判断单次 pair，不借噪声。方向/夹爪退化否决积极建议；20%收益、3/4且覆盖两demo及双常数门只是最小闭环计划候选。没有明确可修原因的判断不能自动化，暂停建议保留父审研究判断条件。posterior不作必过门，repeat不重复计能力均值。

未发现预算或数学规则之间的具体矛盾。210/至少390秒是事前分配，不是运行耗时实测或成功保证；真实自然时序、缓存接入、strict load、BF16数值和资源峰值仍须正式门后一次性验证。冻结后遇具体问题即停止回报，不用剩余名额修复、补样本或训练。4状态/2demo只描述训练内信号，不能证明泛化、视觉因果依赖或 Lift成功；旧0/32仍 UNKNOWN。

子6-1-sol-max已只读核实仍 PAUSED；本执行者没有更改任何 automation，也没有 Git add/commit/push。旧目录只读，缓存/临时文件都留本目录。公开仅 preparation_allowlist.txt 所列原创代码/小结果，并附 preparation_secret_scan.json。main 的 run_deepseek、原始讨论/CLI与local_only/cache/tmp不纳入此允许清单。

准备完成后按原人类及本目录AGENTS授权向主聊天一次回传，回执见 preparation_return_receipt.json；随后等待真实DeepSeek与Codex对最终协议和代码准确SHA审核，并等新的正式 RUN。这里的 READY 不能启动任何实验。
