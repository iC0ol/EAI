# Round 4 自检

## 1. 是否选择了唯一主选题

**是。** 唯一主选题：**几何余量感知的动作块提交（CAC）**，平台 robomimic Square + Diffusion Policy（图像）。报告中不存在并列主推；P2/P3 仅作为 pivot，且说明了为什么没选。

- 没有用"所有候选都不合格/继续调研"作为结论。
- 明确标注"待实验确认"；没有声称已被证明有效。
- 没有把 A1/C1 改名：A1 是误差预算测量/敏感度塑造；CAC 是执行 horizon 的承诺决策，干预点、文献、实验不同（见 FINAL_REPORT A 节）。

## 2. 资产与正成功率证据

- **作者报告**：DP 论文 Table 2 Square 图像 avg 0.80–0.92；MetaFine Table B4 ACT/DP3 49–85（coarse）。
- **官方资产存在**：DP repo/config MIT；robomimic 数据；ManiSkill ACT baseline；MetaFine repo。
- **第三方复现**：未核查。
- **本地跑通**：无。
- **官方 checkpoint**：Square-MH image CNN 的 train_2 / epoch=1950 checkpoint 公开存在（约 4 GB）；本地加载/评估尚未验证。
- 报告严格区分作者报告、公开资产存在与本地复现；没有把 checkpoint 存在写成已跑通。
- 修订后不再声称 DP Square 没有 checkpoint；默认 checkpoint-first，只有兼容性失败时才重训。
- 84.8 GB 预渲染图像包明确标注 HIGH_RISK；主路径是 raw demo 69/74 MB + 本地渲染。

## 3. 具体行动失败 vs 泛泛表述

- 失败：Square nut-on-peg 插入失败（作者报告有 8–20% 失败，不等于本地失败率），不是"空间理解不足"。
- 证据：DP Table 2（作者报告成功率）+ 2610.01626（K=24 demonstration/rollout 的 square 任务中位 λ=0.017；拟合窗口敏感，不能推出最优 horizon）+ DP §4.3（horizon 8 任务级折中）。
- 区分了：感知/几何估计、策略使用、动作接口、闭环执行、数据/评测。报告把失败主要归因于"固定 horizon 下的闭环误差/接触"，并明确这是**合理假设**，Gate B 才分解。
- 报告列出了推翻条件（horizon 无效、always-short 最好、clearance 不预测）。

## 4. 强简单基线

报告列出的基线：
- 固定 horizon 8（原配置）、固定 1/2/4/16；
- always-short（1 步闭环）；
- 不确定性（denoising variance/ensemble/attention entropy）；
- 反应式 visual monitor（VLA-Corrector 式）；
- APEX 执行间隙；
- oracle horizon；
- 任务级最优固定 horizon。

没有只挑弱基线。报告明确：**若 always-short 或 entropy 已最好，CAC 不成立**。这是主动设置的反例。

## 5. 最近邻与创新性

- 核查了 2609.00908（attention entropy 自适应截断）、2607.01804（VLA-Corrector）、2608.15938（开环分析）、2607.17454（Gated GeoBoN）、2610.19765（RAIN）、2606.16504（APEX）、2610.01626（λ）。
- 没有把某篇强竞争论文扩大成"整个方向已解决"；报告说"若 entropy/visual monitor 在 Square/DP 上同样有效，CAC 的几何判据无增量"，并把它作为 Gate B/C 的比较。
- 创新性被标为 HYPOTHESIS：几何余量 + 预测误差增长的 commitment 判据；不是"新架构"。
- 没有把"增加模块/换门控/重加权"称为创新；CAC 的贡献是**时序决策判据**，实现轻量。

## 6. 相关 vs 因果

- 报告没有声称"horizon 导致失败"；它说"固定 horizon 是候选机制，Gate B 用配对 horizon 扫描判断"。
- 明确混杂：初始状态、训练 seed、动作随机性、渲染、episode length、选择偏差；Gate B 用同初始状态配对、固定模型、固定噪声、全部 episode、条件在阶段到达。
- 没有把 DP 的成功率差异直接归因于 horizon；horizon 只是被操纵的变量。

## 7. 统计独立性

