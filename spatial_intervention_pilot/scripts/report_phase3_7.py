"""Report the actual frozen Part A/B results and the enforced Part C stopping gate."""
from datetime import datetime,timezone
import json
from pathlib import Path
import statistics
import xml.etree.ElementTree as ET
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from spatial_pilot.scale_io import digest

root=Path(__file__).resolve().parents[1];report=root/'reports/phase3_7'
m=json.loads((report/'part_a_b_metrics.json').read_text())
assert not m['part_c_gate']['part_c_permitted'], 'This report entry handles the observed No-Go branch only'
cases=list(map(json.loads,(report/'paired_cases.jsonl').read_text().splitlines()))
labels=list(map(json.loads,(root/'diagnostics/phase3_7/private/new24_labels.jsonl').read_text().splitlines()))
audits=json.loads((report/'posthoc_segmentation_path_audit.json').read_text())
generation=json.loads((report/'generation_manifest.json').read_text())
environment=json.loads((report/'environment_after.json').read_text())
frozen=json.loads((report/'frozen_run.json').read_text())
weights=json.loads((report/'model8b_files.json').read_text())
sessions={name:json.loads((root/f'outputs/phase3_7/{name}/session.json').read_text()) for name in ['smoke8b','vlm8b_a','vlm4b_new']}
raws={name:list(map(json.loads,(root/f'outputs/phase3_7/{name}/predictions.jsonl').read_text().splitlines())) for name in sessions}
tests={}
for name,file in [('before','tests_before_final.xml'),('after','tests_after.xml')]:
    suites=list(ET.parse(report/file).iter('testsuite'));tests[name]={k:sum(int(s.get(k,'0')) for s in suites) for k in ['tests','failures','errors','skipped']}
assert tests['after']['tests']==179 and all(tests['after'][k]==0 for k in ['failures','errors','skipped'])
assert not environment['historical_files_changed'] and environment['historical_files_checked']==463
assert json.loads((report/'model8b_preservation_after.json').read_text())['all_match']

part_c={'status':'not_executed','reason':'8B new detour controls 0/6, meeting the user stop rule (0–2/6). Also 9/12 new negatives, below predeclared 10/12 guard.',
        'gate':m['part_c_gate'],'original_core_8b_calls':0,'new_matched_intervention_scenes_generated':0,
        'new_matched_intervention_vlm_calls':0,'counterfactual_image_planner_runs':0,
        'F_A_accuracy':None,'F_B_accuracy':None,'F_AB_accuracy':None,'full_combination_accuracy':None,
        'both_singles_correct_joint_wrong':None,
        'interpretation':'Not measured, not zero. No new evidence isolates an independent counterfactual/compositional defect.'}
with (report/'part_c_status.json').open('x') as f:json.dump(part_c,f,indent=2);f.write('\n')
errors=[]
for c in cases:
    for method,r in c['methods'].items():
        if not r['correct']:errors.append({'sample_id':c['sample_id'],'dataset':c['dataset'],'method':method,'category':c['category'],'truth':c['truth'],**r})
with (report/'error_cases.jsonl').open('x') as f:
    for e in errors:f.write(json.dumps(e,ensure_ascii=False)+'\n')
