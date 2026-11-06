# 实验资产审计（只读，2026-11-06）

**方法**：只读官方仓库网页、README、LICENSE、模型卡、arXiv 正文/abs 页。**未安装、未 clone、未下载权重或数据、未运行任何评估。**
状态定义：
- `VERIFIED`：有直接官方来源支持该字段（不等于本机能跑通）；
- `PARTIAL`：部分字段可核实，关键字段缺失；
- `UNKNOWN`：未找到可核实来源；
- `HIGH_RISK`：已有证据表明复现成本/失败概率高。

## 一、总表

| 资产 | 代码 | 权重 | 数据 | 评估入口 | 许可证 | 公开成功率 | 已知问题 | 状态 |
|---|---|---|---|---|---|---|---|---|
| LIBERO | 是 | 无（训练基线需自训） | 下载脚本；CC BY 4.0 | `libero/lifelong/evaluate.py` | MIT（代码）/ CC BY 4.0（数据） | 论文/榜单 | Python 3.8.13、torch 1.11、MuJoCo EGL；84 open issues | **VERIFIED / 环境 HIGH_RISK** |
| ManiSkill3 | 是 | 基线需自训/另行获取 | 数据采集工具 | 官方脚本 | Apache-2.0（代码）/ CC BY-NC 4.0（资产） | 任务基准 | 资产非商用；版本 `mani_skill>=3.0.0` | **VERIFIED / 许可证需注意** |
| ACT | 是 | 无 | `record_sim_episodes.py` | `imitate_episodes.py --eval` | MIT | README：transfer cube ~90%、insertion ~50% | Python 3.8.10、MuJoCo 2.3.7、dm_control 1.0.14 | **VERIFIED** |
| Diffusion Policy | 是（官方 repo） | 无 | 任务数据脚本 | 官方 eval | MIT（上轮核查） | 论文 | 依赖较旧 | **PARTIAL（本轮未重开页面）** |
| SmolVLA / LeRobot | 是 | 0.5B 公开 | 社区数据 | `lerobot-eval` | Apache-2.0 | 模型卡无数字 | 需 HF 下载；网络不稳 | **VERIFIED（上轮）/ 本轮未重核** |
| KYC 仓库 `ripl/CamPoseOpensource` | 是 | **无** | `setup.sh` 下载 | `reproduce/reproduce.py`、`policy_*/train.py` | MIT | Table I | 单 seed 训练 "hours to a day"；跨机器非 bitwise 一致 | **VERIFIED / 权重缺失 HIGH_RISK** |
| LIT `MAGICLAB-NUS/LIT` | 是（4 个宿主 fork） | MolmoAct2 checkpoint（HF） | YAM 双机械臂 292 episodes / 4.8 GB | `scripts/eval_libero_plus.sh`、`eval_libero.sh` | Apache-2.0 | Table II | ImageWAM 需 gated FLUX.2-dev；README 列出静默失败检查 | **VERIFIED（页面级）** |
| LIBERO-RIG | **未定位** | 无 | manifests 声称发布，无 URL | 声称发布 | UNKNOWN | Table 2/3 | 论文与 abs 页均无链接 | **PARTIAL / HIGH_RISK** |
| More Structure | 无 URL | UNKNOWN | 无 | 无 | UNKNOWN | Table I | 单任务；11 GB 显存配置 | **PARTIAL** |
| 2610.01626 | 无 URL | 无 | robomimic/MimicGen/RoboCasa | 无 | UNKNOWN | 中位 λ | 单作者预印本 | **PARTIAL** |
| 2512.02902 (FTM/FLA) | 无 URL | UNKNOWN | LIBERO-V | 无 | UNKNOWN | 48.5/87.2/90.8 | one-shot 需目标域 1 demo/task | **PARTIAL** |
| 2608.03052 | UNKNOWN | UNKNOWN | RoboCasa365 | UNKNOWN | UNKNOWN | 任务族结果 | VLA 级算力 | **UNKNOWN** |
| 2605.19986 MetaFine | UNKNOWN | UNKNOWN | 组合任务图 | UNKNOWN | UNKNOWN | 摘要称二元成功率可高估 70% | 摘要级 | **UNKNOWN** |
| 2610.12457 SpatialHarness | UNKNOWN | 依赖 GPT-6 Astra（闭源） | 4 个真机任务 | UNKNOWN | UNKNOWN | 摘要：26.7→66.7、0→100 | 依赖闭源前沿模型 | **HIGH_RISK（不可复现）** |

## 二、对本机（单卡 RTX 3090 24GB）的现实含义

1. **可跑的**：ACT/DP + ManiSkill3 或 LIBERO，单任务数十万步、单 seed 数小时到一天；小规模多任务（4–8 个）在数周内可行。
2. **不可跑的**：π0.5/MolmoAct2/GR00T 级 VLA 的从头训练或大规模微调；2608.03052 的 45 任务受控研究；闭源前沿模型（SpatialHarness 的 GPT-6 Astra）。
3. **最大的资产风险不是算力，而是"协议"**：
   - LIBERO-RIG 的 manifests 找不到；
   - More Structure 的失败分类器没有代码；
   - 2610.01626 的 λ 拟合没有代码；
   - KYC 没有权重。
   这意味着任何依赖"别人的测量协议"的候选，都要把协议复现计入 1–2 周工程成本。
4. **许可证**：ManiSkill 资产是 CC BY-NC 4.0（非商用）；LIBERO 数据 CC BY 4.0；代码多为 MIT/Apache-2.0。论文发表通常无碍，但若将来涉及商业合作需注意。
5. **环境**：LIBERO/ACT 的 Python 3.8 + torch 1.11 与当前系统栈差距大；必须在独立 conda/venv 中安装，不得改系统 Python/CUDA/驱动（工作区规则）。

## 三、逐项结论

- **能形成"官方基线阳性"的最小组合**：ManiSkill3 + ACT（官方两个任务）或 LIBERO + ACT/DP。ACT 仓库自报 transfer cube ~90%、insertion ~50%，是可用于 Gate B 的公开阳性参照。
- **不能依赖的组合**：KYC checkpoint 路线（无权重 + 用户已 0/32）；LIBERO-RIG 协议（无 manifests）；SpatialHarness（闭源模型）。
- **`VERIFIED` 的边界**：仅表示"官方页面支持该字段"，不表示本机可安装、可训练、可复现论文数字。本轮没有做任何安装或运行验证。
