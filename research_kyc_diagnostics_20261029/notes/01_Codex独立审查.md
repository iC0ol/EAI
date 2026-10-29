# Codex 独立审查：先定位部署能力缺口

冻结于 2026-10-29 11:42 Asia/Shanghai；此稿在读取本轮 DeepSeek 09 独立意见之前形成。只读源码、既有数据/结果和官方公开记录；未运行模型或仿真。

**目前没有已确认的失败根因。** 0/32 证明该冻结 checkpoint 未通过旧开发门槛；它不能区分训练样本部署能力、视角泛化、环境偏差和实现问题。优先做固定状态下的官方/自定义入口数值对照及 posterior/prior/常数对照；只有前者无明显故障，才进行少量配对相机闭环。

## 1. 证据版本与核对

GitHub `iC0ol/EAI` 分支 `research/u-gate0-v3-overnight` 起点 `a03f16da9110f219be49a0994140c7617a6b45ff`。用户指定的11个文件已通过 GitHub connector 实际读取，并以远端 Git tree blob SHA 对本地字节核对，11/11一致，见 [核对记录](../artifacts/github_evidence_verification.json)。KYC 固定 commit `e0647105a0f3946581d253c55dc9fd1218fa0974` 的19个关键文件亦与本地 vendor 一致，见 [源码记录](../artifacts/official_kyc_source_verification.json)。这确认来源一致，不等于执行语义完全一致。

下文 `R/` 指 `../../research_expansion_20261029/reproduction/`；`K/` 指其 `vendor/kyc/policy_robosuite/`。旧文件不修改。旧总报告、独立审查、FINAL_REPORT、PROTOCOL、RECOVERY及两份结果JSON均已读取。

## 2. 八项实现检查

