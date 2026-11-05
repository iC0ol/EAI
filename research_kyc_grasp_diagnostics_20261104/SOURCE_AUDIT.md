# KYC 0/32：针对性源码与因果审查

本文件由工作站执行者独立读取固定源码及旧原件形成。当前仅CPU准备；新A/B/C均未运行。Codex/真实DeepSeek的范围审查见notes/01、02及discussion/38、39；38关于reset不重建context的说法已在39明确撤回。

## 可直接核验的实现事实

|问题|固定源码事实|可以及不可以说明什么|
|---|---|---|
|官方训练FBO守卫|`policy_robosuite/train.py:102–105,163–166`各查询一次当前绑定`GL_FRAMEBUFFER`，不完整则`env.reset()`|本地`run_experiment.py`训练/验证循环没有这些守卫，是明确源码差异；守卫也没有逐帧健康保证|
|reset生命周期|`robosuite/environments/base.py:104,274–284,338–340`默认hard reset重新加载model、sim并创建offscreen context；HDF5没覆盖这些默认值|guard/reset还可能重新随机化LiftRand几何，不能把两臂图像变化只解释为FBO修复；`reset_from_xml_string`为deterministic路径，A/B另行验证实际sim|
|150与300|`train.py:264`通用默认300；`reproduce/paper_runs.yaml`四个ACT Lift配置覆盖150；本地`default_args`和`evaluate.py`为150|本地未因只跑150而偏离作者Lift专用配置。不能把300当作本次标准|
|训练/验证输入|本地直接使用官方`EpisodicDataset`，train0..199/crop、val200..209/id；getitem设置float32状态、选相机、forward/render、flip、RGB/255、与Plücker共同crop、动作/mask归一化|验证相机文件本地固定train，官方load_data使用args.test_poses_file；这是验证-only配置差异，不等于训练RGB坏。当前C_config的test文件本身也是train，需区分通用默认与本次实配|
|单训练场景|`run_experiment.py:42–45`一个make_env(0)给200训练demo和10验证demo共享；Dataset不按demo恢复XML|HDF5原示教无逐demo XML，单一随机几何是否与每条示教匹配未获证明；不能仅查FBO而忽略场景身份|
|动作语义|官方`action_wrapper.py`将六维delta加到上次绝对目标；旋转是轴角坐标加法；夹爪末维不累加。底层OSC为absolute/world，无interpolation|A/B不重新从实际EEF积分、不改成旋转矩阵组合、不裁剪/平滑/缩放动作；另观测实际送入base.step的绝对命令|
|成功接口|官方eval用reward==1，本地旧eval用原_check_success；HDF5 sparse reward、默认scale1|新A/B逐步同时记录并要求一致；reach沿用EEF-cube距离<0.05m，grasp调用原_check_grasp；不改变成功标准|
|执行算术|官方eval与旧evaluate是policy返回转float32再按float32 stats乘加|旧离线分析的float64反归一化不能用于本轮控制。候选已在准备阶段改为官方float32，另核对policy实际返回与内部捕获逐位一致；没有新ACT因此不是新实验结果|

## 旧结果的有效边界

旧training_progress记录60003更新、20001epoch、16462.3304668训练秒（约4.57h）。实际training_steps日志记录loss/l1/kl、demo_order、耗时和显存；没有逐帧RGB、crop参数、最终训练tensor、FBO/EGL或逐样本time/camera链。loss下降不能补足图像健康证据。

旧准确dev为32物理root，0 success/reach/grasp；另一次repeat不是新独立root。主审本轮亲看旧dev1000初始PNG正常；已证实的条纹/缓冲故障主要来自后续diagnostics，并有局部owner-context释放修复证据，不能泛称旧dev所有图像坏。原训练全程是否受同一问题影响仍UNKNOWN。

旧expert 10/10以make_env(42+i)+直接set_state回放，提供替代场景选择依据，但不是本轮阳性。新A必须通过与B同一个reset_from_xml+state+set_init_action+controller/RNG恢复路径。CPU直接检查：300个demo均未发现逐demo model/XML字段；demo0..3为float64 states，58维，动作数105/102/126/97，共430；不是精确重建原收集XML。生成器CLI默认seed42、生成时seed+demo_id已由源码核实，不进行seed搜索。

## 六问的当前答案与将来所需证据

1. **旧0/32原因是否定位？** 尚未。代码守卫缺口、后来RGB故障、单场景与多demo的几何身份问题是不同层面的证据；目前未建立到旧0/32的完整因果链。
2. **当前checkpoint训练相机下有任务阳性？** 新B尚未运行，未知。旧四状态MAE及20%投资门不用于本轮放行，也不能代替任务行为。
3. **弱变化来自学习还是部署/数据/相机？** 尚不能区分。剩余假设包括学习/latent使用、历史训练输入健康、demo场景错配、视角分布及部署生命周期。新A排查控制/恢复，B作同物理初态相机配对，C查当前真实训练输入；4root不能保证唯一归因或泛化。
4. **是否有具体可复现工程错误？** 后续诊断中的owner释放错误已有受控证据，旧导入冲突已修。缺少官方guard是源码事实，新C是否自然触发且影响实际crop/collate尚待测；当前准备的CPU fixture错误已单独保留并修正，不冒称物理/神经网络故障。
5. **最小修复及是否需重训？** 若当前自然错误进入训练tensor，可提出对应guard/owner释放或场景恢复修复；先验不能判断已训练权重是否需要重训。本轮没有训练授权，任何新训练须研究者审批。
6. **是否继续以KYC作F基础？** 待本轮任务行为与因果验收。个别成功仅为有限任务阳性，不代表论文可靠复现；A失败停止B归因，无可信基线则不自动进入F/persistent/IID研究。

所有将来报告必须分开：源码缺口已证实、当前输入/行为实测、旧训练历史因果未证实。源码/资源准确SHA随candidate_manifest冻结；旧项目始终只读。
