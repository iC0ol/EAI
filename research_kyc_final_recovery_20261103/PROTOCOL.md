# 最后一轮有限恢复：CPU已测，GPU与科学阶段候选 v1

**当前派发仅 CPU_PRE_FLIGHT_AND_REPAIR_ONLY。本文及候选 GPU 代码尚待 Codex、真实 DeepSeek 审准确 SHA。不得据本文启动 GPU。** 当前恢复 id 为 kyc-last-recovery-441e91b0-ee5f-4294-9501-070606a5f695，旧 RUN/目录只读、不转移余额。CPU准备截止2026-11-03 14:58:25；科学8h时钟只在正式S1 RUN开始时写入，不能延长。

人类原文授权 Pre-flight、Stage1 及通过门后的条件 Stage2；Stage3只计划，无训练、optimizer、换checkpoint/结构/seed、下载、安装或系统更改。主审独占Git。以实际状态区分 CPU_IMPORT_READY、限定路径 ENGINEERING_READY、SCIENTIFIC_MEASURED、ENGINEERING_BLOCKED、BASELINE_LIMITED、POTENTIAL_F_SIGNAL、INCONCLUSIVE。

## 真实入口与两轮修复

唯一入口为既有runtime的 `python -B run.py MODE`，cwd为本目录；harness全部在 `kyc_recovery` 包，包内相对导入。`loader.load_actual` 是所有预检与正式worker共用的真实加载器，顺序固定为 experiment_lib→官方common→utils→eval→models→cam_embedding→models.act→models.detr_vae。依赖先按真实源码自身顺序导入；CUDA可见性是CPU与GPU环境的明确差异，不用替代模块或假ROOT通过。对已有sys.modules只核验来源，不删除缓存、不给错模块补字段。

R1处理旧common冲突，保存旧traceback、before/after SHA与差异。R1真实CPU进程已越过ROOT错误，但h5py的平台查询打开/dev/null被新增写保护拦截。R2只允许open解析到os.devnull；其他范围外open写入、remove/rename仍拒绝。R2真实独立进程通过；两轮额度已用完，不能按阶段重置。最后候选完成后再做一次无修改真实CPU覆盖，属于测试重复而非R3；如再暴露错误，记录并封存，不修第三轮。

CPU预检采用相同run.py/runtime/cwd/loader并真实载入上游模块，记录__file__/spec/sys.modules身份、ROOT/DATA/atomic_json/utc语义；真实CPU读冻结checkpoint的375张量、args/stats、四目标、数据和缓存SHA。CUDA_VISIBLE_DEVICES为空，真实PyTorch初始化/迁移入口阻断并记录；禁止GL相关模块导入、env/ACT构造。cuda initialized标志和GPU进程观测留证。实际CPU监督拒绝/OS终止测试用独立测试账本和sleep进程，不能当ACT或GPU调用。

最终覆盖使用相同CLI resolve导入最终builders、GPU预检、input/model/closed、supervisor、analyze等安全分支模块，保存当时全部Python源码快照和SHA。分支main里的设备/仿真/模型构造明确DEFERRED，不用安全导入冒充完整ENGINEERING_READY。之后代码与该快照不一致即拒绝GPU门。

## 单一账本、阶段调度与停止

一个recovery_state.json累计1800 GPU分配秒，整个worker从导入、初始化、debug/失败到清理退出均计入。旧余额0继承。每个阶段显式新dispatch，排他CPU supervisor只fresh-exec一个GPU worker；确认PID/start_ticks退出、租约清空后才能下一阶段，等待主审时不持GPU。各phase的exclusive started marker不删除、失败不返名额，不自动重试。

计划为四个GPU worker：预检1、S1输入1、S1模型1、S2闭环1，硬外上限5但各phase最多一次，R1/R2已用完，因此当前候选不使用第五个或第二次预检作修复。GPU预检≤180秒（总建议≤2次内实际只用1）；S1累计≤600，其中input≤210、model用600−input已用，至少保留390；S2只用1800−所有既用秒。前两段若用满780仍余1020给S2，不保证一定足够完成，不为凑齐16条延长。

