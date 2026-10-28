# F：相机条件策略的标定误差诊断与基线复现

版本：v1 冻结，2026-10-29；已吸收 05/06 两轮真实 DeepSeek 交叉审查。执行模型必须 gpt-6.1-sol，reasoning=max。不是整篇论文复现，也不是已成立的新方法实验。

## 1. 问题、范围与授权

问题：在 Know Your Camera（KYC）官方 LiftRand / ACT 任务中，给 Plücker-conditioned policy 输入整段持续的旋转标定偏差，是否比相同角幅、每次决策独立重采样的旋转误差更影响成功？它是否抵消准确几何相对同数据 RGB-only 的收益？另外区分真实视角移动与仅 metadata 错误。

来源：KYC 的准确外参收益已报道，但不是本机结果；CamVLA 附录 B 已报告独立重采样旋转噪声鲁棒性，不能声称“首次研究外参噪声”。时间相关性差异只是待检验机制，不足以建立论文贡献。此轮先复现基线与辨识缺陷；pose jitter 等强简单方法还必须在后续公平比较，首夜不能据此宣布方法必要。

用户明确授权新实验、交给 6.1-sol 复现、完成后通知主聊天；又明确指定 max 及发布后五小时检查。旧 D/M/U/Spatial/导航保持原样。只写本目录，允许必要公开资产下载和独立环境；不得修改系统 Python/CUDA/驱动、ROS、inspection_robot*，不使用未核验远程 GPU，不开新 workspace/worktree。

主线程 ID：`01a18138-0f15-76b2-b5cf-20e1722782a9`，本机项目 `/home/asus/EAI`。先通过 read_thread 核验原始人类消息中的回传授权。成功、失败或预算终止后向主线程回传一次；保存回传回执防止重复。主线程安排本任务 +5 小时 heartbeat，请读取 ../orchestration/dispatch.json 确认，不重复建同一检查。

## 2. 固定来源与资产

- KYC：<https://github.com/ripl/CamPoseOpensource>，commit `e0647105a0f3946581d253c55dc9fd1218fa0974`。
- RoboSuite 子模块：`ripl/robosuite`，commit `0df3a5f5782937fa2e8fa923910d616b73310b8d`，使用 HTTPS 获取。无需 ManiSkill 子模块。
- 论文：<https://arxiv.org/abs/2510.02268>，ICRA 2026；本轮已读全文与官方训练/评估/数据代码。
- 只取 `liftrand_eef_delta.hdf5`：官方 setup.sh 指向公共 Drive folder `1dmv-ueaP8F0ElqgVXsdmX-S9hvfQb7Yf` 的 demos_robosuite 子目录。必须先列元数据，记录真实单文件 ID、大小、下载 URL 和 SHA256；不执行全 folder 下载。若不可访问，有限重试后报告，不静默换数据集。
- 需要官方 ImageNet ResNet 权重时使用 torchvision 的原始官方来源，记录版本/hash；不得下载 SmolVLA、π0 或其他 VLA。
- 没有核验到 KYC 训练完成权重。现有相邻旧项目/环境只能只读；不可沿用旧任务的结果充当本任务基线。
- 官方 setup.sh 未锁依赖、会建立全局命名环境并下载全量资产，不照运行。全部新环境、pip/模型缓存和 vendor 镜像保存在 reproduction/ 中，最终 freeze 真实依赖版本。优先只安装 ACT 路径必需依赖，重型 DP/SmolVLA imports 可以惰性导入，保留补丁与原件差异。

## 3. 时钟与硬预算

T0 以实际任务发布时间为准，写入 run.json；最晚 T0+12h 自动收尾，前 11h 必须结束模型/仿真工作，最后至少 1h 汇总。主线程与执行线程的五小时检查分别计时，不延长预算。

