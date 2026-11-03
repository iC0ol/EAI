# 真实 CPU 预检与有限修复交付

**CPU_IMPORT_READY；完整 ENGINEERING_READY 尚未成立。** 已完成人类明确派发的真实CPU入口预检、两轮有证据修复及最后一次无修改的候选覆盖。GPU预检、Stage1、Stage2均未启动，ACT/env/GL构造及科学观测为0；checkpoint实际读取了CPU state dictionary，尚未构造policy执行strict load。

R1将整个harness隔离为kyc_recovery包、相对导入和共用真实loader，不补错common字段、不删除sys.modules。首次真实进程已越过旧ROOT冲突，随后h5py为CPU平台信息查询打开/dev/null，被保护误拦。R2仅允许标准空设备的open；其他范围外write/remove/rename仍拒绝。R2真实同入口进程exit0、15.725064秒。两轮已用完，剩0；之后任何新工程失败不追加第三轮。

候选全部写完后，按主审补充授权执行一次无修改最终覆盖（不是R3）。同一runtime、cwd、run.py、真实loader，最终进程exit0、15.688087秒。实际导入9个最终分支/辅助模块，逐一记录file/spec/对象身份和SHA，并保存26个Python源码当时快照。当前代码与快照全部一致。完整记录cpu_preflight/final/，公开结构化摘要CPU_PREFLIGHT_REPORT.json；原始对象id/CLI和源码快照保留本地，不作为公开原始地址。

真实上游experiment_lib/common/utils/eval/models/cam_embedding及act/detr_vae均来自既有只读路径；ROOT/DATA、atomic_json实际写入/原子替换/JSON/utc语义均过检。真实CPU读取现有checkpoint375项张量，全部CPU且有限，args和stats相等；HDF5四目标/state与冻结哈希相同，数据、旧常数和ResNet缓存SHA留证。CUDA initialized前后false、GL模块未导入、设备构造拦截0，CPU进程未在GPU出现。CPU额外预载Torch安装设备保护，GPU可见性改为0；共同vendor-loader序列和模块身份一致，不把这些保护差异或安全导入冒充设备构造通过。

实际CPU预算检查使用独立测试账本：16个模拟逻辑ticket及匹配内部入口只计一次，拒绝ACT17、预检render/ACT、S1step、optimizer和rollout第151步；这些不是实际ACT/step。调用正式supervisor同一terminate函数，真实独立sleep进程收到SIGTERM退出-15，PID身份确认已退出。不能将AST或这些测试替代真实入口，故另有上述实际依赖和元数据加载。

候选协议SHA `3fd12394fd845a4c2df528119655af65ab1a830b55833f5aa278c0c8c004c460`；candidate_manifest SHA `bd4233fbeca8898d0145c3411ae98901897fd24b974984c3b83195cea75843ed`。绑定55个本地文件与113个只读来源，已再次全部核对。R1/R2快照/差异及candidate_diffs分别保存，后续构造器抽取和新阶段整合不是隐含已测的GPU路径，必须由双方看真实代码/SHA。

候选共用builders.input_setup和model_setup：一个GPU预检worker顺序input初始化→原cleanup→model构造strict load→cleanup，期间0render/read/ACT/step；实际可否完成仍DEFERRED，两审必须裁定，不能用一句“一个进程不能顺序做两条路径”或CPU通过代替验证。该worker≤180秒；S1输入≤210、S1累计≤600、S2只剩余，共1800秒包含失败/init/cleanup。四个计划GPU worker≤五个硬上限，每phase一次，因R1/R2用完不使用第二次预检补救。科学8h时钟从新S1 RUN起算；审查等待无GPU。全局counter/阶段门独立S1 16/12/24、S2 16rollout/2400step/80query/80render/160read，实际GPU账本尚未创建，无旧余额转移。

S1样本/16次清单、共同canonical raw、BF16、旧mean/median/方向夹爪/重复容差与20%效应门继承原v2；输入进程全退出后父审实际看图/原数组，绑定input_gate与新RUN_MODEL才前向。S2绑定原root_plan SHA431b852…，精确XML/state/RNG恢复，删除新健康RGB/动作必须等于旧坏图/0-32输出的assert；旧值只解释对照。每query一render+正常/独立sentinel，无视频/额外查询/80份冗余Plucker。success/reach/grasp原谓词、真实轨迹/动作/root配对保留，8root不能称16独立任务。科学开始后不再维修。

0/8训练相机阳性为BASELINE_LIMITED的重要证据；有阳性仅记录有限任务信号，双审研究判断前不自动称可信基线或F阳性。Stage2尚需真实S1通过、双审阶段验收、精确冻结及新派发；Stage3只有计划。模型能力与F两项基础问题仍待实际科学阶段，报告交付不等于科学完成。

旧项目/源码/runtime/数据/权重均只读，113来源锁定核验通过；没有安装、下载、系统或Git写入。所有cache/tmp在本目录。未更改任何automation；阶段回传主动通知主审，不等待5小时。等待候选GPU双审及显式派发，当前不执行GPU。公开限public_allowlist.txt并附secret_scan.json，raw CLI/native id/cache/tmp/完整权重数据排除。
