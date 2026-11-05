# KYC专项抓取诊断：CPU准备候选，尚无GPU运行许可

scope_id：`kyc-grasp-rootcause-c96545a9-5b4f-43b9-91f0-8f42b9343836`。本轮取代旧MAE门，仅在新目录执行；不启动旧supervisor、不继承旧余额。实际执行者固定既有gpt-6.1-sol/max线程。当前只有CPU_PREPARATION_ONLY，本文不是GPU派发。零训练、真实optimizer创建/更新、backward、下载/安装、系统/旧源码更改、换checkpoint/seed/架构、persistent/IID或新算法。

## 冻结来源与真实入口

唯一实验入口是既有`reproduction/env/bin/python -B run.py MODE`，cwd为本目录。harness隔离在kyc_grasp，所有P由自身路径计算。实际共用loader验证experiment_lib、官方common/utils/eval/models/cam_embedding及act/detr_vae的file/spec/sys.modules身份，不删除或注入旧模块。R指向既有只读runtime/源码/数据/权重；cache/tmp仅在新目录。父审独占Git。

CPU预检以同一解释器/cwd/run.py/loader真实导入所有安全分支，并真实导入本地run_experiment/evaluate/validate_semantics。CPUAudit在Torch前阻止robosuite/MuJoCo/GL模块，阻断CUDA初始化/迁移与ACT/make_env构造；独立CPU supervisor监测原PID是否出现在GPU、165秒/RSS/输出限制。实际读取375个CPU有限checkpoint tensor、args/stats、HDF5/四专家/采样与资源SHA，不执行policy构造/strict-load。真实预算拒绝测试和OS终止测试只是CPU接口检查，不伪称ACT/物理成功；官方wrapper提取函数在假CPU底层上验证累计契约，不替代真实A。

代码完成后保存实际CPU时源码快照。任何候选代码与快照不一致，GPU gate拒绝。官方执行float32乘加在真实CPU Tensor上执行原eval算术表达式，要求逐位相同；GPU时另要求policy返回的[0].float()与捕获internal normalized_chunk逐位一致。执行动作保持float32，分析若需float64不能反向驱动控制。

## 固定替代root与相机

`root_plan.json`事先固定demo0..3、seed42..45，HDF5原float64初态与完整原动作。公开数据没有逐demo XML，只能称基于生成器默认seed的一次替代场景，不称原示教XML精确恢复。不因本轮结果换demo、seed、几何、动作或相机。原10/10不代替本轮A。

GPU预检候选一次生成全部4root：每个make_env(42+i)保存新XML，然后真正reset_from_xml_string+HDF5 state+forward+set_init_action，冻结canonical state、wrapper累计初始目标、原controller/gripper目标、Python/NumPy/CPU/CUDA RNG、实际env.sim.model关键物理/几何数组和尺寸。冻结的不是旧Python env.model模板的推定：以后恢复必须加载同一XML文件，并验证实际sim state、实际sim物理指纹与控制器目标。`roots/manifest.json`在任何A/B行为之前封存4个root及全部文件SHA。

A与B调用同一个roots.restore：原XML加载、state、forward、set_init_action、原controller/gripper快照及RNG、相机；逐项查原文件SHA/actual state/actual sim geometry/controller目标。不同相机不能要求相同RGB。每root训练相机固定i+1，处于Dataset窗口[i,i+1,i+2]；dev只借先前1000+i的T，并不是其物理初态。B偶root train→dev、奇root dev→train，预先平衡顺序。

## 单一硬预算与阶段门

全scope最多900 GPU分配秒，含worker所有导入/初始化/调试失败/清理，单GPU顺序。每phase最多一次、各需独立RUN_PHASE dispatch，租约、PID/start_ticks和exclusive started marker均保留，无自动重试/重置/oldbalance。候选五phase：gpu-preflight、expert-a、policy-b、c-local、c-official。最大12轨迹、每条150步；A4+B8；B40个30步prior块；C44个getitem。精确操作上限见phase_plan.json：预检2render/4read、A8/16、B48/96、C每臂22/44；总102render/204read，0额外warmup。

