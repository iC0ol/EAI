# Spatial Intervention Pilot：工作站先导实验与 Agent 执行说明

版本：v0.1（2026-10-20）  
研究性质：**诊断性先导实验**，不是已证实的新方法或论文创新。  
工作站前提（需实际复核）：Linux、NVIDIA RTX 3090 24GB、32GB 内存；**不要假定现有驱动、CUDA 或 Python 版本准确**。

## 0. 目标、问题与禁区

本轮只回答：
- **H1**：在局部干预效果判断相对正确时，VLM 是否仍会错误判断全局可执行性（充分性）？
- **H2**：这种错误是否依赖路线/任务关系，并在匹配的未见布局中稳定出现？

**本轮不训练、不微调、不安装 ROS2/Gazebo/MuJoCo，不使用机械臂，不接真实机器人，不进行在线干预。**
不升级系统驱动、CUDA Toolkit、Linux 发行版，不改动 `inspection_robot_ws` 或现有 ROS 2 环境。全部运行在新建隔离 Python 环境与新目录。

注意：从程序中直接改变障碍物位置，仅代表**假设编辑后的最终几何可通行性**，不代表机器人能安全、真实地移动这个物体。

## 1. 研究对象的简化定义

使用一张**原始场景**图片、文字任务、机器人尺寸，以及三种候选的后态编辑 `A`、`B`、`A+B`。输入不允许包含修改后的实际图片、几何求解器输出或正确标签。机器人使用平面圆形足迹（例如半径 0.25m，作为初始可配置参数），前期假定全向平面移动，**不宣称能代表差速底盘的转向约束**。

`F(s,I,g,c)`：在明确的**有限分辨率几何模型**中，对场景 `s` 施加**合法且相容**的编辑 `I` 后，机体 `c` 是否能从起点到目标点，并满足任务 `g`。真实连续空间不可达不能仅通过离散 A* 失败断言；用离散模型真值并报告分辨率与边界问题。

第一轮的三类逻辑：

| 场景类型 | F(A) | F(B) | F(A+B) | 解释 |
|---|---:|---:|---:|---|
| `serial` 两处串联阻塞 | 0 | 0 | 1 | 两个编辑缺一不可 |
| `parallel` 两条替代路线 | 1 | 1 | 1 | 任意一个编辑已足够 |
| `side_effect` B 带来新的阻塞 | 1 | 0 | 0 | 修改更多反而可能更差 |

以上属于**测试样例的期望标签**，生成器必须以几何算法核验，不能简单照表写死，也不能把 AND/OR 逻辑本身宣称成新发现。副作用场景中 B 的**后态位置产生的新障碍**必须显式记录和正确绘制；不得遗漏关键信息制造所谓“推理难题”。

优先保证两种场景的局部编辑尽量一致、全局通路组织不同（matched pair），并对对象颜色、名字、地图旋转和镜像做受控反平衡，防止颜色与正确标签关联。

## 2. 阶段与验收

### Phase 0 — 只读硬件与软件体检

执行：
```bash
uname -a
cat /etc/os-release
nvidia-smi
python3 --version
command -v conda || true
df -h "$HOME"
free -h
```

输出 `reports/environment.md`：操作系统、驱动、GPU 型号/显存、空闲存储、Python/conda、可用 CUDA 运行状态、网络访问模型仓库的情况。与用户交流任何需要 `sudo`、修改驱动、卸载已有包、跨目录修改的方案，不要自行执行。

### Phase 1 — 新建隔离环境和工程（CPU 优先）

目录建议：`~/research/spatial_intervention_pilot`；如已有同名目录先检查，不得覆盖。使用 Python 3.11 独立 conda 或 venv。

- 基础包：`numpy`, `pillow`, `matplotlib`, `shapely`, `networkx`（或纯 Python A*）, `pandas`, `pyyaml`, `pytest`, `tqdm`。
- 使用 Shapely 做障碍膨胀、碰撞和区域合法性检测；栅格路径规划使用 A* 或 BFS，**禁用穿角斜向移动**。
- 工程可先只做 CPU 数据生成，等单元测试、可视化通过后才下载 VLM 权重。
- 保存 `environment.yml`/`requirements.lock`，以及仓库 git commit/hash 和随机种子。

