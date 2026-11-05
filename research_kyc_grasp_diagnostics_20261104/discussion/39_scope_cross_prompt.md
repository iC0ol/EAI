接续38，读取本轮notes/01_Codex独立源码与因果审查.md和notes/02_初始交叉审查.md（目录/home/asus/EAI/research_kyc_grasp_diagnostics_20261104），做针对性真实交叉。没有代码GPU批准请求。

你的38“env.reset不重建MjRenderContext”可能错误。请重新直接查看 /home/asus/EAI/research_expansion_20261029/reproduction/vendor/robosuite/robosuite/environments/base.py:83/104/239-251/261-284/319-340 与具体HDF5配置的审计 artifacts/parent_initial_source_data_audit.json。默认hard_reset=True且非deterministic_reset调用_load_model/_initialize_sim，后续新sim无context时创建MjRenderContextOffscreen。需要承认默认hard reset会重建，而不能从reset docstring“Resets simulation”推定不重建。它仍不保证解决旧故障，保留current FBO检查不足/几何变化混淆。

确认A4+B8（各<=150步），A共享本轮reset_root，zero policy inference beforeAvalid，C两臂真实getItem->crop->collate tensor证据；不让旧MAE门限制新闭环。报告旧dev1000存留初始图主审肉眼正常，仅后续诊断坏图已知，所以要严格限定历史因果。明确同意或质疑notes/01、02关键边界，哪些必需代码条件交给执行者；不重复整篇源码审查、不泛化论文60.6%到本轮四root。仍等待集成候选与精确SHA双审，不能提前APPROVE RUN。
