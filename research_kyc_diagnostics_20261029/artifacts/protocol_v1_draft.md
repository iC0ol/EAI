# GPT-6.1-sol / max：KYC 有限排障任务

版本 v1，2026-10-29。研究主线程 `01a18138-0f15-76b2-b5cf-20e1722782a9`。当前为待 DeepSeek 第2轮交叉审查的完整稿；只有 `orchestration/review_gate.json` 记载双方通过本文件准确SHA256并真实派发后才构成执行任务。阅读本目录 AGENTS.md 和 00_原始任务书.md。

## 1. 目标、角色、唯一可写范围

你是用户指定的 **gpt-6.1-sol，reasoning=max** 执行者。在 `/home/asus/EAI` 当前分支工作，不创建工作区/worktree、不切分支。所有新代码、日志、输入派生物、结果只写 `/home/asus/EAI/research_kyc_diagnostics_20261029/execution/`；你可更新本轮根 STATUS 和 orchestration 的执行状态/回执，不能修改已冻结协议和研究意见。旧 `research_expansion_20261029` 全部只读。

只回答冻结KYC ACT在准确外参下为何0/32：H1入口不一致、H2后验与prior部署能力、H3相机泛化、H4采样/环境/历史渲染。不要做新方法、完整重训、扩大seed/epoch/模型、正式test或D/M/U复现。任何新完整训练必须由人类另行明确批准。本轮训练更新数必须为0。

Codex和真实DeepSeek负责研究判断与验收；你报告原始证据、实现与实际计数。不要替代双方写最终科学定论。人类原始任务明确要求完成后将结果返回Codex/DeepSeek；请用 read_thread 核验主线程人类原文与本任务附件中的分工/回传授权，再通过 send_message_to_thread 向上述主线程一次性回传实际完成/失败及证据路径，保存回执，不重复发送。

## 2. 冻结旧来源

- 旧根 `R=/home/asus/EAI/research_expansion_20261029/reproduction`。研究起点Git `a03f16da9110f219be49a0994140c7617a6b45ff`，公开仓库 `iC0ol/EAI`，分支 `research/u-gate0-v3-overnight`。
- KYC `R/vendor/kyc`，commit `e0647105a0f3946581d253c55dc9fd1218fa0974`；RoboSuite `R/vendor/robosuite`，commit `0df3a5f5782937fa2e8fa923910d616b73310b8d`。
- 现成运行时只读使用 `R/env/bin/python`。不安装/升级包，不修改系统Python/CUDA/驱动/ROS/inspection_robot或任何旧项目，不下载新数据/模型。新缓存只写execution/cache，并禁用旧路径pycache写入；现有ImageNet缓存只读复用，缺资产则报告而不下载。
- 数据 `R/assets/liftrand_eef_delta.hdf5`，46832160 bytes，SHA256 `fc89e2a46624b877cd35ae383df9ad09a84b7881c655bc114812164d6ff45377`；只用训练demos0–199和既有dev物理root，不访问未运行test标签/轨迹选择方案。
- 唯一策略 `R/checkpoints/C_latest.pt`，845671886 bytes，SHA256 `c904a97002571d96e3ee6b66057d09162cbdcb5e926cb6ea0b660ca1390bce13`，60003updates/20001epochs，C_config/stats在checkpoint与manifests。禁止修改或另存训练版本，不用previous择优。
- 必读旧FINAL_REPORT、PROTOCOL、RECOVERY、dev_summary、offline_action_audit、run_experiment/evaluate/experiment_lib；本轮Codex独立审查及09/10/后续DeepSeek真实回复。旧协议中的旧运行授权/旧主线程Git职责不扩展到这次；本任务的新角色与上限优先。

## 3. 先冻结记录与硬上限

开始先读STATUS/status/completion/run.lock和dispatch；核对PID及`/proc/PID/stat`start_ticks，不能重复启动。记录本机GPU型号/空闲/占用进程、CPU/RAM/磁盘、环境版本、实际命令、Git状态、来源hash。

