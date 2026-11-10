# Round 4 文档修订记录（2026-11-10）

## 范围

本次只修订第四轮 Gate A 交付文档与 Gate B 协议；没有执行实验，也没有修改 main、前三轮目录或研究代码。

## 修订内容

1. **Square-MH checkpoint 更正**
   - 原报告误写“无 checkpoint”。
   - 官方目录列出 image/square_mh/diffusion_policy_cnn/train_2/checkpoints/epoch=1950-test_mean_score=1.000.ckpt，约 4 GB。
   - 默认路径改为先下载/加载官方权重并做本地 smoke test；只有兼容性失败或本地结果异常时才按官方配置重训。
   - 公开 checkpoint 不等于本地已跑通；文件名的 test score 也不是本项目新初始状态上的结果。

2. **误差传播证据更正**
   - square λ=0.017 明确限定为 2610.01626 的 K=24 robomimic open-loop demonstration/rollout 任务中位数。
   - 该论文指出传播前置、拟合窗口敏感；λ 是有限窗口摘要，不决定全局最优 horizon。

3. **clearance 定义更正**
   - 不再使用单一 r_tol - d_xy 作为最终几何量。
   - Gate B v2 要求在 nut 坐标系中，以真实 collision geometry/轮廓计算 peg 相对 nut 内孔的最小有符号间隙；yaw 纳入投影，d_z 单独记录。
   - 若几何不可可靠读取，标记 BLOCKED，不用近似量冒充 clearance。

4. **J2 统计协议更正**
   - 不再用一次 episode 中各 horizon 的单次成败直接生成 oracle label。
   - 改为同一保存状态的 horizon 分支实验，并用 horizon×clearance 交互作为主检验；oracle/AUROC 仅作次级分析。

## 修改文件

- reports/FINAL_REPORT.md
- reports/PRIMARY_TOPIC.md
- reports/GATE_B_PROTOCOL.md
- reports/SELF_AUDIT.md
- reports/COMPLETION.json
- reports/REVISION_LOG.md（本文件）

## 来源

- Diffusion Policy official README: https://github.com/real-stanford/diffusion_policy#-checkout-our-experiment-logs
- Official Square-MH image CNN checkpoint directory: https://diffusion-policy.cs.columbia.edu/data/experiments/image/square_mh/diffusion_policy_cnn/train_2/checkpoints/
- Measuring the Stability Assumption Behind Action Chunking — author page: https://aryangoyal7.github.io/publication/2026-stability-action-chunking
- arXiv:2610.01626: https://arxiv.org/abs/2610.01626

## 实验状态

- checkpoint downloaded: **no**
- dependencies installed: **no**
- training / inference / simulation / benchmark: **not run**
- Gate B v2: **ready for local execution after environment/checkpoint smoke test**


5. **DP 论文评估样本数补充**
   - 论文评估方法的通用描述为 3 个训练 seed、名义 50 个环境初始条件。
   - 脚注明确指出 robomimic 任务因评估代码 bug 实际只使用 22 个环境初始条件。
   - 报告与自检已避免把 Square 结果写成 3 seeds × 50 个独立初始条件；Gate B 使用独立 100 个初始状态。
   - 来源：https://journals.sagepub.com/doi/10.1177/02783649241273668