| 项目 | 上限 |
|---|---|
| GPU | 1×RTX3090，累计 GPU 分配占用不超过 8 GPUh；VRAM 峰值不超过 20 GiB |
| CPU | 最多 3 线程；DataLoader workers=0，sim/env 顺序执行 |
| RAM | 进程树 RSS 20 GiB；MemAvailable <5 GiB 持续 60s 自动停当前作业并保存 |
| 网络下载 | 总计 12 GiB（数据、权重、依赖均计），并发最多 2，单来源失败最多重试 2 次 |
| 磁盘 | 新增环境/资产/缓存/输出合计 45 GiB；剩余磁盘不得低于 60 GiB |
| 准备与排障 | 90min；只有可度量的下载/编译进度可延至 120min，但总预算不增加；最多 2 项明确修复 |
| 训练 | 优先完成 C 的同模型主检验；U 仅在剩余预算能完成同等训练步和评估时执行；最多 U/C 两个 ACT、seed=0，无新方法训练 |
| 正式评估 | 50 独立 state-camera roots；最多 550 rollout，每次至多 150 环境步 |
| smoke/dev | 最多 10 expert replays、32 dev roots、64 额外 policy rollout；不计为 test |

先记录硬件、空闲量和已运行用户作业，不杀其他进程。首次小通路测吞吐、渲染耗时、训练步耗时、VRAM/RAM，并分别估算 C-only 和 U/C 两模型加评估能否放入剩余预算；不能把 epoch 数换成未经测量的小时数。两个全模型约120,006更新，8 GPUh仅留训练也要求约4.17 updates/s；尚无本机吞吐证明，绝不保证完成。

## 4. 工程与语义前置检查

1. 先读本目录 AGENTS、协议及 STATUS/锁。保存精确 commit、环境版本、命令、输入 hash，建立 run_id 和原子阶段状态。
2. 验证数据属性 env_args / action_space / demo 数；只用前 200 原始 demos 训练、接下来的 10 demos 验证；同源派生视角不作为独立 episode。
3. 确认 KYC `eef_delta` 是相邻**绝对目标 pose**的差分，执行经其 wrapper 累加。不是当前 EEF-relative OSC delta。对首 10 个固定 demo 做 expert action replay；低于 9/10 完成或显著偏离原 state，停止长训练并报告语义/实现问题。
4. 明确 cam2world、world2cam、OpenGL/OpenCV 约定；验证 3D 点投影、ray 方向/矩、旋转左右乘、crop 和 raymap 同步。使用模拟几何仅作为 evaluator 的检查输入，不向 policy 增加真值通道。
5. 记录环境 reset、model XML/randomized scene、初始状态、camera pose 与种子。旧 sim state restore 教训必须落实：不能只还原 state 而丢失 XML/随机桌面变换。用相同记录重放，验证一次无噪结果可重复。
6. RGB-only 输入 metadata 扰动时，其同图像动作输出必须保持一致（固定 RNG，数值 allclose）；准确元数据/扰动元数据进入 C 的**相同 raymap 接口**，不修改动作或使用 oracle 直接替代策略。

任一步失败最多进行有理由的两项修复，保存补丁与验收。到预算仍失败，TECHNICAL-BLOCKED / IMPLEMENTATION-LIMITED；不以随机网络/错误动作 rollout 作科学阴性。

## 5. 训练基线及公平性

U：官方 `robosuite_act_lift_randomized_image_only`；C：官方 `robosuite_act_lift_randomized_with_conditioning`。`original=0`，delta EEF，200 demos、每示教 n=3/m=1 相机采样、1 side camera，crop、late_imagenet、batch70、chunk30、其余 ACT/优化超参使用固定来源默认。两者训练 seed=0，记录相同训练来源和采样计划；架构差别限于原方法 conditioning 分支。分支容量不同是原方法固有差异，不能声称参数完全相同。

官方 Lift 配置目标为 **20001 epochs**，每 epoch 遍历 demo Dataset，非单梯度步。本机先 smoke 2 epochs + 30 个优化步测吞吐；若需要因 VRAM 降 batch，两方法相同 effective batch、梯度累计，记录偏差并重测。不得为了快而换小网络/缩图/减示范。

