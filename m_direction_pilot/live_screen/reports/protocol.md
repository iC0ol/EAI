# M-Gate0-L 独立预登记：在线一致性代理状态方向筛查

2026-10-23，Asia/Shanghai。依据用户本轮明确授权及附录任务书执行；附件中的未来Gate1
只是待审批方向。本轮不修复旧源状态、不重跑旧协议、不训练、不新增救题模块，不执行
2000后缀矩阵。起点89d89fbcd6458e50ae875746dd1adcdb032ec121，独立分支
research/m-gate0-live-screen；全部新文件在m_direction_pilot/live_screen/。

本协议与全部状态/160行计划/动作合法性审计先独立commit，执行代码另commit，最后才有
新仿真step/策略成功率。旧Gate0、R及所有D/spatial文件、分支ref只读并校验哈希。

## 1. 对象、资源和证据边界

唯一对象是 **replayed-prefix surrogate / log-action proxy**：从原episode XML/初态真实
执行日志前缀得到在线状态s_tilde，名义动作a_log[t]来自原日志。这不等于原HDF5 s_star，
不证明日志动作在s_tilde上仍是最优专家动作，不直接构成真实专家动作误差监督。
所有结论保留proxy-state outcome measurement限定；不由方向图声称训练M有效或有创新。

复用原Square PH HDF5、Clean42 final EMA与独立D Python环境；数据SHA
45d8cabb6d57a4c03e839aa5e4b3e58fb60fe8bd20e1951fec563a2abfd14951，checkpoint SHA
1b4cdec2acc38977c6d3be0ab651dad595a67ccdee97be5d41b2ebebd230bae9。
robomimic0.4.0/robosuite1.5.1/MuJoCo3.2.3、OSC_POSE20Hz、25×0.002s子步、world
delta、平移单位1→0.05m目标增量均保持原值。无安装/下载/系统修改/新checkpoint。

原R已确认P0/P1/P2在线前缀物理可重复但与原源状态不符；接受R-Fail，不再试reset变体、
solver、warmstart改值、缓存修补或放宽1mm阈值。固定初始化采用已审计P1：create_env→
env.reset→reset_to原model/初态/ep_meta→真实日志前缀。后续不传送到记录state。

策略输入完全沿用原native env.step返回的16D：object[7:14]世界pose、EEF site pos/body
quat、gripper qpos。两帧历史、horizon16、OA预测[1:9]、chunk8、DDIM16/eta0不变。
R的同步kinematics仅在独立MjData上只读计算物理偏差/几何，绝不替换策略native输入。
离线源与在线缓存/派生位姿的语义差异如实保留，不能借此声称原Gate A通过。

## 2. 全部状态、动作与分母先冻结

原12状态一律保留，不重新抽样、不按名义成功或翻转筛选。沿用原source-separated split：

| ID | Episode | t | Split | 原几何阶段 |
|---|---|---:|---|---|
|S00|demo_191|52|dev|grasp|
|S01|demo_191|107|dev|insertion|
|S02|demo_21|65|dev|grasp|
|S03|demo_21|165|dev|insertion|
|S04|demo_56|55|dev|grasp|
|S05|demo_56|110|dev|insertion|
|S06|demo_32|61|dev|grasp|
|S07|demo_32|127|dev|insertion|
|S08|demo_105|71|held-out|grasp|
|S09|demo_105|126|held-out|insertion|
|S10|demo_27|78|held-out|grasp|
|S11|demo_27|155|held-out|insertion|

动作单位向量x,y,z与xy=(1,1,0)/sqrt2、xz=(1,0,1)/sqrt2、yz=(0,1,1)/sqrt2，
全部±、r=0.2，只有首次动作平移3维改变，旋转3/gripper1逐值保持日志原值。
r对应10mm目标增量，不能称实际EEF位移。先纯数据检查12×6×2=144个干预动作。
平移达到/超过[-1,1]边界或其他分量原本非法，记技术拒绝，不clip、不替换状态/radius。
若有预检拒绝，停止该科学执行并交付全部分母，不悄悄补样。

## 3. 在线分叉、随机性与完整观察

每个suffix都独立创建环境并完整重放前缀。state ID的原stable_seed在环境创建前固定
Python/NumPy；Torch FP32、确定性算法/cuDNN、TF32关闭、CUBLAS workspace固定，2线程，
3090单环境。DP每次replan用按state ID/stream0/replan index确定的独立Generator，
记录seed、初始噪声hash、generator前后hash及实际输入历史，不受调用顺序影响。