- 统计单位：episode（同初始状态的 5 个 horizon 配对）；训练 seed 是方差来源；Gate B 1 seed，Gate C 3 seeds。
- 没有用大量 episode 冒充多个任务；主任务 1 个，Gate C 2 个任务。
- 配对设计：同一组 100 个初始状态，5 个 horizon 共用；McNemar/bootstrap。
- 选择偏差：不用成功轨迹估 clearance；用全部 episode，条件在插入前状态。
- 功效：Gate B 的 100 episodes 可检测 ~10–15 pp 配对差异；5 pp 差异可能不足，报告明确"若差异 <5 pp 停止"，避免把不显著当不存在。
- 没有任意阈值伪装成科学定律；8 pp/0.7 AUROC 是**工程决策门槛**，不是自然常数；报告说明了这一点。

## 8. Gate 顺序

- Gate A：本轮完成（资产、失败、竞争、方案）。
- Gate B：设计但**未执行**；`GATE_B_PROTOCOL.md` 冻结。
- Gate C：未设计细节，未执行；只有通过 Gate B 才进入。
- 没有把 Gate B 写成已完成；没有把 Gate C 的方法写成已验证。

## 9. 小论文与毕业论文的不同贡献

- 小论文：CAC 判据/模型 + 2 任务对比 + 消融；方法型；最低证据明确。
- 毕业论文：在线 clearance/误差动力学估计（无特权状态）+ 切换成本 + 多阶段；新问题是部分可观测/模型漂移/切换成本，不是"离线变在线"。
- 明确风险隔离：若小论文判据不成立，毕业论文可转向在线估计的测量问题，但仍依赖同一资产；不靠"再加模块"续命。

## 10. 风险与转向

- 三个风险：always-short 最好；clearance 不预测；平台/基线失败。
- 每个都有可观察信号和处理；保留资产（DP/robomimic/渲染/horizon eval）供 P2/P3 复用。
- 没有承诺"论文一定发表"；没有承诺方法一定有效。

## 11. 权限边界

- 未训练、未推理、未仿真、未安装、未下载模型/大型数据、未实现算法、未派发 Agent。
- 只下载论文 PDF 到 ignored `papers/`；读取 raw.githubusercontent 配置；arXiv/HF API 元信息；本地算术。
- 未修改旧报告、旧实验、系统环境、ROS/CUDA/驱动；未读取私有标签/真值。
- 发布仅限 ROUND4 原创文件；第三方全文/源码不提交。

## 12. 已知限制

1. DP Square 本地基线未跑；0.80–0.92 是作者报告；Square-MH 官方 checkpoint 已存在但尚未本地加载。
2. checkpoint/config 与当前本地依赖、渲染图像分布是否兼容未验证；只有重训时才需要完整本地渲染。
3. DP/robomimic 旧栈在 3090 上能否稳定运行未验证。
4. 2609.00908/VLA-Corrector 仅摘要级；其方法细节可能改变竞争判断。
5. Gated GeoBoN/RAIN 仅摘要级；P2 的竞争判断有限。
6. 没有做引文追踪；"未被直接做"是有界否定。
7. v1 的 8 pp/AUROC 门槛不是统计定律；Gate B v2 将 J2 主检验改为共同状态分支中的 horizon×clearance 交互，AUROC/oracle 仅作次级分析。
8. 若 Gate B 的 100 episodes 不足，报告不会把"不显著"解释为"现象不存在"，而是增加 episodes 或停止并说明功效不足。


## 13. 2026-11-10 修订自检

- 已核对 Diffusion Policy 官方 README 与 Square-MH image/CNN/train_2 checkpoint 目录；公开文件约 4 GB，尚未下载或本地加载。
- 已修正“无 checkpoint”的事实错误；本地成功率仍明确标注为 UNKNOWN。
- 已修正 2610.01626 的 λ 解释：square 0.017 对应 K=24 demonstration/rollout 任务中位数，论文明确 λ 受拟合窗口影响且不直接决定最优 horizon。
- Gate B v2 不再使用简单 r_tol - d_xy 作为 clearance，也不再把单次 rollout winner 当作无噪声 oracle 标签。
- Gate B v2 采用 checkpoint-first、固定 horizon 配对扫描、共同状态分支和 horizon×clearance 交互分析。
- 本次修订没有下载 checkpoint、安装依赖、运行训练/推理/仿真或 benchmark；Gate B 仍未执行。