quality={'attempted':24,'verified':24,'failed':0,'illegal_geometry':0,'resolution_disagreement':0,'unresolved':0,'automatic_replacements':0,
         'three_resolution_searches':72,'positive_controls':12,'negative_controls':12,
         'positive_reference_clearance_min_m':min(l['reference_path_min_clearance_m'] for l in labels if l['passable']),
         'positive_reference_clearance_max_m':max(l['reference_path_min_clearance_m'] for l in labels if l['passable']),
         'image_pipeline_failures':sum(r['methods']['bfs']['status']=='pipeline_error' for r in cases),
         'bfs_astar_prediction_disagreements':sum(r['methods']['bfs']['prediction'] is not r['methods']['astar']['prediction'] for r in cases),
         'posthoc_obstacle_iou_min':min(a['obstacle_IoU_excluding_two_pixel_frame'] for a in audits),
         'posthoc_obstacle_iou_mean':statistics.mean(a['obstacle_IoU_excluding_two_pixel_frame'] for a in audits),
         'posthoc_max_endpoint_error_m':max(v for a in audits for v in a['endpoint_errors_m'].values()),
         'rgb_positive_paths_checked':sum(a[k]['predicted_passable'] is True for a in audits for k in ['bfs','astar']),
         'rgb_invalid_positive_paths':sum(not a[k]['path_collision_free_in_private_geometry'] for a in audits for k in ['bfs','astar'] if a[k]['predicted_passable']),
         'rgb_returned_path_min_clearance_m':min(a[k]['path_min_clearance_m'] for a in audits for k in ['bfs','astar'] if a[k]['predicted_passable'])}
with (report/'quality_summary.json').open('x') as f:json.dump(quality,f,indent=2);f.write('\n')

# Scientific static visualization; Oracle omitted from performance bars because it defines the labels.
fig,axes=plt.subplots(1,2,figsize=(12,4.5),sharey=True)
colors=['#4679bd','#df8b32','#4f9c76','#9464af'];names={'4b':'4B VLM','8b':'8B VLM','bfs':'RGB + BFS','astar':'RGB + A*'}
for ax,dataset,title in zip(axes,['old16','new24'],['Existing 16 diagnostic controls','New 24 frozen controls']):
    x=np.arange(4)
    for i,method in enumerate(names):
        s=m['sets'][dataset][method]
        vals=[s['categories'][c]['correct']/s['categories'][c]['total']*100 for c in 'ABCD']
        ax.bar(x+(i-1.5)*.19,vals,width=.18,label=names[method],color=colors[i])
    ax.set_xticks(x,['A: straight','B: detour','C: barrier','D: enclosed']);ax.set_title(title);ax.set_ylim(0,110);ax.grid(axis='y',alpha=.2)
axes[0].set_ylabel('Correct (%)')
handles,legend_labels=axes[1].get_legend_handles_labels()
fig.legend(handles,legend_labels,loc='lower center',ncol=4,fontsize=9)
fig.suptitle('Diagnostic cases only; shared RGB segmentation for BFS/A*; no significance claim',fontsize=10)
fig.tight_layout(rect=[0,.08,1,.95]);fig.savefig(report/'method_comparison.png',dpi=160);fig.savefig(report/'method_comparison.svg');plt.close(fig)

