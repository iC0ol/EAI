# Spatial Intervention Pilot — Phase 0–3.5

## Phase 3.5：错误来源定位（已完成）

本轮只使用原六核心样本，派生 24 张 NONE/A/B/AB 后态图和 6 个独立目标重叠问题。
后态图只包含当前几何、障碍和 Start/Goal，不含编辑标记、类别、真值或求解器路径。
诊断模型只读专用清单与图像，不读私有映射、旧预测或真值；独立评估在全部推理结束后进行。
沿用 Phase 3 的模型、revision、环境、随机种子与解码参数，使用预先冻结的两个新英文 prompt。

- [phase3_5_diagnostic.md：结论、限制、逐样本比较和原文链接](reports/phase3_5/phase3_5_diagnostic.md)
- [24 张后态诊断图预览](reports/phase3_5/poststate_inputs_montage.png)
- [原始回答、解析错误、耗时和显存](outputs/phase3_5/predictions.jsonl)
- [配对评估与独立重叠检查](reports/phase3_5/evaluation.json)
- [输入清单与派生图](diagnostics/phase3_5/inputs/)；[独立几何敏感性与半径能力诊断](diagnostics/phase3_5/private/geometry_diagnostics.json)

模型对 24 图全部回答不可达，14/24 正确，与恒不可达基线相同；10 个可达图全部漏判。
18 项配对由旧 6/18 变为新 8/18，但 7 项恢复伴随 5 项退化，不能据此隔离编辑后状态想象困难。
重叠检查正确 40/54、误报 14 项；因 54 项真实重叠全为否，不据此声称一般空间感知能力。
物体尺寸±5%和机器人半径±0.02m、两分辨率下的240次搜索无标签翻转。见证路径可贴边至约1.25mm，
而可达图的网格圆盘容量约0.80/0.90m，不能把见证最小裕量当通道余量。

新结果分置于 `diagnostics/phase3_5/`、`outputs/phase3_5/`、`reports/phase3_5/`，没有混入原 data 或覆盖 Phase 3。
阶段命令为 `bash scripts/run_phase3_5.sh prepare|geometry|infer|evaluate`，报告入口为
`PYTHONPATH="$PWD/src" .venv/bin/python scripts/report_phase3_5.py`。已有产物拒绝覆盖。
测试：`PYTHONPATH="$PWD/src" .venv/bin/python -m pytest tests tests_vlm tests_phase3_5`，94项全部通过。
本轮停止，等待研究者复核；不训练、不扩充基础场景、不升级环境。

以下 Phase 3 与 Phase 0–2 记录保留作历史说明。

这是离线诊断性先导实验。Checkpoint B 已经研究者检查，Phase 3 部署与六核心样本推理冒烟现已完成。
几何环境和原始数据完整保留；VLM 采用独立 `.venv-vlm`，不训练、不扩充正式数据，也不修改已有 ROS/CUDA/驱动。
交接说明原文保留在 `docs/handoff_v0.1.md`。

## Phase 3：独立 VLM 冒烟

模型为 `Qwen/Qwen3-VL-4B-Instruct`，revision `ebb281ec70b05090aa6165b016eac8ec08e71b17`。
torch 2.6.0+cu124、torchvision 0.21.0+cu124、Transformers 4.57.1，独立依赖见 `requirements-vlm.in` 和
`requirements-vlm.lock`，不会改原 `requirements.lock` 或 `.venv`。

实际准确率为 F_A=3/6、F_B=2/6、F_AB=1/6，完整组合=0/6。全部结构化回答可解析，没有 OOM；
生成平均 4.905 秒，torch peak allocated 8842.2MiB。结果暴露了空间判断错误，但不能从这六例独立归因于纯组合推理。
当前停止，等待研究者检查。

- [Phase 3 实际结果、错误案例与显存/耗时报告](reports/phase3/smoke_report.md)
- [六核心原始预测、解析结果和错误字段](outputs/phase3/core/predictions.jsonl)
- [独立后评估结果](reports/phase3/evaluation.json)
- [首次模型调用前冻结的配置与 prompt 哈希](reports/phase3/frozen_run.json)

推理只读取 `public_inputs.jsonl` 与选中原图，不读取私有标签/scene/QC/类型；进程审计钩子会拒绝这些读取。
固定英文 prompt：`prompts/spatial_smoke_en_v1.txt`。每条推理保留 prompt 全文、图像哈希、图像张量网格、
图像 token 数、视觉编码器调用次数，以及实际生效的 greedy 参数。

```bash
bash scripts/bootstrap_vlm.sh
bash scripts/run_vlm.sh download
bash scripts/run_vlm.sh single
bash scripts/run_vlm.sh three
bash scripts/run_vlm.sh core
PYTHONPATH="$PWD/src" .venv/bin/python -m spatial_pilot.evaluate
PYTHONPATH="$PWD/src" .venv/bin/python scripts/build_phase3_report.py
```

先单图，再指定三样本，最后六核心；前一阶段的结果原样复用，每个正式样本只生成一次。
另一次模型生成默认值异常的调试尝试单独归档在 `outputs/phase3/debug_sampling_defaults`，不计入评估，
prompt 在修正前后不变。已有输出不会被覆盖，复跑前必须保留历史结果。
仅在全部六核心推理结束后，独立 CPU 评估程序才读取私有标签。
测试命令：`PYTHONPATH="$PWD/src" .venv/bin/python -m pytest tests tests_vlm`，保留原 62 项并新增 13 项。
新增文件分组为 `requirements-vlm.*`、`configs/vlm_smoke.yaml`、`prompts/`、`tests_vlm/`、
`outputs/phase3/` 与 `reports/phase3/`；本地环境 `.venv-vlm/` 与 `.cache/vlm/` 不入 Git。

以下为 Phase 0–2 几何流程；`reports/pilot_summary.md` 保留为 Checkpoint B 的历史报告。

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
│   └── infer_vlm.py, evaluate.py       # Phase 3 公开输入推理 / 独立后评估
├── scripts/
│   ├── bootstrap.sh, run.sh, audit_environment.py
│   ├── check_reproducibility.py, check_resolution.py, build_reports.py
├── tests/                             # 真值、合法性、冲突、泄漏、复现测试
├── data/
│   ├── images/                        # 12 张模型可用原图，768×768
│   ├── scenes/<opaque_id>/scene.json   # 完整私有几何与各编辑后位姿
│   ├── public_inputs.jsonl            # 仅原图、规则、半径、候选编辑，无答案/类型
│   └── private_labels.jsonl           # 四状态真值、合法性、路径、净空与局部效应
├── outputs/predictions.jsonl          # Phase 2 历史空文件；Phase 3 见 outputs/phase3/
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

Phase 3 只针对六个获准核心样本；没有实现正式 Phase 4/5 全集研究、学习基线或训练。
六样本冒烟不构成统计结论。完成并同步结果后停止，等待研究者检查。

实现时查阅的主文档：[Shapely buffer](https://shapely.readthedocs.io/en/stable/reference/shapely.buffer.html)、
[Shapely covers](https://shapely.readthedocs.io/en/stable/reference/shapely.covers.html)、
[uv CLI](https://docs.astral.sh/uv/reference/cli/)。依赖行为以锁定版本与测试结果为准。
