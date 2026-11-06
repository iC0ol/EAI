# 检索与访问日志（本次复审）

所有日期为 2026-11-06（Asia/Shanghai）。检索截止日：2026-11-06。
工具：arXiv Atom API、arXiv abs 页面、GitHub 网页（REST API 403 限流）、本地已下载的公开 arXiv 文本。
**未**使用 Semantic Scholar / Google Scholar（本轮不需要重复上轮的引文追踪；见限制）。

## A. 旧材料访问

| # | 入口 | 结果 | 限制 |
|---|---|---|---|
| A1 | `git show codex/spatial-action-survey-20261105:research_spatial_action_20261105/reports/EXECUTIVE_SUMMARY.md` | 成功，全文 | 旧报告结论视为待核查证据 |
| A2 | 同上 `reports/FINAL_REPORT.md` | 成功，688 行全文 | 同上 |
| A3 | 同上 `reports/SELF_AUDIT.md` | 成功，268 行 | 同上 |
| A4 | 同上 `notes/nearest_neighbor_review.md` | 成功，139 行 | 同上 |
| A5 | 同上 `sources/papers.jsonl`、`notes/full_text/` | 按需抽查，未全量重读 101 篇 | 旧登记数字只作线索，不作本报告事实 |

## B. 检索查询（arXiv API，`export.arxiv.org/api/query`）

| 轮 | 查询（摘要） | 命中数 | 用途/结果 |
|---|---|---|---|
| R1-1 | spatial + manipulation + failure + precision | 18 | 发现 2610.12457 SpatialHarness、2605.19986 MetaFine |
| R1-2 | action chunk + error + closed-loop | 18 | 发现 2608.15938、2607.01804、2610.19765（纠正类工作密集） |
| R1-3 | calibration + manipulation policy + action | 13 | 未发现直接做"任务容差"的论文 |
| R1-4 | depth + manipulation + representation + when | 4+ | 发现 2608.27497 MAGP（度量尺度） |
| R1-5 | spatial reasoning + robot + action + failure | — | 多为 VLM 基准，非策略层 |
| R1-6 | error accumulation + robot + policy | — | 无直接命中 |
| R2-1 | tolerance + manipulation + policy + spatial | 5 | 无"任务几何容差"论文；进一步确认 LIBERO-RIG 的 tolerance 是 rig 轴 |
| R2-2 | 3D + 2D + manipulation + "when does" | 0 | — |
| R2-3 | spatial representation + action + benefit | 9 | 无收益预测研究 |
| R2-4 | failure mode + intervention + robot | 14 | 发现 2609.39145 Blackout vs Freeze、2609.33707 View Collapse |
| R2-5 | spatial uncertainty + action + observe | 3 | 主动观察已密集 |
| R2-6 | cross-view + manipulation + policy | 22 | 视角鲁棒性仍高密度（22 条） |
| R3 | constraint violation / unintended contact / safety filter / spatial constraint / reachability | 19/9/2/14/5 | 安全约束方向已高度饱和（SafeStage、ShieldVLA、ActSafeGuard、SafeVLA 等） |
| R4 | occlusion / object permanence / self-occlusion / temporal object-centric / memory+occlusion | 20/14/20/14/12 | 遮挡记忆方向已高度饱和（SCOUT、OccluDex、Ledger、StateMem、MEM 等） |
| R5 | value of information / information gain / active perception / sensor placement / spatial resolution | 1/8/16/10/20 | VoI 在操作中几乎空白，但主动感知系统层已饱和 |
| R6 | foveated / adaptive resolution / observability / Cramer-Rao / precision+grasp | 7/9/20/3/5 | 发现 FoveaVLA、ART-VS；"看哪里/看多清"也已被占 |
| R7 | system identification / step response / perturbation recovery / spatial servoing / goal perturbation | 5/0/4/0/1 | **"策略的空间阶跃响应"无直接命中**（仅检索证据，不等于空白） |
| R8 | which tasks benefit / spatial information when / intervention predict / heterogeneous ablation | 2/9/19/9/0 | 最接近的是 2608.03052（本体感觉版受控研究）；无"空间收益机制判别"直接工作 |
| R9 | base placement / where to stand / mobile manipulation reachability | 15/7/11 | 基座放置已成熟（reachability map、B*、MoMa-Pos 等） |

原始输出：`logs/arxiv_search_round1.txt` … `round9.txt`（本地，未提交）。

## C. 论文访问与阅读层级

本地全文来自上轮公开下载的 arXiv 文本（`research_spatial_action_20261105/papers/`），本轮复制到本目录 `papers/`（gitignored）。逐篇层级见 `sources/papers.jsonl`。

- **全文/关键章节实读**：2607.09825、2610.18843、2609.12641、2510.02268、2610.01626、2609.27247、2512.02902、2606.02277、2610.29646、2608.03052、2605.18746、2609.37292、2602.12032、2602.23408、2609.28955、2609.16815、2609.06114。
- **仅摘要**：2610.12457、2609.39145、2609.33707、2605.19986、2608.15938、2607.01804、2610.19765、2608.27497、2610.13516、2611.05058。报告中对这些只作"存在性/竞争密度"判断，不引用其具体机制或数值作为强主张（个别数字会标注"摘要级"）。

## D. 资产访问

| 入口 | 结果 | 限制 |
|---|---|---|
| github.com/MAGICLAB-NUS/LIT | 200；Apache-2.0；一个 checkpoint（MolmoAct2）+ YAM 数据；eval 脚本 | 未 clone、未下载权重 |
| github.com/ripl/CamPoseOpensource（KYC） | 200；MIT；无预训练权重；setup.sh 下载数据 | 未安装/训练 |
| github.com/Lifelong-Robot-Learning/LIBERO | 200；MIT / 数据 CC BY 4.0；84 open issues；Python 3.8.13 + torch 1.11 | 未安装 |
| github.com/haosulab/ManiSkill | 200；代码 Apache-2.0 / 资产 CC BY-NC 4.0 | 未安装 |
| github.com/tonyzhaozh/act | 200；MIT；两个仿真任务 | 未安装 |
| arxiv.org/abs/2610.18843（LIBERO-RIG） | 200；无代码/数据链接，正文称发布 manifests | 未能定位 manifests → PARTIAL |
| api.github.com | 403 限流 | 改用网页 |

## E. 未做 / 不能声称

- 未做引文追踪（S2/Scholar）；因此"未发现"仅指本轮 9 组查询与已读论文的参考文献范围。
- 未读 2026 年全部相关论文；42 篇摘要级旧登记未补全文。
- 未验证任何论文的会议终稿与 arXiv 版本差异。
- 未运行代码、未下载模型/数据、未做仿真。
