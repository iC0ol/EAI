# 环境审计 — Phase 0 / 1

记录时间：2026-10-20T16:58:17.052129+08:00（Asia/Shanghai）。所有结果来自实际工作站检查。

| 项目 | 实测结果 |
|---|---|
| 操作系统 | Ubuntu 22.04.5 LTS，Linux 6.8.0-60-generic，x86_64 |
| GPU | NVIDIA GeForce RTX 3090，24576 MiB |
| NVIDIA 驱动 | 550.144.03 |
| nvidia-smi 显示 CUDA | 12.4；这是驱动支持上限，不能当作 Toolkit 安装版本 |
| 系统 Toolkit | /usr/local/cuda-11.8，nvcc 11.8.89 |
| CUDA 可用性 | cuInit=0，cuDeviceGetCount=0，设备 1 个，Driver API=12040；没有测试 PyTorch 或模型 CUDA kernel |
| 物理内存 | 初始 free -h 总量 31GiB，可用 21GiB |
| 磁盘 | 初始 df -h 可用 287G；报告时可用 285.73 GiB |
| 默认 Python | /home/asus/anaconda3 的 Python 3.9.13 |
| 系统 Python | /usr/bin/python3，3.10.12 |
| 已有 conda | /home/asus/anaconda3/bin/conda，22.9.0；没有修改已有环境 |
| 已有 ROS | 环境变量 ROS_DISTRO=humble，/opt/ros/humble；没有安装或修改 |
| 新项目 Python | 3.11.17，独立 .runtime/python + .venv |
| 环境工具 | uv 0.13.3 (x86_64-unknown-linux-gnu)，位于项目 .tools/bin |
| CPU 包 | 全部依赖导入/测试成功，uv pip check 检查 19 个包兼容 |
| GEOS | 3.14.1 |

## 隔离与边界

项目根目录：`/home/asus/research/spatial_intervention_pilot`。Python 运行时、venv、uv、下载缓存、临时文件均在此目录中。
venv 不继承 system site-packages；run.sh 只在子进程中排除 ROS 与动态库搜索变量。
没有执行 sudo、修改系统包/驱动/Toolkit、激活或修改旧 conda、操作机器人、下载权重或安装训练/推理框架。

前后保护哈希检查：113 个文件，变化 0 个。
范围为 inspection_robot_ws/src（排除 .git）以及选定 ROS setup、nvcc、系统 Python、shell 配置和 base-conda history。
这是一份有明确范围的保护快照，不是全系统未变动的证明。详见 protected_before.json 与 protected_comparison.json。

## 网络探测（只取 HEAD，未下载权重）

- https://huggingface.co/api/models/Qwen/Qwen3-VL-4B-Instruct → 200
- https://pypi.org/simple/shapely/ → 200

初始系统 Python urllib 请求 Hugging Face 时发生 SSL UNEXPECTED_EOF，完整错误保留在 logs/audit_initial.log。
随后系统 curl 对同一官方模型 API 返回 HTTP/2 200，见 logs/huggingface_head.log。
最终系统 Python urllib 复查同一端点也返回 200，见 logs/audit_final.log；首次 TLS 错误属于保留的瞬态记录。
元信息端点可访问，不等于已经验证权重文件 CDN 或实际 Hugging Face 下载客户端；后者留待 Phase 3。
没有关闭证书校验或修改代理配置。

## 安装版本

| 包 | 版本 |
|---|---|
| PyYAML | 6.0.3 |
| Pygments | 2.21.0 |
| contourpy | 1.3.3 |
| cycler | 0.12.1 |
| fonttools | 4.67.0 |
| iniconfig | 2.3.1 |
| kiwisolver | 1.5.1 |
| matplotlib | 3.11.2 |
| numpy | 2.4.6 |
| packaging | 26.3 |
| pandas | 3.0.6 |
| pillow | 13.0.0 |
| pluggy | 1.7.0 |
| pyparsing | 3.3.3 |
| pytest | 9.1.1 |
| python-dateutil | 2.9.0.post0 |
| shapely | 2.2.0 |
| six | 1.17.0 |
| tqdm | 4.70.1 |