| 资源/动作 | 本轮总上限 |
|---|---|
| 优化器更新 | **0**；禁止backward/optimizer.step，不为load创建训练循环 |
| 固定样本ACT前向 | **32次**，batch=1；任何失败调用、调试、重复、posterior均计，调用前持久化计数 |
| 闭环 | **16条**，每条≤150个env.step，≤5次30步chunk query；合计≤2400steps、≤80模型query |
| 仿真/模型GPU | **1 GPUh = 3600 GPU分配秒**，1张卡顺序执行；从本轮首次CUDA初始化或offscreen渲染开始到释放GPU进程的墙钟保守计时，包含输入准备、渲染、失败、调试、闭环，不以平均利用率折算 |
| CPU/RAM/VRAM | ≤3CPU线程，workers=0；RSS≤16GiB，VRAM≤12GiB；MemAvailable<5GiB持续60s停，磁盘余量<60GiB停；不杀别人的进程 |
| 新增磁盘/网络 | ≤2GiB；无模型/数据/软件包下载。只读网页/源码小文件查询允许 |
| 时间 | 派发后≤8h整体结束，给额度中断恢复留余地；实际运行GPU预算不可因额度检查延长；Stage0只读技术排查最多90min主动工作，Stage1运行≤1h，至少保留30min写报告 |

32固定诊断与80闭环query是两个明确类别；总policy调用上限112，不能将额外固定前向记成闭环或大batch。常数、统计、tensor-only crop不算ACT前向；其GPU渲染时间仍计入3600秒。计数、进程锁、deadline应由独立supervisor/计数器约束，agent额度中断时作业仍能自行停止并写completion。不要等到额度快耗尽才实现收尾。

先写不可变run_manifest、budget、协议hash、sample/root计划及gitdiff基线，再执行。失败后仅可修正本次新诊断脚本的明确工程错误（如输出路径/shape读取/hook），最多2项，先存error/补丁/理由，所有已发生调用和秒数照计。不得修旧模型/旧数据、改算法或换指标；错误涉及实验语义则停下回传。

## 4. Stage0：只读，先给结论

无需GPU、模型前向、新env实例或仿真。可CPU加载可信本地checkpoint并读tensor元信息、原始HDF5与已有轨迹。不得让读checkpoint隐式初始化CUDA。

逐项独立核验：

1. 11指定文件及官方源差异；真实checkpointSHA、updates、args、state_dict键/非有限参数/统计与加载路径。CPU检查不必创建ACT（其build会.cuda）。
2. 用前200demos重算官方ACT stats，和checkpoint/JSON逐维比较；动作标准化与还原。drop=1时qpos为`-state_mean/state_std`，不是零；cam token零。L1 mask分母如实解释。
3. 每epoch demo覆盖、60003update连续、恢复边界、RNG/sampler差异；旧日志未记录的随机时刻/crop/视角不能凭seed冒称全可重建。
4. 现存32+1条动作/轨迹异常，不把目标增量和当EEF实测位移；专家10/10的排除范围。
5. 原始env_version、缺demoXML/RGB、原始/randomized设置与旧恢复修复；旧数据没有RGB，不设计对不存在图片的比较。
6. 官方framebuffer检查缺失的历史可查证据；当前MuJoCo3.3.0满足PR5所提区间。没有历史图像/GL状态就写UNKNOWN，不重跑训练追认。
7. 针对性核查官方匹配checkpoint、issues、releases/作者解释；只用公开一手来源。不要扩大选题普查、联络作者或下载新权重。核对KYC YAML eval_start_epoch=10000覆盖默认20000；早期每次10、后期50，不能一概写50。

输出`stage0_report.md`与机器可读`stage0_gate.json`，在任何Stage1前落盘：
- `STOP_CONCRETE_ISSUE`：已发现可解释异常的明确问题，保存证据，先结束并回传，暂不运行无关检查。
- `NEEDS_BOUNDED_STAGE1`：列明未决假设及为何只读不足；共同批准的本协议已授权以下条件诊断，不另等人类重复确认。
- `BLOCKED`：缺资产/环境不兼容或证据矛盾，保存并返回，不装环境或重训。

## 5. Stage1A/B：8个固定来源样本，总前向≤32

先在任何模型调用前冻结8样本清单：demos `[0,50,100,150]`，先列4个`t=0`，再列4个`t=floor((demo_length-1)/2)`；各demo camera=train_cameras索引`demo_id+1`（确认属于m=1,n=3窗口）；保持原256×256、chunk30、单side camera、C配置、BF16。若长度或索引不合法则停，不按结果换样本。专家标签来自对应原actions[t:t+30]，不足30按官方mask保留；不换时刻挑好动作。

