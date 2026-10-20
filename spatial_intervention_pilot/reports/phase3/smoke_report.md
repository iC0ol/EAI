# Phase 3 — Qwen3-VL-4B-Instruct 冒烟测试

记录时间：2026-10-20T17:32:22.853610+08:00。Checkpoint B 已经研究者批准。
本轮只部署模型并对指定六个核心样本做一次固定提示推理，不训练、不微调、不扩充数据集。

## 模型与环境

- 官方来源：[Qwen/Qwen3-VL-4B-Instruct](https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct)。
- 模型 revision：`ebb281ec70b05090aa6165b016eac8ec08e71b17`；参数量 4,437,815,808，原始 BF16 safetensors，两分片共 8.887GB（含配置/分词器）。
- 权重分片大小及 SHA256 已对照 Hugging Face LFS 元信息验证，见 model_files.json；未上传权重。
- 独立环境 `.venv-vlm`，Python 3.11.17；torch 2.6.0+cu124、torchvision 0.21.0+cu124、
  Transformers 4.57.1、Accelerate 1.10.1，完整依赖与下载哈希见 ../../requirements-vlm.lock。
- RTX 3090；驱动 550.144.03；系统 Toolkit 保持 11.8。新环境使用官方 cu124 用户态 wheel，CUDA/BF16 矩阵运算检查通过。
- 加载类 `Qwen3VLForConditionalGeneration` + `AutoProcessor`，BF16、`sdpa`、全部在 cuda:0，无量化或 CPU offload。
- 固定 seed=20261020，batch=1，do_sample=false，num_beams=1，max_new_tokens=256。
- 原图 768×768；processor min/max pixels=65536/589824；逐样本图像网格和 token 数记录在 input evidence。
- prompt=`spatial-smoke-en-v1`，SHA256=`5d8b0a86cf5f28089fed94ae61f32c2ac34bd91bb39112dce5bbe8c31d871fca`。在首次模型推理前冻结，没有根据正确答案修改。

## 推理顺序与输入边界

1. single：s_80e62d24efbf，一次真实单图推理。
2. three：复用 single 的第一条原始结果，新增 s_6850ce92ab65 与 s_9fe7791779c0。
3. core：原样复用 three 的三条结果，再推理另三个已指定核心样本。正式结果对六张图各调用一次模型。
   此前另有一次 single 调试尝试，因 Transformers 覆盖生成默认项而排除；原文和日志完整保留在
   outputs/phase3/debug_sampling_defaults。总计七次模型调用，没有基于答案挑选结果。
4. 所有六条推理完成后，单独 CPU 进程执行 evaluate.py，此时才读取 private_labels。

输入加载器只读取 data/public_inputs.jsonl 与本阶段选中的 data/images 文件；不把样本 ID、场景类型、文件名或答案传入 prompt。
Python 审计钩子阻止推理进程读取 private data 和全部 reports/QC。实际数据读取清单保存在各阶段 session.json。
每条记录都含非空 pixel_values、image_grid_thw、image token 数和实际视觉编码器调用次数，验证不是纯文本调用。
raw response、严格 JSON 解析、parse_error、prompt全文/哈希、图像哈希、模型 revision 均已保存。
不提取 markdown 围栏、不把字符串/数字强制变成布尔值、不重试挑选回答、不用真值修复格式。

## 六个样本的实际结果

A/B/AB 顺序；1=true、0=false、null=不确定。完整组合要求三个状态同时正确。

