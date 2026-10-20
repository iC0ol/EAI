# Spatial Intervention Pilot — Phase 0 / 1 / 2

这是离线诊断性先导实验。当前只交付几何场景与有限分辨率标签，等待研究者检查。
没有安装 PyTorch/Transformers、下载 VLM 权重、训练、执行机器人操作或修改已有 ROS/CUDA/驱动。
交接说明原文保留在 `docs/handoff_v0.1.md`。

## 运行

工作目录：`/home/asus/EAI/spatial_intervention_pilot`。
Git 仓库根目录为 `/home/asus/EAI`，项目保留在该工作区的子目录；没有另建 Codex 工作区或 worktree。

```bash
cd /home/asus/EAI/spatial_intervention_pilot
bash scripts/run.sh all
```

此命令依次执行 6 个核心实例检查、生成 12 个审查场景、完整 pytest、独立重生成字节比对、
0.025m 追加分辨率检查和报告更新。无需联网；每一步失败都会返回非零退出码并保留日志。
仅复查测试：`bash scripts/run.sh test`。仅重新生成：`bash scripts/run.sh generate`。
环境重建使用 `bash scripts/bootstrap.sh`，下载的只是 Python 与 CPU 基础依赖，按哈希锁安装。
现有环境正常时无需重建。所有解释器、依赖、缓存和 pytest 临时目录都在本目录下；不激活 conda，
不改用户 shell 配置。`run.sh` 仅在其子进程中排除 ROS/Python 动态库变量，避免环境混入。

## 文件结构

```text
spatial_intervention_pilot/
├── README.md, AGENTS.md, pyproject.toml, requirements.lock
├── configs/pilot.yaml                 # seed=20261020，半径与网格/渲染参数
├── docs/handoff_v0.1.md                # 提供的交接说明原件
├── .runtime/python/                   # 独立 CPython 3.11.17
├── .venv/                             # 独立第三方包，无系统 site-packages
├── .tools/, .cache/                   # 局部 uv 与缓存，Git 忽略
├── src/spatial_pilot/
│   ├── geometry.py, edits.py, scenes.py, oracle.py
│   ├── render.py, make_dataset.py
│   └── infer_vlm.py, evaluate.py       # 明确禁用的后续阶段入口
├── scripts/
│   ├── bootstrap.sh, run.sh, audit_environment.py
│   ├── check_reproducibility.py, check_resolution.py, build_reports.py
├── tests/                             # 真值、合法性、冲突、泄漏、复现测试
├── data/
│   ├── images/                        # 12 张模型可用原图，768×768
│   ├── scenes/<opaque_id>/scene.json   # 完整私有几何与各编辑后位姿
│   ├── public_inputs.jsonl            # 仅原图、规则、半径、候选编辑，无答案/类型
│   └── private_labels.jsonl           # 四状态真值、合法性、路径、净空与局部效应
├── outputs/predictions.jsonl          # 空文件；尚未推理，不能当失败预测
└── reports/
    ├── environment.md, dependencies.json, environment raw logs
    ├── qc_montage.png                 # 12 张原图与私有标签总览
    ├── qc_core_edits.png              # 6 核心场景 × 4 编辑状态
    ├── scene_review.html, edits/      # 48 张私有编辑后审查图
    ├── pilot_summary.md, tests.xml, core_tests.xml
    ├── generation_manifest.json, generation_failures.jsonl
    ├── reproducibility.json, resolution_audit.json
    ├── protected_before.json, protected_comparison.json
    └── logs/                         # 安装、网络、测试、生成与复现日志
```

## 查看与数据边界

先看 `reports/qc_montage.png` 和 `reports/scene_review.html`。HTML 支持点击查看完整原图与四个编辑后状态。
私有 QC 图包含正确标签和绿色求解器见证路径，**禁止用于 VLM 输入**。
公开图只画原始障碍、Start/Goal、半径、坐标尺度和候选最终足迹的虚线框；虚线框并非编辑后观测。
候选操作的精确中心、足迹尺寸及朝向规则同时在 public_inputs 中给出。所有文件名使用不含类型的稳定 ID。
完整 `scene.json`、private_labels、reports 都属于私有数据。

## 几何定义

单位米。机器人半径 0.25m，平面全向，不能代表差速转弯或编辑的物理执行过程。
Shapely 膨胀障碍，四邻接 BFS，逐条验证边线段，不允许穿角或跨过薄墙。
起终点使用真实坐标与经过碰撞检查的局部网格连接，不能无声吸附到障碍外。
对圆弧 buffer 使用 32 段/象限并微量外扩补偿弦近似；物体之间允许零面积边界接触，机器人接触算碰撞。
编辑只允许保持形状与朝向的指定平移。单个不合法编辑、相互冲突的编辑组合抛出不同错误，不混入 F=0。

每个状态同时运行 0.10m、0.05m 网格；不同结果标为 `oracle_unresolved`，F=null，排除主评价。
另对全部状态做 0.025m 检查。F=0 仅表示配置网格图搜索失败，不能证明连续空间不可达。
`path_min_clearance_m` 是**返回的见证路径**对原始障碍和地图边界的最小裕量，不是最大净空路径或通道宽度。

预期模板仅供测试断言；oracle 不读取 EXPECTED 或 family 计算标签。标签来自应用编辑后重新构建的碰撞几何。
主集合为每类 2 个参数化基础布局及各自的旋转/镜像视图，共 12 个。串联/替代路线有 4 对局部编辑相同的匹配视图，
其中仅 2 对属于不同参数布局；这不是 12 个独立拓扑，也还不能检验 H1/H2。

## 版本、审计与待办

`requirements.lock` 锁定全部第三方包与下载哈希；Python/uv 版本固定在 bootstrap.sh。
Pillow 使用工作站 DejaVuSans 字体，字体哈希与 GEOS 版本见 dependencies.json；跨机器复现需要相同字体。
generation_manifest 保存配置哈希、源代码 commit、seed、失败/未决计数、核心样本及匹配组。
reproducibility 检查重新生成后的全部 data 文件（含 PNG）逐字节相同；时间戳不参与比对。
保护清单对原有机器人 src 与选定 ROS/CUDA/系统/用户配置文件做前后哈希比较，范围见报告，不能声称审计了全部系统。
按用户明确要求，本地 Git 与公开 GitHub 仓库 `iC0ol/EAI` 同步源码和全部场景/测试结果；
Python 运行时、环境与缓存不上传。历史审计日志保留迁移前路径，当前运行路径以最新报告为准。
这里的“private_labels / 私有 QC”表示不向模型输入暴露的评估真值，不表示这些文件不在公开仓库中。

下一步只能在研究者确认场景与标签后进行。infer_vlm / evaluate 当前只返回明确的“未开始”提示；
Phase 3–5 逻辑尚未实现，不能解读为已经验证 VLM、JSON 解析或评估指标。

实现时查阅的主文档：[Shapely buffer](https://shapely.readthedocs.io/en/stable/reference/shapely.buffer.html)、
[Shapely covers](https://shapely.readthedocs.io/en/stable/reference/shapely.covers.html)、
[uv CLI](https://docs.astral.sh/uv/reference/cli/)。依赖行为以锁定版本与测试结果为准。