GPU预检≤90分配秒：4替代root真实生成及清理、真实train/val Dataset初始化（不getitem）、root0训练/dev两帧normal+独立sentinel、模型实际构造/375项strict-load/清理；0ACT、step、rollout、getitem、训练。实际通过后才称限定ENGINEERING_READY，不称A/B或训练reader通过。内部分配暂列A180/B360/C各135只是候选；必须由双审在真实预检后另签allocation_gate，绑定预检结果/实耗/roots manifest，并确保所有分配+预检实耗≤900；不够就停，不扩容。

每GPU阶段由独立supervisor fresh-exec worker；GPU配额前15秒TERM、3秒后KILL，worker另有PDEATHSIG与配额前5秒alarm。科学8h从首个正式科学dispatch起算，后续deadline相同，墙钟前30秒停止留清理；预检不启动科学钟。CPU亲和≤3、数值线程3、RSS16GiB、整设备VRAM12GiB、目录全部文件150MiB（包括审查raw/log）。每约2秒监测只报告采样峰值，不称连续峰值；预检/每阶段开始也查资源。压缩数组先在有界内存完成并核实际字节，≤146MiB才写，留4MiB清理/log；存储不够保留PARTIAL并停止，不删旧证据或扩额。

engineering_gate与science_gate均须Codex/真实DeepSeek APPROVE，绑定manifest/protocol和真实review文件SHA。每dispatch绑定scope/executor/phase/时窗/900总额及独立phase配额。A/B还核完整4root；B另须expert_gate绑定本轮A4/4、成功双接口和原件，完全没有旧20% MAE条件。等待父审没有活GPU worker，不自动下一阶段。

## Stage A：实际控制阳性

固定4条、完整105/102/126/97原始动作，共430步；不加尾动作、不按成功早停。每条原wrapper执行delta，hook实际base.step观测底层绝对目标，要求与上一累计目标+本步6维delta逐位一致，末维夹爪不累计。初始第一绝对命令与HDF5 starting_abs_action误差<1e-4；每步EEF与原next_obs比较，控制契约门沿用既有expert检查max偏差<0.02m。

动作前保存真实初始EEF位置/旋转、物体位置和已核命名关节的夹爪qpos；每步记录delta、实际底层绝对目标、真实EEF pose、cube位置/高度、距离、夹爪命令/qpos/contact、reward、reward==1、原_check_success、reach<0.05m与原_check_grasp。夹爪不能静默写空数组，须核验实际命名关节索引，并与obs字段可用值核对。步后位置单独标注，不能冒充动作前位置。

A初/终各1健康帧，均算render/read预算。每条固定原长度；若env意外done或控制/判定不一致，记录并停止。任一完整专家轨迹不阳性、恢复不匹配或控制门失败，停止后续，不换root，不解释为神经网络问题。只有本轮4/4通过并获父审/DeepSeek阶段验收，才能派发B。

## Stage B：4个物理root训练/dev配对

固定8条，各150步、每30步查询1块，共每条5query/150step、全B40ACT/1200step。不以成功提前停止。准确T同时控制相机和Plücker元数据，prior仅image/qpos/cam_extrinsics，无truth/action/posterior标签。固定checkpoint重新strict-load，eval/no_grad、FP32参数+BF16 autocast、TF32关；没有优化器、额外warmup或补推理。原policy返回作为执行来源；保留完整norm/raw动作块及dtype、外层/内部ticket、输入哈希、RGB/T、实际执行前缀和全部真实轨迹。

每query一帧normal+sentinel，query0/4保存PNG，另末帧1次（每条6render/12read已单列）；ModelRuntime(save_inputs=False)避免40次复制9通道大输入。4root两相机只算4个独立物理来源。任务阳性按root配对报告，同时给success/reach/grasp、实际EEF/物体/夹爪、方向/控制跟踪证据；个别成功不称论文可靠复现，也不自动执行F实验。

## Stage C：当前训练reader自然生命周期、两臂有限审计