| 检查项与代码位置 | 观察与已确认差异 | 是否足以解释失败 | 最小追加检查 |
|---|---|---|---|
| 1 训练数据流：`R/scripts/run_experiment.py:39–44,59–64`；`K/utils.py:354–431,441–498`；`K/train.py:99–181` | 适配器直接调用官方 Dataset/ACT，200 demos、每次随机时刻，m=1/n=3相机窗口，9通道共同crop；70/70/60的三个batch。val camera改train池，禁用训练内rollout，是已冻结差异；自定义入口另未执行官方framebuffer检查 | 未证明。val差异改变验证分布，训练内评估还会改变RNG/环境状态；不能仅据此归因。渲染历史健康性无直接证据 | Stage0列差异、帧缓冲与版本证据；Stage1保存固定训练样本的官方Dataset图像和张量，与独立入口比对，不立即重训 |
| 2 部署数据流：`K/eval.py:152–173,200–237`；`R/scripts/experiment_lib.py:23–40`、`evaluate.py:30–32,54–79` | 都flipud RGB、/255、同Plücker、零外参token、归一化qpos、BF16、30步chunk、动作mean/std还原；自定义复制输入避免ACT原地RGB归一化二次作用，使用冻结XML/state/RNG根而非每次随机reset | 源码层面同构，尚无同输入数值等价证据；原地归一化风险在当前clone路径已有防护 | 同checkpoint、同真实状态/相机，分别走官方Evaluator helpers及自定义入口，比较RGB/ray/qpos/token/归一化动作和生成chunk；固定eval/RNG/精度 |
| 3 ACT posterior/prior：`K/models/act.py:18–58`、`models/detr_vae.py:65–119`；`R/scripts/run_experiment.py:31–34` | `actions`存在即走动作条件CVAE后验，即使`eval()`仍然如此；部署无actions，latent=0。验证loss含后验及KL，且L1乘mask后按全部元素平均，padding影响分母 | 这是确定的指标含义，不是已定位的bug；最后KL很小也不支持凭空断言严重posterior-prior鸿沟 | 同训练来源样本、同图像，保存先验及两次固定随机种子后验的原始动作、mu/logvar；分别报有效步归一化L1、原始xyz/旋转/夹爪误差，与训练集固定常数比较 |
| 4 归一化：`K/utils.py:123–190,410–431`；`K/eval.py:222–230`；`R/scripts/experiment_lib.py:39`、`evaluate.py:31–32,89` | qpos在drop=1下先置原始零再归一化，等于`-mean/std`，不是归一化后零；state切片含义可疑但双方在drop=1时相同。checkpoint自带stats，评估读取它；std正常有限 | 无旧U的极小std异常；不能因非零qpos token就称输入bug | CPU重算前200 demos stats，与checkpoint及JSON逐维一致；还原actions回原始数据；不可临时改drop概率 |
| 5 RGB与ray实际对应：`K/utils.py:327–392`；`K/cam_embedding.py`；`R/scripts/validate_semantics.py`及`results/semantics/camera_raymap_checks.json` | cam2world、GL前向-z、矩后方向的6通道及9通道共同crop有代码和代数检查。源代码双0.5形成index+1偏移也被原样保留 | 旧反投影用同一解析R/K造点再投回，只证明自一致；不能当独立渲染对应验收。半像素偏移是上游共同约定，不足以解释0/32 | 先作两入口逐元素比对；若需物理核验，用同帧独立MuJoCo相机/真实可见几何投影作只读评估，记录像素中心约定。禁止为提高成功率改ray通道 |
| 6 sampler/RNG/恢复：`R/scripts/run_experiment.py:12–27,43–54,59–69`；`K/utils.py:482–496`、`K/train.py:121–145` | 自定义独立Torch generator，完整保存perm/offset/generator及Python/NumPy/CPU/CUDA RNG；日志60003更新、每epoch全部200demo。官方DataLoader使用全局RNG，训练内评价也消耗RNG并reset共享env | 同seed不逐步等价已确认；采样覆盖和分母没有缺失证据。改变RNG不等于解释所有行为失败 | 只读核对每epoch coverage、resume边界；列出不可重建的随机时间/相机/crop历史，不伪称已还原完整训练输入 |
| 7 checkpoint：`R/scripts/run_experiment.py:25–29,45–54,70–77`；`evaluate.py:87–89` | 原子写latest、轮换previous，带模型/优化器/采样/stats。评估先验SHA再strict默认load；冻结845671886 bytes，SHA `c904a97002571d96e3ee6b66057d09162cbdcb5e926cb6ea0b660ca1390bce13`，60003updates/20001epochs | 已有主审哈希与执行记录一致，无错载旧smoke证据；仍应由新执行者独立查内部字段、缺失键和非有限值 | Stage0 CPU读取元信息及参数统计；禁止写回checkpoint，禁止实例化优化步骤；模型推理才进入Stage1计数 |
| 8 32失败轨迹：`R/results/dev_rollouts.jsonl`、`results/traces/*.npz`、`offline_action_audit.json`；`evaluate.py:63–79` | 独立n=32，另同root重复1，4950steps；均无reach/grasp/success。第一步xyz跨root std约6.86e-5、2.58e-5、1.23e-4m；全程目标增量平均z=-5.59e-4m，夹爪变化明显 | 支持当前开发条件输出平移集中；不能证明训练条件下也塌缩，不能把累计目标增量当实际EEF位移，也不能用ray敏感性替代任务能力 | 对固定训练来源状态做prior/专家/训练常数对照，再按门槛做训练池相机与原dev相机同root闭环。新日志另记录实际EEF与物体位置供后验分析 |

## 3. 新查到的官方复现线索及反证