| 样本 | 评估后读取的类别 | 真值 A/B/AB | 预测 A/B/AB | 完整组合正确 | 生成秒 | torch 峰值 MiB |
|---|---|---|---|---|---:|---:|
| s_80e62d24efbf | serial | 0/0/1 | 1/1/1 | False | 4.997 | 8834.5 |
| s_6850ce92ab65 | parallel | 1/1/1 | 0/1/0 | False | 5.061 | 8834.5 |
| s_9fe7791779c0 | side_effect | 1/0/0 | 1/1/1 | False | 4.633 | 8832.8 |
| s_f5dc98934220 | serial | 0/0/1 | 0/1/0 | False | 5.166 | 8842.2 |
| s_8bbc91f1568a | parallel | 1/1/1 | 0/1/0 | False | 4.666 | 8841.7 |
| s_8ed968aae7fe | side_effect | 1/0/0 | 1/1/1 | False | 4.907 | 8834.8 |

| 状态 | 正确数/全部六个 | 准确率 | null/格式失败视为未知 |
|---|---:|---:|---:|
| F_A | 3/6 | 50.0% | 0 |
| F_B | 2/6 | 33.3% | 0 |
| F_AB | 1/6 | 16.7% | 0 |

完整组合正确：0/6。
全部状态决策正确：6/18。
JSON 解析失败：0。所有未知/格式失败均保留在分母中，没有删除失败样本。

| 类别 | 状态正确数 | 完整组合正确 |
|---|---:|---:|
| serial | 2/6 | 0/2 |
| parallel | 2/6 | 0/2 |
| side_effect | 2/6 | 0/2 |

## 组合错误的解释边界

本次没有出现 F_A、F_B 均正确而 F_AB 错误的样本。
这个计数仅描述输出与标签的模式。即使单独编辑判断正确，也不能证明模型已正确识别全部局部几何；
若单独编辑也判断错误，更不能只凭六个样本把错误归因为组合推理。错误案例和模型原文见 error_cases.jsonl 与下文。
在可见原图/公开编辑信息中，模型多次声称 A' 与 Goal 重叠，或 A' 与 B' 重叠，但目标区域实际相隔明显距离；
这提示视觉定位或局部几何理解错误可能参与其中，不能把全部 F_AB 错误归为组合逻辑。
两个副作用样本都预测 1/1/1，漏判 B 后态带来的通道阻塞；因为 F_B 本身也错，这不是单独隔离出来的组合错误证据。
不根据这些样本报告统计显著性、泛化能力、H1/H2 成立或方法创新。

## 耗时与显存

- 六次生成总计 29.430s；平均 4.905s，范围 4.633–5.166s。
- 单独模型加载耗时：{"single": 3.148322151042521, "three": 2.5603574998676777, "core": 2.4354030839167535} 秒，不混入生成耗时。
- torch peak allocated 最大 8842.2MiB；peak reserved 最大 8986.0MiB。
- nvidia-smi 0.5 秒采样的全 GPU 显存最大 9992MiB，含桌面和其他进程，不能当作模型独占占用。
- 生成耗时在调用前后做 CUDA synchronize；图像预处理耗时与 sample elapsed 分开保存。首次冷运行与后续运行差异不能解释为样本难度。

## 保留与故障记录

原 Phase 0–2 的 38 个几何/数据/测试/锁定文件哈希全部不变。原 62 项几何测试保留，新增 13 项边界/解析/评估测试，
本次共 75 项，失败/错误 0。原几何 .venv 与 requirements.lock 没有安装或升级任何包。
最初安装命令缺少 cu124 索引导致找不到 torch；已先报告并保留 install_attempt1_missing_index.log，
随后只显式补上同一官方索引，模型、依赖版本、驱动和系统 CUDA 均未更换。
首个单图调试还暴露 Transformers 4.57.1 的 model-specific generation defaults 回填行为：
初始 GenerationConfig 中处于默认值的 do_sample=false 被模型仓库的 true 覆盖。
已先报告、完整保留并排除这次尝试；随后固定 use_model_defaults=false，并直接向 generate 传递
do_sample=false、num_beams=1 和禁用的采样参数，核验 prepare 后的实际值。prompt 内容与 SHA256 完全不变。
全部安装/下载/加载/推理/评估日志位于 logs/。大权重、.venv-vlm 与缓存被 Git 忽略。