### A 输入与入口

同一个固定float32官方Dataset状态、同一个camera和同一渲染环境，分别取得：
- 原官方`EpisodicDataset(transform=id)`结果（可临时控制其随机选择只指定已冻结t/camera，代码/上下文管理记录完整；不改变正常数值计算）；
- 官方`Evaluator._render_cam_image/_image_to_tensor`及官方qpos/token构造；
- 自定义`experiment_lib.policy_input`等价路径。

不直接运行旧evaluate.py主程序或snapshot/rollout，它们会写旧目录。若复用纯helper确保只读；新诊断wrapper只写execution。相同状态从相同source还原，记录执行前后XML/state/RNG及图像hash。RGB uint8、Plücker六通道、qpos、extrinsics、归一化actions、mask的shape/dtype/min/max/hash/maxabs误差均保存。RGB要求逐像素一致；浮点输入报告bit equality及`atol=1e-7, rtol=1e-6`，超差先查数值来源，不先判根因。随机crop另以冻结top/left/size对9通道做tensor-only对应检查，不改部署图像；保存crop参数，不能分别随机crop RGB/ray。

全部比较使用同raw图像/状态；prior两入口必须不含actions/is_pad/成功/场景真值。posterior允许已授权的训练action标签，仅用于离线诊断，永不流入闭环。

前向分配：8样本官方prior+自定义prior各1次=16；前4个t0样本额外官方prior重复各1次=4；8样本posterior各1次=8；前4个t0样本第二个固定seed posterior各1次=4，总32。官方prior重用作B，无额外预测；新分配取代10回复中未计入的重复调用建议。

policy.eval/inference_mode、同checkpoint、相同RNG/精度设置，输入每次clone避免ACT原地RGB归一化。posterior真实动作路径原样reparametrize；种子对样本j为20261029+j、20262029+j。通过一次内部model forward的只读hook捕获a_hat、mu/logvar，不改forward算法、不为获取数组再call。posterior不是有效部署控制器，禁止rollout。

输出容差在看结果前固定：normalized chunk maxabs `tol=max(1e-5,2*rmax)`，rmax是4个同入口prior重复中最大maxabs；另逐维报告raw单位误差。若rmax>1e-3，标`NUMERICAL_UNSTABLE`并停C，不用扩大容差掩盖差异。若输入一致而输出超差，记执行/数值未解释，不能直接判H1因果；若输入或输出明确超差，停C并保存官方/自定义差异、完整输入输出。阶段结果不足8样本时标PARTIAL，不能突破32次补齐。

独立几何检查如可在同批固定渲染中完成：只使用当前实际MuJoCo cam_xpos/cam_xmat/fovy与可见几何的世界点/分割像素作评估端投影，报告遮挡与半像素约定；不可用待检ray生成点再回投冒称独立验证。真值不入policy。若无可靠可见对应，标未完成，不为此扩大样本或改旧raymap。

### B 部署行为、常数与停止C的规则

Stage0或运行前固定训练demos0–199全部原始动作每维mean/median；这只是CPU统计，不拟合8诊断标签；两个常数在所有30位置重复。主常数对手为median，mean为附加；可报告物理zero动作但不把它当强基线。

每样本保存专家/官方prior/自定义prior/每个posterior的normalized与raw chunk、mask，报告：有效元素归一化L1与官方padding分母L1；xyz/轴角/夹爪独立原始单位MAE；每步与整chunk方向/范数（expert范数≤1e-4m的xyz步方向记不适用）、预测和专家的变异；posterior KL/mu/logvar。对posterior先对同样本种子平均，再在8样本汇总，不让重复多的样本权重大。第一步与整chunk分别看。4demo/8来源状态不是8独立任务，不能给泛化成功率。

**不得要求posterior必须优于prior才能进C。** healthy prior可以与posterior接近；小KL并不单独证明latent问题。

除A异常/非有限/错误shape/超预算外，只在以下明确预登记的描述性open-loop地板同时满足时停止C：
1. 全有效步汇总的prior xyz归一化MAE ≥ train-median xyz MAE，且≥6/8样本各自不优于该median；
2. 至少满足一个附加异常：a)在expert raw标准差≥1e-4m的轴中至少2轴，prior跨全部有效样本/步标准差≤expert对应轴的0.1倍；或 b)逐样本平均posterior的汇总xyz归一化MAE≤prior的0.5倍。

