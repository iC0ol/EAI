"""Post-inference reporting only: evaluate first, then summarize audited artifacts."""
from collections import defaultdict
from datetime import datetime
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import xml.etree.ElementTree as ET
import yaml

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'reports/phase3'


def read(path):
    return json.loads((ROOT/path).read_text())


def bits(values):
    return '/'.join('null' if values[k] is None else str(int(values[k])) for k in ['F_A','F_B','F_AB'])


def main():
    result = read('reports/phase3/evaluation.json')
    cfg = yaml.safe_load((ROOT/'configs/vlm_smoke.yaml').read_text())
    env = read('reports/phase3/environment.json')
    weights = read('reports/phase3/model_files.json')
    frozen = read('reports/phase3/frozen_run.json')
    baseline = read('reports/phase3/geometry_baseline.json')
    changed = [name for name,sha in baseline.items() if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=sha]
    if changed:
        raise ValueError(f'Geometry preservation violated: {changed}')
    for name,sha in frozen['sha256'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=sha:
            raise ValueError(f'Frozen inference file changed: {name}')
    sessions = {stage:read(f'outputs/phase3/{stage}/session.json') for stage in ['single','three','core']}
    for session in sessions.values():
        assert session['status']=='completed'
        allowed = {'data/public_inputs.jsonl'} | {f'data/images/{sid}.png' for sid in session['sample_ids']}
        assert set(session['data_read_events']) <= allowed
        assert session['prompt_sha256'] == frozen['sha256'][cfg['prompt_path']]
    cases = result['cases']
    groups = defaultdict(list)
    for case in cases:
        groups[case['family']].append(case)
    by_family = {}
    for family,rows in groups.items():
        by_family[family] = {'samples':len(rows),'decisions_correct':sum(sum(r['correct'].values()) for r in rows),
                             'decisions_denominator':len(rows)*3,
                             'full_combination_correct':sum(r['full_combination_correct'] for r in rows)}
    timings = [r['inference_seconds'] for r in cases]
    peaks = [r['peak_vram_mb'] for r in cases]
    runtime = {'generation_total_seconds':sum(timings),'generation_mean_seconds':statistics.mean(timings),
               'generation_min_seconds':min(timings),'generation_max_seconds':max(timings),
               'peak_allocated_mib':max(peaks),
               'peak_reserved_mib':max(json.loads(line)['peak_reserved_mib'] for line in
                   (ROOT/'outputs/phase3/core/predictions.jsonl').read_text().splitlines()),
               'nvidia_peak_total_device_mib':max(r['nvidia_peak_device_used_mib'] for r in cases),
               'model_load_seconds_by_stage':{s:v['model_load_seconds'] for s,v in sessions.items()},
               'by_family':by_family,'geometry_preserved_files':len(baseline),'changed_geometry_files':changed}
    (OUT/'runtime_summary.json').write_text(json.dumps(runtime,indent=2)+'\n')
    rows = '\n'.join(f"| {r['sample_id']} | {r['family']} | {bits(r['truth'])} | {bits(r['prediction'])} | "
                     f"{r['full_combination_correct']} | {r['inference_seconds']:.3f} | {r['peak_vram_mb']:.1f} |" for r in cases)
    state_rows = '\n'.join(f"| {key} | {v['correct']}/{v['denominator']} | {v['accuracy']:.1%} | {v['unknown']} |"
                           for key,v in result['per_state'].items())
    group_rows = '\n'.join(f"| {family} | {v['decisions_correct']}/{v['decisions_denominator']} | "
                           f"{v['full_combination_correct']}/{v['samples']} |" for family,v in by_family.items())
    explanations = []
    for case in cases:
        explanations.append(f"### {case['sample_id']} ({case['family']})\n\n"
                            f"Oracle A/B/AB = {bits(case['truth'])}; prediction = {bits(case['prediction'])}.\n\n"
                            f"```json\n{case['response_text']}\n```\n")
    conditional = [r['sample_id'] for r in cases if r['both_singles_correct_ab_wrong']]
    suites = list(ET.parse(OUT/'all_tests.xml').getroot().iter('testsuite'))
    tests = sum(int(s.get('tests')) for s in suites)
    failures = sum(int(s.get('failures'))+int(s.get('errors')) for s in suites)
    note = (f"存在 {len(conditional)} 个样本：F_A、F_B 均正确而 F_AB 错误，样本为 {', '.join(conditional)}。"
            if conditional else "本次没有出现 F_A、F_B 均正确而 F_AB 错误的样本。")
    report = f'''# Phase 3 — Qwen3-VL-4B-Instruct 冒烟测试

记录时间：{datetime.now().astimezone().isoformat()}。Checkpoint B 已经研究者批准。
本轮只部署模型并对指定六个核心样本做一次固定提示推理，不训练、不微调、不扩充数据集。

## 模型与环境

- 官方来源：[Qwen/Qwen3-VL-4B-Instruct](https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct)。
- 模型 revision：`{cfg['model_revision']}`；参数量 4,437,815,808，原始 BF16 safetensors，两分片共 {weights['total_bytes']/1e9:.3f}GB（含配置/分词器）。
- 权重分片大小及 SHA256 已对照 Hugging Face LFS 元信息验证，见 model_files.json；未上传权重。
- 独立环境 `.venv-vlm`，Python 3.11.17；torch {env['packages']['torch']}、torchvision {env['packages']['torchvision']}、
  Transformers {env['packages']['transformers']}、Accelerate {env['packages']['accelerate']}，完整依赖与下载哈希见 ../../requirements-vlm.lock。
- RTX 3090；驱动 550.144.03；系统 Toolkit 保持 11.8。新环境使用官方 cu124 用户态 wheel，CUDA/BF16 矩阵运算检查通过。
- 加载类 `Qwen3VLForConditionalGeneration` + `AutoProcessor`，BF16、`sdpa`、全部在 cuda:0，无量化或 CPU offload。
- 固定 seed={cfg['seed']}，batch=1，do_sample=false，num_beams=1，max_new_tokens={cfg['max_new_tokens']}。
- 原图 768×768；processor min/max pixels={cfg['min_pixels']}/{cfg['max_pixels']}；逐样本图像网格和 token 数记录在 input evidence。
- prompt=`{cfg['prompt_version']}`，SHA256=`{result['prompt_sha256']}`。在首次模型推理前冻结，没有根据正确答案修改。

## 推理顺序与输入边界

1. single：s_80e62d24efbf，一次真实单图推理。
2. three：复用 single 的第一条原始结果，新增 s_6850ce92ab65 与 s_9fe7791779c0。
3. core：原样复用 three 的三条结果，再推理另三个已指定核心样本。总共只对六张图各调用一次模型。
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
{rows}

| 状态 | 正确数/全部六个 | 准确率 | null/格式失败视为未知 |
|---|---:|---:|---:|
{state_rows}

完整组合正确：{result['full_combination_correct']}/{result['full_combination_denominator']}。
全部状态决策正确：{result['all_state_decisions_correct']}/{result['all_state_decisions_denominator']}。
JSON 解析失败：{result['parse_failures']}。所有未知/格式失败均保留在分母中，没有删除失败样本。

| 类别 | 状态正确数 | 完整组合正确 |
|---|---:|---:|
{group_rows}

## 组合错误的解释边界

{note}
这个计数仅描述输出与标签的模式。即使单独编辑判断正确，也不能证明模型已正确识别全部局部几何；
若单独编辑也判断错误，更不能只凭六个样本把错误归因为组合推理。错误案例和模型原文见 error_cases.jsonl 与下文。
不根据这些样本报告统计显著性、泛化能力、H1/H2 成立或方法创新。

## 耗时与显存

- 六次生成总计 {runtime['generation_total_seconds']:.3f}s；平均 {runtime['generation_mean_seconds']:.3f}s，范围 {min(timings):.3f}–{max(timings):.3f}s。
- 单独模型加载耗时：{json.dumps(runtime['model_load_seconds_by_stage'])} 秒，不混入生成耗时。
- torch peak allocated 最大 {runtime['peak_allocated_mib']:.1f}MiB；peak reserved 最大 {runtime['peak_reserved_mib']:.1f}MiB。
- nvidia-smi 0.5 秒采样的全 GPU 显存最大 {runtime['nvidia_peak_total_device_mib']}MiB，含桌面和其他进程，不能当作模型独占占用。
- 测量包含图像预处理与每次生成前后 CUDA synchronize，另保存 sample elapsed；首次冷运行与后续运行差异不能解释为样本难度。

## 保留与故障记录

原 Phase 0–2 的 {len(baseline)} 个几何/数据/测试/锁定文件哈希全部不变。原 62 项几何测试保留，新增 12 项边界/解析/评估测试，
本次共 {tests} 项，失败/错误 {failures}。原几何 .venv 与 requirements.lock 没有安装或升级任何包。
最初安装命令缺少 cu124 索引导致找不到 torch；已先报告并保留 install_attempt1_missing_index.log，
随后只显式补上同一官方索引，模型、依赖版本、驱动和系统 CUDA 均未更换。
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

'''+ '\n'.join(explanations)
    (OUT/'smoke_report.md').write_text(report)
    print(json.dumps(runtime,indent=2))


if __name__ == '__main__':
    main()
