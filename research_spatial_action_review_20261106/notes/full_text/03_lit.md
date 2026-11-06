# 2609.12641 Breaking the Vision-Action Shortcut (LIT)

- 作者：Jianman Lin 等 4 人
- 版本/日期：arXiv v1，2026-09-11
- 来源：<https://arxiv.org/abs/2609.12641>；本地全文 `papers/2609.12641__breaking_vision_action_shortcut.txt`；仓库 <https://github.com/MAGICLAB-NUS/LIT>
- 读取层级：**全文**（Table I/II、§IV-B/C/D、真实机器人段、Fig. 5 描述）

## 内容

- 把视觉条件从动作生成器中移除，只通过"位姿监督的潜在 token"传递视觉信息；在 π0.5、MolmoAct2、FAST-WAM、ImageWAM 四个架构上评估。
- Table II（LIBERO-Plus，7 种扰动 × 4 架构）关键单元：
  - Camera Viewpoints：π0.5 58.29→80.30 (+22.01)；MolmoAct2 39.40→48.41 (+9.01)；FAST-WAM 16.40→43.83 (+27.43)；ImageWAM 82.16→84.55 (+2.39)。
  - Sensor Noise：79.89→91.94；49.03→70.77；37.70→56.89；96.54→97.57。
  - Language Instructions：52.15→71.50；75.69→73.58；68.90→69.55；90.97→90.05（两处负增益）。
  - 28 个单元中 26 个改善，最大下降 2.11 pp。
- 真实机器人：Lighting OOD 53.3→70.0；Camera OOD 30.0→46.7；Distractors OOD 50.0→63.3（+16.7/+16.7/+13.3）。

## 我的再分析（仅算术，不是实验）

对 Table II 全部 28 个（baseline, Δ）单元拟合 headroom 零模型 Δ = α(1 − b/100)（过原点最小二乘）：
- α = 0.249，R² = 0.488；corr(b, Δ) = −0.70。
- 相机列 4 个单元并非单调：baseline 39.40 的增益 (+9.01) 小于 baseline 58.29 的增益 (+22.01)。
- 分架构 corr：π0.5 −0.60，MolmoAct2 −0.67，FAST-WAM −0.84，ImageWAM −0.90。

结论：headroom 在同一论文的 28 个单元里解释约一半方差，是必须控制的强混杂；但**不是**"大部分方差"，且相机列 4 点不构成单调证据。上轮把它称为"最严重风险/可能已解释大部分方差"是过度概括。

## 限制

- 单一 benchmark（LIBERO-Plus）；真实机器人每任务 25 ID + 10 OOD rollouts（作者在 §IV-D 给出），统计强度有限。
- "通用接口修复"在真实机器人上三轴近似等幅改善，但这与 LIBERO-Plus 上轴间差异很大并存——说明"定向 vs 通用"依赖基准与度量。
- 仓库：Apache-2.0；只显式链接 MolmoAct2 的 checkpoint；YAM 双机械臂数据 292 episodes / 4.8 GB；ImageWAM 需 gated FLUX.2-dev；README 自述有 "latent interface not used" 的静默失败检查。

## 可用事实

- SUPPORTED：LIT 在 28 个架构×扰动单元中 26 个改善；真实机器人三轴 +13.3…+16.7 pp。
- SUPPORTED（我的算术）：headroom 零模型在该表上 R²≈0.49。
- CONTRADICTED（对上轮措辞）："收益几乎随 (1−baseline) 排序"——相机列不单调，且只有 4 点。
