# Gate 1 数据与时间约定

## 原始数据证据

官方 Square PH：`v1.5/square/ph/low_dim_v15.hdf5`，revision
`74fa018461f479cd9fd15b924a16103012096203`，文件 SHA256
`45d8cabb6d57a4c03e839aa5e4b3e58fb60fe8bd20e1951fec563a2abfd14951`。
[官方文件发布页](https://huggingface.co/datasets/robomimic/robomimic_datasets/blob/74fa018461f479cd9fd15b924a16103012096203/v1.5/square/ph/low_dim_v15.hdf5)。

实际 200 条示教、30,154 次转移；episode 长度 107–236。官方 mask 为 180 train /
20 valid（另有比例子集 mask，不使用）。每条 `data/demo_N` 包含 `actions`、
`states`、`obs`、`next_obs`、`rewards`、`dones` 及 XML/env metadata。
具体 shapes/dtypes、10 个观测字段见 `data_audit.json` 和 `logs/hdf5_structure.txt`。

`states[t]` 是 MuJoCo flattened simulator state，不是动作；其中时间字段在 demo_0
逐步相差 0.05 秒。数据元信息与实际运行环境均为 **20Hz / 50ms**，仿真积分步长
0.002 秒。1、2、4 个控制步分别为 50、100、200ms。

## 转移含义

[官方 v0.4 提取代码](https://github.com/ARISE-Initiative/robomimic/blob/7c66e7a41b5d9dcc905b1a68346bfee1b49b79c9/robomimic/scripts/dataset_states_to_obs.py#L110)
直接保留 `actions` 与 `states`，用 `states[t]` 恢复当前观测，用 `states[t+1]`
恢复 `next_obs[t]`，末项通过最后一个 action 执行得到。
实际全数据所有字段满足 `next_obs[t] == obs[t+1]`（最大绝对误差 0）。
这证明文件内转移连续性；额外使用源码与状态恢复验证语义，不能只依赖长度。

对本实验选择的原始同步状态分量，采用：

`obs_selected[t] = observation(states[t]) → actions[t] → next_obs_selected[t]`。

例如 demo_0 的 t=10：eef position 为
`[-0.069275985, 0.020184002, 0.998143434]`，action 为
`[-0.002, 0.357, -0.243, 0.013544749, 0.040544286, 0.142031029, -1]`，
next eef position 为 `[-0.067999793, 0.025860784, 0.994999545]`。
完整数值例子在 `data_audit.json:transition_example_t10`。

控制器是 BASIC composite 下的 OSC_POSE，固定 impedance、world reference frame。
7 维输入是归一化的 `[delta_xyz, delta_axis_angle_xyz, gripper]` 控制命令，
不是绝对位置或真实执行位移。平移范围缩放到 ±0.05m、旋转到 ±0.5rad，
gripper 符号控制开合。代码见
[OSC set_goal](https://github.com/ARISE-Initiative/robosuite/blob/51cc01785bab80ffeed20da15e67d7dd4140e76a/robosuite/controllers/parts/arm/osc.py#L225)。
`control_delta=true`、`input_ref_frame=world`、`lite_physics=false` 等原元信息保持不变。
控制目标每 50ms 更新，底层动力学和接触决定真实运动；正常响应滞后不当成日志 delta。

## 训练前发现的派生观测缓存问题

官方 v1.5.1 `object` 的顺序为相对 eef 位置 3 + 相对四元数 4 + 世界位置 3 +
世界四元数 4。前 7 维传感器依赖 `obs_cache` 中的 nut pose，却在 nut 绝对
pose 的 sensor 之前更新，见
[nut sensors 顺序](https://github.com/ARISE-Initiative/robosuite/blob/51cc01785bab80ffeed20da15e67d7dd4140e76a/robosuite/environments/manipulation/nut_assembly.py#L562)
与 [相对位姿实现](https://github.com/ARISE-Initiative/robosuite/blob/51cc01785bab80ffeed20da15e67d7dd4140e76a/robosuite/environments/manipulation/manipulation_env.py#L263)。

实际恢复 demo_0/1/2 的所有连续 states，第一次刷新与原文件公共窗口的相对位置
误差 <4.7e−8m；相同物理状态第二次刷新，相对位置会改变，最大分别
0.030786 / 0.022602 / 0.020406m。世界物体 pose 的 7 维误差均为 **0**，eef
position 最大误差 <5.6e−16m。因此不能宣称完整 23 维 object+proprio 都是同一
时刻的纯状态函数，也不能将这个缓存现象当成人工动作 delta 的恢复结果。
原始单条整轨迹 action replay 仍成功（demo_0 127 步，123 步首次成功），但这
不足以消除训练与在线传感器刷新方式的差异。

本实验在任何 optimizer update 前固定只选 `object[7:14]` + 原 eef pos 3 /
quat 4 / gripper qpos 2，共 **16 维**。没有修复、重算或平移动作以外的任何原始值；
三组输入相同。相对派生字段排除在策略输入之外，原 HDF5 不变。
完整逐状态证据在 `observation_cache_diagnostic.json`，摘要及修订哈希在
`observation_cache_summary.json` 和 `data/manifests/pretraining_observation_amendment.json`。

## 加载器与闭环时间

训练样本起点 s，输入为 `obs_selected[s], obs_selected[s+1]`，预测 16 步
`action[s:s+16]`。当前时刻是 s+1，官方 `oa_step_convention=True` 从预测
索引 1 取接下来 8 个动作。`n_obs_steps=2`、`n_action_steps=8`、`n_latency_steps=0`。
[官方 predict_action 的切片](https://github.com/real-stanford/diffusion_policy/blob/5ba07ac6661db573af695b419a7947ecb704690f/diffusion_policy/policy/diffusion_unet_lowdim_policy.py#L155)
由实际类的自动化测试验证。训练不用 padding，所有 16 步目标都在 `[4,T−4)`。

原 DP runner 对非零 latency 会丢弃最新观测/最早预测动作，以模拟推理延迟；本次
不执行该路径。计算期间仿真停止，只在正常 20Hz 控制时间轴推进实际动作。
reset 使用提前冻结的 50 个随机初态；首个历史观测重复只是过去历史初始化。
success 使用官方 `_check_success`：nut 对应 peg 的 xy 容差 <0.03m、z 低于
table+0.05m 且 eef 足够远；400 步内曾成功即记成功，继续到完整 400 步。
