# 健康 RGB 下冻结 checkpoint 诊断 v2 候选

**PREPARATION_ONLY / CANDIDATE，尚未最终双审，不是 RUN。** 本协议、可运行代码与 candidate_manifest.json 的准确 SHA 必须同时获 Codex 和真实 DeepSeek APPROVE，并收到主审新的 RUN 派发，才可启动实验。准备阶段仅源码、只读核验、纯 CPU mock/AST/小数组；目前没有新 GL、ACT 构造或 forward。旧研究目录、框架、环境、数据及权重只读，主审独占 Git。

问题限定为四个已见训练状态上的动作生成信号：健康共同 RGB 下，既有 checkpoint 的官方与自定义 prior 是否吻合、相对两个已冻结强常数如何、动作条件 posterior 的单次诊断有何差距。不是训练、视觉因果依赖、泛化或 Lift 成功测试。旧 0/32 历史原因独立保持 UNKNOWN。

## 固定来源及原调用顺序

仅旧 execution/sample_plan 的 0/1/4/5，顺序不变：demo0/t0/camera1、demo50/t0/camera51、demo0/t52/camera1、demo50/t48/camera51。四样本来自两 demo，不能称四个独立任务。state/T/expert/mask/seed 沿用旧文件，全部四个 chunk 有效30步；max_seq_length=130。selected sample_plan.json 与来源映射逐项冻结，不能按结果换样本。

实际旧 execution/scripts/stage1.py::prepare_inputs 为 `make_env(0)` → 保存源 XML → `EpisodicDataset(list(range(200)), stats, args, transform='id', env=env, max_seq_length=130)` → `Evaluator(env, stats, DATA, args)` → 独立 `PluckerEmbedder(256,cuda)`。每样本恢复 f32 源状态与 seed，依次：实际 Dataset.__getitem__（只固定原 time/camera 两次抽样并恢复 RNG）→ Evaluator._render_cam_image(T) → lib.render(env,T)。不调用 evaluate/step/rollout。Dataset 加载200demo保持原构造/自然生命周期，不是新增模型样本或数据扩张。

owner 释放事务和 Telemetry 从已审 render_controlled 字节复制，SHA 与差异留证；新安装点在首 make_env 前。只用弱 renderer 注册和 primitive ID，不保留 HELD fixture、不手动析构、不补 make_current、不重建 FBO、不删资源字段伪装释放、不额外调用 gc.collect。清理保留原 ds.env=None、env.close；MjSim.free 源码自身 gc.collect 仍按原行为执行，不能把它写成 harness 强制触发。自然目标窗口日志单独判断：读图前未出现 owner≠活 previous 的释放，记 NOT_REPRODUCED；健康输入可继续本诊断，不把它冒称自然修复复现。

新整合差异为 input_runtime.py 的自然析构接入、预算读回拦截、两个 worker、保存输入传递、model 构建只读适配及模型计数，必须审查，不能由旧局部 PASS 自动批准。完整 source_map/patches 与 candidate manifest 是门的一部分。

## 输入 worker 与健康门

每状态三入口各一次，最多12 native mjr_render、24 native mjr_readPixels。正常缓冲仍为上游 np.empty；每次附加独立 np.full(165) sentinel，均在原 render 锁内，正常与 sentinel 各计一次。隐式/失败尝试计入既定上限，不补调用。

必须存在实际 current=env 活 renderer owner，原 FBO/RBO identity 已知且有效，读回观测 GL codes=[0]，正常 raw=sentinel，独立缓冲且锁持有。查询只遵守 owner=current；错误 context 明确 NOT_MEASURED，不用默认 FBO0状态冒充离屏对象。任意健康门失败立即停止，不继续模型。sample0 的三个入口均需 RGB 像素 SHA=688297023a217d9874c347fdd0a6821def4d0a57d6abc8899014c63860976c37；其他状态还需主审实际看图，熵、可解码或 loss 均不能替代。

v2在正式RUN前修正静态健康门遗漏：每次mjr_render及mjr_readPixels的前后事件均须通过current/原对象/GL错误检查，render区另验证原锁仍持有；before不合格时不调用native，after不合格立即停止，不能让遥测排空的render错误被后续成功readback掩盖。此修改不新增任何render/read调用、GC或资源重建，见父审CPU反例及回归测试。

每帧保存 normal raw、sentinel、flip 输入/输出、RGB float tensor、NPZ、PNG，核对五个精确边界；保留 state/T/XML、owner/context/namespace/事件。三入口 RGB 和状态精确一致。统一模型比较的 canonical raw 是该样本真实 Dataset 第一次正常读回，先已保存再仅一次 flip 得 common_rgb。官方 pure preprocessing 为旧 official_eval_data 的准确 AST 函数，调用真实 Evaluator._image_to_tensor；custom 为原 lib.policy_input，二者共用该 common_rgb。不得把两次独立 render 的差异当模型入口差异。

