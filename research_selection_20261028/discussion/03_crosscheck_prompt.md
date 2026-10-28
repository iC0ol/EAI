# 第二次交叉质疑：新增直接竞争与可复现性反证

继续本会话。保持只读研究边界；不实验、不训练、不推理、不安装依赖、不下载权重/数据。本轮约 12 分钟内完成，先读已下载全文和代码，只为缺失关键出处检索；不要另开候选。

统一候选 ID：A=跨时间 chunk 聚合；B=整轨迹数据筛选的局部覆盖；C=本体状态捷径与空间泛化；D=延迟接缝；E=语言绑定。A/B/C 是仅有的三个深入对象。你上轮把 A 与 D 混用，请更正。Codex 没有主张“阶段分层本身就可发表”，那不是我们的真实分歧；不要给对方创造立场。

新增证据：
1. GAP, Jingxian Lu et al., When would Vision-Proprioception Policies Fail in Robotic Manipulation?, arXiv:2602.12032v1, 作者页面和 arXiv 标注 ICLR 2026。全文 sources/gap.txt，方法 §4、Table 1/2/4、附录 §9/10。它已经按运动阶段削弱本体分支梯度，比较 vision-only / concat / masking / dynamic fusion，直接比你提出的门控更接近“防状态捷径”的问题。
   官方 https://github.com/GeWu-Lab/GAP ，commit 2f605436c68eedf328c05520d52877604af730d3。已下载 sources/gap_README.md、gap_gap_gap.py、gap_gap_dataset.py、gap_gap_policies_bc.py、gap_gap_cfgs_gap.yaml、gap_gap_cfgs_task_assembly.yaml、gap_gap_inference.py、gap_costdirection.py。
   独立静态审查发现：gap/gap.py:85 的 lambda = self.cfg.lambda 是 Python 语法错误（stdlib ast.parse 证实，artifacts/gap_static_parse.json，无导入/执行）。:83 对整个 batch 的 phase 取 max，:86 用 1 - lambda * phase_p 乘累计后的梯度；不同于论文 Eq5 的 lambda*(1-rho) 与逐步叙述。train/valid demo_range 分别 [0,100]/[0,10]，同 data_path；dataset.py 确实切相同来源，验证集包含在训练集。代码里的明显问题不代表论文实验就是这样跑的；修代码也不构成论文创新。
2. When Absolute State Fails: Evaluating Proprioceptive Encodings for Robust Manipulation, Maxime Alvarez et al., arXiv:2605.13067v1；arXiv 标注 ICRA2026 Workshop From Data to Decisions，不是主会。sources/absolute_state.txt。方法对线性 rail 两维做 episode-relative state AND action，其他关节保留绝对值，并非所有本体都删除。TableII ID SR 5/50/20%，OOD 0/25/20%；Abs OOD 危险动作后停止并计0，样本数/分母描述需谨慎。8×H200、200k updates、2500 demos，不能声称3090低成本原样复现。它直接覆盖简单坐标重写，并不是新题。
3. NOSTRA 全文 sources/nostra.txt §III-B 的 gate 用 KL 相邻变化与历史变化均值比较，fo=20 ko=10 fc=2 kc=2，不是单纯 KL 大小阈值。所以你写“NOSTRA KL很可能也会触发干净空间OOD”只是推断，平稳偏移未必触发，不能据此宣布覆盖所有空间泛化。另一方面，它确实覆盖泛化的模态可靠性切换机制。请把这两个结论拆开。
4. CUPID sources/cupid.txt §5/§6/§7/§9：有 closed-loop return 数据，模拟100/真实25 rollout用于curation；performance influence是 return-weighted action influence，不是“预测动作被哪些demo解释”就等于价值。§9说独立排序忽略子集交互。但这不证明我们 B 的局部阶段覆盖假设成立，也不能把 future work 当缺陷实证。官方 agiachris/cupid commit2941eba9427a3398d3cbe26b10c01e3ece56bd18公开，训练→rollout→TRAK→再训练，不是纯离线免费预处理。

Codex 暂定判断与请你反驳的问题：
- A：完整候选 medoid 不是创新；有 off-support 数学反例但无自然任务失败率，不应把 blank-camera stress test 当自然缺陷证据。B：无局部覆盖损失直接实证；C：受控缺陷证据最强，但已有 GAP/NOSTRA/relative-encoding 直接覆盖窄机制，而且公开资产/代码语义不足以给出可信第一夜基线。暂定本轮“当前无合格候选”。
- 请特别挑战：我们是否把“创新成立”错误提前成了“优先复现资格”的门槛？C 有真实缺陷，是否仍值得只复现 GAP/State-free？如果你主张保留，请给不依赖新模型的具体待判问题、现成公开资产/入口、最强简单对照，以及最小第一夜证据；不能因代码有bug就造方法创新，也不能无资产就假定训练一晚。
- 对 GAP 的代码与论文差异，请核对定位；如果源码属于简化发布、无法等同论文实现，请清楚限定。不要执行或修改它。
- 你上轮要求“先证明NOSTRA KL失效”才能重开 C 太狭窄：相近方法未必同一输入/任务，合理新问题也可从其他可核验线索起步。请给真正能够推翻当前停止建议的最小证据，而非为保留另造新条件。
- 核对阳性对照：应走相同选择/门控接口、同预算；oracle 只给 gate标签却完全绕开实际候选/动作空间不能证明该接口可改进。任务成功改善与接口敏感性分别记录；oracle 未证明最优性不称上界。
- 最终分别给 A/B/C 的来源证据状态（本轮 NOT_RUN，不能把查新淘汰写成 VALID-NEGATIVE 新实验）与投入建议。不要用“无候选”否定整个领域。列保留/撤回/降级和真实未决分歧，明确全文实际阅读范围与未找到资产。

允许有不同结论，不需要为了共识同意我。最终最多 1 优先 +1 备选，也可全部不保留。不得延展成第四个深入候选。
