# EAI 工作区

- 沿用 `/home/asus/EAI` 的现有检出，不另建工作区或 worktree。实验和 Python 环境只放在此工作区内。保持 `inspection_robot*`、ROS 2、系统 Python、NVIDIA 驱动、系统 CUDA 和工作区外的环境原状。
- Square-MH 图像 Diffusion Policy 的 B0、B1 Pilot/Full、B2 Discovery/Confirmation 和 continuation-h4 已完成。保留 Gate B 的代码、配置、环境、资产、运行目录、快照、哈希、报告与源码包。子目录的历史执行授权仅对应各自已完成的阶段。 [Gate B AGENTS.md](gate_b_v2/AGENTS.md) · [Gate B 协议](research_spatial_action_round4_20261109/reports/GATE_B_PROTOCOL.md) · [B2 v1.1 冻结协议](research_spatial_action_round4_20261109/reports/B2_PROTOCOL_REVISION_20261116.md)
- Gate C 尚未授权。后来单独获准的 Square-MH 分量先导和 PACE / RoboTwin 双任务实验均已结题。新实验、仿真、推理、训练和数据扩展须研究者另行授权。[当前交接](当前阶段的交接文档.md)
- 前次工作区整理已同步到 `codex/b2-continuation-h4-20261119` 和 `main`。研究者本次授权将最近的实验结果与交接发布到公开的 `iC0ol/EAI`，使用当前研究分支 `codex/pace-robotwin-paired-20261125` 并普通快进 `main`。按明确路径暂存和审核，保留其他分支和提交历史。
- 公开提交限于获准发布的源代码、文档、配置和结果。Python 运行时、虚拟环境、权重、数据集、二进制快照、缓存和凭据留在 Git 之外。