推荐目录：
```text
spatial_intervention_pilot/
├── README.md
├── AGENTS.md
├── configs/
│   └── pilot.yaml
├── src/spatial_pilot/
│   ├── geometry.py
│   ├── scenes.py
│   ├── edits.py
│   ├── render.py
│   ├── make_dataset.py
│   ├── oracle.py
│   ├── infer_vlm.py
│   └── evaluate.py
├── tests/
│   ├── test_oracle.py
│   ├── test_edits.py
│   └── test_dataset.py
├── data/
│   ├── images/
│   ├── public_inputs.jsonl
│   └── private_labels.jsonl
├── outputs/
│   └── predictions.jsonl
└── reports/
    ├── environment.md
    ├── qc_montage.png
    └── pilot_summary.md
```

### Phase 2 — 几何真值与场景生成（关键；不允许跳过）

先手工定义最少 **6 个能被程序验证的实例**：每类 2 个。然后逐步扩展到 **24～36 个基础场景**（三类尽量均衡），其中若可行至少有若干组仅修改全局路线拓扑但局部编辑相似的 matched pairs。

每个样本需有：
- 原始场景完整数据 `scene.json`；物体边界、墙、起点/终点、尺寸单位、候选编辑、任务规则、编辑后的对象位姿。
- 原始图像（建议首轮顶视 640～768px、统一颜色语义和比例尺，图中有 A/B、Start/Goal，**不能画出求解器真值路径**）。
- 各个编辑的合法性、是否冲突、`F_none/F_A/F_B/F_AB`，以及各编辑改变了哪些局部空间区域、是否产生新阻塞。
- 净空最小裕量（或离边界距离）、求解分辨率、生成随机种子、渲染参数、场景族 ID。

**求解约束：** 对圆形机器人进行障碍 buffer 膨胀；离散 A* 邻接一致；不能沿对角穿过两个障碍格之间的角落。对临界边界样本用更细网格复算；分歧样本标 `oracle_unresolved` 暂不计入主评价。不能通过“求解器没找到路径”直接声称连续空间物理不可行。

编辑需验证：后态无对象间不合法重叠、没有把障碍移到墙内，A/B 合法且相容；不把“编辑的最终状态可行”和“机器人能执行该编辑轨迹”混为一谈。

单元测试至少包括：
1. 三种类型各 2 个例子的 F 符合预期；
2. A+B 顺序无关**仅在编辑定义互相相容的场景**中成立；
3. 颜色/ID 调换不改变几何标签；
4. 存在编辑后新产生阻塞的样例；
5. 不合法/冲突编辑不会被静默当作 0 标签；
6. 生成与渲染固定随机种子可复现；
7. 图像中不出现答案、oracle 路径、数据文件名标签；
8. 生成失败需明确计数，不能在统计里悄悄丢样本。

在继续前输出 `reports/qc_montage.png`，每类至少 4 个场景；请用户核对可读性和模型输入信息是否足够。

### Phase 3 — VLM 环境安装、单图冒烟

优先试 `Qwen/Qwen3-VL-4B-Instruct`，来源：https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct 。如 Transformers 适配/显存遇到阻碍，备选 `Qwen/Qwen2.5-VL-3B-Instruct`，需在报告记录替换原因，**不同模型成绩不可直接归因于方法**。

- PyTorch 依据官方 https://pytorch.org/get-started/locally/ 的 Linux/Pip/CUDA 组合安装，**先检查已有驱动与兼容性，不复制猜测的 CUDA 指令**。
- 可参考 https://huggingface.co/docs/transformers/model_doc/qwen3_vl 使用 `AutoProcessor` + `Qwen3VLForConditionalGeneration`，优先稳定可用的 Transformers 版本及 `attn_implementation="sdpa"`。
- 首次仅跑**一张图和一个短问题**，断言图像确实传入模型而不只是纯文本；记录 GPU 占用、推理耗时、输出文本。
- 一张图一次请求，短 JSON 响应、`max_new_tokens=128~256`、确定性解码（`do_sample=False`）。不要一开始使用 vLLM 服务、FlashAttention 手工编译或大量模型，以免调试层次混乱。
- GPU OOM 时优先降低图像分辨率、每批只处理一张、控制生成长度，必要时再选量化或更小模型；不得让 Agent 重新安装系统驱动解决一般显存不足。