前缀native历史由实际obs逐步建立。在t先a_log[t]或a_log[t]+delta一步，再追加native
obs[t+1]，policy.reset后在t+1首次replan，其后每8步，未来不使用专家动作后缀。
总episode400控制步，prefix t计入，suffix=400-t（包括干预一步）。不因成功/失败提前结束。
Y=官方task在suffix内ever-success，另存final、first success和每步success flags。
若分叉时已经成功则技术拒绝，不能把已完成状态当可判别反事实。所有前缀成本单列。

每支实际composite7维、arm scale前后、目标/参考、gripper、qpos/qvel/time、native历史、
物体/EEF测地姿态角、contact摘要、源/代理差异、CPU/GPU成本与代码SHA均保存。
仅首次干预不得clip；冻结策略后续的既有控制器裁剪另记录，不改变策略/控制器路径。
每个同状态正式分支的fork state/controller/cache/history/RNG指纹须与该状态名义支一致。
Source mismatch只报告，不再作为本次online-pair拒绝阈值；原阈值独立栏永远不更改。

## 4. L-A：4条技术后缀

S00和S03来自两个dev来源、两个阶段；各两条独立完整前缀+零扰动suffix，共4条。
逐状态比较完整prefix/fork/suffix，不只比较最后成功。重复验收沿用旧A数值：
初态和全轨迹obs/action/物理位置≤1e-5，旋转测地角≤1e-4rad，raw state≤1e-4；
controller goal、gripper及replan输入历史≤1e-5；raw qpos/qvel/time、缓存/控制器/随机流
fork指纹一致，replan/噪声表和全部success flags、ever/final必须一致。
不一致即Technical Invalid停机，不试不同状态/seed/solver。旧源状态偏差始终单列。

## 5. 固定预算与逐级门槛

| Stage | 固定完整suffix计划 | 数量 |
|---|---|---:|
| A | S00/S03各2零重复 |4|
| B1 | 全8dev：1 nominal + xyz± |56|
| B2 | 同8dev：xy/xz/yz±，复用B1名义 |48|
| B3 | 全4held-out：1 nominal +全部6方向± |52|
|总|所有名义、技术重复均计数|160|

严格A→B1→B2→B3，stage内按计划行顺序。每次先append-only reservation，失败/partial
尝试同样占用1个槽位，绝不自动重跑/覆盖。源未运行、技术拒绝、缺失Y保持独立状态，不填0。
最大12h从A执行进程开始；另有保守绝对截止2026-10-24 05:00:40 Asia/Shanghai（本次任务
开始约12h），取两者较早。每个控制步/推理前检查deadline，超时保留partial并停机。
无额外radius/seed43/任务/探针/2000 suffix预算。

每个stage完成后只按以下固定规则判断，不在中途挑精彩状态：

1. 任意技术、receipt、RNG/时间、协议哈希或预算问题：Technical Invalid，停止。
2. 强符号/改善预警：在≥2个不同source episode出现改善(Ynom=0,Ydelta=1)或正负
   反转，且这些同类预警合计覆盖≥2个不同单位方向标签，视为独立方向复核成立，停止
   当前对称、只减成功PSD路线。B1的不同世界轴可以构成独立方向；若只有同一个轴
   或单一来源，则不能据此强No-Go，B2混合方向可作后续独立方向检查。
   正负不平均；改善和正负不对称分别计数，不混为同一统计事件。单个共同随机流不能
   证明总体成功概率不对称，决策是当前proxy/paired-stream模型与论文成本的实用No-Go，
   不是概率对称性定理，更不否定真正专家状态上的所有方向监督。
3. B1如果全部48个perturbed Y均等于各自nominal Y，则Stop/insufficient information，
   B2/B3不运行。不能排除未测mixed-only效应，也不能称完整global3×3已被排除。
4. B1存在任意有效后果且不触发2，运行全部B2。B2后重查2。若同状态等模长方向间
   Y对比只存在于<2个不同dev来源，则按稀疏/信息不足停止，不以uniform damage冒充
   方向信息；完整12状态和未测held-out分母保留。
5. B2有≥2来源的方向信息、无强PSD预警，且至少world-full和object/task固定基线可
   可靠拟合，才开放B3。即使dev某简单规则全解释，仍允许按本条在固定held-out上一次
   检查其充分性。B2拟合结果先落盘、SHA封存并commit，B3不拟合/调参/挑状态。
6. B3结束后仍报告所有signed结果与强预警；不增加重复探针来救对称模型。

## 6. 事前固定的简单解释模型