全部包与下载哈希见 ../requirements.lock。安装过程见 logs/bootstrap_uv.log、python_install.log、
venv_create.log、resolve.log、install.log、dependency_check.log。
字体与 lock 哈希、解释器路径及完整版本快照见 dependencies.json。

## 原始只读命令输出

```text
$ uname -a
Linux asus 6.8.0-60-generic #63~22.04.1-Ubuntu SMP PREEMPT_DYNAMIC Tue Apr 22 19:00:15 UTC 2 x86_64 x86_64 x86_64 GNU/Linux


$ cat /etc/os-release
PRETTY_NAME="Ubuntu 22.04.5 LTS"
NAME="Ubuntu"
VERSION_ID="22.04"
VERSION="22.04.5 LTS (Jammy Jellyfish)"
VERSION_CODENAME=jammy
ID=ubuntu
ID_LIKE=debian
HOME_URL="https://www.ubuntu.com/"
SUPPORT_URL="https://help.ubuntu.com/"
BUG_REPORT_URL="https://bugs.launchpad.net/ubuntu/"
PRIVACY_POLICY_URL="https://www.ubuntu.com/legal/terms-and-policies/privacy-policy"
UBUNTU_CODENAME=jammy


$ nvidia-smi
Tue Oct 20 16:55:03 2026       
+-----------------------------------------------------------------------------------------+
| NVIDIA-SMI 550.144.03             Driver Version: 550.144.03     CUDA Version: 12.4     |
|-----------------------------------------+------------------------+----------------------+
| GPU  Name                 Persistence-M | Bus-Id          Disp.A | Volatile Uncorr. ECC |
| Fan  Temp   Perf          Pwr:Usage/Cap |           Memory-Usage | GPU-Util  Compute M. |
|                                         |                        |               MIG M. |
|=========================================+========================+======================|
|   0  NVIDIA GeForce RTX 3090        Off |   00000000:01:00.0  On |                  N/A |
| 35%   60C    P2            123W /  350W |     930MiB /  24576MiB |     16%      Default |
|                                         |                        |                  N/A |
+-----------------------------------------+------------------------+----------------------+
                                                                                         
+-----------------------------------------------------------------------------------------+
| Processes:                                                                              |
|  GPU   GI   CI        PID   Type   Process name                              GPU Memory |
|        ID   ID                                                               Usage      |
|=========================================================================================|
|    0   N/A  N/A      2233      G   /usr/lib/xorg/Xorg                            133MiB |
|    0   N/A  N/A      2431      G   /usr/bin/gnome-shell                           75MiB |
|    0   N/A  N/A    122903      G   clash-verge                                     4MiB |
|    0   N/A  N/A    569251      C   python                                        296MiB |
|    0   N/A  N/A   1794285    C+G   /opt/todesk/bin/ToDesk_Session                312MiB |
|    0   N/A  N/A   2973769      G   ...cess-track-uuid=3190708988185955192         81MiB |
+-----------------------------------------------------------------------------------------+


$ python3 --version
Python 3.9.13


$ /usr/bin/python3 --version
Python 3.10.12


$ /home/asus/anaconda3/bin/conda --version
conda 22.9.0


$ df -h /home/asus
文件系统        大小  已用  可用 已用% 挂载点
/dev/nvme0n1p2  468G  159G  286G   36% /


$ free -h
               total        used        free      shared  buff/cache   available
内存：       31Gi       8.5Gi       1.7Gi       107Mi        21Gi        22Gi
交换：      2.0Gi       1.0Mi       2.0Gi


$ /usr/local/cuda-11.8/bin/nvcc --version
nvcc: NVIDIA (R) Cuda compiler driver
Copyright (c) 2005-2022 NVIDIA Corporation
Built on Wed_Sep_21_10:33:58_PDT_2022
Cuda compilation tools, release 11.8, V11.8.89
Build cuda_11.8.r11.8/compiler.31833905_0

```