根据吞吐对训练计划作一次预算决定，写入 `frozen_training_plan.json`，**在查看任何正式 test 之前冻结**：优先 C 到官方20,001 epochs并保留其完整评估余量；若单 C 也无法装入预算，可用剩余训练额度推算固定完整epoch数 K，K<官方目标明确为预算诊断，不称论文数值复现。C-only 允许回答同模型主问题，U 和其相关对比必须记 NOT_RUN。只有剩余预算可完成同 K 的 U 及评估时才进入 U 阶段；不能先训练一个明显不足的 U 来比较。C/U若均运行但其中一个意外中断，只能比较已保存的共同更新数checkpoint并明确局限；不可把两种训练预算混算或覆盖重训。

原代码验证数据会使用 `test_cameras.json`。本轮将 val 的 camera 来源改为 train camera pool（验证 episode 仍为独立 10 条），避免正式 test views 被用作模型选择；记录这是协议偏差。禁用官方训练内的 test rollouts；使用固定最后共同步 checkpoint，不能按 test 成功率选。保存 optimizer/RNG/采样状态支持恢复；不要只保存权重。

32 dev roots 用于验收 baseline 是否学会动作与任务：报告完整成功数、loss 与轨迹质量，不调网络/误差幅度。C 准确外参若只有 0–3/32 成功（接近地板），不继续误差科学判定；U/C 存在明显动作错误、近常量或未学会时 IMPLEMENTATION-LIMITED。该门槛是避免地板的工程规则，不是 KYC 复现通过线，也不代表其余成功率均已达到论文水平。大于门槛但低于论文仍需报告训练不足风险。

## 6. 冻结测试设计

测试单位是一个独立环境初始化（含随机场景）与一个相机组合 root。固定 train seed0 不提供训练方差估计。dev env seed 1000–1031；test env seed 5000–5049。官方 test_cameras 的前50个 pose用于 test，第50–81个用于 dev，核查列表够长且不与训练相机数值重复；不足或重合时只能在**运行前**从官方合法采样域用固定seed 20261029生成替补，冻结 manifest，不按结果选视角。val 使用训练相机pool。50个root全部报告，不删失败、不只选有响应 root。

每个 test root 保存真实 camera transform T、初始 sim/XML 和所有 RNG；配对重置。冻结噪声 RNG 与轴/方向列表。动作/成功由统一 evaluator 记录，policy 不读成功标签。

### A. 图像/相机物理状态不变，只改变输入元数据

- U-clean（RGB-only，无元数据）；C-clean（准确 T）。
- C-persistent-5、C-persistent-10：root 的随机轴 u_i 均匀取单位球面，误差 ΔR=Exp(angle·u_i)，整段保持；world-frame 左乘真实 R，t 保持，重新计算 raymap。
- C-iid-5、C-iid-10：每次 policy query 独立均匀球面轴，同一固定角幅。与 persistent 的单步边缘分布相同，只改时间相关性。每条记录 query 编号、Rhat。

U 对 metadata-only 处理理论相同，不重复增加 rollout 来虚增样本量；smoke 阶段已做严格阴性接口验收。

### B. 真实相机移动的分解（只一个预登记角度）

测试每个 root 相机围绕官方 workspace look-at 点做 ±10°方位角位移（符号由root固定随机），保持距离/仰角并朝向同一目标；记录新 T'，确实重新渲染。若动作过程中相机保持固定：

- U-moved（新图像）。
- C-moved-correct（新图像，输入 T'）。
- C-moved-stale（同新图像，输入旧 T）。

视角超出合法范围、目标不可见等排除只能在运行前按几何判定，保存全部根与原因；不得看成功后排除。不新增 camera delay 等第四种失配。

C-only 共7×50=350正式 rollout；加U两个设置后9×50=450。真实移动的两个 C 设置是主阶段必需诊断，不能因为省时而只保留冻结图像的噪声实验。最多留100 rollout作预先声明的工程重跑余量：只重跑记录完整的进程错误，不替换物理失败或挑最好一次。

## 7. 指标、假设与解释

