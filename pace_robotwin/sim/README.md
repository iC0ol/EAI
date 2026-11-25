# PACE RoboTwin 仿真环境

仿真客户端使用 PACE `5d0f4a92415f8899963cba7f0f929f1b9c5f75db` 自带的 RoboTwin 2.0 副本。PACE 记录的 RoboTwin 基础版本为 `13c3c47ff4312dd62484bcd51be034af55c062d1`。安装树为 `vendor/RoboTwin-PACE`，其中任务、控制器、相机、语言与评估代码沿用上游，缓存兼容性由 `pace.robotwin.load_cached_scenes` 验证。[PACE 安装说明](https://github.com/niejunnan25/PACE/blob/5d0f4a92415f8899963cba7f0f929f1b9c5f75db/README.md#robotwin-evaluation)

两项任务沿用 `demo_clean`、ALOHA AgileX 双臂和三个 D435 RGB 视角。每张图为 `uint8[3,240,320]`，动作接口为绝对关节目标，维度为 14。官方步数上限分别为 `stack_blocks_three` 的 1200 和 `place_phone_stand` 的 400。缓存内的语言通过官方 helper 从 `unseen` 模板生成。

## 运行

从 EAI 根目录执行下面的命令加载仿真进程环境。该环境采用现有系统 Python 3.10 建立 venv，并使用 PyTorch 2.4.1 的 CUDA 11.8 wheel 编译 CuRobo v0.7.8。CUDA、Vulkan 和驱动均通过现有工作站设施使用。仿真缓存、编译产物和临时文件在 `runtime/sim` 下。

```bash
source pace_robotwin/sim/runtime.sh
"$PACE_SIM_PYTHON" "$PACE_ROBOTWIN_ROOT/pace/scripts/evaluate.py" --help
```

首次安装可从已有的 `vendor/PACE` 本地克隆同一 commit。以下命令将所需的发布资源提取到 `assets/sim/robotwin` 并生成本机资源路径，再安装仿真运行时。

```bash
git clone --local --no-hardlinks pace_robotwin/vendor/PACE pace_robotwin/vendor/RoboTwin-PACE
source pace_robotwin/sim/runtime.sh
/usr/bin/python3.10 pace_robotwin/sim/fetch_assets.py
ln -s "$PACE_SIM_ROOT/assets/sim/robotwin/embodiments" "$PACE_ROBOTWIN_ROOT/assets/embodiments"
ln -s "$PACE_SIM_ROOT/assets/sim/robotwin/objects" "$PACE_ROBOTWIN_ROOT/assets/objects"
(cd "$PACE_ROBOTWIN_ROOT" && /usr/bin/python3.10 script/update_embodiment_config_path.py)
bash pace_robotwin/sim/install_runtime.sh
```

资源来自 RoboTwin 发布的 `TianxingChen/RoboTwin2.0` revision `3dc3b798668feb99ac61cc9086d84cbcc3d79186`。提取 `embodiments/aloha-agilex`、`objects/077_phone`、`objects/078_phonestand` 以及 RoboTwin 初始化所需的 `objects/objaverse/list.json` 和 `objects/same.json`，逐文件校验 ZIP CRC 并记录 SHA-256。`demo_clean` 关闭随机背景、杂物和点云。仿真安装采用 PACE 模块依赖的 SciPy 1.15.3 和 NumPy 1.26.4。SAPIEN 3.0.0b1 的 URDF UTF-8 修改和 MPLib 0.2.1 的 screw planning 修改按 PACE 官方安装脚本执行，只应用于本地 venv。[官方资源发布](https://huggingface.co/datasets/TianxingChen/RoboTwin2.0/tree/3dc3b798668feb99ac61cc9086d84cbcc3d79186) · [RoboTwin 安装手册](https://robotwin-platform.github.io/doc/usage/robotwin-install.html)

## 工程验收

仅用官方缓存 seed 2。默认取其中第一个场景，检查三路 RGB、14 维关节观测、绝对关节动作后的物理状态变化、成功谓词及 reset 后的计数。`--expert` 另行执行官方脚本专家，验证成功时的计数停止和再次 reset。

```bash
source pace_robotwin/sim/runtime.sh
"$PACE_SIM_PYTHON" pace_robotwin/sim/verify_environment.py --index 0 --expert \
    --output "$PACE_SIM_RUNTIME/engineering.json"
```

工作站上的两项验收均在缓存 seed 2 的场景 `300000` 通过。两项任务的官方专家都触发了成功终止，再次初始化将成功标记和动作计数复位。验收索引位于 `runtime/sim/READY.json`，依赖清单位于 `runtime/sim/installed.txt`。单独运行仿真时，3090 的全机显存峰值为 6168 MiB。`stack_blocks_three` 和 `place_phone_stand` 的进程峰值 RSS 分别为 3.93 GiB 和 4.38 GiB。
