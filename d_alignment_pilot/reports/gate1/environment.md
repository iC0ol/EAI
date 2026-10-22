# Gate 1 环境与部署

审计日期：2026-10-22，Asia/Shanghai。EAI 起点为
`687d75d53c0f30ea630762312b65dd3d0ff06d8b`，独立分支 `research/d-gate1`。
所有新文件、环境、缓存、源码依赖、数据和结果均位于 `d_alignment_pilot/`。
原工作区 903 个已跟踪文件的基线哈希见 `preserved_before.json`。

## 硬件和资源限制

| 项目 | 实测 |
|---|---|
| GPU | NVIDIA GeForce RTX 3090，24,576MiB |
| 驱动 | 550.144.03；nvidia-smi 标示最高 CUDA 12.4 |
| 初始 GPU 占用 | 586MiB，包含桌面及已有其他 Python 进程；没有停止这些进程 |
| CPU | Xeon E-2224，4 核 / 4 线程 |
| RAM | 31GiB 总量，约 23GiB available |
| Swap | 2GiB，其中已用约 1.8GiB |
| 初始磁盘 | 254GiB 可用 |
| 本实验限制 | 1 个模拟环境；Torch/BLAS/Numba 2 线程；数据窗口单进程预载 |

原始硬件记录见 `logs/nvidia_before.txt`、`memory_before.txt`、`disk_before.txt`、
`cpu.txt` 和 `uname.txt`。没有使用 sudo，没有修改驱动、系统 CUDA、ROS2、
系统 Python、inspection_robot 或原 spatial 项目。

## 固定软件

| 软件 | 版本 / 官方 SHA |
|---|---|
| Python | 项目 `.venv`，3.9.13；基于已有 Anaconda 解释器创建 |
| PyTorch / torchvision | 2.2.2+cu121 / 0.17.2+cu121 |
| NumPy / h5py | 1.26.4 / 3.11.0 |
| MuJoCo | 3.2.3，DeepMind 官方 Python bindings |
| robomimic | 0.4.0，`7c66e7a41b5d9dcc905b1a68346bfee1b49b79c9` |
| robosuite | 1.5.1，`51cc01785bab80ffeed20da15e67d7dd4140e76a` |
| Diffusion Policy | `5ba07ac6661db573af695b419a7947ecb704690f` |
| diffusers / HF hub | 0.11.1 / 0.23.4 |

完整 transitive pins 见 `requirements.lock`。框架通过固定源码路径导入，并未以
可浮动的 pip 最新版本替代。`pip check` 实际通过，记录见 `logs/pip_check.txt`。
PyTorch 自带 cu121 用户态库安装在独立 venv 中，不是系统 CUDA 升级。
实际模块路径与运行时版本另存 `runtime_versions.json`。训练启用 TF32、关闭
cuDNN benchmark，没有强制 deterministic algorithms；固定种子与哈希用于追溯，
不保证跨硬件或驱动的逐 bit checkpoint 重现。

审查当前官方仓库及 v0.5 release 后，发现
[v0.5 lang_utils](https://github.com/ARISE-Initiative/robomimic/blob/ae5799f0fae05c4559ee1f9645b0f77eb5251929/robomimic/utils/lang_utils.py)
会在模块导入时加载 CLIP 权重。执行采用已有 v1.5 支持的
[v0.4 环境包装器](https://github.com/ARISE-Initiative/robomimic/blob/7c66e7a41b5d9dcc905b1a68346bfee1b49b79c9/robomimic/envs/env_robosuite.py)
和原始 DP 低维模块，避免这一副作用。没有下载任何预训练权重。
当前主分支和选定 release 的 SHA 全部记录在 `configs/versions.json`。

## 部署障碍及已解决事项

系统 Python 3.10 缺少 ensurepip，因此未安装系统 venv 包，改用已有 Python 3.9
建立隔离环境。早期 pip 启动继承 ROS PYTHONPATH，产生外部元数据告警；后续
启动器清除继承路径并设置 `PYTHONNOUSERSITE=1`。没有安装或修改 ROS 包。
默认 Aliyun mirror 下载停滞，改从官方 PyPI 安装完全相同的 pins。
所有实际安装输出与早期错误保留在 `logs/`。

低维模式不启用任何 renderer；缺少可选 `robosuite_models` 的告警不影响 Panda。
GPU 已实际完成一次 batch=256 的 forward/backward，**0 次 optimizer update**：
16,553,233 参数，包含冷启动 0.440 秒，峰值分配 490,484,736 bytes。
这只是部署 smoke，不是策略训练或性能结果；详见 `gpu_smoke.json`。

启动器禁用 WandB、HF/Transformers 网络下载，缓存及未来临时构建目录均指向本项目。
原始 HDF5、external、venv、缓存和 checkpoint 被本目录 `.gitignore` 排除。

## 结案执行障碍

首次交付时 5 次训练及闭环评估完成，第六次 Larger seed 43 最后记录 42,400
更新，进程和 driver 均不存在，无最终 checkpoint、traceback 或进程退出状态。
原始事实保存在 `interruption.json`。当时没有额外尝试授权，未重跑。

2026-10-23 研究者明确授权补跑同一条件和 seed 一次。重查同一会话的历史
记录，2026-10-22 22:53:21 +08:00 已用 5 小时额度达到 100%，`task_complete`
带明确错误码 `usage_limit_exceeded`：**额度耗尽确实结束了智能体轮次**。
本地训练还继续到 23:28:08，没有退出码证明其随后如何终止。不能把轮次结束与
训练进程退出的因果关系混为一谈，也不推断为驱动、显存、CPU 或数据问题。
只读查询 23:15–23:35 内核日志返回 `-- No entries --`，无法据此排除 OOM。
证据为 `interruption_diagnosis.json`；原始私有会话、账户标识与凭据均未导出。

当前实时额度工具在补跑前返回 5 小时剩余 91%、每周剩余 67%，允许继续，未使用
任何重置券。[OpenAI 官方说明](https://learn.chatgpt.com/docs/pricing#what-happens-when-you-hit-usage-limits)
目前说明活跃轮次可在公平使用范围内继续；它不提供本次历史本地进程的退出原因。

补跑保持原有独立 venv、单环境与 2 线程限制，用 `start_new_session=True` 的
本地 supervisor 顺序执行原冻结训练器与评估器，记录子进程 PID、exit code。
不自动重试，不修改系统服务。授权与七次尝试的预算说明见 `retry_authorization.md`。
续办时可用磁盘约 245GiB，RAM available 约 23GiB；这不能代表中断时的资源状态。

授权补跑已完成，训练和评估子进程退出码均为 0；现为六个完整策略、300 回合。
补跑 GPU 占用墙钟 0.330972 h，峰值分配 707,224,576 bytes、保留
771,751,936 bytes；其余环境版本、硬件配置与线程数均未改变。