两臂各fresh process，一个make_env(0)给真实train Dataset0..199/crop与val200..209/id共享；不构造模型或optimizer、不训练、不计算loss。两臂均为原本地训练初始化与同一受控采样，仅c-official在官方两个位置执行从固定train.py提取的原IF guard/reset语句（先验证、后训练）。不执行有CUDA顶层副作用的整个官方train.py，不伪称完整长训重放；本地原Loader批70被有限审计选择的10val+12train子集替代，default_collate仍是实际同一函数。

每臂10个val t0，加demo0..3各t0/中点/末尾12个train，总22；两臂44getitem、44render、88read，无额外render搜索错误。时间/相机两次选择受控并留证，每对使用相同Python/NumPy/Torch/CUDA RNG起点；其余Dataset逻辑/RandomCrop实际执行一次。记录实际3个random.randint crop参数、source float32 state、demo/time/window/camera/T/K、raw normal/sentinel、flip/uint8→pre-crop、实际crop后item→实际default_collate模型前所有tensor、动作序列/mask/索引及源头SHA。NumPy CPU复核原nearest映射与实际crop RGB逐位一致，不新增CUDA transform或ACT。

所有44个实际crop后item tensor完整保存在真实collate的可索引数组中，逐item与batch slice逐位核对，避免另存44份同内容；每个item有准确文件/索引/hash。原始readback对保存12个预定代表及首个故障，其余仍实际双读并记录双方hash/健康/差异。2个预定train代表额外保存完整pre-crop+post RGB数组；故障时每split最多额外保存首个真实pre/post/标签及collate。不能用代表帧健康代替最终训练tensor证据；全部batch image/qpos/actions/is_pad/cam_extrinsics都保存。

C不安装owner-aware释放修复，不HELD、不强制析构/额外GC；仅原生析构外加测量。GL/EGL只读查询与glGetError drain、CPU拷贝/保存会改变时序/错误队列可见性，须列测量影响；不绑定/重建FBO、不强迫错误。A/B与预检则安装既有受控owner-aware修复和严格读回健康门。

每臂记录初始XML/actual sim cube尺寸和物理指纹，guard前后XML/几何、reset次数；每item保留actual geometry。两臂只在source state/camera/RNG和实际几何相等时解释纯guard效果；几何不同标混淆。公开HDF5无原demo XML，所以当前训练场景与原收集场景身份仍未证明。

每个split首次健康错误后保留真实item/collate及链并停止该split；validation故障后仍进入原定第二guard和train split，最多原12个训练sample、无新增重试。分别记录validation_fault/train_fault及两条实际collate链。若native异常在tensor前发生，诚实标PARTIAL/未证实传播。GL/FBO异常单独不足以证明像素坏；normal/sentinel不确定性须确认差异经过实际crop并进入collate才标当前readback不确定性传播。若差异全被crop去除，不能说最终训练输入污染。可疑条纹/重复需主审看实际数组；全健康且自然目标窗口未出现记NOT_REPRODUCED。无论何结果，都不能追认旧4.57h曾同样损坏。

## 交付、验收与停止

每阶段保存原命令/PID/start_ticks/退出/日志/分配秒/独立计数、原数组/帧/轨迹及SHA，主动异步回传已获人类授权的主线程。每次父审和真实DeepSeek分别读原件后交叉，不以分析字符串代替放行；不因为剩预算或部分成功加轨迹。任何预算/恢复/健康/数值/输入来源错误停止、原件封存、无自动修复或重试。所有新改动仅在当前未冻结CPU准备期留diff；GPU后须另外保存错误、双审和新的明确授权才能考虑改变。

最终六问须区别：明确代码缺口、当前自然训练输入故障、旧0/32历史原因。A失败优先控制/恢复，A阳性+B双相机阴性支持当前checkpoint缺行为但仍非唯一因果；训练阳性/dev退化支持有限相机分布差异；C当前污染仍不能替代历史证据。本轮不授权重训或F机制试验。必要证据按允许清单和秘密扫描由主审公开iC0ol/EAI；runtime/缓存/完整权重/数据/凭据不上传。完成后停止等研究者决定。