### Phase 4 — 正式 zero-shot 诊断（先不训练）

固定一个 Prompt 版本；禁止逐场景修改提示词。提问仅提供：**原始场景图像、任务规则、机器人半径及允许编辑的描述**，不给编辑后截图/Oracle 路径/未来真值。

推荐问题模板：
```text
You are evaluating a hypothetical scene edit for a circular mobile robot.
Use only the provided original image, robot radius, task rules,
and the candidate edit definitions. Do not assume edits were executed.
For each edit NONE, A, B, and AB, estimate:
(1) whether the edit is legal according to the stated task,
(2) whether a collision-free route from S to G would exist afterward,
(3) which local region is cleared or newly blocked.
If image evidence is insufficient, say uncertain rather than inventing facts.
Reply with one valid JSON object with keys:
"NONE", "A", "B", "AB"; for each give
"legal": true/false/null,
"passable": true/false/null,
"local_effect": short string.
No long explanation.
```

图像中的 A/B 必须只是物体/编辑 ID，不能因颜色或编号泄露正确答案；候选操作参数与任务禁止区要对模型可见。`null` 表示模型由于观测不足无法可靠判断，**不得与物理不可行或 oracle 搜索失败混为同一种标签**。

先跑 `6` 个 smoke examples，修好 JSON 解析、批次记录和自动恢复后，跑 `24～36` 个先导场景。每个场景一次联合询问 NONE/A/B/AB；另抽取部分样本进行逐编辑独立询问，量化“在同一 prompt 中比较多个编辑”的提示方式影响。

每次推理记录：`sample_id`, `model_id`, `model_revision`, `prompt_version`, `seed`, `decoding_config`, `response_text`, `parsed_output`, `parse_ok`, `inference_seconds`, `peak_vram_mb`, `input_image_sha256`。失败和超时单列，不能只统计模型答得出 JSON 的样本。

### Phase 5 — 指标与错误诊断

最少统计：
1. **F 判断准确率**：分别统计 A/B/AB，并按 serial/parallel/side_effect 分类。
2. **危险误通过率**：模型预测可行、oracle 实际不可行的比例；同时报告分母（所有预测通过或所有不可行情形）。
3. **局部正确但全局错误**：定义清楚何为局部效应预测正确，按 scene group 统计。
4. **matched-pair relation flip**：局部编辑效应基本相同、全局结构不同的一对场景，模型能否在应当变化的全局标签上同步改变判断。
5. **拒答、JSON 不合法、推理失败、耗时、显存**。
6. **几何/视觉错误定位**：至少选 10 个样本人工审核（包括正确、错误、未知），对复杂样本可引入“补充已知场景拓扑信息”诊断，但这属于额外信息的 oracle 辅助条件，不能冒充原始模型成绩。

先设置非学习基线：按训练部分或开发样本频率作标签先验；简单的独立编辑启发式。更重要的是同观察输入下的**图像颜色/形状分割 + 几何求解器**（只限规则颜色 2D 阶段；它若表现强也属于有价值的结论）。真实几何坐标驱动的 oracle 只作为上界，不得作为同等信息 VLM 对手。

报告必须区分：视觉识别错误、局部干预效果错误、组合拓扑错误、任务约束错误。每类展示原图、候选编辑、标签与预测，并列出不能判定的证据不足案例。小样本只报告计数及不确定性（可按基础场景组进行 bootstrap），不要宣称统计显著。

### Phase 6 — 先导决策