[作者 issue #1 回复](https://github.com/ripl/CamPoseOpensource/issues/1#issuecomment-3533166490)明确说明framebuffer失效可能损坏图像，train.py为此检查并reset。自定义训练未复制该检查，是实质实现差异；但旧训练没有逐batch图片或framebuffer状态，因此**不能证明历史训练损坏，更不能直接归为A类根因**。现在重新渲染健康也不能排除历史损坏。若Stage0没有历史证据，这一项必须保留未知，不为排查它重跑四小时训练。

[issue #2 作者回复](https://github.com/ripl/CamPoseOpensource/issues/2#issuecomment-3598554639)说明论文报告test_cameras结果。这支持用新视角作论文评价，但当前32个dev的seed/pose组合仍不等于作者的3训练seed均值。这个issue没有给出能解释本次0/32的修复。

[PR #5](https://github.com/ripl/CamPoseOpensource/pull/5)提出MuJoCo版本兼容约束，是未合并贡献者建议，不是已确认的作者根因；可与冻结环境版本比对，不能据此自动安装/升级。公开releases列表为空；这次仓库与issues核查没有找到匹配LiftRand/eef_delta/ACT条件模型的官方训练完成checkpoint，不能把未找到写成绝对不存在。

数据存1.4.1环境元信息、当前固定分支版本1.5.1，无逐demo XML/存储RGB。官方Dataset同样只恢复states。专家10/10及初始状态精确恢复反对“动作wrapper整体完全错误”；却没有排除模型训练时的视觉背景、几何随机化或历史渲染异常。LiftRand的白平面/地板有freejoint进入states，因此也不能笼统说去掉reset导致背景永远固定。

## 4. 初步优先级与最小设计（待交换审查）

| 假设 | 支持 | 反对/边界 | 最小验证 | 成本 | 优先级 |
|---|---|---|---|---|---|
| H1 输入/输出适配不等价 | 未做同状态端到端数值对照 | 关键路径同构、专家回放与stats正常 | A：官方Dataset/id、官方eval helpers、自定义入口同样本张量；再比较prior chunks | 最多16次前向，包含后续B共享的8次prior | P0 |
| H2 prior不能表达已见来源样本动作 | dev平移集中；val是后验且有padding分母 | 小KL、没有训练状态prior数据；后验也可能仅学到常数 | B：8固定训练状态/相机，prior对照两次posterior与train-only固定mean/median；有效步和分组误差 | 后验16次；合计A+B最多32次 | P0 |
| H4 归一化/错载/采样覆盖 | 尚需新执行者独立内部字段核验 | 旧哈希、日志、expert10/10已通过 | Stage0 CPU、源码、日志；异常先停 | 无模型前向/新仿真 | P0 |
| H4 历史渲染损坏或环境差异 | 官方有framebuffer警告；自定义缺检查；版本/XML差异 | 旧图像未存，不能推断；state含部分随机化 | 先查历史日志/版本/现存帧；A只说明当前渲染 | 只读优先，历史结论可能无法恢复 | P1 |
| H3 视角泛化 | 原32全为新相机池 | 还无训练池闭环阳性 | C：8固定dev物理root，每root train-pool及原dev-pool相机配对，共16rollout | ≤2400steps，与A/B同计≤1GPUh | P2，A/B先过门 |

样本与常数细节尚未冻结：候选demos0/50/100/150，各取t=0和序列中点，camera index=demo+1（属于其训练窗口）。8个样本来自4demo，不能按8独立任务计；图像使用同一fullframe/id部署处理，另以张量检查共同crop，不把训练视角表现称未见任务成功率。两个后验种子只看随机性，不把重复算独立n。

常数应只用训练demos0–199计算，至少训练全帧每维mean与median，不能在8诊断样本上拟合后冒称部署基线。L1的自然常数对手是median，mean用于对照z=0标准化动作；mask有效项分母必须同时报告，不能和旧平均loss直接横比。物理动作xyz/轴角/夹爪分别报，避免夹爪或静止片段掩盖移动误差。

C的16条只是机会成本诊断，不能保证辨别小泛化差异。训练相机池仍配新物理root，因此失败不能严格推出“所有训练条件无能力”。若A存在明显不等价先停；若B prior显然不能胜过固定常数且无合理动作，先记录并停C，不把未跑写0。具体量化停止规则须双方冻结。

## 5. 投入判断

我支持一次上述有限诊断，不支持再次完整训练。只有具体等价性错误、可信匹配checkpoint或明确且可验证的修复机制才值得提出下一轮恢复方案；源码差异与两模型意见一致均不能替代因果证据。A/B/C/D分类应允许D：缺少历史训练图像可能使部分H4永远未决；因机会成本暂停F可以合理，但不能宣布KYC或相机鲁棒性科学失败。

即使恢复成功，持续标定误差与IID差异、自然频率、普通pose-jitter/重新标定基线仍须过关。已有KYC、CamVLA的外参噪声、AnyCamVLA视角适配和MoVie自监督视角适应构成限制，排障过程本身不形成论文创新。
