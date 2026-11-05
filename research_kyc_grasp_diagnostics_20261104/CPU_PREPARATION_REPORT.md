# CPU准备交付：GPU尚未批准

**CPU_IMPORT_READY，仅CPU入口/资源/接口通过。** 最终同runtime/cwd/run.py实际进程exit0，14.183402秒；真实上游loader、本地run_experiment/evaluate/validate_semantics、安全CLI分支和辅助模块均实际导入。当前26个Python源码与实际CPU快照SHA一致；安全入口/辅助身份记录共17项。没有执行构造器、CUDA、GL、make_env、render、ACT、step、训练或真实optimizer。

真实CPU读375项有限checkpoint张量、原args/stats、HDF5与四专家原始来源；四份reference_next_eef存在、形状/有限性通过且与HDF5 next_obs/robot0_eef_pos原值精确相等。固定demo0..3动作105/102/126/97，共430；原数据无逐demo XML，替代场景身份明确。CPU guard前后CUDA initialized=false、GL模块空、阻断设备尝试0；独立supervisor未观察到该CPU PID使用GPU，已退出。Torch数值线程3、interop1。

CPU测试使用正式charge/CallGuard：40个**模拟**logical/internal ticket计数相符，ACT41、每rollout第6查询/151步、13轨迹/45getitem及预检禁用操作/optimizer/GPU门均拒绝；实际ACT/step为0。生产terminate函数确实SIGTERM了独立sleep子进程、exit-15，原PID失活。提取的真实wrapper函数在假CPU底层验证累计契约，绝不是物理阳性。官方eval原算术表达式在真实CPU Tensor上执行，与候选float32乘加bit equal，无新ACT；GPU时另断言policy返回等于内部捕获。

五次CPU实际运行均留存：第一次预算测试夹具active_rollout为空，被正式guard正确拒绝；只把测试夹具改为带label，没有削弱正式guard，原traceback/前后源码/diff见repairs/CPU_fixture。第二次真实通过。父审随后要求执行float32/真实policy返回一致性，修改留diff，第三次实际通过官方算术契约。父审随后要求C validation故障后仍进入预定train split，追加后第四次真实通过。DeepSeek40及主审notes06又限定三项修订：目录缺失父目录创建且仍拒绝覆盖、四专家EEF源头断言、C原22槽位内demo0/1的t0重复。本次第五次是该限定修订后的唯一最终CPU覆盖。CPU确实执行两处生产mkdir语句，缺失父目录创建成功，重入被FileExistsError拒绝且已有marker未变；没有执行设备构造器。两组repeat的源状态/相机/seed约束已检查，未执行项实际调用比较函数输出NOT_RUN；没有执行真实C。上述均为准备阶段明确修订后的测试覆盖，不是GPU重跑。旧manifest/协议归档candidate_history/pre_review40，九个被改文件前后及diff见repairs/review40_delta。所有旧原件均保留；没有GPU额度消耗或科学时钟。

候选新scope共用root恢复、base.step观测、严格加载、native/sentinel读回和ticket账本。A4+B8总12轨迹，B40 prior、C44实际getitem，取消旧20%门；详见协议与plan。C完整crop后item保存在实际collate的可索引数组中，代表pre-crop另存，防止大数组重复；两组t0重复沿用原末状态槽位与保存标记，within_arm_repeat只记录source/geometry/T/crop/raw/postcrop对比，早停缺项NOT_RUN且不追补。正式内秒额必须真实GPU预检后再双审冻结；预检候选≤90，总≤900。

396个旧只读来源已锁SHA（含实际Panda/Lift XML引用的mesh/texture、官方/本地源码、数据/权重/日志），与前次已冻来源的交集23项全部匹配。当前源码/权重/数据/旧结果没有写入。原始cpu_preflight/result含Python对象身份id等，仅本地保存；公开报告已剔除module_id。公开只按public_allowlist，排除runtime/cache/tmp/原生地址/凭据/完整模型数据。

**DEFERRED：** 实际4root生成/恢复、真实sim几何和控制器、GL初始化/健康读回、GPU模型strict-load、40 ACT/闭环、C实际crop/collate。CPU通过不能代替这些。全部GPU工程与科学阶段当前NOT_RUN；六问不作新增根因结论。准确候选manifest SHA见CANDIDATE_SHA256SUMS.txt；等待父审与真实DeepSeek准确SHA批准和新的phase dispatch，不自批，不Git操作，不更改automation。