## 重现

```bash
cd /home/asus/EAI/spatial_intervention_pilot
bash scripts/bootstrap_vlm.sh
bash scripts/run_vlm.sh download
bash scripts/run_vlm.sh single
bash scripts/run_vlm.sh three
bash scripts/run_vlm.sh core
PYTHONPATH="$PWD/src" .venv/bin/python -m spatial_pilot.evaluate
PYTHONPATH="$PWD/src" .venv/bin/python scripts/build_phase3_report.py
```

已有阶段输出时入口会拒绝覆盖；历史结果需先保留，不能用新结果无声覆盖。本轮完成后停止，等待研究者检查。
官方加载参考：[Transformers 4.57.1 Qwen3-VL](https://huggingface.co/docs/transformers/v4.57.1/model_doc/qwen3_vl)、
[PyTorch 官方 cu124 版本表](https://pytorch.org/get-started/previous-versions/)。

## 原始结构化回答

### s_80e62d24efbf (serial)

Oracle A/B/AB = 0/0/1; prediction = 1/1/1.

[原始模型输入](../../data/images/s_80e62d24efbf.png)

```json
{
  "F_A": true,
  "F_B": true,
  "F_AB": true,
  "explanation": {
    "A": "A moved left, clears path to Goal without collision.",
    "B": "B moved right, clears path to Goal without collision.",
    "AB": "Both moved, path remains clear with no overlaps."
  }
}
```

### s_6850ce92ab65 (parallel)

Oracle A/B/AB = 1/1/1; prediction = 0/1/0.

[原始模型输入](../../data/images/s_6850ce92ab65.png)

```json
{
  "F_A": false,
  "F_B": true,
  "F_AB": false,
  "explanation": {
    "A": "A' collides with Start and Goal region.",
    "B": "B' clears path to Goal without collision.",
    "AB": "A' and B' overlap, blocking route."
  }
}
```

### s_9fe7791779c0 (side_effect)

Oracle A/B/AB = 1/0/0; prediction = 1/1/1.

[原始模型输入](../../data/images/s_9fe7791779c0.png)

```json
{
  "F_A": true,
  "F_B": true,
  "F_AB": true,
  "explanation": {
    "A": "A moved left, clears path to Goal without collision.",
    "B": "B moved down-left, clears path to Goal without collision.",
    "AB": "Both moved, path remains clear with no overlaps."
  }
}
```

### s_f5dc98934220 (serial)

Oracle A/B/AB = 0/0/1; prediction = 0/1/0.

[原始模型输入](../../data/images/s_f5dc98934220.png)

```json
{
  "F_A": false,
  "F_B": true,
  "F_AB": false,
  "explanation": {
    "A": "A's new position overlaps with Goal, blocking path.",
    "B": "B's new position clears path to Goal without collision.",
    "AB": "A and B's new positions block path to Goal together."
  }
}
```

### s_8bbc91f1568a (parallel)

Oracle A/B/AB = 1/1/1; prediction = 0/1/0.

[原始模型输入](../../data/images/s_8bbc91f1568a.png)

```json
{
  "F_A": false,
  "F_B": true,
  "F_AB": false,
  "explanation": {
    "A": "A's new position overlaps with Goal, blocking path.",
    "B": "B's new position clears path to Goal without collision.",
    "AB": "A and B together block path; A overlaps Goal."
  }
}
```

### s_8ed968aae7fe (side_effect)

Oracle A/B/AB = 1/0/0; prediction = 1/1/1.

[原始模型输入](../../data/images/s_8ed968aae7fe.png)

```json
{
  "F_A": true,
  "F_B": true,
  "F_AB": true,
  "explanation": {
    "A": "A's new position doesn't block path to goal.",
    "B": "B's new position doesn't block path to goal.",
    "AB": "Both A and B's new positions don't block path to goal."
  }
}
```