lines=[
'# Phase 3.7 — 模型规模与公开图像几何规划对照', '',
f"报告时间：{datetime.now(timezone.utc).isoformat()}。诊断性选题终局验证；没有训练、微调、提示优化或新增方法模型。", '',
'**结论：建议停止当前“纯二维地图可达性 / 反事实组合缺陷”硕士小论文路线（No-Go）。**',
'8B BF16 在 RTX 3090 正常运行，但新24题仍为14/24，与4B相同；新绕行正例由4B的3/6降到8B的0/6。',
'公开 RGB 提取+BFS/A* 在旧16题和新24题均全对，且返回路径通过事后真实几何碰撞检查。',
'8B 未通过用户规定的基础绕行门槛，**Part C 未执行**。不能把旧4B的反事实错误归因为独立组合缺陷，也不能声称本轮已经评估8B的反事实能力。', '',
'## 1. 目的、历史背景和研究边界', '',
'Phase 3 六核心A/B/AB共6/18正确、完整组合0/6；Phase 3.5直接后态24图全部预测不可达、14/24等于恒否；Phase 3.6新基础16图为12/16，绕行仅1/4。',
'本轮检验模型规模是否改善基础判断，以及相同公开PNG和米制半径/尺寸下，VLM与固定RGB分割后的图搜索有何差异。',
'A1复用Phase 3.6的16个已分析控制图和原4B结果；A2为新24个预先冻结布局。旧16是已分析诊断集；新24也是手工诊断控制，不作为随机抽样正式论文测试集。',
'两个集合分开报告，不把它们拼成一个独立未见测试集。没有显著性检验、总体能力估计或泛化提升结论。', '',
'## 2. 工作站、8B部署与权重来源', '',
'初始 RTX 3090 24GB，nvidia-smi占用608MiB，磁盘可用约270GB；已有PID 569251的Python进程占296MiB，未终止其他进程或清理其他项目。',
'驱动550.144.03、系统Toolkit 11.8、ROS2、系统Python与操作系统均保持；沿用项目内原 .venv-vlm，不安装/升级包。',
'Python3.11.17、torch2.6.0+cu124、torchvision0.21.0+cu124、Transformers4.57.1、Accelerate1.10.1；原几何环境19包、推理环境42包版本一致。',
'官方8B来源：[Qwen/Qwen3-VL-8B-Instruct](https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct)。官方加载类Qwen3VLForConditionalGeneration+AutoProcessor，现有版本实际加载成功，无须采纳网页中的升级命令。',
'8B revision=`0c351dd01ed87e9c1b53cbc748cba10e6187ff3b`；4B revision=`ebb281ec70b05090aa6165b016eac8ec08e71b17`。',
f"8B实际参数量8,767,123,696；全部参数dtype=torch.bfloat16、SDPA、cuda:0、batch1、torch.inference_mode()，无量化或CPU offload。独立缓存 .cache/phase3_7/model8b。",
f"下载用时{weights['download_seconds']:.1f}s，完整文件{weights['total_bytes']:,}bytes，四个safetensors分片。每个权重SHA256与官方LFS元信息一致，小文件也保存大小和SHA256；完成后再次验证一致。",
'[官方revision/文件元信息](model8b_source.json) · [逐文件下载校验](model8b_files.json) · [权重保留复核](model8b_preservation_after.json)', '',
'先使用独立公开绘制的smoke图，不进入两个评分集，只检查BF16加载、实际视觉编码和严格JSON。该唯一一次smoke输出合法JSON，未按答案选择图片、调prompt或改加载参数。',
f"smoke模型加载{sessions['smoke8b']['model_load_seconds']:.3f}s，生成{raws['smoke8b'][0]['inference_seconds']:.3f}s。之后冻结环境。正式8B加载{sessions['vlm8b_a']['model_load_seconds']:.3f}s，正式4B加载{sessions['vlm4b_new']['model_load_seconds']:.3f}s；不混入单图延迟。",
f"8B torch峰值allocated={max(r['peak_allocated_mib'] for r in raws['vlm8b_a']):.1f}MiB、reserved={max(r['peak_reserved_mib'] for r in raws['vlm8b_a']):.1f}MiB，全GPU采样峰值={max(r['nvidia_peak_device_used_mib'] for r in raws['vlm8b_a'])}MiB（含桌面和其他进程），运行中仍约有6.2GB空闲。",
'加载前另有19,500MiB空闲显存保护门槛；无OOM、依赖故障、量化替代、模型替换或进程清理。', '',
'## 3. 新24题构建与独立真值', '',
'四类各6个，12可达、12不可达；半径0.25m、12×12m地图、圆盘二维全向平移、不允许碰触边界/障碍。',
'新布局包括：三岛斜向直通、支墙旁直通、斜墙走廊、四柱上方直通；双岛/三角岛绕行、三段dogleg、三层交错挡板、圆C形开口逃出、两室高位连接；',
'多折线隔断、错位竖墙、十字四区、双横带、带分支竖隔断、斜阶梯；非对称六边形、菱形、双重嵌套环、双庭院、圆角外墙、内凹沙漏封闭区域。',
'坐标先写定，生成seed202610217只稳定不含类别的ID与打乱顺序，不依据模型输出筛选或替换。D4碰撞几何+端点规范签名与旧12图、Phase3.6的16图及本轮互相比对，没有整图旋转/镜像重复。',
'此检查不声称所有案例具有互不相同的抽象拓扑，也不是统计独立性证明；若干封闭环共享“Goal在孔内”的基本结构。',
'每图用原Shapely碰撞模型、0.10/0.05/0.025m四邻接完整边检查Oracle，共72次搜索，结果一致；另对配置自由空间作GEOS连通分量分解，与三网格结果一致。',
'正例均有逐段无碰撞的设计参考路线，最小额外净空0.75–1.75m（已减机器人半径）；A直线均可行，B直线均被挡。',
'负例有原始未膨胀几何的分离证据：C连接相对地图边界，D具有包含Goal而不含Start的闭合孔洞。',
'有限网格失败不是连续空间不可达的数学证明；显式多边形和GEOS拓扑是进一步证据，仍不是形式化验证，且两套检查共享GEOS库。',
f"首次生成尝试24、成功24、失败0、非法0、分辨率分歧0、未决0、自动替换0，耗时{generation['seconds']:.3f}s。没有在模型答错后替换题目。",
'[全部尝试](../../diagnostics/phase3_7/private/generation_attempts.jsonl) · [新24私有真值/路线/分离证据](../../diagnostics/phase3_7/private/new24_labels.jsonl)', '',
'研究者总览含类别和ID，绝不作为模型输入：', '',
'![24个新基础控制场景](new24_overview.png)', '',
'[私有路径总览](new24_private_paths.png) · [逐图私有QC](private_qc/)；模型图只保留几何、Start、Goal，没有路径、答案、类别、ID或编辑提示。', '',
'## 4. 冻结、Prompt和推理隔离', '',
f"首次正式推理前冻结时间{frozen['frozen_at']}，正式运行源码commit `{sessions['vlm8b_a']['source_commit']}`。",
'[公开输入/顺序/规则/代码冻结](../../diagnostics/phase3_7/inputs/frozen_public.json) · [私有真值及环境冻结](frozen_run.json) · [smoke后环境锁定记录](environment_frozen.json)',
'主prompt为原样复制的poststate-reach-en-v1，SHA256=`0b28e77b7730da560df6f7f78f1c58298c002808955b55b7821f3310cfc7c0c7`，与Phase3.5/3.6逐字节相同；没有根据答案修改提示。',
'两个模型均seed20261020、max_new_tokens256、显式do_sample=false/use_model_defaults=false、num_beams1、temperature/top_p/top_k=null；检查prepare后实际greedy参数。',
'保持768×768、processor min/max_pixels=65536/589824，模型各自官方processor/chat_template。每张图确有非空pixel_values、576图像tokens和一次视觉编码，具体张量及展开prompt保存在逐例_input.json。',
'公开上下文仅units、workspace_dimensions_m、robot_radius_m；样本ID、类别、几何坐标、Oracle路径、QC、旧预测均不进入prompt。',
'Python审计钩子只允许读取本轮公开清单/PNG及旧16张干净PNG，拒绝所有private、data、reports和历史outputs。推理进程没有导入生成器或评估器。',
'8B正式40调用（旧16+新24），4B正式24调用（仅新24），旧16条4B结果原文件哈希引用；另有唯一一次不评分8Bsmoke，总计本轮65次VLM视觉执行。没有重试或挑选回答，全部严格JSON成功，无截断。',
'RGB40次图像提取产生BFS/A*各40条预测。所有推理结束后，独立CPU评估器才打开旧/新私有标签；原文、parse_error、配置/图像哈希、耗时和显存记录全部保留。', '',
'## 5. 公开RGB提取与图搜索：信息边界及规则', '',
'RGB代码只导入PIL/NumPy和标准库，不读取/导入生成器坐标、Shapely Oracle、私有标签或路径。公共清单与图像经过同一读防火墙。',
'固定rgb-grid-v1：RGB容差4，墙#445060、障碍#DD9350、边框#182332、Start#2475C4、Goal#16805B；按照公开绘图图例一次性定义，未按测试答案逐例修改。',
'地图边框范围从图像颜色检测，结合公开12×12m估计比例（本轮52px/m）；Start/Goal由彩色圆盘像素质心识别。没有把已知绘图器的72/44px偏移或真实端点坐标传给管线。',
'占据像素按公开0.25m圆盘（13px）加固定2px余量做欧氏圆盘膨胀；边框/外侧禁止。每2px一个节点（约0.03846m）；四邻接边检查所有中间像素，端点连接用保守supercover，禁止穿角与接触。',
'BFS与A*使用完全相同的分割/安全栅格/边和端点连接；A*用曼哈顿启发式。它们不是两个独立视觉模型，比较只检验搜索选择是否改变可达性。',
'如帧/圆盘检测或连接失败，记录unknown/pipeline_error和异常，不用私有几何补回。实际40图管线失败0，两搜索可达性分歧0。',
'该分割器依赖封闭、干净的已知颜色风格；对未知纹理、遮挡、自然图像或语义物体不作能力主张。深色注释并非设计中的障碍，抗锯齿颜色/像素边界仍可能造成小范围误分。',
f"事后才用真实几何审核：障碍IoU（去掉2px边框）最低{quality['posthoc_obstacle_iou_min']:.4f}、均值{quality['posthoc_obstacle_iou_mean']:.4f}，端点最大误差{quality['posthoc_max_endpoint_error_m']:.5f}m。差异未被用于修正预测。",
f"20个可达图的40条BFS/A*路径，连同真实起终点的短连接，全部通过独立几何碰撞复核；返回路径最小额外净空{quality['rgb_returned_path_min_clearance_m']:.5f}m。它是实际返回见证的净空，不是最优通道余量。",
'[事后分割与路径审核](posthoc_segmentation_path_audit.json) · [从像素得到的占据/安全图与路径](../../outputs/phase3_7/rgb/)',
'真值Oracle直接拥有多边形坐标，用于定义标签和参考上限；它的标签自洽不能包装成公平图像方法100%性能。', '',
'## 6. 五组方法对照', '',
'### 6.1 旧16题（已分析诊断集）', '',
'| 方法 / 输入信息 | 总体正确 | A直通 | B绕行 | C隔断 | D封闭 |', '|---|---:|---:|---:|---:|---:|']
for dataset in ['old16','new24']:
    if dataset=='new24':lines+=['','### 6.2 新24题（本轮冻结控制）','','| 方法 / 输入信息 | 总体正确 | A直通 | B绕行 | C隔断 | D封闭 |','|---|---:|---:|---:|---:|---:|']
    for method in ['4b','8b','bfs','astar']:
        s=m['sets'][dataset][method]
        lines.append('| '+names[method]+('（原结果复用）' if dataset=='old16' and method=='4b' else '')+' | '+f"{s['correct']}/{s['total']} ({s['accuracy']:.1%})"+' | '+' | '.join(f"{s['categories'][c]['correct']}/{s['categories'][c]['total']}" for c in 'ABCD')+' |')
    n=16 if dataset=='old16' else 24
    lines.append(f'| 真值几何Oracle / 私有真实坐标 | {n}个参考标签，三网格一致 | 标签参考 | 标签参考 | 标签参考 | 标签参考 |')
