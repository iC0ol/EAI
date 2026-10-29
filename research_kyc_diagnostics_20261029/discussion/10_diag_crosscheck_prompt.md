这是本轮第1次实质交叉审查。请读取 /home/asus/EAI/research_kyc_diagnostics_20261029/notes/01_Codex独立审查.md；该稿在Codex读你09回复之前已冻结，hash见 artifacts/codex_independent_freeze.json。你的09原文保持不改。现在逐点反驳或接受以下意见，给出修改后的联合优先级表；尚非最终任务批准。

1. 09预算有算术错误：16样本×官方/自定义prior已32次，再做posterior并不是“同32样本”免费得到。建议总8样本：4 demos=0/50/100/150 ×t=0、中点；每样本官方prior1、自定义prior1、posterior两固定seed2，总32次（失败调用、重复、调试前向也计）。后验原始输出用同一次内部model forward的只读hook抓取，不能再额外forward。每call batch=1；不以大batch绕预算。闭环另最多16×5=80次chunk query，按rollout预算明示，不混成32固定诊断。
2. qpos不是归一化后零：drop1使原始qpos为零，归一化为-mean/std。extrinsics token才是零。请核对并更正。state数据切片含时间的潜在问题在drop1时不构成本轮训练-部署差异。
3. H3不能因0reach就降为逻辑上不足：如果视觉表征严重OOD，训练视角有效、新视角完全没动作是可能的。当前缺训练池阳性，H2也只是候选，不能称最可能因果。两侧新8对都成功并不自动说明旧评估bug；先查是否复用了原dev精确物理root/相机/入口，有无协议变化。
4. 常数以训练0–199全集每维mean、median固定，median是L1更合适对手；不在诊断8个样本拟合。可再报按训练采样分布/未来chunk位置加权的常数，但要明确估计分布与非新训练性质。不同动作单位分开，mask仅有效元素分母，另报告官方padding分母以解释旧loss。全7维prior不优于常数不能直接断定latent gap；必须看posterior是否好、局部运动误差/夹爪/方向及小KL。
5. 只跑4demo×2时刻，若prior差，最多说明这些来源训练状态在部署处理下差；不等于所有训练条件闭环无能力。停止C可以是机会成本决定，但此时最终宜D/IMPLEMENTATION-LIMITED，不应凭open-loop直接C。C两侧0/8也只有很宽区间，不证明普遍无效。请给诚实A/B/C/D边界。
6. 新官方证据：train.py:102–106,163–166有framebuffer检查，自定义run_experiment没有。作者issue1回复 https://github.com/ripl/CamPoseOpensource/issues/1#issuecomment-3533166490 说失效可能损坏图像；没有旧训练图片/GL状态，因此不能追认历史损坏，当前新渲染健康不能排除历史故障。环境mujoco==3.3.0，满足未合并PR5提的>=3.3,<3.4，不能以版本为已确认根因。请审查该线索优先级与最低检查。
7. 09称“每1000epochs评估50条”过度：train.py:130为50 if epoch>eval_start_epoch else eval_episodes，默认eval_start_epoch=20000,eval_episodes=10；Lift num_epochs20001下epoch最后是否20000，YAML/runner有无覆盖？请实际核实再描述。三seed及官方评估是论文数值对照需求，不是本轮有界单checkpoint诊断必须补齐的预算。
8. 09又写CamVLA附录C，而上一轮08已纠错到正文Extrinsic Noise Robustness/Figure5；请用确切已缓存来源核实，若非本轮必要就避免再引错定位。官方checkpoint只可写“本次所查repo/releases/issues未找到匹配公开权重”，不能绝对断言不存在。

候选Stage1A需官方Dataset(transform=id)固定demo/t/camera的张量（可局部控制随机数但不改变算法）对比官方Evaluator helpers与自定义；保持相同raw状态/视角/fullframe，动作chunk标签只进posterior和独立指标，prior无标签。共享crop需另作张量检查，不占模型前向。独立物理pixel投影若检查应取真实MuJoCo世界点与对应渲染像素，不能自己用ray造点再反投影。

请具体建议：如何冻结A的容差（同一BF16入口应严格一致但浮点差不可草率归因）、B拒绝进入C的可审计条件、C八配对root沿用旧1000–1007状态/原dev相机并加入trainpool固定indices0/25/50/75/100/125/150/175的局限。双方不强行共识，保留你仍不同意的点；然后给预算可执行的修订方案。
