# 最终科学过门核验（v2）

## 结论

**APPROVE。**

v2 已落实 11 的六项要求，且未扩大研究范围。批准范围仅限：**冻结 Stage0 只读排查，以及满足门控后的 Stage1A/B（32 次固定前向）与 Stage1C（16 条×150 步、≤80 query）；总 GPU ≤1 GPUh、优化器更新 0、无正式 test、无新完整训练。** 未来工作均不是已执行结果。

## 两项争议

1. **重复前向**：v2 §5A 第74行已改为 8 官方 prior + 8 自定义 prior + 样本0/1官方重复2 + 样本2/3自定义重复2 + 8 posterior + 4 第二 seed =32；`rmax_official`/`rmax_custom` 分开、取 max；只称“经验容差内一致”，不称所有差异都是噪声。这个处理正确，接受。两次重复仍不足以覆盖所有非确定性，v2 已诚实标注；不要求扩大预算。

2. **posterior 是否必须优于 prior**：v2 §5B 第88行已撤销该门槛；第90–107行只把 `posterior_gap` 作为**预登记的停止预算规则**，不是 C 的控制策略。这个逻辑成立。健康 prior 可以接近 posterior；小 KL 不单独证明 latent 问题。

## 对“posterior 不参与 C 选择”措辞的实质回答

**满足科学意图，前提是把“C 选择”限定为选择 C 的 root、camera、seed、checkpoint、权重或修复方案。** v2 已写明 posterior 不选这些、不做闭环控制器；`posterior_gap` 只决定“是否还值得花剩余预算进入 C”，是**预算门**，不是 C 的条件选择器。v2 §5B 第107行还要求“不能临时改变规则”，§6 的 roots/cameras 已冻结。因此两句话不矛盾：posterior 不参与 C 的**设计/执行选择**，只参与**是否启动 C 的预登记停止规则**。

建议加一句非阻塞性说明以便审计：**“posterior_gap 只决定 C 是否启动；一旦启动，§6 的 8 roots/相机/顺序不再受 posterior 结果影响。”** 这不是必须修改，不影响批准。

## 六项核对

1. §5A 第74行：32 次分配自洽，失败/调试均计，batch=1；接受。
2. §5B 第84行：主常数改为训练采样加权的 per-position median（30×7），权重 `1/(200 L_d)`，padding 排除，raw 与 prior 同 `action_std`；另报 mean、单向量常数与 zero。这个基线比 v1 公平，接受。
3. §5A 第76行：posterior 用官方 Dataset(id)+官方 ACT 路径，一次 hook 捕获 a_hat/mu/logvar/is_pad_hat；不闭环、不选 root/camera/seed/checkpoint/修复；接受。
4. §5A 第66行：固定 t/camera 仅用 wrapper/subclass/窄上下文，保存并恢复 RNG，不改 vendor；接受。
5. §5B 第90–107行：停止伪代码明确有效元素、种子先平均误差、有效 xyz 汇总、6/8、raw 方差、近零分母；停后 D 不是 C；接受。
6. §6 第113–117行：16 条仅 8 物理 roots，旧 dev state 配训练池相机不等于完整训练条件，宽区间不作普遍结论；接受。

## 预算与科学边界

- 32 固定 + 80 闭环 =112 policy calls；16×150=2400 steps；≤1 GPUh；0 optimizer updates；无隐藏类别混算。§3 已写明失败/调试计费，supervisor 需实际执行。
- A 只提供入口/数值证据，不直接判 H1 因果；B 地板只作机会成本停止；C 的 0/8 不作普遍无能力；H4 历史 framebuffer 仍是 UNKNOWN。边界正确。
- 没有新方法、没有完整重训、没有正式 test；不把排障当论文贡献。

## 批准范围

**仅批准冻结 Stage0 与有条件 Stage1A/B/C，按 32 前向、16 rollout、1 GPUh、0 更新执行。** 任何新完整 ACT 训练、增加 seed/epoch/模型、正式 test 或新算法均需人类再次明确批准；本核验不构成那些授权。