lines+=['','两集合的恒可达/恒不可达基线均为50%（旧8/16，新12/24）。JSON成功率：旧4B16/16保留、8B40/40、新4B24/24；unknown均0。','','![分场景准确率](method_comparison.png)', '',
        '### 6.3 混淆计数与召回', '',
        '| 集合 | 方法 | TP | FP | TN | FN | 未知 | 可达召回率 | 不可达识别率 |','|---|---|---:|---:|---:|---:|---:|---:|---:|']
for dataset in ['old16','new24']:
    for method in ['4b','8b','bfs','astar']:
        s=m['sets'][dataset][method]
        lines.append(f"| {dataset} | {names[method]} | {s['TP']} | {s['FP']} | {s['TN']} | {s['FN']} | {s['unknown']} | {s['reachable_recall']:.1%} | {s['unreachable_recognition_rate']:.1%} |")
lines+=['','### 6.4 同图4B→8B配对变化', '',
        '| 集合 | 4B错→8B对 | 4B对→8B错 | 双方正确 | 双方错误 | 预测一致 |','|---|---:|---:|---:|---:|---:|']
for d in ['old16','new24']:
    p=m['paired'][d];n=16 if d=='old16' else 24
    lines.append(f"| {d} | {p['4b_wrong_8b_right']} | {p['4b_right_8b_wrong']} | {p['both_correct']} | {p['both_wrong']} | {p['prediction_agreements']}/{n} |")