先判断符号/改善，不以拟合掩盖模型失配。所有科学结果为二元Y配对，不当作连续Q/Hessian。
主表始终保存±分别Y和DeltaY。统计按episode→state层级；160条相关后缀不是160个
独立样本，无显著性或狭窄区间。方向排序检查仅在同状态内有Y=0和Y=1的方向间进行。

固定模型：scalar（同模长全tie）、world-diag、world-full PSD3×3、object-diag、
object-full PSD3×3、task/insertion-full PSD3×3、可靠时的contact-full PSD3×3。
物体/peg旋转取实际在线fork的raw-qpos克隆kinematics，不用源pose；输入方向先R.T旋转，
模长不变。task frame可能与world重合，不能虚构独立几何优势。

真实contact frame预定规则：用fork原生最后一次solver中涉及SquareNut与gripper/peg的
contact，排除table-only；提取mj_contactForce正法向力fn，C=sum(fn*n*n.T)/sum(fn)。
总fn≥1e-3N、λmax≥0.8且λmax-λsecond≥0.5才接受主法向n。法向符号按peg z/y/x顺序
首个非正交参考取正；切向1为peg x投影到法平面（退化用peg y），切向2=n×切向1。
记录geom IDs/names、位置、法向、力及solver时刻。ncon只计数；不满足规则记unavailable。
源demo未保存contact不妨碍测量在线contact，但native solver的子步时刻局限必须报告。

拟合是固定低容量的**探索性二元排序基线**，不训练概率教师，不将DeltaY当无噪声连续损失。
对每个dev状态，列出所有(Y_fail=0,Y_safe=1)同模长perturbed方向对，风险score=q=d.T M d。
目标为mean(logaddexp(0,-(q_fail-q_safe)))+0.001||M-I||F²；每状态内平均，再每源episode
内平均，再来源平均，避免方向多的状态伪独立加权。M为共享常数、PSD、trace3；diag
用3变量，完整矩阵用6个对称变量（含全部3交叉项），固定I起点，SLSQP maxiter2000、
ftol1e-10。无排序对或solver未成功/PSD超容差则unavailable，不声称被M击败。

完整特征[dx²,dy²,dz²,2dxdy,2dxdz,2dydz]；B1单轴秩3，B2六方向秩6，只代表
设计可辨识，不代表8状态已精确估参。对所有±单条结果建排序对，对称模型无法区分
全向量反号；这些不可满足的对照必须显示，不能通过正负平均隐藏。
scalar state权重不改变同状态排序。contact拟合至少需2个dev来源有可靠frame和排序信息；
留出缺几何时按不可比缺失处理，不能把缺失当0分。

B3以冻结score比较同状态的独立方向排序：margin>1e-6正确，<-1e-6违背，其余tie，按
episode/state报告。至少2个held-out来源有信息，且某固定global/object/task/contact
模型在其全部可比held-out方向对无违背/tie时，才称它在测试集上足够的初步证据；
不能泛化为普遍充分。若所有可靠强基线在≥2个held-out来源均有预定方向残余，才称
descriptive residual，仍不是需要学习M的统计证明。contact不可用时不能声称击败contact。

## 7. 论文实用性与五个最终问题

论文建议按证据分开：technical资格、proxy方向信号、固定基线、对称PSD、真实专家标签。
可信方向初证需A通过且至少2个独立来源有等模长方向Y差异；符号强预警同时记录。
现有a_log合规性只证明控制范围/阶段和源/代理偏差，不能证明在proxy上专家最优。
不把DPπ(s_tilde)替代a_log或用未来BC误差下论文结论。

若没有独立方向残余、强PSD失配、终局无信息，或无法合理连接真实专家标签，均建议
以有限时间小论文目标停止当前M版本，不靠新增头/模块/换状态/改规则保留方向。
只有proxy残余可信、简单规则不足、符号未被明显否定，才可讨论另行授权的真实专家
状态/标签一致性+方法有效性方案；绝不直接训练M或进入Gate1。本轮不采集新数据。
SCRIM/SDP/AggreVaTeD为强近邻，参考此前已核实主文献，不声称本轮复现或超过它们。

## 8. 交付与审计

reports/{technical_go_nogo.md,direction_outcome_gate.md,paper_viability.md,commands_and_costs.md}，
outputs中保留160行完整计划/实际分母、全部signed配对、源/代理差异、episode统计、
几何availability、冻结baseline、逐次成本和SHA索引。原始NPZ本地local/按branch独占保存；
日志append-only。所有原文件与原分支ref保持不变，新分支push后停止等待研究者review。
最终明确回答用户五问，给出协议/执行/最终SHA；任何未执行的比较都明确标注未评估。
