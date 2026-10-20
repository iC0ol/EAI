"""Build a descriptive diagnosis report after the independent evaluator has run."""
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import statistics
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo
import yaml

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/phase3_5'


def read(path):return json.loads((ROOT/path).read_text())
def bits(values):return '/'.join('?' if value is None else str(int(value)) for value in values)
def fraction(metric):return f"{metric['correct']}/{metric['denominator']}"


def main():
    result=read('reports/phase3_5/evaluation.json')
    geometry=read('diagnostics/phase3_5/private/geometry_diagnostics.json')
    mapping=read('diagnostics/phase3_5/private/query_map.json')
    session=read('outputs/phase3_5/session.json')
    cfg=yaml.safe_load((ROOT/'configs/phase3_5.yaml').read_text())
    preds=[json.loads(line) for line in (ROOT/'outputs/phase3_5/predictions.jsonl').read_text().splitlines()]
    preserved=read('reports/phase3_5/preserved_before.json')
    changes=[name for name,digest in preserved['files'].items() if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest]
    assert not changes,changes
    frozen=read('reports/phase3_5/frozen_run.json')
    assert all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==sha for name,sha in frozen['sha256'].items())
    predictions=Counter(str(row['prediction']) for row in result['poststate_cases'])
    truth_counts=Counter(str(row['truth']) for row in result['poststate_cases'])
    model_constant_negative_correct=truth_counts['False']
    runtime={kind:{'queries':len(rows),'generation_total_seconds':sum(r['inference_seconds'] for r in rows),
                  'generation_mean_seconds':statistics.mean(r['inference_seconds'] for r in rows)}
             for kind in ['poststate','overlap'] if (rows:=[r for r in preds if r['kind']==kind])}
    runtime['peak_allocated_mib']=max(r['peak_allocated_mib'] for r in preds)
    runtime['peak_reserved_mib']=max(r['peak_reserved_mib'] for r in preds)
    runtime['nvidia_peak_device_used_mib']=max(r['nvidia_peak_device_used_mib'] for r in preds)
    runtime['hit_token_limits']=sum(r['hit_token_limit'] for r in preds)
    runtime['vision_forward_calls']=sum(r['vision_forward_calls'] for r in preds)
    atomics=[json.loads(line) for line in (OUT/'overlap_atomic_results.jsonl').read_text().splitlines()]
    overlap_groups={name:[r for r in atomics if predicate(r['field'])] for name,predicate in {
        'Start/Goal':lambda f:f.endswith(('.start','.goal')),
        'walls':lambda f:f.endswith('.walls'),
        'other_original':lambda f:f.endswith('.other_original'),
        'AB_targets':lambda f:f=='AB_targets'}.items()}
    overlap_group_rows='\n'.join(f"| {name} | {sum(r['correct'] for r in rows)}/{len(rows)} | "
                                f"{sum(r['prediction'] is True and not r['truth'] for r in rows)} |" for name,rows in overlap_groups.items())
    state_rows='\n'.join(f"| {state} | {fraction(metric)} | {metric['accuracy']:.1%} |" for state,metric in result['poststate_by_state'].items())
    categories=result['paired_categories']
    family_rows='\n'.join(f"| {family} | {fraction(r['phase3_paired'])} | {fraction(r['poststate_paired'])} | {fraction(r['poststate_all'])} |"
                          for family,r in result['families'].items())
    scene_rows=[];case_details=[]
    for sid in cfg['sample_ids']:
        rows={r['state']:r for r in result['poststate_cases'] if r['sample_id']==sid}
        ordered=[rows[state] for state in cfg['states']]
        truth=bits(r['truth'] for r in ordered)
        new=bits(r['prediction'] for r in ordered)
        old=bits(rows[state]['phase3_prediction'] for state in ['A','B','AB'])
        scene_rows.append(f"| {sid} | {ordered[0]['family']} | {truth} | {old} | {new} |")
        links=' · '.join(f"[{state} 后态图](../../diagnostics/phase3_5/images/{rows[state]['query_id']}.png)" for state in cfg['states'])
        responses='\n'.join(f"- {state}: {rows[state]['explanation']} ([raw](../../outputs/phase3_5/{rows[state]['query_id']}_response.txt))" for state in cfg['states'])
        overlap=next(r for r in result['overlap_cases'] if r['sample_id']==sid)
        bad=[r['field'] for r in overlap['fields'] if not r['correct']]
        qid=overlap['query_id']
        case_details.append(f"### {sid} ({ordered[0]['family']})\n\n真值 NONE/A/B/AB={truth}；旧 A/B/AB={old}；新 NONE/A/B/AB={new}。\n\n"
            f"[原始图](../../data/images/{sid}.png) · {links}\n\n{responses}\n\n"
            f"重叠诊断错误字段：{', '.join(bad) if bad else '无'}。回答：{overlap['explanation']} "
            f"([完整原文](../../outputs/phase3_5/{qid}_response.txt))\n\n"
            f"Phase 3 原解释：`{json.dumps(overlap['phase3_explanation'],ensure_ascii=False)}`\n")
    capacity_rows=[];witness=[];positive_capacity=[]
    for row in geometry['states']:
        baseline=next(r for r in row['sensitivity'] if r['condition']=='baseline')
        margin=baseline['resolutions'][-1]['path_min_clearance_m'];cap=row['capacity']
        low=cap['max_radius_feasible_lower_m'];high=cap['max_radius_infeasible_upper_m']
        if margin is not None:witness.append(margin)
        if baseline['passable']:positive_capacity.append((low,high))
        margin_text='无见证路径' if margin is None else f'{margin:.6f}'
        capacity_rows.append(f"| {row['sample_id']} | {row['state']} | {margin_text} | {low:.6f}–{high:.6f} | {low-.25:.6f}–{high-.25:.6f} |")
    separation_rows=[]
    for sid,record in geometry['overlap'].items():
        d=record['details']
        separation_rows.append(f"| {sid} | {d['A']['start']['minimum_separation_m']:.3f} | {d['A']['goal']['minimum_separation_m']:.3f} | "
            f"{d['B']['start']['minimum_separation_m']:.3f} | {d['B']['goal']['minimum_separation_m']:.3f} | {d['AB_targets']['minimum_separation_m']:.3f} |")
    suites=list(ET.parse(OUT/'tests.xml').getroot().iter('testsuite'))
    tests=sum(int(s.get('tests',0)) for s in suites)
    failures=sum(int(s.get('failures',0))+int(s.get('errors',0)) for s in suites)
    report=f'''# Phase 3.5 — 错误来源定位诊断

完成时间：{datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()}。仅使用原有六核心样本，不训练、不扩充正式数据、不升级环境。
旧 Phase 3 结果与全部 {len(preserved['files'])} 个受保护文件逐字节不变；全部新产物放在 diagnostics/phase3_5、outputs/phase3_5、reports/phase3_5。

## 主要观察

**24 张后态图全部被预测为不可达。** 正确 {fraction(result['poststate_all'])}（58.3%），但这与“恒预测不可达”基线 {model_constant_negative_correct}/24 完全相同。
真实可达的 {truth_counts['True']} 张全部漏判，真实不可达的 {truth_counts['False']} 张全部判对。不能把这称为理解后态拓扑的成功。
在可与 Phase 3 配对的 A/B/AB 共 18 项中，旧结果 {fraction(result['phase3_paired'])}，新结果 {fraction(result['poststate_paired'])}；
7 项旧错新对，同时有 5 项旧对新错，净增 2 项可由恒不可达偏置解释，**不足以证明错误主要来自编辑后状态想象**。

独立目标重叠诊断正确 {fraction(result['overlap_atomic'])}，误报 {result['overlap_false_positive_count']} 项。
真实几何的 54 项重叠检查全部为否；因此恒预测“不重叠”会得 54/54，新任务的准确率也不能证明通用重叠感知能力。
原回答中的若干 Start/Goal/目标物体重叠解释被独立几何检查否定。

几何敏感性共 {geometry['attempted_sensitivity_searches']} 次搜索，标签变化 {len(result['sensitivity_label_flips'])}、未决/非法条件 {len(result['sensitivity_unresolved_or_illegal'])}。
返回的 BFS 见证路径最小裕量为 {min(witness):.6f}–{max(witness):.6f}m；这不等于通道所能提供的余量。
可达场景在 0.025m 网格中的最大可通过圆盘半径约 0.80m 或 0.90m，明显大于当前 0.25m；错误并非只发生在贴边临界几何上。

## 实验隔离与输入

- 模型仍为 {cfg['model_id']}，revision `{cfg['model_revision']}`；BF16、SDPA、cuda:0。
- 现有 .venv-vlm 与 .venv 没有安装/升级；torch 2.6.0+cu124、Transformers 4.57.1、原驱动及系统 CUDA 均保留。
- seed={cfg['seed']}；batch=1；max_new_tokens={cfg['max_new_tokens']}；显式 do_sample=false、use_model_defaults=false、num_beams=1。
- 后态 prompt：`{cfg['prompts']['poststate']['version']}`，SHA256 `{session['prompt_sha256']['poststate']}`。
- 重叠 prompt：`{cfg['prompts']['overlap']['version']}`，SHA256 `{session['prompt_sha256']['overlap']}`。
- 配置、prompt、输入清单、24 图和核心代码在首次推理前冻结，见 frozen_run.json；未根据答案改 prompt 或重跑选答。
- 24 张模型输入图只画真实当前几何、障碍物、Start 和 Goal；无类别、编辑名、候选虚线、答案、文件名或绿色路径，PNG 无文字元数据。
- 保持原图地图位置、比例、物体颜色及 Start/Goal 标记；去掉对象字母、原图标题/坐标轴/编辑描述/虚线目标。地图尺寸与半径通过中性文本给出。
- 后态问题不传 sample_id、NONE/A/B/AB 或 family；内部 q_id 为不含语义的哈希。重叠问题只用原图和原 public 字段中的候选定义。
- 推理进程只读专用清单/后态图及六张原图；读防火墙禁止 private、scene.json、QC、旧预测和所有 reports，也禁止改写基线。
- 30 次图像编码器执行、非空 pixel_values 和 image tokens 均有记录；这验证了传图路径，但不保证模型实际利用了视觉线索。
- 推理全结束后，独立 CPU 评估进程才读取 query_map、private_labels、旧预测和独立几何诊断。

## 直接后态可达性

| 状态 | 正确数 | 准确率 |
|---|---:|---:|
{state_rows}

| 样本 | 类别（仅评估后读取） | 真值 NONE/A/B/AB | Phase 3 预测 A/B/AB | 后态预测 NONE/A/B/AB |
|---|---|---|---|---|
{chr(10).join(scene_rows)}

| 类别 | 旧 A/B/AB | 新 A/B/AB（同分母） | 新 NONE/A/B/AB |
|---|---:|---:|---:|
{family_rows}

18 项配对：双方正确 {categories.get('both_correct',0)}；旧错新对 {categories.get('phase3_wrong_poststate_correct',0)}；
双方错误 {categories.get('both_wrong',0)}；旧对新错 {categories.get('phase3_correct_poststate_wrong',0)}；
任一未知 {categories.get('unknown_in_one_or_both',0)}。NONE 没有 Phase 3 预测，不混入配对分母。
JSON 解析失败 {result['parse_failures']}；格式错误/未知会保留在分母，不用真值修复。

## 候选目标重叠的独立检查

定义为正面积相交；仅边界接触单独记录，不计为重叠。Start/Goal 为半径 0.25m 的圆盘。
A' 与 B 原始物体、B' 与 A 原始物体分别检查；另独立检查 A' 与 B'，避免把单编辑与同时编辑的参照物混淆。
几何函数含正重叠/分离/仅接触的单元测试，避免全否真值由写死逻辑造成；这些测试没有增加模型样本。

| 对象关系 | 正确数 | 假重叠误报 |
|---|---:|---:|
{overlap_group_rows}

真实重叠正例数为 0。只能描述负例误报，不能估计正例检出率，更不能直接比较本任务与可达性任务的原始准确率来支持 H1。

下表是候选物体与对应机器人圆盘或另一候选目标之间的最小间隔（m），全部大于 0；完整墙/其他原始物体相交面积及间隔见 geometry_diagnostics.json。

| 样本 | A'–Start | A'–Goal | B'–Start | B'–Goal | A'–B' |
|---|---:|---:|---:|---:|---:|
{chr(10).join(separation_rows)}

Phase 3 中“目标 A 与 Goal 重叠”“A' 与 B' 重叠”等明确断言缺乏几何支持；直接距离也排除了仅边界接触。
这里只核对字面明确的相交断言，不把含糊的“Goal region”或“blocks route”自动当作同一种几何重叠错误。
新重叠诊断仍有错误：六例都误报 A' 与另一原始物体重叠，其中一个样本的九项关系全部误报。
此外，部分新回答的 JSON 与解释自相矛盾，例如结构化 B.walls=false/AB_targets=false，却在解释中声称二者重叠；
原文完整保存，评估只按预定 JSON 字段评分，不替模型调和解释。
合法无重叠也不等于全局可达：副作用 B 可以不与任何障碍相交，却堵住圆形机器人的必经通道。

## 几何扰动与余量

每个后态分别检查 baseline、全部可移动物体以各自质心缩放 0.95/1.05、机器人半径 0.23/0.27m，
每种条件均运行 0.05 与 0.025m 四邻接、整段边碰撞检查。共 24×5×2={geometry['attempted_sensitivity_searches']} 次搜索，
无标签翻转、无分辨率分歧、无非法扰动。半径扰动等价于改变障碍 buffer 和地图边界 inset，不能冒称仅膨胀实体障碍。

见证裕量是某一条 BFS 返回路径的 min(distance(path, obstacles/boundary)−r)，BFS 可能贴边。
通道能力通过同一 0.025m 网格上的半径可行性二分估计：下端存在有效路径，上端在该图中不可达，半径区间宽≤0.005m。
这是整个路线所容许圆盘尺寸的网格估计，含端点限制，不是连续空间最大值或任一局部原始墙间宽度的精确测量。
下端减去 0.25m 才是可利用的半径余量；对当前不可达场景，余量为负，不能填成零。

| 样本 | 状态 | 当前见证最小裕量 m | 网格最大可行半径区间 m | 相对 r=0.25 的半径余量区间 m |
|---|---|---:|---:|---:|
{chr(10).join(capacity_rows)}

**F=0 仍仅是有限模型中的不可达，不宣称连续空间不可达。** 0.05m 未动样本与新增 0.025m 复核均保持既有标签。

## 可以定位到什么、尚不能定位什么

1. 运行层：图片确实传入，权重/依赖未变，30 次 JSON 解析成功、无 OOM/截断；不支持“纯文本误调用”作为本次失败来源。
2. 局部空间关系：明确重叠断言被几何距离否定，新重叠任务仍有假阳性及解释矛盾，支持存在位置关系判断或指令/对象参照理解问题。
3. 编辑后状态预测：7 项恢复同时伴随 5 项退化，且后态输出全部不可达；不能把恢复解释为移除了编辑想象后能力变好。
4. 整体可达性：已直接给出正确后态，仍漏判全部 10 个可达图，表现为极强的不可达回答偏置；
   它可能来自空间感知、路线搜索/拓扑理解、提示解释或回答策略，当前实验不能进一步唯一归因。
5. 纯组合缺陷：尚无控制住局部感知与后态理解后的证据。本轮不声称证明组合推理缺陷、H1/H2、统计显著性或跨布局泛化。

原图与后态图不仅信息不同，prompt、输出字段及对象标注也不同；因此是诊断信息条件对比，不是只改变“状态想象”一个因素的因果实验。
六个基础样本含受控视图，不能把 24 张后态图当作 24 个独立布局。

## 运行、测试与保留

- 94 项测试全部通过（原 75 项完整保留，新增 19 项）；实际计数 {tests}、失败/错误 {failures}，见 tests.xml / logs/tests.log。
- 209 个历史项目文件哈希不变；Phase 3 原始回答、预测、prompt、锁文件和几何数据均未覆盖。
- 本次没有安装任何依赖、下载新权重、训练或写入 ROS/驱动/系统 CUDA。
- 后态生成约 24 图；独立几何诊断耗时 {geometry['elapsed_seconds']:.2f}s；模型加载 {session['model_load_seconds']:.2f}s。
- 后态生成耗时平均 {runtime['poststate']['generation_mean_seconds']:.3f}s/图；重叠生成平均 {runtime['overlap']['generation_mean_seconds']:.3f}s/图。
- torch peak allocated {runtime['peak_allocated_mib']:.1f}MiB，reserved {runtime['peak_reserved_mib']:.1f}MiB；nvidia-smi 全 GPU 采样峰值 {runtime['nvidia_peak_device_used_mib']}MiB（含其他进程）。
- token 上限命中 {runtime['hit_token_limits']} 次。GPU 时间在 synchronize 前后测量，预处理和 elapsed 单独保存。

```bash
cd /home/asus/EAI/spatial_intervention_pilot
bash scripts/run_phase3_5.sh prepare
bash scripts/run_phase3_5.sh geometry
bash scripts/run_phase3_5.sh infer
bash scripts/run_phase3_5.sh evaluate
PYTHONPATH="$PWD/src" .venv/bin/python scripts/report_phase3_5.py
```

prepare、geometry、infer 拒绝覆盖现有产物；旧实验与本次输入保持独立。推理与评估/报告使用不同进程。
完成后停止，等待研究者复核，未开展下一阶段。

## 六个案例与原始回答链接

'''+ '\n'.join(case_details)
    (OUT/'phase3_5_diagnostic.md').write_text(report)
    summary={'poststate_prediction_counts':dict(predictions),'poststate_truth_counts':dict(truth_counts),
             'constant_negative_baseline_correct':model_constant_negative_correct,
             'poststate_confusion':{'true_positive':sum(r['prediction'] is True and r['truth'] for r in result['poststate_cases']),
                 'false_positive':sum(r['prediction'] is True and not r['truth'] for r in result['poststate_cases']),
                 'true_negative':sum(r['prediction'] is False and not r['truth'] for r in result['poststate_cases']),
                 'false_negative':sum(r['prediction'] is False and r['truth'] for r in result['poststate_cases'])},
             'runtime':runtime,'protected_file_count':len(preserved['files']),'changed_historical_files':changes,
             'tests':tests,'test_failures':failures}
    (OUT/'report_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
