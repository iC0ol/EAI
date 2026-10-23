# M-Gate0-R 独立预登记：专家前缀恢复工程诊断

2026-10-23，Asia/Shanghai。用户本轮明确授权启动R0→R1→R2工程诊断；附件是诊断方案，
其中下一轮科学矩阵只是建议，不是执行指令。本轮不执行任何方向扰动、Gate B、训练、
其他任务或新模型。保留旧Gate0 Invalid结论及阈值，不作科研No-Go推断。

起点为537e6a6db79ed1e8aa884b4bad8a44f08b17c480；独立分支research/m-gate0-replay-recovery，
同一EAI checkout，无新worktree/环境/下载/系统改动。仅新增reports/replay_recovery、
outputs/replay_recovery、scripts/replay_recovery；大型原始trace放既有ignored local/replay_recovery。
旧M全部56个文件（包括原哈希清单自身）、旧D/spatial源树与旧分支只读并核验SHA。

## 预登记顺序、证据与假设

R0只读旧trace、HDF5、锁定上游源码，无环境step。之后本协议、固定plan.json及R0证据
单独commit；登记SHA后再提交/运行诊断代码。任何新仿真step前必须已登记且源码已commit。
P0直接使用旧A_S00_repeat0.npz，SHA由原记录校验，不重跑、不覆盖。

R0_source_audit.md与R0_audit.json区分事实/假设。已确认：官方rollout为reset→get_state→reset_to；
给定demo的官方playback为env.reset→env.reset_to(model,states,ep_meta)。model路径内部还有
reset/重建XML。不能从这一差异预先认定外层reset为根因。offline extractor逐状态reset_to并
强制采样；online step返回缓存。HDF5无转换命令与完整采集运行时记录，不能宣称已核实全部
历史执行过程。原trace没有逐步contact/goal/warmstart；源HDF5也没有，缺失必须标注。

假设依次为：reset初始化差异；在线传感器采样/缓存；控制器/夹爪隐藏状态；接触数值敏感性；
采集运行时或积分器状态信息缺失。只做下述固定对照，不试不同控制器参数、solver配置、
warmstart值或随机来源来追求通过。

## R1：demo_191，t=52，固定路径

D1/P1：与P0使用相同stable_seed(S00)，在环境创建前设置Python/NumPy随机状态。
create_env后，显式env.reset()，再env.reset_to原XML/初态/ep_meta，然后逐步执行原52个专家
控制命令。除初态之外不设置记录state；不使用专家未来动作；不修改任何命令或控制参数。
ControllerTap调用原函数一次、原值传递。P1不在live环境强制更新观测或调用额外forward。

若D1有任何物理或native观测不一致，执行D2/P2：独立环境、同一P1初始化与专家前缀；
每步先记录native step观测及raw state，再在相同qpos上调用env.get_observation()的强制
observable刷新，记录其前后缓存、qpos/qvel/warmstart变化。P2不额外sim.forward。
强制观测刷新不保证底层body/site派生量已跟随最终积分qpos，故再用独立MjData的
mj_kinematics导出同步位姿作第三对照。P2明确不是有效控制rollout，不交给策略。

P1和P2均完整执行至52后评价，不因中途误差删去接触段证据。异常/无效尝试占用一个
prefix槽位，停止并报告；不自动重跑。P0对照不消费新prefix预算。

## 不同的观测定义与严格物理门槛

旧Gate A所有阈值及按native观测计算的max/at-fork结果独立保留：位置≤1mm、角度≤0.01rad、
selected obs max≤1e-3、state max≤0.01、time≤1e-8；不修改旧文件，不宣布旧A通过。

新技术候选采用控制边界的同步16D观测：复制qpos到独立MjData，仅调用mj_kinematics，
读取nut世界位置/xyzw、EEF site位置和EEF body四元数、原gripper qpos。
EEF body/site约定必须与原Clean的16D一致，不偷换姿态字段；不改权重、归一化或动作接口。
该观测不更新live缓存、控制器、warmstart或时间；每次用live状态hash确认只读。
先对当前source episode t=0..fork的记录states离线算16D，须与HDF5原16D max≤1e-5。

新技术验收仍要求整个prefix的raw time/qpos/qvel/flattened state max≤旧0.01，nut与EEF
同步物理位置≤旧1mm、姿态角≤旧0.01rad，同步16D/source obs max≤旧1e-3。
这是独立的时刻对齐定义，不等价于旧native-observation Gate A通过。任何真实物理误差
超阈值，缓存修正不能挽救。若P2运行，P1/P2 raw物理轨迹差须≤1e-12，否则缓存访问
可能影响轨迹，原因不清时不继续。