距每段配额15秒TERM，3秒后仍活则KILL；worker另有PDEATHSIG和距租约截止5秒的默认alarm。科学RUN+8h硬截止预留30秒释放。监控每约2秒，CPU三核亲和性/数值线程3、RSS16GiB、整设备显存12GiB、目录150MiB；采样峰值不冒称连续保证。cache/tmp全部本目录，所有网络/下载禁止，旧源码/数据/权重/runtime只读。

全局上限：S1 16 ACT、12 render、24read；S2 16rollout/2400step/80query/80render/160read。S2每rollout150step/5query/5render/10read。make_env计划最多10次（预检1+S1输入1+S2每root一次共8），硬外上限11；S1模型不准make_env。科学阶段开始后冻结代码，不再维修；当前两轮已用完，预检若失败也封存，不开第三轮恢复。

## GPU预检候选：同进程顺序验证两条真实构造路径

`gpu-preflight` 首先调用正式S1同一 `builders.input_setup`：原make_env(0)→Dataset(list200,id,max_seq130,env)→Evaluator→独立PluckerEmbedder；owner-release/遥测在首env前安装。只构造，不__getitem__/render/read/step。调用同一close_input，删除引用、原env.close，要求所有登记GL context已销毁、无fatal，然后释放空闲tensor缓存。

随后安装正式同一ModelRuntime（无pending call，任何隐式forward立即拒绝），调用正式S1模型同一builders.model_setup：固定原args、late_imagenet缓存只读URL映射及SHA，局部torch proxy仅将AdamW工厂变为inert NoOptimizer；官方模型架构/weights/key不改。完整375项strict load，missing/unexpected为0，stats/args/有限值核验、eval/requires_grad=False。没有任何ACT调用、render、read或step；所有GPU原语时间计预算。最后close_model及进程退出，才标限定 ENGINEERING_READY_INPUT_AND_STRICT_LOAD，健康读回/BF16/闭环仍未测。

一进程顺序完成并不共享科学观测；两个构造/清理步骤及来源分别留证。该方案回应两条路径覆盖分歧，仍需两审检查真实代码后批准，不把CPU通过或候选逻辑当实际GPU通过。失败立即停止，禁止为测试模型额外消耗16前向或12/24采图。

## Stage1固定诊断

完整继承references/stage1_v2_protocol.md所定0/1/4/5（demo0/50,t0/t52/t48,camera1/51）、sample_plan与16次call_plan、原seed、canonical raw、id/no-crop、BF16 autocast/FP32参数/TF32off、零动作标签prior与单次动作条件posterior。不拟合新常数，复用旧30×7训练采样加权mean/median。没有训练、warmup、调试重试或替换权重。

输入通过同一builders建立原真实三入口，正常np.empty读回加独立165 sentinel，原锁内分别计数。render/read前后均需current为活动owner、原namespace对象有效、GL codes=[0]；错误context不测owner对象，未通过立即停。每帧五个保存边界精确核对。sample0像素SHA固定688297023a217d9874c347fdd0a6821def4d0a57d6abc8899014c63860976c37。无HELD/强制析构/额外GC/补绑定/FBO重建；自然目标窗口未出现独立记NOT_REPRODUCED，不假称修复自然复现。

三入口Dataset/Evaluator/custom图像各一次/状态，共12render、24read；官方/custom纯预处理共享真实保存的Dataset canonical raw；实际Dataset完整输出也核对。uint8/state/mask/动作与保存边界精确，浮点atol1e-7/rtol1e-6。input完全退出后父审实际看12帧和raw/边界，input_gate绑定文件集/源头/结果/进程预算记录和审核证据；再有新s1-model派发才加载模型。等待无GPU。

