**审查声明**：只读查看指定任务书、AGENTS、官方/本地源码与既有结果；未运行、未修改；未读新notes中的Codex意见。旧20% MAE门已被本轮任务书取代，本审查不以它阻止A/B/C闭环。

## 1. 官方与本地的三层区分

**明确代码缺口**
- 官方`train.py:102-105,163-166`在epoch边界用`glCheckFramebufferStatus(GL_FRAMEBUFFER)`查完整性，失败则`env.reset()`；本地`run_experiment.py:58-82`没有OpenGL导入、FBO检查、GL错误查询或失败reset。这是明确缺口。
- 但官方检查不是真正重建：它只查当前绑定的FBO，未绑定/查询robosuite的`offFBO`，也无`glGetError`；`env.reset()`（`environments/base.py:261`）只重置仿真，不重建`MjRenderContext`。真正重建需`add_render_context`/`free`（`binding_utils.py:1143-1148,1181-1187`）。因此“官方有守卫、本地没有”是源码事实，但官方守卫本身不完整，不能据此追认历史根因。
- 成功/初态不一致：官方`eval.py:85,173-184,229-240`用`eval_max_steps`、`env.reset()`（train.py不传`init_state`）、`set_init_action()`、`reward==1`；本地`evaluate.py:23-24,54-81`用`reset_from_xml_string`+state+RNG+相机、`_check_success`。这两处不是同一接口，A必须同时记录`reward==1`与`_check_success`；若不一致，本地0/32可能含判定伪影。
- 150与300：官方`train.py:264`默认300，但`paper_runs.yaml`的Lift配置均覆盖`eval_max_steps:150`（如6-9、30-33行）；本地`default_args`与`evaluate.py`实际5×30=150。本地与本文Lift标准一致，**不能把通用300当成本实验标准**。
- 预处理：官方`utils.py:456-471`训练用`args.transform`（crop）、验证用`id`；本地`run_experiment.py:43-44`同样是crop/id，训练预处理一致。但本地验证相机文件用`train_cameras.json`（第44行），官方`load_data`用`args.test_poses_file`（默认`test_cameras.json`，466-471行），属验证-only差异。
- 本地`make_env`硬编码`original=False`（`experiment_lib.py:21`），官方`train.py:47-48`尊重`args.original`；当前C_config为`original=false`，对应randomized而非fixed，不能称fixed paper条件。
- eef_delta累计：双方共用`action_wrapper.py:18-47`，本地`reset_root`后`set_init_action`；`semantics.json`十次专家回放10/10、首命令误差<2.4e-7，支持累计语义，但A须在**实际A/B reset路径**下复验。

**目前可复现训练输入污染**
尚未成立。旧RGB报告`02:82-97`的坏图来自诊断三入口路径，不是训练`EpisodicDataset`；Stage C必须证明坏图进入真实训练张量`data['image']`，不能只凭一次render或FBO状态。

**旧训练因果**
旧训练日志只有loss/l1/kl（`run_experiment.py:69-70`），无逐步图像、FBO、时刻/相机/crop记录；旧报告`02:107-111`明确历史RGB/GL缺失。loss下降、修复后的健康图、单点FBO状态都不能证明旧4.57小时训练发生过同样污染。0/32原因仍UNKNOWN。

## 2. Stage A/B：替代物理root与匹配阳性

现有`validate_semantics.py:16-26`已用`make_env(42+i)`+`states[0]`对demo0..9做专家回放，`semantics.json`为10/10、首命令误差<2.4e-7、EEF轨迹误差小；`data_split.json:41-50`明确无逐demo XML。这是当前最强替代证据，但只是替代root，不是原示教场景。

建议：
- A用demo0..3，`make_env(42+i)`+`states[0]`，**一次冻结XML+state**；A/B必须使用同一`reset_from_xml_string`+state+`set_init_action`路径，不能用semantics的直接`set_state`代替。记录`source_default_seed=42+i`、`per_demo_XML_present=false`，不得称原场景完全重建。
- A四次专家回放，≤150步；同时记录`reward==1`与`_check_success`、EEF/物体高度。若任一专家失败或两种成功判定不一致，停止，不进入B，先修控制/初态/判定，不能归咎网络。
- B仅在A 4/4通过后：四个替代root × train相机i+1（训练窗口[i,i+1,i+2]的中间相机）与旧dev root1000+i的**T仅作相机位姿**配对，8条，≤150步。不得称旧dev物理root；不要挑选root/相机。A+B共12条，无追加。
- 该B不能直接重放旧dev 0/32的物理root；它是在新替代root上区分“专家阳性 vs 策略失败”。A阳性、B训练/开发均阴性→策略/评估；B训练阳性、开发阴性→相机分布；A失败→控制/root问题。

## 3. Stage C：坏RGB是否进入训练张量

- 用真实训练路径：`EpisodicDataset`（`utils.py:354-392`）以`transform='crop'`（`run_experiment.py:43`）构造，`default_collate`（63行）后、`policy(data)`（65行）前抓取`data['image']`；同时保存crop前raw、crop参数、crop后tensor。
- 只有坏图出现在该tensor中，才能说“当前坏RGB进入训练预处理”。若raw坏但crop后tensor正常，不能算训练输入污染；若只在单次render/FBO状态异常，也不能。
- 比较sample0 raw与已知健康raw时注意：旧健康输入用`id`，训练用`crop`，应比较crop前raw或复现crop；不得把健康修复后的图当旧训练历史证据。
- 若C当前复现坏图并进入tensor：记录为**当前训练路径污染**；仍不能证明旧4.57小时训练同样发生。若C不能复现：记NOT_REPRODUCED，历史因果无法建立，不能仅凭缺失FBO守卫批准重训。
- 训练/验证预处理：crop/id与官方一致；验证相机文件差异需在报告注明，不能混为训练污染。

## 4. 预算、停止与可行性

- 900s硬上限可行：`semantics`十次专家回放合计11.3s，旧dev 33条rollout循环均值约1.26s；A+B 12条加初始化/健康/记录，900s有较大余量。建议子上限：预检/初始化≤120s，A≤120s，B≤480s，C≤150s，余量≤30s；任何子项超限即停，不挪用/扩额。
- 12条轨迹、每条≤150步；单GPU顺序；CPU≤3核/线程、RSS≤16GiB、整卡VRAM≤12GiB、输出≤150MiB；0训练/optimizer/backward。
- 停止条件：A任一失败或成功判定不一致；B非有限动作/异常；C发现坏图进入tensor后仍不得训练；总时超900s；任何root/相机事后挑选；均停止并报告。
- 本轮只给审查与方案，**不批准任何未见的候选集成代码或派发**；协议、代码和准确SHA须另行双审。
