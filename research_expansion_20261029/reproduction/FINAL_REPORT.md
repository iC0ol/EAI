# KYC 相机条件策略复现最终报告

**任务已按冻结停止规则结束。完整度：PARTIAL；证据状态：IMPLEMENTATION-LIMITED。**

C完成官方训练数量，但准确外参dev为 **0/32成功**，未达到4/32最低工程门槛。正式持续偏差 vs IID、0/5/10°任务曲线、真实相机移动分解全部 **NOT_RUN**。本轮没有可辨识的标定误差任务成功结论，不能称论文数值复现或科学阴性。

停止原因：DEV_BASELINE_FLOOR: accurate-metadata C succeeded 0/32; protocol stops formal error/moved-camera rollouts。不是预算耗尽；不因还有GPU余额而继续调参、重训或追加条件。报告生成：2026-10-29T06:38:25.895723+08:00。

## 来源与执行范围

用户原始人类消息已从主聊天read_thread核验，包含实际实验及完成后回传授权，见[authorization.json](authorization.json)。发布时间2026-10-29 01:26:35 +08:00，派发设置gpt-6.1-sol / max。冻结协议SHA256 `f1f24733775a4de78cc07147b3497e047376e4a6440d45800a91d600d1126390`，未修改。

KYC固定commit [`e0647105a0f3946581d253c55dc9fd1218fa0974`](https://github.com/ripl/CamPoseOpensource/tree/e0647105a0f3946581d253c55dc9fd1218fa0974)，RoboSuite固定commit [`0df3a5f5782937fa2e8fa923910d616b73310b8d`](https://github.com/ripl/robosuite/tree/0df3a5f5782937fa2e8fa923910d616b73310b8d)。上游源码未编辑，直接导入官方ACT、Dataset、delta wrapper；新代码只负责监督、恢复和评估。

官方公开Drive单文件liftrand_eef_delta.hdf5：ID `1s2sGrLVbHIpTCDXld0NIu8bI5HoRYsqo`，46,832,160 bytes，SHA256 `fc89e2a46624b877cd35ae383df9ad09a84b7881c655bc114812164d6ff45377`。300原始demos中只用0–199训练、200–209验证，无数据扩展。另取官方ImageNet ResNet18权重，无KYC训练完成权重。资产及依赖见[asset_manifest.json](asset_manifest.json)、[requirements.freeze](requirements.freeze)。本地旧环境的runtime/依赖独立复制到新目录后补齐，原环境未改动，没有使用旧任务策略权重。

## 分阶段完整度

| 阶段 | 完整度 | 真实结果 |
|---|---|---|
| 动作/几何验收 | COMPLETE，有1项记录修复 | expert10/10成功，ray方向/矩/投影通过 |
| C冒烟 | COMPLETE | 2 epochs +30更新，共36更新，计入总量 |
| C训练 | COMPLETE | 20,001 epochs，60,003优化更新，seed0 |
| U训练 | NOT_RUN | 等量训练和评估不适合冻结预算；仅初始化接口阴性检查 |
| dev准确外参 | COMPLETE / IMPLEMENTATION-LIMITED | 0/32成功、0接近、0夹持；另1次clean重放不算独立root |
| dev固定观测动作诊断 | COMPLETE | 32 roots；5/10°及zero/shuffle，不增加闭环噪声rollout |
| 50 test roots ×7设置 | NOT_RUN | dev地板规则触发，未生成test物理场景或执行test策略 |
| 配对成功差及区间 | NOT_RUN | success/n/difference/CI均null，不填0 |

### 训练与恢复证据

保持官方Lift配置：original=0、200 demos、n=3/m=1、单side camera、256×256、crop、late_imagenet、batch70（每epoch70/70/60）、chunk30及其余默认ACT超参。没有缩图、缩网络、减少示范或新方法训练。配置见[manifests/C_config.json](manifests/C_config.json)。每epoch遍历200-demo Dataset，20,001 epochs对应60,003更新。

完整batch冒烟稳态均值0.3063s，计划于2026-10-29T01:40:38.583923+08:00、任何test之前一次冻结为C-only。C记录训练时间4.573h，最终checkpoint于2026-10-29T06:15:06.676837+08:00保存。最后训练loss 0.39281928539276123，末1000更新平均L1 0.3673173515200615，最后验证loss 0.3310866355895996。loss下降未建立任务学习证据。

最终checkpoint SHA256：`c904a97002571d96e3ee6b66057d09162cbdcb5e926cb6ea0b660ca1390bce13`。包含model、optimizer、scheduler、Python/NumPy/CPU/CUDA RNG、sampler排列/游标/生成器。正式阶段真实恢复smoke的36更新检查点，并在对话中断期间独立完成60003更新。五小时检查重算最终hash、验证PID启动ticks及flock，没有重启训练。

### 语义验收与已知偏差

eef_delta经官方wrapper累加成世界坐标绝对目标；前10条固定demo全部成功，最大EEF轨迹偏差约43微米，首目标重建最大误差约2.4e-7。公开HDF5无逐demo XML，回放仅用官方生成器默认seed42+i，未搜索成功seed。HDF5 env_version为1.4.1，固定子模块声明1.5.1；无法证明精确采集模型一致。

cam2world为OpenGL坐标，RGB竖直翻转；ray通道为origin×unit direction后接unit direction，crop同步。保留官方raymap额外0.5像素偏置，解析投影按同接口验证。见[results/semantics/camera_raymap_checks.json](results/semantics/camera_raymap_checks.json)。

原轨迹末状态/compiled XML重载图像不一致，失败exit1和原件保留，原因没有证明。修复后对与配对评估相同的“源码模型XML+初始完整state”连续恢复，图像逐像素一致；dev root1000完整clean rollout额外重放一次，全部动作及成功状态完全一致。本验收不承诺任意中途状态恢复。详见[repairs.json](repairs.json)、[patches/README.md](patches/README.md)。

验证相机按协议改为训练pool，禁用训练内test rollout，使用最终固定checkpoint。自定义可恢复sampler的独立seed0 RNG流与官方DataLoader不完全相同。U接口阴性检查延到dev，未训练U。smoke的两份滚动状态文件被正式训练更新，旧hash不能重验；不可变吞吐结果、日志及最终阶段hash保留。评估入口在五小时续查时完成，训练结束至检查之间约12分钟空闲监督。这些偏差均不作为已排除的失败原因。

## dev观察与结论边界

准确外参0/32成功，均执行150步，无非有限动作；0次EEF到目标距离小于5cm，0次夹持。各root最大对象高度均值0.820734m。root1000的目标平移增量总和约[-0.00091,-0.00114,-0.07668]m，x/y增量很小；这是目标增量之和，不是实测EEF位移。逐根结果见[results/dev_per_root.csv](results/dev_per_root.csv)，原始动作、高度、成功/夹持标签在results/traces/，未删除失败根。

固定观测下，10°metadata误差导致30×3平移动作差Frobenius范数均值约1.623mm，旋转分量差范数约0.000306rad；夹持通道符号分歧比例均值0.084。这些是动作张量差，不能当作任务或EEF位姿误差。zero/shuffle也改变输出，故C并非数值上完全忽略raymap；在baseline地板下仍无法推断成功率影响。

RGB-only初始化架构对同RGB下扰动raymap的输出最大差为0，只是接口阴性检查，不是学会任务的U基线。原始chunk及有向平移/旋转差见[results/dev_fixed_observation.jsonl](results/dev_fixed_observation.jsonl)、[results/offline_action_audit.json](results/offline_action_audit.json)。

正式设置与dev的0/32分开：

| 正式设置 | 状态 | success / n |
|---|---|---|
| C-clean | NOT_RUN | NA / NA |
| C-persistent-5 | NOT_RUN | NA / NA |
| C-iid-5 | NOT_RUN | NA / NA |
| C-persistent-10 | NOT_RUN | NA / NA |
| C-iid-10 | NOT_RUN | NA / NA |
| C-moved-correct | NOT_RUN | NA / NA |
| C-moved-stale | NOT_RUN | NA / NA |

主对比persistent10−iid10、5°诊断、移动stale−correct、discordance、bootstrap95%区间与0/5/10°成功曲线均NOT_RUN。冻结的50个test root与噪声轴仅是计划，不能算已执行样本。移动方案围绕名义workspace_center位移并重新朝向；原pose有target jitter，实际旋转角另存；边界符号按结果前几何反向。该协议解释已注明且本轮未执行，供研究者后续审查。

## 资源与交付

GPU按阶段起止并包含轮询尾部的保守分配约4.642h，上限8h；torch reserved峰值5.182GiB；分钟采样进程树RSS峰值2.375GiB。下载保守统计0.521GiB，新增磁盘采样峰值9.709GiB。详见[resource_summary.json](resource_summary.json)和logs/resources.jsonl。RSS/设备显存/磁盘是分钟采样，不能声称没有采样间峰值；torch另记录allocator峰值。

模型/仿真在dev地板处停止，早于12:26:35计算截止；最终13:26:35上限未改变。没有新worktree，没有修改系统Python/CUDA/驱动/ROS/旧项目，没有Git index、commit/push操作。原始计数见[actual_counts.json](actual_counts.json)，阶段exit与hash见stages/，恢复和实际命令见[RECOVERY.md](RECOVERY.md)，交付一致性见[delivery_integrity.json](delivery_integrity.json)。环境、权重、数据、镜像、缓存、完整XML和日志留本地；原创小型成果由主研究者独立复核后公开同步。

**下一步应先取得可信的官方行为基线，再研究标定时间相关性。** 专家回放和接口检查降低了明显动作/通道接错的疑虑，但没有证明实现与论文等价。研究者可先审查数据/依赖/采集版本、训练过程及先验推理的数值一致性，或取得可信官方checkpoint；目前不能指定根因、提出新网络必要性、宣称鲁棒或科学无效。本轮停止，不追加实验。
