# Codex独立源码与因果审查（先于读取DeepSeek38）

本轮新授权有效。旧四状态MAE门只是上轮投入规则，不能替代本轮任务级诊断，也不作为本轮闭环前置条件。旧checkpoint和旧0/32原件不改。

## 已直接核实

1. 官方 `policy_robosuite/train.py:102–105,163–166` 在epoch开始和训练批次前检查 `glCheckFramebufferStatus(GL_FRAMEBUFFER)`，非完整则 `env.reset()`。本地 `scripts/run_experiment.py` 在相应训练/验证路径没有该检查/reset；这是具体实现差异。官方检查不是万能健康证据：它只查询当时current context/当前绑定FBO，不能证明所有后续读回或整个epoch都健康。
2. 官方 `reproduce/paper_runs.yaml:25–33` randomized Lift ACT with conditioning为num_epochs20001、eval_max_steps150；`train.py:264` 通用默认300被此覆盖。本地default_args与旧evaluate均150。不能将旧失败解释为少执行了150步。
3. 本地确实使用官方EpisodicDataset，train0..199、val200..209，官方load_data亦如此；crop训练/id验证，按相机窗口m*demo_idx选n=3中的1相机。实际getitem先设float32状态、相机、forward、render，flipud->RGB/255->同crop的RGB与Plücker->归一化动作。每demo并不恢复单独XML。Dataset析构会env.close，训练/验证共享env，必须审生命周期但不能仅据析构存在推定训练中已触发。
4. `eef_delta` wrapper:30–38 将Δpose累加到上次**绝对目标**，并非每步从真实EEF重新积分；旋转轴角坐标也是按源代码加法，不能为了更好结果改成旋转矩阵组合。set_init_action从真实EEF读初始目标。数据controller为absolute/world，reward_shaping=false。官方eval用reward==1，本地用_check_success；新诊断逐步同时记录验证一致，reach采用旧距离<0.05m，grasp使用原contact判据。
5. CPU直接查看HDF5：只有data级env_args/action_space/total，demo0..3无attrs或model XML；states为float64，维度58；动作数105/102/126/97（合计430）。旧expert以生成器默认seed42+i一次生成模型，回放前set_state/forward/set_init_action；旧前4均成功，EEF对next_obs最大差约1.13e-5m、1.97e-6m、1.40e-7m、1.70e-7m。但这些不是本轮A的替代，也不能证明缺失XML完全相同。
6. 旧60003条训练日志只有loss/l1/kl、批次顺序、计时和显存等字段，无每步RGB/最终训练tensor/FBO/EGL健康记录。训练loss下降不提供健康图证据。旧准确dev为32独立root全部0成功/接近/夹持，另一次重复不增加独立样本。

源文件SHA、HDF5只读元数据和旧训练日志字段见 `artifacts/parent_initial_source_data_audit.json`。上述读取没有导入模型、仿真或GL，也未消耗GPU实验预算。原论文与配置复核来源为 https://arxiv.org/html/2510.02268v1 和 https://github.com/ripl/CamPoseOpensource/blob/e0647105a0f3946581d253c55dc9fd1218fa0974/reproduce/paper_runs.yaml ，不是另开文献调研。

## 有限且可判别的设计要求

A与B共享本轮一次冻结的物理XML/state/controller初始目标和RNG。候选demo0..3、seed42..45依次预定，不按本轮结果挑选。训练相机i+1在各demo窗口内；dev相机仅借旧root1000+i的外参，不能把新demo物理初态叫旧dev root，更不能将新0/4与旧0/32视为同批配对。

必须重做4条expert，完整430原始动作、不增补、不平滑；B8条各150步上限/5块，总1200步/40ACT。A+B合计12条上限。控制阳性不通过或恢复不一致时停止B的神经网络归因；新预算内任何明确修复须先保留错误、局部diff和双审，再决定是否有剩余登记名额，不重置预算、不换root。专家结束长度按原数据记录，不为了和B等长复制最后动作。

轨迹除了success/reach/grasp，还要每步真实EEF/物体/夹爪、delta与底层绝对目标、控制器跟踪误差、原reward；query记录完整预测块与实际执行前缀，0/30/60/90/120查询帧和必要终帧。A同一动作接口同一成功判据；初态的精确model/state匹配比图像匹配更关键，不同相机不能要求RGB相同。

C必须用实际原Dataset/getitem并追踪读回到**实际crop后训练tensor**及对应demo/time/action。建议无guard原本地生命周期和官方guard路径两臂，有限预定输入/RNG重复；未触发自然故障记NOT_REPRODUCED。不得默认加上已修复owner释放后观察正常，再宣称原本地训练健康。也不应为得到故障强制析构/释放后称自然长训问题。

重要混淆：guard调用env.reset可能重新随机化LiftRand几何。如果两臂图像不同，要同时保存几何摘要/XML hash/state/T，避免将场景变化直接解释为FBO修复。检测readback中的无效buffer、原生owner对象与最终tensor污染可以证明当前链路问题；没有当年逐帧证据不能证明同样污染贯穿旧4.57h训练。需要区分：代码缺口已证实、当前复现影响训练输入、旧训练历史根因是否可追溯。

## 六问的预期证据边界

如果A阳性、B训练/dev都无reach/grasp且输入健康，能排除本轮控制执行主因并说明checkpoint在这组替代训练初态也缺任务阳性；仍不能单独区分学习不足、旧训练输入/场景错配或表示问题。若train阳性而dev退化，相机分布差异获得直接配对证据，但只有4root不构成论文复现。若C自然坏图进入训练tensor且guard可稳定消除，可提出最小guard/owner生命周期修复及再训练需求，历史因果仍需严格限定。

目前不批准GPU；等待真实DeepSeek独立意见、执行者准确候选代码/真实CPU预检，再冻结GPU预检和阶段协议。总GPU<=900分配秒含失败清理，不能因为研究问题重要就扩预算或训练。