模型按原16清单batch1：四样本各官方prior/custom prior/官方posterior=12，再0/1各两prior repeat=4。首次外层与匹配内部forward同ticket只扣一次，隐式/额外/失败尝试可见并停止。所有调用clone输入，避免原ACT in-place normalize污染。sample0/1各自重复maxabs任一>1e-3不稳，否则pair tol=max(1e-5,2×本状态两重复差最大值)；4/5只有单pair≤1e-5，不能借0/1噪声。入口不吻合不解释H2。

首次官方prior能力误差用float64/valid-mask，四状态等权。报告xyz/7维MAE、每demo/位置/维、两种RMSE（pooled与mean-state）、raw规范单位、方向/夹爪/多样性，分别比较两个完整常数，分母0=null，近零地板≤1e-8=INCONCLUSIVE。posterior/repeat不重复计能力均值。专家xyz>1e-6米才算余弦，预测≤1e-6记0而不删；夹爪raw sign与相邻有效step transition Hamming，和median相比方向/正确率不得降低、transition不得增加（1e-8舍入松弛）。

S2候选数值门维持xyz MAE≤0.8×每个mean/median、至少3/4同时胜双常数且覆盖两demo、7维整体不差、方向/夹爪无退化，全健康/strict-load/入口/稳定通过。20%仅投资效应门，不统计显著、不证明任务行为。主审及真实DeepSeek各自验收实际S1输出并交叉确认，stage2_gate精确绑定分析、model_result及闭环代码/协议后，才可有条件派发S2，不再让人类重复批准已满足的条件范围。

## Stage2准确外参闭环候选

root_plan原SHA431b852e4aed785f72cbdc3fd8b59aefd981328c37f2098af5e8cea341a35416，root1000–1007，既定train/dev T和偶root train先/奇root dev先。恢复每个物理root XML/state/RNG的原SHA和精确state，再set_init_action；两条件物理起点相同，8root不称16独立任务。模型/原prior/动作执行未改，真实labels只在执行后评估记录，不能进策略。

每query一次lib.render、normal+独立sentinel、完整健康门，再同一ModelRuntime prior出30×7动作块；每rollout最多5query/150step，累计80/2400。记录各块norm/raw动作、逐step实际动作、EEF/物体轨迹、success/reach/grasp、初始state/XML/RNG/T及每root配对；success=env._check_success，reach=真实距离<0.05m，grasp=原_check_grasp。无IID/persistent、额外截图查询或视频，不保存80份Plucker大张量，S2只存输入hash/raw/sentinel及动作/轨迹。

**删除旧dev新RGB必须等于旧clean_RGB及新动作必须等于旧0/32动作的assert。** 原物理恢复保留；旧图像hash/动作差异仅解释性记录，不当健康修复正确性的门。实际0/8训练相机阳性为BASELINE_LIMITED重要证据；有阳性只标TASK_POSITIVITY_OBSERVED_DUAL_REVIEW_REQUIRED，少量成功不自动为可信基线。报告两条件连续成功/reach/grasp计数及8root配对，不事后挑root/相机。是否足以称POTENTIAL_F_SIGNAL由预登记边界下双审实际证据决定；无论如何Stage3不执行，只能向人类提交方案。

## 交付与续办

保存R1/R2、真实CPU每次进程/命令/flag/来源/原始错误/无设备证据、最终CPU源码快照、候选manifest准确SHA、旧完整性及资源检查。GPU各阶段PID/start_ticks/实际累计计数/原数组/停止记录与NOT_RUN独立留证，不能用报告完成冒充测量。

公开仅允许清单内原创代码及小结果，原CLI/XML/原生地址/cache/tmp/runtime/权重/完整数据排除。执行端不stage/commit/push、不新建automation、不改主automation、不兑换券；按实时reset+120秒或最多5h复用既有检查，不能延长硬预算。人类已授权各阶段主动异步回传父审，CPU完成后回传候选等待GPU双审；等待无GPU。
