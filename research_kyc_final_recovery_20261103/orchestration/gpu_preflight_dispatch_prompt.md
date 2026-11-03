正式派发 RUN_PHASE=gpu-preflight，一次且仅一次。用户已授权的最后有限恢复范围为 /home/asus/EAI/research_kyc_final_recovery_20261103，recovery_id=kyc-last-recovery-441e91b0-ee5f-4294-9501-070606a5f695。你使用 gpt-6.1-sol / max 执行。

Codex独立notes/03、交叉notes/04与真实DeepSeek32b独立、33交叉均批准 GPU_PREFLIGHT_ONLY，工程门engineering_gate.json和dispatch/gpu-preflight.json已写入。准确protocol SHA 3fd12394fd845a4c2df528119655af65ab1a830b55833f5aa278c0c8c004c460，manifest SHA bd4233fbeca8898d0145c3411ae98901897fd24b974984c3b83195cea75843ed。请核对新增门/派发/短交叉意见及实际进程，无需再次全文复读旧研究或重复CPU测试。

仅运行冻结入口：既有reproduction/env/bin/python -B run.py supervise gpu-preflight（以cli.py的实际参数接口为准，cwd新目录）。同一worker顺序input_setup→close_input→model_setup strict-load→close_model，最多180 GPU分配秒，所有启动/失败/清理入总1800秒；0ACT/render/readPixels/env.step/rollout/训练。单阶段唯一attempt，不重启；两修复用完，任何实质错误即停封存，不修改候选或增加第二次预检。单GPU顺序、3核/RSS16G/整设备VRAM12G/目录150MiB，保留原独立supervisor/提前终止。当前另有小额外部GPU占用曾被观察，请只记录、不能触碰外部进程；资源不符合门就停止。

科学Stage1/2未批准，science_clock不能创建。保存真实PID/start_ticks、命令/退出/分配秒/计数、原始日志、构造/strictload/清理证据、SHA完整性。即使gpu_preflight_result缺失或actual_GPU_path=false也不能称零GPU，用独立supervisor和原日志判定。若监督记账受退出竞态影响，先只读核实并保守报告，不重跑/修复。主审独占Git，你不add/commit/push。

运行结束或失败立即按用户授权异步回传本主线程01a18138-0f15-76b2-b5cf-20e1722782a9，附原始证据路径、准确计数、过程实际已到哪一步，不自动下一阶段。等待无GPU。不扩大审查循环或另建automation；现有子检查6-1-sol-max由本次派发更新。