lines+=['',
'旧16总体净增1题，但绕行仍1/4：8B修正中央块绕行，同时把原来4B答对的L走廊判错；另修正一例水平隔断。',
'新24旧错新对4、旧对新错4，总体持平。8B改善A(+1)和C(+3)，同时B(-3)、D(-1)退化。不能只展示被修正的案例来声称参数规模解决了问题。',
'8B旧16输出5可达/11不可达，新24输出8可达/16不可达；4B新24为12/12。没有恒否，但8B新正例漏判7/12、负例误报3/12。', '',
'### 6.5 每图延迟（秒，包含图像处理）', '',
'| 集合 | 方法 | PNG至预测平均秒 | 计时边界 |','|---|---|---:|---|']
for d in ['old16','new24']:
    for method in ['4b','8b','bfs','astar']:
        s=m['sets'][d][method]
        note='原Phase3.6 elapsed，历史运行' if d=='old16' and method=='4b' else 'VLM elapsed：图像读取/处理+生成/解码等' if method in ['4b','8b'] else '读取+分割+膨胀+连接+搜索；预处理完整计入'
        lines.append(f"| {d} | {names[method]} | {s['end_to_end_mean_seconds']:.4f} | {note} |")
lines+=['',
'RGB新24的图像/栅格预处理均值0.16985s，BFS搜索0.08609s、A*搜索0.08582s；表中均已相加，未用纯搜索与VLM纯生成作比较。',
f"新4B纯生成均值{statistics.mean(r['inference_seconds'] for r in raws['vlm4b_new']):.4f}s；8B40图纯生成均值{statistics.mean(r['inference_seconds'] for r in raws['vlm8b_a']):.4f}s，作为附属记录，不替代上表端到端比较。",
'共享RGB预处理虽只执行一次，对每种方法都完整计入，不把A*当免费分割。RGB计时不包括调试图导出；VLM沿用runner elapsed，含少量输入/原文证据写盘，边界并非严格微基准。',
'模型加载/下载均单独报告、不计单图延迟。旧4B延迟来自历史运行，冷启动、缓存、CPU/GPU执行环境及输出长度有差异；不做精确加速倍数或统计速度结论。', '',
'## 7. 代表性错误及解释核实', '',
'以下均为推理后分析，不更改输入、prompt、栅格或答案；是代表性案例，不是解释正确率的盲评统计。', '',
'- **明显直线仍漏判（两模型）** p_32d6a22ec7c2ec8f：直线x=3、y=1.5→10.5，障碍均在更右侧，参考净空1.25m。8B却称obstacles blocking direct and indirect paths；4B也判false。不是反事实或组合任务。',
'- **双岛绕行（4B对、8B错）** p_7573e6e10d3a96ab：8B称0.25m半径无法在障碍间或外侧通过。上绕参考路线(1.5,5)→(1.5,10)→(10.5,10)→(10.5,5)净空1.25m，否定这种尺寸解释。4B的true正确，但move directly若指直线也与几何不符，答对不等于解释可靠。',
'- **三角岛（4B对、8B错）** p_b49e1b1f3d1fd436：8B称无法绕过三角障碍；经(2,2)→(10,2)→(10,10)合法，参考净空1.75m。',
'- **三层挡板（4B对、8B错）** p_e6f1ddef95e00ff7：8B从direct paths被挡及半径限制推断不能绕行；预先验证的上下交替路线净空0.85m。',
'- **圆C形墙（双方错）** p_de448527dd8433ec：8B说no path exists around；实际可从左侧2.8m开口退出，走下方外侧绕到Goal，参考净空1.15m。',
'- **嵌套闭环（4B对、8B错）** p_70c5c792dd442f3c：8B称可以inward through gaps between concentric squares。环间空地不等于墙上入口；两条墙环都闭合，Goal在最内层，几何中没有所说的穿墙缺口。',
'- **菱形/圆角闭环（双方错）** p_e9d59eb2777fc8fe、p_412eb82fa7aa1df7：模型称可绕过外墙到Goal，但Goal在闭合内孔中，绕外侧不能进入。RGB两算法均判不可达。',
'- **旧题局部恢复与退化并存** c_345724ed30668b5a从4B错变8B对；c_2c2b0c3cc18e3654从4B对变8B错。后者8B称size和L-shaped barrier使不可达，但参考路线净空1.25m。', '',
'这些错误涉及通路搜索、局部尺寸解释、孔洞/封闭关系或视觉解析，无法由简短输出唯一归因。不存在本轮控制下证明纯组合缺陷的证据。',
'[全部方法错误原文与答案](error_cases.jsonl) · [40题完整配对原文/真值/路径](paired_cases.jsonl)', '',
'## 8. Part C停止记录：未执行，不是零分', '',
'正式推理前已固定：新6个绕行至少4个正确，且新12个负例至少10个正确，才允许探索性复查；3/6也未达最低门槛。后一个门槛是预先操作化“隔断没有严重退化”的保守运行条件，不是统计可靠性定义。',
'实际8B绕行0/6，直接满足用户“仅0–2个先停止”的规则；负例9/12也未达保守门槛。因此没有运行原Phase3六核心的8B、没有生成8个匹配干预场景、没有运行其4B/8B/公开编辑+BFS。',
'本轮Part C的F_A、F_B、F_AB、完整组合正确率、单项均对而联合错误次数，以及模型/图像反事实配对均为**未测（N/A）**；不能填成0或从基础任务推算。',
'旧Phase3的4B反事实错误仍完整保留，但本轮无法回答8B是否仍有独立的反事实缺陷、或在基础判断正确后联合干预是否重复出错。',
'[机器可读停止记录](part_c_status.json) · [冻结门槛及实际计数](part_a_b_metrics.json)', '',
'## 9. 选题终局判断：分别回答三个问题', '',
'**问题一：更大的VLM是否改善基础空间推理？** 没有获得一致改善。旧16净增1，新24总体持平；C隔断改善，但新B绕行退化到0/6，D封闭也退化。',
'本轮不支持“4B太小，换同系列8B即可解决”为主要工作假设。模型能力仍可能参与错误；两个checkpoint的训练等因素也非只改变参数量，不能据此证明规模完全无关或全部错误的唯一原因。', '',
'**问题二：这类二维地图可达性是否更适合几何求解？** 在当前干净、封闭图例、已知尺度/半径的控制条件下，公开RGB提取+标准搜索解决全部40题，VLM仍不稳定。',
'对这一任务，本轮没有显示VLM的正确率或可验证路线优势；通用搜索提供了可检查见证，不需真实多边形输入。A*与BFS一致只说明同一图的搜索选择不改变判断。',
'这支持把纯二维几何可达性作为几何求解问题，而非单独包装成VLM新方法论文；不否定包含语言语义、开放物体类别、任务约束和现实感知的广义具身空间推理。', '',
'**问题三：是否仍有独立反事实干预研究空隙？** 当前证据不足。基础绕行和封闭判断未控制好，Part C按规则停止，尚未发现“基础可靠而假设编辑/联合关系仍清晰且可重复出错”的隔离证据。',
'**建议停止当前纯二维地图+反事实组合缺陷路线，No-Go。** 不再为获得更好成绩而换prompt、调渲染、下载更多模型、扩充题量或训练LoRA。若研究者以后提出不同语义/约束问题，应作为新的研究决策另行审查，本任务不实施。', '',
'## 10. 证据限制、测试与历史完整性', '',
'- 仅一对同系列checkpoint、单seed/greedy、单图风格、40个诊断案例，旧16已分析，新24手工设计；不做总体推断或显著性/泛化措辞。',
'- 场景各类的形状、密度、转弯数及颜色没有全面因子平衡；H1/H2不是只改变参数规模一个因素的严格因果实验。',
'- RGB规则专用于公开配色，不能推断自然图像表现；分割并非逐像素完美，额外安全余量也可能在其他窄缝图中造成漏判。',
'- 原始多边形Oracle拥有额外真实坐标；标签自洽不作公平方法100%成绩。本轮图像方法预测和事后几何复核严格分开。',
'- 简短解释不是内部推理轨迹，正确/错误机制只能有限核实；没有执行Part C，不能确认或否认广义反事实能力。', '',
f"推理前最终{tests['before']['tests']}项、推理后{tests['after']['tests']}项测试全部通过，失败/错误/跳过均0。原132项完整保留，新增40项协议/图像/评分测试及7项运行证据测试。",
'检查覆盖24题合法性/宽裕量/三网格一致、旧题原样复用、Prompt/配置一致、RGB独立性、圆盘膨胀与接触、同图BFS/A*、失败无回退、严格JSON、一次正式调用、真实视觉执行和评估时间顺序。',
'原Phase0–3.6全部463个已跟踪项目文件SHA256一致，包括全部旧源码、README、AGENTS、原预测、场景、报告和依赖锁；两环境版本和两模型文件全部匹配。',
'inspection_robot源码及选定ROS/CUDA/系统Python/shell等113项保护文件未变，未终止其他进程。该审计有明确范围，不声称扫描了整个系统。',
'[前环境检查](environment_before.json) · [后环境/历史保护检查](environment_after.json) · [测试日志](logs/tests_after.log) · [全部原始输出SHA256](raw_output_sha256.json) · [文件结构/重现边界](README.md)', '',
'全部源码、非敏感配置、24场景、原始输出与报告同步到公开iC0ol/EAI；模型权重、环境、运行时和缓存不上传。',
'**Phase3.7至此结束，等待研究者复核；不自动开启下一阶段。**', '',
'## 附：逐例配对（1可达，0不可达）', '',
'| 集合 | 图像ID | 类别 | 真值 | 4B | 8B | RGB+BFS | RGB+A* |', '|---|---|---|---:|---:|---:|---:|---:|']
def bit(v):return '1' if v is True else '0' if v is False else 'null'
for c in cases:
    phase='phase3_6' if c['dataset']=='old16' else 'phase3_7';sid=c['sample_id']
    lines.append(f"| {c['dataset']} | [{sid}](../../diagnostics/{phase}/images/{sid}.png) | {c['category']} | {bit(c['truth'])} | "+' | '.join(bit(c['methods'][method]['prediction']) for method in ['4b','8b','bfs','astar'])+' |')
lines+=['','旧4B原始回答：[Phase3.6预测](../../outputs/phase3_6/predictions.jsonl)；新模型原文：[8B40图](../../outputs/phase3_7/vlm8b_a/) · [4B新24](../../outputs/phase3_7/vlm4b_new/)。','']
with (report/'phase3_7_diagnostic.md').open('x') as f:f.write('\n'.join(lines))
print('Report, five-method tables, paired appendix, error cases, figures and explicit Part C No-Go record written.')
