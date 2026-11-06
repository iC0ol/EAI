# Round 3 检索与访问日志

日期：2026-11-06（Asia/Shanghai）。检索截止：2026-11-06。
本轮不做开放式泛检索；只查与 A1 直接相关的定义、竞争、代码。

## A. 论文/代码访问

| # | 入口 | 结果 | 限制 |
|---|---|---|---|
| A1 | `https://arxiv.org/pdf/2605.19986` | 200；42 页 PDF；`pdftotext -layout` 成功（2,634 行） | 未读全部附录页 |
| A2 | `git clone --depth 1 https://github.com/Hiangx-robotics/MetaFine.git` | 成功；commit `9d23841684295abc3a4163c6a5918e2590555ffa`（2026-10-01）；MIT；7,139 tracked files；170 MB | 未安装、未运行 |
| A3 | `https://huggingface.co/api/datasets/hiangx/MetaFine` | 200；公开、非 gated；assets/task specs | 未下载数据 |
| A4 | `https://huggingface.co/api/datasets/hiangx/MetaFine_CoRL26` | 200；公开；π0 baseline demos（T1–T5） | 未下载 |
| A5 | `https://arxiv.org/pdf/2609.03142`（EGR） | 200；961 行 | 只读摘要/方法/实验关键段 |
| A6 | `https://arxiv.org/pdf/2606.16504`（APEX） | 200；1,164 行 | 同上 |
| A7 | `https://arxiv.org/pdf/2607.11167`（Pix2Act） | 200；1,083 行 | 同上 |
| A8 | `https://arxiv.org/pdf/2610.02898`（MixVLA） | 200；1,304 行 | 同上 |
| A9 | `https://arxiv.org/pdf/2609.33707`（View Collapse） | 200；1,501 行 | 同上 |
| A10 | `https://arxiv.org/pdf/2609.39145`（Blackout vs Freeze） | 200；2,367 行 | 同上 |

## B. arXiv API 查询（本轮）

| 查询 | 命中 | 用途 |
|---|---|---|
| equivariance + imitation learning + manipulation | 16 | 发现 Pix2Act、EquiBot 等；等变增广已成熟 |
| task-relevant + invariance + robot + policy | 9 | 发现 EGR、MixVLA（关键竞争） |
| sensitivity + precision + visuomotor + policy | 5 | 发现 APEX（执行间隙） |
| margin + manipulation + policy + spatial | 13 | 无"margin×gain→收益"直接工作 |
| data augmentation + precision + manipulation + policy | 8 | 增广/精度关系有零散工作，无 A1 同构 |

原始输出：`logs/arxiv_search_r3.txt`（本地，未提交）。

## C. 代码核查路径（MetaFine）

| 文件 | 行号 | 核查内容 |
|---|---|---|
| `README.md` | 36–49 | 三维诊断、19 envs、21 skills、40+ assets、7 backbones |
| `README.md` | 117–123 | Python 3.10/3.11、≥8 GB VRAM、~3 GB code+assets |
| `README.md` | 155–160 | assets/configs 另发数据集 |
| `README.md` | 179–214 | record→merge→replay→convert→train→evaluate；"no universal --task-graph eval adapter" |
| `README.md` | 254–257 | roadmap：AI planner、PPI leaderboard、多模态（未实现） |
| `core/env_mixins.py` | 47–84 | eval_randomize_camera / pos / rot；`np.random.uniform`，未显式播种 |
| `core/env_mixins.py` | 86–107 | ambient light randomization |
| `utils/eval_sweep.py` | 33–35 | LIGHT/CAMERA_POS/CAMERA_ROT levels |
| `utils/eval_sweep.py` | 64–90 | 轴→env kwargs；无 object/target pose 扰动 |
| `utils/eval_metrics.py` | 85–105 | EpisodeResult：success、stage_flags（bool）、smoothness |
| `utils/eval_metrics.py` | 121–146 | EvalSummary：success_rate、stage_rates、AUSC |
| `utils/eval_setup.py` | 93–126 | task-graph 模式：goal_predicate + stage_predicates |
| `utils/task_graph.py` | 50–66 | stages = [{name, success}]；独立谓词 |
| `core/predicates.py` | 93–115 | `pose_near`：绝对坐标 + tolerance |
| `core/predicates.py` | 118–124 | `placed_in`/`stacked_on` 为 TODO（永远 False） |
| `core/env.py` | 2025–2075 | MultiSkillEnv：单物体；stage_predicates 独立布尔 |
| `core/env.py` | 2130–2200 | evaluate()：stage flags + goal_predicate |
| `core/env.py` | 640–658 | PegInHole：`peg_head_pos_at_hole` 连续读出 |
| `core/env.py` | 3466–3525 | PutBlocks：`stage_id` 状态机 |
| `core/env.py` | 3684–3705 | AssemblingKits：pos_eps=2e-2、rot_eps=4°、height_eps=3e-3；`pos_diff_norm` |
| `core/policies/pi05/evaluate.py` | 204–249 | `--task-graph` 支持 |
| `core/policies/pi05/evaluate.py` | 780–812 | episode_seeds 预计算、跨 profile 复用（配对）；env 每 episode 重建 |
| `core/skill.py` | 165–190 | grasp 成功用 Qwen-VL API（`utils/evaluator.py`） |
| `utils/evaluator.py` | 24–35 | 需要 `DASHSCOPE_API_KEY`；单帧 VLM 判定 |
| `core/policies/pi05/README.md` | 1–60 | 需要用户提供 `--policy-path` checkpoint |
| `find` | — | 仓库内无 `.pt/.pth/.safetensors/.ckpt` |

## D. 未做 / 不能声称

- 未运行 MetaFine 的任何 env/eval/train；"能跑"与"已跑通"严格区分。
- 未下载 HF 数据集（assets 431 objects 等）；仓库内只有 40 个 capabilities。
- 未获取任何策略 checkpoint；论文的 7 策略结果不可直接复现。
- 未做引文追踪；"未发现同构"仅限本轮 5 组查询与已读论文。
- 未读论文全部附录；已读与代码/实验/阶段指标相关的部分。