实际 Dataset 输出也需对照 pure official；比较 RGB3、Plücker6、完整9ch、drop-before-normalize qpos、零外参 token、T/K、动作归一化和 valid mask。uint8 RGB、mask、固定状态、动作及保存边界精确一致；浮点 RGB 与其余浮点 shape 一致且 allclose(atol=1e-7,rtol=1e-6)，逐字段 shape/dtype/hash/maxabs 留证。固定 transform=id，无 crop 诊断；不将该设置改写为历史训练设置。

input worker 原 cleanup 完成并退出后，主审核对全部图像、raw/sentinel/转换链、源头和 NPZ SHA、进程退出与计数。input_gate 必须保存实际看图及 CPU 原件审核证据文件 SHA，并绑定 RUN id、代码 manifest、input_result、所有输入文件和源头 SHA、input stage process/budget record。没有主审 **RUN_MODEL** 明确批准，第二阶段拒绝启动；等待期间没有 GPU worker 或活租约。

## 模型 worker、precision 与16次清单

第二 worker 只读已冻结 inputs，不导入 simulator/Dataset/Evaluator，不再 make_env/render。读已有 C_latest.pt，SHA 对照旧 CPU checkpoint audit，args/stats 精确一致，375 tensor 有限；完整 policy.load_state_dict(strict=True)，missing/unexpected 均零，不吞键或临时改结构。

保持官方 ACT 架构与 late_imagenet 初始化语句。现有 resnet18-f37072fd 缓存只读且完整 SHA 验证，仅允许已冻结原 URL 映射到该本地文件，不联网或复制权重。为不建立 optimizer，只在 models.detr_vae 模块内用 torch proxy 将该 build 的 AdamW factory 替为 inert NoOptimizer；其余 torch 属性委托原模块。真实 torch 模块和 vendor 文件不改，checkpoint optimizer state 不载入。该窄适配必须双审，不能将 strict load 前的随机模型当实验结果。

参数和输入 FP32，沿旧部署 **CUDA BF16 autocast**，TF32 off、cudnn benchmark=False/deterministic=True，不开 torch deterministic-algorithm 替代，不以不支持为由换 precision 重跑。构造 seed0；每次独立设 Python/NumPy/Torch/CUDA seed 为旧 sample.seed1：0→20261029，1→20261030，4→20261033，5→20261034。eval、inference_mode/no_grad、requires_grad=False；禁止 backward/autograd.grad、optimizer 创建/状态载入/更新、env.step、rollout。

call_plan.json 固定顺序：先0、1、4、5各 official_prior、custom_prior、official_posterior（12）；再0 official_prior repeat、custom_prior repeat；再1同两 repeat（4）。每次 batch1，无 warmup、调试/重试、第二 posterior seed。prior 外部键集恰为 image/qpos/cam_extrinsics，不含 actions/is_pad；官方内部原字典有这两键但值必须 None，不能含标签。posterior 只用已保存的真实 Dataset 图像/规范化动作和 mask，显式标记动作条件诊断，不选择 latent 或 checkpoint；prior 原代码 latent=0，posterior 一次 seeded reparameterization。

ACTPolicy.__call__ 先为逻辑尝试记账；匹配的内部 DETRVAE.forward 首次进入同一 ticket，记录内部实际调用但不重复扣一次。直接内部调用/重入/额外内部 forward 各记额外尝试并停止，失败不返还，cap拒绝尝试留 ledger。batch/键/分支及 eval/no_grad 检查在 native forward 前。保存完整30×7 normalized/raw动作、内部实际输入、padding预测、mu/logvar、seed、输入和输出 SHA、posterior 原 loss。每次从保存输入 clone，避免 ACTPolicy 原 in-place ImageNet normalization 污染下一次。

sample0/1：各状态分别算官方和 custom repeat 对首次的 normalized maxabs，任一>1e-3 即 NUMERIC_UNSTABLE；否则该状态入口 tol=max(1e-5,2×max(该状态两重复差))。完成该状态两重复后入口差>tol 即停止。sample4/5 没有重复，pair bit_equal 或 maxabs≤1e-5 只称该次吻合；超过则立即在该状态 custom 调用后停止，剩余调用 NOT_RUN。不借0/1噪声，不称 BF16 bit-consistency，不改阈值找阳性。入口不吻合时停止 H2 解释。

## 预算与独立 CPU 监督

全局唯一 RUN id，累计2 experimental Python worker、2 make_env（计划只用1）、16 ACT、12 render、24 readPixels、600 GPU分配秒，含 imports/init/strict load/失败/cleanup。输入子分配210秒，195秒触发终止，保留15秒释放；模型可用600−实际已计输入秒，至少390，距其分配截止15秒终止。实际整个子进程寿命计费，不以 CUDA util 代替。资源每约2秒采样，RSS16GiB、全设备显存12GiB（覆盖纯 EGL，含原有占用）、亲和性三核/数值库线程≤3、新输出150MiB；不能冒称采样峰值为连续峰值。

