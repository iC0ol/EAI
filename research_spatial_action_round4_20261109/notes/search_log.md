# Round 4 检索与访问日志

- 日期：2026-11-09（Asia/Shanghai）。检索截止：2026-11-09。
- 原则：不做开放式泛检索；只补决策缺口（资产、正基线、最近邻、horizon 证据）。
- 本轮未运行任何训练/推理/仿真；下载仅限论文 PDF 与官方元信息。

## A. 差量核查（在已有三轮材料之上）

| # | 入口 | 结果 | 对本轮决策的作用 |
|---|---|---|---|
| A1 | arXiv 2303.04137 Diffusion Policy 全文（`papers/dp.txt`） | Table 2 视觉策略：Square ph DP-C 0.98/0.92、DP-T 1.00/0.90；Square mh DP-C 0.98/0.84、DP-T 0.94/0.80（max/avg last-10，3 seeds × 50 initial conditions） | 证明 Square 图像 DP 有**作者报告的正成功率**（avg 0.80–0.92） |
| A2 | 同上 §4.3 / Fig.5 | "action horizon 8 optimal for most tasks"；too long reduces reaction，too short loses consistency | 证明 horizon 是已知权衡，但只做了**任务级**固定选择 |
| A3 | 同上 §5 训练细节 | 图像任务 3000 epochs；84×84；batch 64 | Gate B 训练预算 |
| A4 | `raw.githubusercontent.com/real-stanford/diffusion_policy/main/diffusion_policy/config/task/square_image.yaml` | 200；obs 2×84×84 + eef/gripper；action 7；dataset `square/{ph,mh}/image.hdf5`；n_test 50；n_envs 28 | 资产接口与评估入口 |
| A5 | 同上 `train_diffusion_unet_image_workspace.yaml` | horizon 16；n_action_steps 8；batch 64；num_epochs 8000（论文实际 3000） | horizon 可改；Gate B 用 3000 |
| A6 | robomimic 数据集文档 | Square PH 200 trajectories、MH 300；raw/low_dim 下载链接 | 数据规模 |
| A7 | HF raw Square 文件头 | ph 68,982,198 bytes（~69 MB）；mh 73,913,499 bytes（~74 MB） | 可下载；本地渲染图像可行 |
| A8 | `diffusion-policy.cs.columbia.edu/data/training/robomimic_image.zip` | content-length 84,754,919,326（~84.8 GB） | 预渲染图像包过大；改用 raw demo 本地渲染 |
| A9 | 同上 `robomimic_lowdim.zip` | 1,930,261,710 bytes（~1.93 GB） | 低维 fallback |
| A10 | `raw.githubusercontent.com/haosulab/ManiSkill/main/examples/baselines/act/README.md` | 200；ACT baseline；PickCube-v1；100 motion-planning demos；30k iters；pd_ee_delta_pos | 备选平台；正基线数字未在 README 给出（PARTIAL） |
| A11 | ManiSkill3 论文 2410.00425 | BC/DP/ACT/PerACT baselines；PickCube RGB；无精确表格数字 | 备选平台的官方支持证据 |
| A12 | MetaFine 论文 Table B4（上一轮已读） | ACT 49/63/63、DP3 75/85/63（Grasp/Toggle/Press）；Peg/Plug/Stack 0% | 仅作 coarse fallback；精度任务无正基线 |
| A13 | arXiv 2609.00908 摘要 | attention entropy plateau → training-free truncation；π0.5/X-VLA；RoboTwin/LIBERO/真机 | 最近邻：自适应 horizon 已被做，但信号是 attention entropy，不是几何 |
| A14 | arXiv 2608.15938 摘要 | 长开环主要帮助非马尔可夫演示；上下文足够长时闭环最好 | 最近邻：horizon 的机制分析；无几何余量 |
| A15 | arXiv 2607.01804 摘要 | VLA-Corrector：latent visual monitor + 截断/重规划 | 最近邻：反应式检测，不是预测式几何 |
| A16 | arXiv 2607.17454 摘要 | Gated GeoBoN：Best-of-N 用 cross-view depth reprojection consistency 选择；N=8 提升 66.3→68.4 / 80.8→82.5 | P2（选择）强竞争 |
| A17 | arXiv 2610.19765 摘要 | RAIN：预测 action error 决定 refine 程度 | 最近邻：refine 而非 horizon |
| A18 | arXiv 2606.16504 摘要 | APEX：执行间隙适配；tracking error −41.2%；success +4.8–25.8 pp | 强简单基线/替代 |
| A19 | arXiv 2602.17659 摘要 | CAG：双分支反事实选择 | P2 竞争 |
| A20 | 上一轮 2610.01626 | robomimic λ：can 0.009 / lift 0.015 / square 0.017 / tool hang 0.026；78% lift deadband；闭环稳定罕见 | 失败机制证据：Square 有误差放大状态 |

原始查询/输出：`logs/`（若有）；本轮主要为直接 URL 读取，无大规模 arXiv 查询。

## B. 访问限制

- GitHub API 403 限流；仓库文件用 raw.githubusercontent.com 读取。
- 未下载 84.8 GB 图像包；仅确认大小。
- 未下载 raw Square demo（69/74 MB）；Gate B 时下载。
- 未安装 robomimic/DP；未训练；未渲染。
- ManiSkill ACT 的精确正成功率未在 README/论文正文找到（PARTIAL）。
- MetaFine 精度任务 ACT/DP3 为 0%（Table B4），不作为主平台。

## C. 停止检索的条件

已掌握足以排序的证据：主平台（Square+DP）有作者报告的正基线、明确的精度任务、可改 horizon 的配置、可计算的 clearance；最近邻（2609.00908/VLA-Corrector/Gated GeoBoN/RAIN/APEX）已核对。除 Gate B 才能回答的基线/现象问题外，不再扩大检索。
