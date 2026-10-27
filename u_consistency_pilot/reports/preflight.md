# 0A 资源审计

结论：**TECHNICAL-BLOCK**。指定模型权重、匹配训练数据/可信 scaler 来源未定位，兼容环境未验证。按资源缺失即停止的约束，未进入加载、动作语义执行验收、分支重现或 G 训练。

## 仓库保护

实际工作目录由 `pwd` 和 `git` 验证为 EAI 仓库；公开报告用 `EAI` 别名代替本机绝对路径。起始分支 `research/m-gate0-live-screen`，commit `9ca5c2e8423d37ec05194c9df9330c0aade69fed`，`git status --short --branch` 显示工作树干净。远端 `https://github.com/iC0ol/EAI.git`。本地和远端均没有同名 `research/u-gate0`，已在同一 checkout 用 `git switch -c research/u-gate0` 建立分支。未新建 worktree、stash、reset、clean 或改写历史。

已读根 AGENTS.md。没有编辑 Spatial，未启动 D/M 实验或改写其结论。起始受保护文件 git 索引摘要 SHA256 为 `e538228da0823252de575f48e67f27bd833ebd7681e60b9c5b31509b4181db1c`，对应命令 `git ls-files -s AGENTS.md README.md 'd_alignment_pilot/*' 'm_direction_pilot/*' 'spatial_intervention_pilot/*' | sha256sum`；交付前重复核对。

## 可核对的资源证据

`outputs/resource_manifest.json` 保存每个搜索范围、文件/目录计数、深度/时间边界、错误数和命中。工作区、HF/torch 缓存及常见数据目录的扫描均完成，按明确排除规则不扫描环境包目录和隐私目录。指定 HF 模型/数据集缓存目录都不存在。精确文件名和预期大小检索均未命中；扫描包括 HF blob 实体，因而不只依赖文件名。

| 范围别名 | 已检查文件 | 状态及限制 |
|---|---:|---|
| EAI | 32,019 | 扫描完成；排除环境、运行时包和受保护目录 |
| HF_CACHE | 120 | 扫描完成；未发现指定模型/数据集仓库 |
| TORCH_CACHE | 172 | 扫描完成；无匹配命中 |
| HOME_DATASETS | 21 | 扫描完成；无匹配命中 |
| HOME_DOWNLOADS / DOCUMENTS / DESKTOP / WORKSPACE | 36 合计 | 扫描完成；无匹配命中 |
| HOME_SHALLOW | 2,369 | 深度有界，780 个目录被深度规则剪枝 |
| MEDIA_0 | 309,840 | 20 秒到时停止；另有深度剪枝，**不是外接盘完整扫描** |
| OPT | 1,174 | 有 1 次权限错误及深度剪枝；不触碰 ROS |

另一次全局 `rg --files` 检索因外接盘规模主动中止（退出码 130）；停止前 `ps` 观测该检索已运行 92 秒，总时长没有保存，不作为完整扫描的证据。没有申请特权访问、读取认证文件、跟随目录软链或解包未知归档。不能据此声称所有磁盘、任意重命名归档内部绝无所需资源；本结论是本次有限资源审计未定位到可用可信资产。

工作区命中的是既有 diffusion-policy 的 PushT **代码**；既有 D 数据为其他任务。它们不满足指定 LeWM 权重/训练分布/scaler 来源要求。没有拿旧 DP/LIBERO 或小数据替代，没有新下载约 13 GB 数据，没有建立 U 环境。

模型与数据 revision、文件大小和 SHA256 均从研究者提供的 pins 原样保存。无本地文件可哈希核验，故它们是**期望 hash**，不是下载验证成功记录。没有声称 ACID 官方 IDM 权重存在；本次未阅读或复制论文内容，论文链接仅作协议来源登记。

## 硬件和已有环境

RTX 3090，24,576 MiB；驱动 550.144.03。RAM 总量 33,514,676,224 B。工作区可用磁盘审计快照 264,364,638,208 B，足够研究者建议的约 110 GB 预留，但未解压，不是对实际解压体积的测量。

仅检查包分发元数据，没有 `import torch`、模拟器导入或 CUDA context。已检查 8 个现有环境前缀，完整包版本在 `environment_packages.json`。D 环境有 torch 2.2.2+cu121 / torchvision 0.17.2+cu121 / numpy 1.26.4 / h5py 3.11.0；VLM 环境有 torch 2.6.0+cu124。所有已查环境的分发元数据均未发现 stable-worldmodel、pymunk、pygame 或 gym/gymnasium。元数据缺项不等价于穷尽全部源码/可编辑安装兼容性检查；**兼容性未通过验收**，没有据此搭新环境或无界移植。

审计期间已有 Python CUDA 进程，初查运行已超过一天；后续出现桌面远程会话 GPU 进程。它们不属于 U，均未终止或修改。初次 GPU 总显存 581 MiB；报告的后续快照为 869 MiB，另一次查询为 914 MiB。不能把这些后台/桌面占用算成 U 的 VRAM 或 GPUh。

## 实际执行与环境锁定

从 EAI 根目录执行：

```bash
PYTHONDONTWRITEBYTECODE=1 /usr/bin/time -v /usr/bin/python3 -I -B \
  u_consistency_pilot/scripts/run_gate.py --output u_consistency_pilot/outputs
/usr/bin/python3 -I -B u_consistency_pilot/scripts/summarize.py \
  --outputs u_consistency_pilot/outputs
```

首条命令实际退出码 **2** 是脚本定义的资源阻塞状态；资源候选需要审查时退出码 3。并非训练命令失败或训练已开始。审计过程 `2026-10-27T07:42:09.079805Z` 至 `07:42:31.573481Z`，脚本内部墙钟 22.493663371074945 秒；外层 time 为 22.55 秒，user 5.66 秒、sys 2.52 秒，最大 RSS **28,404 KiB**，swap 0。实际摘要命令结果在 `validation.json` 登记。

审计使用既有系统 Python **3.10.12**，只有标准库；二进制 hash、内核、glibc 和配置 hash 见 versions.json，没有安装依赖。系统 Python、CUDA、驱动和已有环境均未修改。没有可供锁定的实验环境；不能将既有包清单称为已验证的 LeWM 运行锁。审计后仅增加公开日志中 GPU 进程路径取 basename 的脱敏，并把空 CSV 的换行规范为 LF，未重跑扫描；实际执行版与交付版脚本 hash 均登记在 audit_execution.json。

`audit_execution.json` 的实测峰值是审计进程 RSS，**不是整个 agent/桌面的累计峰值**。全任务精确并发 RAM 峰值未测得，预算中保留 null；主机 RAM 和显存仅有时点快照。U 没有 GPU 进程，GPU 占用时段累计为 0，任务 GPU 显存为 0。实验吞吐和语义指标全部 NOT_RUN。

## 未通过的 0A 验收

strict load、固定预处理/latent 来源、scaler 重建及 ddof 差异实测、真实索引/flatten 顺序/单位、5 步端点、控制频率、6 roots × 2 重放、隐状态/接触/图像与下一块一致性、NaN/常量 latent/色序/端点检查、RNG 和吞吐：**全部 NOT_RUN**。HDF5 README 与训练 .lance 接口差异尚未核验，没有重建数据框架。未选择实际 goal、τ 或校验 J<1 与官方 success 的一致性。详见 action_semantics.md。