主对比：C-persistent-10 − C-iid-10 的 paired task-success difference。若U完成，次要应用对比 C-persistent-10 − U-clean 是否抵消准确几何优势，C-clean − U-clean 是基线效用参照；它们是系统级比较，不是严格同容量的因果效果。5°剂量与 B 的 C-moved-stale − C-moved-correct 是诊断对比，不能用最大效果替换主对比。

报告每个设置 success/n、paired discordance（哪一方独有成功）、按 root 配对 bootstrap 95% interval（固定重采样seed20261029），及 0/5/10° 曲线。多个设置共用root，不能把450次当450独立样本；checkpoint不算独立seed。对50 roots 区间很宽，不能用 p>0.05 宣布等价/已解决。

任务成功以官方 Lift success、150环境步为准；不将短时误差当任务成功。辅助记录 action范数、实际执行chunk数、对象高度、非有限值、夹持/提升阶段、恢复准确元数据是否经同接口改善。另在32个dev root的固定观测上，保持policy/RNG一致，比对准确与错metadata的原始动作向量，记录有向平移差、旋转差、首动作与完整chunk的累积差；长rollout不同state不能直接当同state动作偏差。该机制诊断不增加训练，不能把输出变化解释为任务成功变化。zero/shuffle raymap只用于dev敏感性验收，不计新方法。如果C对合理元数据误差和zero/shuffle均数值不敏感，记MEASUREMENT-LIMITED，不直接宣布机器人鲁棒。

50个root主要筛查大效应：在最坏discordance比例为1时，paired差值95%区间的正态近似半宽可达约0.277（最终仍用实际配对区间）；不能把<5个百分点或不显著当作阴性证据。预登记实际关心的损失量为20个百分点，仅作为后续投入阈值而非保证检验功效；跨过该量的宽区间为INCONCLUSIVE。二级比较只描述性报告，不反复检验后挑最显著的一项。

真实自然频率未测。A/B均为有物理含义的受控诊断，不声称真实部署的漂移发生率。若只观察到一般噪声退化而 persistent vsIID 没有可辨差异，当前更窄机制不获支持；若差距不明确，INCONCLUSIVE。若简单校准/现有方法足以解释，不继续追加网络。即使差距明显，也只是后续加入 pose-jitter/标定校正强基线的资格，不能直接 POTENTIAL-GO 为新算法背书。

## 8. 作业实现、五小时恢复、交付

当前本目录尚无可运行实验入口；执行 Agent 需实现 `scripts/prepare.py`（或等价）、`scripts/validate_semantics.py`、`scripts/run_experiment.py`、`scripts/summarize.py` 与独立 supervisor，保存最终真实命令。不要把这些规划路径冒称已经存在。

Supervisor 必须独立于对话进程运行（setsid/Popen start_new_session 等实际核验），持有 run lock，保存 PID/进程启动时间/命令/阶段/退出码，原子写 status.json；每分钟资源日志，预算触发时保存当前 checkpoint并终止自己的子进程树；不要误杀其他用户作业。下载/安装/训练/评估分别有 COMPLETE/FAILED 标记和hash，恢复不重跑完成阶段，不覆盖结果。

五小时检查：先读状态，再核对 PID 与启动时间、日志增长和产物；运行中不重复提交；额度中断不会使已启动 supervisor 等待模型。若需下一次检查，执行线程在自己同一 heartbeat 上顺延5小时；总预算不变。完成后停自己的检查并通知主聊天。仅在确有进展/失败/完成时回传，不持续“仍在运行”。

至少保存：STATUS.md、run.json、asset_manifest.json、requirements.freeze、补丁、冻结科学配置/分割/根清单、逐root结果、配对统计、资源与时间日志、恢复命令、actual_counts、错误修复记录、少量代表性帧、FINAL_REPORT.md、completion.json。区分 COMPLETE/PARTIAL/NOT_RUN 与证据状态；未运行不填0。

不切branch、不commit/push、不碰共享 Git index。主线程审查后统一公开同步原创代码/小型结果/报告，所有第三方镜像、环境、权重、大数据和凭据排除。