此阈值只用于停止继续花预算，不是已检验的科学效应阈值。若样本不足、分母近零或条件模糊，先报告不确定，不伪称通过；可在剩余冻结预算内执行C以辨别闭环，不能临时改变规则。若prior有效而posterior未胜，允许C。若停C，最终依据仅open-loop诊断，宜D/IMPLEMENTATION-LIMITED，不能声称普遍训练任务无能力。

## 6. Stage1C：最多8旧root×两视角

仅Stage0通过、A无明显错误/不稳定、B未触发上述地板且预算足够，才进入。

沿用旧dev root **1000–1007** 的既存XML/state/RNG及准确原dev T；不得修改旧snapshot manifest。分别配训练池indices **0,25,50,75,100,125,150,175**。以各root两条顺序执行，顺序按root奇偶交替先train或dev，冻结表后不得按结果改变。每条重置完全相同物理初态和wrapper init action。训练池camera仍配dev物理state，因此不是所有训练条件复现。

16条总共8个物理roots，均为新测条件但不是新增独立root；原32结果保留。每条最多150steps/5queries，不延长horizon等成功。准确T生成raymap，不含任何持续/IID噪声，不变控制语义、drop概率、crop/模型参数。policy只读合法RGB、固定标定、原设定qpos/token。evaluator另记录实际EEF、物体位置、成功/抓取/reach（旧<5cm定义）、全部动作与查询输入hash，不能将评估标签回注模型。

先校验原dev初始图像hash及前次状态hash；需恢复原RNG，所有验证动作调用计入C query，不能另加“免费smoke”。闭环若与旧同root结果/动作不符，保存差异并审查数值/恢复原因，不能直接认为恢复成功。配对结果完整报告每root、success/reach/grasp、discordant pairs；提供描述性区间但不显著不代表等价。0/8的宽上界说明无法证明普遍无能力；任何阳性也不等于论文KYC已复现。

## 7. 收尾、回传、公开同步

任何完成/失败/预算中止都写STATUS、status.json、completion.json、FINAL_REPORT.md；至少包含真实commands及退出码、进程起止时间、counts、预算消耗、原始逐样本/逐root数据、hash、阶段门槛、已运行/NOT_RUN、错误修复、只读旧文件复核。无数据的率/数量用null+NOT_RUN，不填0。小型npz/json/png可公开；模型、原始大数据、runtime、第三方源码镜像、完整XML、缓存、凭据及rawCLI transcript不公开。报告不要将本机费用估计当实际API账单。

Stage2只提决策依据：A明确差异及是否能解释/需什么最小修复；B训练池阳性新视角失败的有限证据；C只有实际闭环支持本批训练池无效且无具体修复时才可建议机会成本暂停；D未决原因与证据边界。不能因已花训练成本建议默认再训。你可给下一步预算建议，但不执行。

你负责本轮原创代码/小型产物的公开Git同步：完成前与主线程共享本轮Git状态，主线程在你执行期间不操作Git index。仅逐路径stage本轮目录可公开文件，检查diff/秘密/大文件/第三方镜像；不使用`git add .`，不reset/rebase/force-push或碰旧改动。沿当前分支正常commit/push至已授权iC0ol/EAI，记录commit及remote SHA；网络失败保存原件并回传，不伪报同步。不得在未确认范围时提交别人的并发文件。主研究后续验收稿由主线程汇总/另次同步。

自动检查：复用主线程为你绑定的`6-1-sol-max`，不重复新建。先读orchestration/clocks/dispatch和工具查询真实额度；账户共享，优先真实resetsAt+120s续办，最长5小时核查兜底。额度不足时保存可靠检查点，让独立作业继续受硬预算约束，不空等/忙轮询，不兑换额度重置券。每次核查读真实PID/start_ticks/log/output再决定；恢复不能重复运行。若任务尚未完成，更新同一检查并记下时间，不能延长3600秒GPU或派发+8h总限。

完成/终止后关闭自己的检查，向主线程回传一次，包含：阶段、实际32/16/秒数计数、主要证据/未决问题、commit/URL、是否需要主审，附回执。Codex与DeepSeek将分别独立验收并至少交叉质疑一次，再给人类最终8部分研究报告。
