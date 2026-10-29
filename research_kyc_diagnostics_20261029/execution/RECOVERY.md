# 本轮已受控提前停止

先读 FINAL_REPORT.md、completion.json、status.json、stage1_gate.json、counts.json，再核对supervisor_identity.json和active_child.json的PID/start_ticks。相同PID可能已被复用，不能据此重启或误杀。

Stage1A当前RGB渲染前提失败，32固定前向、B、C均未启动；剩余额度不是自动续跑授权。本轮任务已停止，等待主研究团队验收。旧research_expansion只读，不安装环境、不改驱动、不重训。

已执行的长进程入口是本目录 scripts/supervise.py --stage stage0 和 --stage stage1，由现成 reproduction/env/bin/python -B 运行；都使用独立SID，并已退出。stages/内保留精确命令与exit0。0表示遵循停止门结束，不表示全部诊断完成。

无新观测地复核：

```bash
PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=3 OPENBLAS_NUM_THREADS=3 MKL_NUM_THREADS=3 /home/asus/EAI/research_expansion_20261029/reproduction/env/bin/python -B /home/asus/EAI/research_kyc_diagnostics_20261029/execution/scripts/analyze_render.py
PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=3 OPENBLAS_NUM_THREADS=3 MKL_NUM_THREADS=3 /home/asus/EAI/research_expansion_20261029/reproduction/env/bin/python -B /home/asus/EAI/research_kyc_diagnostics_20261029/execution/scripts/verify_delivery.py
```

这些CPU脚本会刷新对应报告时间戳，优先查已交付文件。完整XML/RNG、机器raw命令和CLI保留在忽略的local_only/logs；公开NPZ含逐张量原件和hash，能够核对图像异常。修复没有执行，不能把下一步建议当成授权。