继续研究的支持证据：多个独立布局中反复出现局部效应较对、全局组合错误，且不是提示词泄漏或低分辨率标签错误；同观察几何方法尚有受语义/观察限制的不足。此时下一阶段才尝试**关系条件化监督**与公平学习基线。

停止/改题证据：所谓错误只来自图像质量/文字理解；换强一点的 VLM 基本消失；同观察视觉分割+求解器就可靠解决所有可定义子任务；合成数据只是一组 AND/OR 模板；编辑的真实真值不稳定。若 geometry-only 更强，不代表问题无价值，但不能继续声称 VLM 的必要性。

**不应以一个人为指定的准确率阈值决定全部科研投入**。以错误是否稳定、是否独立于简单基线、差异是否值得发表为依据。

## 3. Agent 必须交付

1. `reports/environment.md`：工作站与依赖审计。
2. 全部生成器/几何/渲染/推理/评估源码，能单命令重现；`README.md` 解释运行步骤。
3. `pytest` 完整结果，尤其是编辑合法性与 oracle 三类逻辑检查。
4. `reports/qc_montage.png` 与 `data/public_inputs.jsonl`（没有隐藏标签）、`data/private_labels.jsonl`。
5. `outputs/predictions.jsonl`：包括失败记录与响应原文。
6. `reports/pilot_summary.md`：汇总结果、分类型误差、10 个可读案例、局限、是否值得继续的判断。
7. 源码 `git` 状态、环境锁定、模型 revision、所有随机种子。

**禁止**：不经用户同意创建公开 GitHub 仓库、上传数据/模型、在已有 ROS 工作区做改动、删除既有环境、自动升级 NVIDIA 驱动。用户可在本地新目录 `git init` 以便保存实验版本。

## 4. 推荐工作节奏与检查点

- **Checkpoint A**：Phase 0 / Phase 1 通过，给出环境记录，确认依赖可用。
- **Checkpoint B**：Phase 2 中 6 个单元例子 + 单元测试 + 可视化通过，供用户看场景和 oracle 结果。
- **Checkpoint C**：Phase 3 一张图成功在 GPU 上推理。
- **Checkpoint D**：Phase 4/5 先导样本完成后，回传案例和表格，研究者判断是否扩展样本。

每次遇到错误，不要盲目迭代更换模型/依赖；先记录最小复现实例、完整 traceback、现有版本和改动原因，再做最小修改。每阶段先单测通过，再进入下一阶段。

## 5. 可供 Agent 直接执行的启动指令

> 你现在在我的 Linux 工作站上，任务是准备 `Spatial Intervention Pilot`，它是针对 VLM 空间可执行性与假设场景编辑的**离线诊断实验**，不是机器人导航/操作项目。请严格按本文件 Phase 0→1→2→3→4→5 顺序工作，并在 Checkpoint A/B/C/D 汇报实际证据。
>
> 本次只允许创建独立目录和独立 Python 环境；不得修改旧 ROS2/Gazebo、`inspection_robot_ws`、NVIDIA 驱动或系统 CUDA。未经许可不执行 sudo、不删除已有文件、不推送 GitHub。先检测系统和 GPU 再挑依赖版本，优先使 CPU 几何 oracle 和可视化完整通过，然后才配置 Hugging Face VLM 模型。每次失败先保留日志，不得靠更换大模型掩盖数据、标签或提示错误。
>
> 本轮先做到 Checkpoint B（6 个 oracle 单测实例和至少 12 张场景可视化，通过自动测试），然后向我报告。未经我检查这批场景与标签，不要大规模生成数据或下载大型模型权重。说明运行命令、文件路径、测试通过数、至少 3 个可能的实验偏差及其避免方式。

## 6. 基础资料

- Qwen3-VL-4B-Instruct 官方模型卡：<https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct>
- Hugging Face Qwen3-VL 文档：<https://huggingface.co/docs/transformers/model_doc/qwen3_vl>
- PyTorch 安装引导：<https://pytorch.org/get-started/locally/>
- Shapely 几何工具手册：<https://shapely.readthedocs.io/en/latest/manual.html>