## R2与预算（总上限6条prefix、4条zero suffix）

只有R1物理重建及上述观测语义验收通过，才能运行R2。事前固定原S02=demo_21,t65,grasp，
S09=demo_105,t126,insertion，覆盖两个不同源episode和两阶段；不换“好看”的来源。
两条R2首个prefix都通过前，不执行任何suffix。

| prefix槽位 | 路径 | 执行条件 |
|---|---|---|
| D1 | P1 S00 t52 | R0注册后 |
| D2 | P2 S00 t52 | D1存在物理/观测差异，仅诊断 |
| D3 | P1 S02 t65 | R1通过；保留live环境 |
| D4 | P1 S09 t126 | R1通过；保留live环境 |
| D5 | P1 S02 t65重复 | D3/D4均通过，作为第二条zero起点 |
| D6 | P1 S09 t126重复 | D3/D4均通过，作为第二条zero起点 |

D3/D4环境保留至门槛判定后直接用于首个suffix；D5/D6才重建第二次起点。这样后缀验证
用到的所有专家前缀也计入6条总账，不另藏4条prefix。全部prefix最多486个control steps；
零后缀为S02两次335步、S09两次274步，共最多1218 control steps。官方20Hz、每步25个
0.002s子步下最多42600 integration steps。任何低层新step都计数，构造/reset中如出现
积分step也必须计入并中止未登记的额外积分。硬墙钟48小时，不追加预算。

仅技术通过才执行Z1/Z2 S02与Z3/Z4 S09：先原a*_t一步，delta=0，随后固定Clean42、
两帧同步历史、DDIM16、chunk8至episode总步400。噪声使用原按state/replan独立Generator
的paired stream0；策略第一次重规划t+1，之后每8步，完整运行不因success提前停。
每次恢复同一Python/NumPy分叉随机状态，checkpoint及动作SHA一致。

零重复沿用旧A的数值容差：初始/全轨迹obs、动作及位置≤1e-5，角≤1e-4rad，state≤1e-4；
噪声表/replan索引、官方ever/final success及全部success flags必须一致。记录名义成功
有无信息量，不把重复当独立Bernoulli样本。任一失败立即停，不运行剩余suffix。

## 原始测量和因果局限

每个控制边界保存source/native/synchronous/(P2 forced)16D、raw state及time/qpos/qvel/act
分项、几何误差、controller goals/ref/update flags、夹爪控制、observable采样值/更新时间、
qacc_warmstart、actuator ctrl。真实sim.step前后记录每子步状态、warmstart、控制器goal、
ncon和每个接触点geom IDs/names、位置、normal、contact-frame力/矩及dt×force冲量代理。
接触力是求解器force，dt乘积只称子步冲量代理，不冒充源示教真实冲量或精确累计冲量。
明确接触数据对应子步求解时刻，不把积分后qpos与旧派生量混为同刻。

原始NPZ/逐子步JSONL本地留存并SHA索引；Git放逐control-step小CSV、t38..52接触摘要、
P0/P1/P2完整比较、小JSON/报告/图。所有动作与数值是实测；源未保存contact/warmstart
不能做不存在的源间数值对比，也不能把接触相关性写成已证明根因。

## 决策与停止

R-Pass（仅技术候选）：R1及跨至少两个来源、两个阶段的R2通过，且两个状态zero-zero均通过。
只允许提交后续科学预登记草案供讨论；本轮不自动撰写或启动附件第6节科学矩阵。
R-Partial：raw物理合理但同步观测语义无法兼容/验证，停止并列障碍。
R-Fail/Engineering blocked：固定初始化对照仍有接触段真实物理超阈值且预算内固定路径
无法解释/修复，或zero-zero success变化；本轮停止该恢复路径，M假设未经科研检验。
R-Inconclusive：对照互相矛盾、关键数据不足/仪器异常、预算到达上限，不补探针。

报告旧结论与新技术结论分开。新protocol/plan/R0和所有旧文件哈希先commit，登记SHA，
执行代码另commit；每次prefix/suffix先独占reservation，日志与结果禁止覆盖。最终push
新分支并给出预登记/执行/最终commit，停止等待研究者review。