`supervisor.py --stage input` 与经批准后的 `--stage model` 是两个显式 CPU 监督调用，每个只 fresh-exec 一个实验 worker。共享 run_state/计数/总GPU与排他锁；每 stage 的 exclusive started marker 永不删除，失败不能重启。先持久化预算租约再启动；未确认自身 PID/start_ticks 已退出前不释放租约，监督异常留终止记录。监控不可用、GPU/内存/盘超限、正式RUN+8小时截止（预留30秒收尾）、具体源码/接口/健康/strict-load问题均停止。无第三 worker、无失败修复循环或重启旧terminal。CPU准备可修错，冻结后任何具体问题停止回传，不兑换剩余预算。

worker 在框架导入前另装 Linux PDEATHSIG=SIGTERM 和距本租约截止5秒的默认 SIGALRM 备份；监督进程丢失或监控阻塞不能变成无限 GPU 孤儿。默认 alarm 终止仍算失败、占额度，不能据此重开 worker。

## 固定 CPU 统计和投入筛选

仅复用旧 constants.json 的训练采样加权30×7 mean/median，来源 HDF5 SHA 和 stats 旧核验及本轮 parent_reference_baselines 均绑定。**不拟合新常数，不逐状态/坐标拼接常数，不按表现选择 policy。** MAE 预登记锚点 median，同时必须分别比较完整 mean；RMSE分别报告两者。

对首次输出以 float64 计算 e_raw=a_pred−a_expert，e_norm=e_raw/action_std；valid-step MAE=mean|e|，RMSE=sqrt(mean e²)，逐样本、demo、chunk位置、7维分别保存。主 MAE 先对每状态有效步/维平均再四状态等权。RMSE同时注明 mean-of-state-RMS 与 pooled-valid-step RMS。规范化/物理单位分开：xyz米，旋转为 axis-angle 坐标增量弧度，夹爪无量纲命令。posterior/repeat 不重复计能力均值。两常数误差比分别报，分母0→null；任一主常数地板≤1e-8为近零地板 INCONCLUSIVE，不扩大解释。

方向仅专家 xyz 范数>1e-6米的有效步计算余弦；预测范数≤1e-6记0并计数，不删除失败预测。先sample平均，再有项sample等权；另报逐轴 sign 一致。夹爪 raw第7维 sign，零单列、与±1不符；有效步 sign 正确率；相邻有效步 sign是否改变作为 transition，报告相对专家 Hamming 错误。无专家 transition 只能说未增加误转换，不能证时序能力。比较官方 prior 首次与 median：cosine和夹爪正确率不得降低、transition错误不得增加（1e-8仅舍入松弛），明确退化→INCONCLUSIVE，无积极闭环建议。

候选最小闭环**计划信号**须全健康/加载/入口/重复门通过，四状态等权 normalized xyz MAE≤0.8×median 且≤0.8×mean，至少3/4状态各自同时优于两常数、覆盖两demo，normalized7维MAE≤median且≤mean，方向夹爪无退化。20%是投入筛选规则，不是科学阈值，不代表任务成功。

若健康/一致/稳定，但官方 prior xyz及7维整体误差均分别不优于两常数且没有明确可修原因，可建议因机会成本暂停当前 checkpoint/F复现路径；不构成 KYC/相机鲁棒性科学 No-Go。弱收益、混合或地板近零为 INCONCLUSIVE，默认不优先自动延长。posterior 好不作必过门，也不自动认定训练失败。后续闭环、完整训练、算法和扩容只可提交计划，均未授权。

## 留证、回传和公开范围

冻结协议/代码/来源/样本/调用序/CPU结果/cached资源 SHA，保存真实命令、PID/计数/预算租约、每项 NOT_RUN、原数组和旧完整性。candidate 仅供双审；主审若改任一文件，必须重建准确 manifest 后重审。RUN门模板和输入门模板均不是批准。

新 cache/temp 在本目录；旧源码/权重/数据/runtime 及系统不写、不装、不下载。原XML/native地址/raw CLI只 local_only/logs，运行时写入审计限制本目录；Python audit不能声称覆盖所有 native文件系统调用，GL/CUDA cache环境也明确指向本目录或禁用。公开仅允许清单内原创代码与小结果，秘密扫描，执行端无 add/commit/push。

准备完成按已有用户回传授权一次通知主审 PREPARATION_READY_NO_GPU，然后等最终双审及正式 RUN。子6-1-sol-max保持 PAUSED，主检查负责准备续办，不改主automation。正式分阶段进度/完成按既有授权回传，等待审核不持有GPU。任何成功均不恢复闭环或训练权限。
