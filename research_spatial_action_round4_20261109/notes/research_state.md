# Round 4 研究状态

- 日期：2026-11-09（Asia/Shanghai）。
- 会话：同一 DeepSeek 会话，接续前三轮；上一轮报告作为只读历史证据。
- 目录：`/home/asus/EAI/research_spatial_action_round4_20261109/`（ROUND4）。
- 分支：`codex/spatial-action-round4-20261109`。
- 本轮只有 Gate A：文献/代码/资产只读、理论/统计、方案设计、原创报告。**未训练、未推理、未仿真、未安装、未下载模型/大型数据、未实现算法。**
- 实际执行：下载论文 PDF（DP、ManiSkill3、LIBERO 等）到 ignored `papers/`；读取 raw.githubusercontent 配置；arXiv/HF API 元信息；本地算术。

## 本轮决策

**唯一主选题（待实验确认）：几何余量感知的动作块提交（Clearance-Aware Commitment, CAC）。**

- 平台：RoboMimic Square（图像 DP，mh 优先；ph 备选）。
- 方法：用任务空间几何余量 + 预测误差增长决定执行多少个 chunk 步骤；在紧余量时缩短/重规划，在松余量时保持开环。
- 第一项 Gate B：固定 horizon 扫描（1/2/4/8/16）+ oracle horizon/clearance 相关性；不训练方法。
- 备选：ToolHang（第二任务）；ManiSkill3 PickCube+ACT（平台 fallback）；低维 DP Square（数据 fallback）。

## 为什么选它（相对 P2/P3）

- P1（commitment horizon）：第一项实验最便宜（只改 eval 的 n_action_steps），现象可观察，正基线有作者报告，3090 可行。
- P2（clearance-aware selection）：需要采样 K + 预测器；Gated GeoBoN/RAIN 强竞争。
- P3（clearance auxiliary）：需要重训多个变体；归因难；auxiliary 任务拥挤。
- P1 的最近邻是 2609.00908（attention entropy）与 VLA-Corrector（reactive visual deviation）；差异是**几何余量 + 预测式**。这是 HYPOTHESIS，Gate B 裁决。

## 已裁决

- 不把 A1/C1 改名：A1 是误差预算测量；本选题是**执行 horizon 决策**，干预点是“何时停止开环”，不是敏感度/表征。
- 不把论文成功率当本地复现：Square DP 0.80–0.92 是作者报告；本地未跑。
- 不把 84.8 GB 图像包作为唯一数据路径：raw demo 69/74 MB，可本地渲染。
- 不选 MetaFine 精度任务：ACT/DP3 0%，无正基线。
- 不选 ManiSkill 作为主平台：ACT 正基线数字未在官方 README/正文给出（PARTIAL）；作为 fallback。

## 未验证（Gate B 才能回答）

1. 本地 DP Square 图像基线能否达到 ≥0.70（作者报告 0.80–0.92）。
2. 固定 horizon 是否在 Square 上产生 ≥8 pp 的差异。
3. 局部 clearance 是否预测 oracle horizon（AUROC ≥0.7）。
4. always-short 是否已经最好（若是，CAC 的 success 增益消失）。
5. DP/robomimic 旧环境能否在 3090 上稳定安装/训练。
6. 本地渲染的图像质量/分布是否与 DP 论文一致。

## 有限下一步

- Gate B（需单独授权）：见 `reports/GATE_B_PROTOCOL.md`。
- 若 Gate B 通过：Gate C 训练 task-space error dynamics model + CAC 规则；2 任务、3 seeds、100 episodes、equal compute。
- 若 Gate B 失败：按 `reports/FINAL_REPORT.md` §G 的 pivot 表转向 P2/P3 或 ManiSkill 平台；不重新做大规模文献调研。
