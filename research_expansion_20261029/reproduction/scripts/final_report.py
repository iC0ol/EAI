"""Generate an honest terminal report using the standard library only."""
import json,datetime
from common import ROOT,utc,read_json,atomic_json,sha
def rows(p):return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []
def local(x):return datetime.datetime.fromisoformat(x).astimezone(datetime.timezone(datetime.timedelta(hours=8))).isoformat() if x else 'NA'
def main():
    status=read_json(ROOT/'status.json',{});run=read_json(ROOT/'run.json',{});sem=read_json(ROOT/'results/semantics.json',{});train=read_json(ROOT/'training_progress.json',{});dev=read_json(ROOT/'results/dev_summary.json',{});test=read_json(ROOT/'results/test_summary.json',{});loss=read_json(ROOT/'results/loss_summary.json',{});audit=read_json(ROOT/'results/offline_action_audit.json',{});plan=read_json(ROOT/'frozen_training_plan.json',{});smoke=read_json(ROOT/'results/smoke_throughput.json',{});ck=read_json(ROOT/'checkpoint_manifest.json',{})
    stages={p.stem:read_json(p) for p in sorted((ROOT/'stages').glob('*.json')) if not p.stem.endswith('_attention')}
    devrows=rows(ROOT/'results/dev_rollouts.jsonl');testrows=rows(ROOT/'results/test_rollouts.jsonl');fixed=rows(ROOT/'results/dev_fixed_observation.jsonl')
    counts={'expert_replays':sem.get('expert_n'),'expert_successes':sem.get('expert_successes'),'expert_action_steps':sum(x['steps'] for x in sem.get('rows',[])) if sem else None,'C_optimizer_updates_including_smoke':train.get('updates'),'C_completed_epochs':train.get('completed_epochs'),'C_train_original_demos':200 if train else None,'C_validation_original_demos':10 if train else None,'U_training_state':'NOT_RUN','U_optimizer_updates':None,'U_scientific_rollouts':None,'U_initialized_interface_forward_calls':2 if (ROOT/'results/U_metadata_negative_control.json').exists() else None,'dev_independent_roots':dev.get('n'),'dev_successes':dev.get('successes'),'dev_repeat_rollouts':dev.get('extra_reproducibility_rollouts'),'dev_total_policy_rollouts':len(devrows) if devrows else None,'dev_environment_steps_including_repeat':sum(x['steps'] for x in devrows) if devrows else None,'dev_fixed_observation_roots':len(fixed) if fixed else None,'C_dev_inference_queries':sum(x['query_count'] for x in devrows)+5*len(fixed) if devrows else None,'formal_test_state':test.get('state','NOT_RUN'),'formal_test_rollouts':len(testrows) if testrows else None,'formal_test_independent_roots':len({x['root_id'] for x in testrows}) if testrows else None,'paired_success_comparisons':'COMPLETE' if test.get('complete') else 'NOT_RUN','new_method_training':'NOT_RUN'}
    floor=dev.get('state')=='IMPLEMENTATION-LIMITED';evidence='IMPLEMENTATION-LIMITED' if floor else ('MEASUREMENT-LIMITED' if dev.get('metadata_insensitive') else ('EVALUATED_SINGLE_SEED' if test.get('complete') else 'TECHNICAL-BLOCKED'));completeness='COMPLETE_C_ONLY_PROTOCOL' if test.get('complete') else 'PARTIAL'
    reason='DEV_BASELINE_FLOOR: accurate-metadata C succeeded 0/32; protocol stops formal error/moved-camera rollouts' if floor else status.get('reason','see stage logs')
    res=rows(ROOT/'logs/resources.jsonl');gpu_names={x['name'] for x in read_json(ROOT/'queue.json',{'stages':[]})['stages'] if x.get('gpu')};starts={x['stage']:x for x in rows(ROOT/'logs/events.jsonl') if x.get('event')=='START'};intervals=[]
    for name in sorted(gpu_names):
        if name in starts and name in stages and stages[name].get('completed_utc'):
            seconds=(datetime.datetime.fromisoformat(stages[name]['completed_utc'])-datetime.datetime.fromisoformat(starts[name]['utc'])).total_seconds();intervals.append({'stage':name,'conservative_seconds_including_poll_tail':seconds})
    resource={'utc':utc(),'supervisor_gpu_allocation_seconds':status.get('gpu_allocation_seconds'),'gpu_allocation_upper_seconds_from_stage_intervals':sum(x['conservative_seconds_including_poll_tail'] for x in intervals),'gpu_stage_intervals':intervals,'sampled_process_tree_RSS_peak_bytes':max((x['rss_bytes'] for x in res),default=None),'sampled_device_memory_peak_bytes_including_display':max((x['gpu_memory_total_used_bytes'] for x in res if x.get('gpu_memory_total_used_bytes') is not None),default=None),'torch_allocated_peak_bytes':max(train.get('vram_allocated_peak_bytes',0),smoke.get('vram_allocated_peak_bytes',0)),'torch_reserved_peak_bytes':max(train.get('vram_reserved_peak_bytes',0),smoke.get('vram_reserved_peak_bytes',0)),'sampled_min_mem_available_bytes':min((x['mem_available_bytes'] for x in res),default=None),'sampled_min_disk_free_bytes':min((x['disk_free_bytes'] for x in res),default=None),'sampled_max_new_disk_bytes':max((x['new_disk_bytes'] for x in res),default=None),'download_bytes_conservative':max((x['download_bytes_conservative'] for x in res),default=None),'cpu_affinity':read_json(ROOT/'cpu_affinity.json'),'resource_sample_count':len(res),'sampling_limitation':'RSS/device memory/disk are minute samples; torch reports its own allocator peak; no continuous RSS high-water claim'}
    atomic_json(ROOT/'resource_summary.json',resource);atomic_json(ROOT/'actual_counts.json',counts)
    integrity=[]
    for stage,d in stages.items():
        for name,expected in d.get('outputs',{}).items():
            if stage=='05_C_smoke' and name in ['checkpoint_manifest.json','training_progress.json']:
                integrity.append({'stage':stage,'path':name,'state':'ROLLING_FILE_SUPERSEDED','note':'smoke throughput retained; these two files explicitly track latest training state'});continue
            actual=sha(ROOT/name) if (ROOT/name).is_file() else None;integrity.append({'stage':stage,'path':name,'state':'MATCH' if actual==expected['sha256'] else 'MISMATCH','expected_sha256':expected['sha256'],'actual_sha256':actual})
    fixed_inputs={'protocol_sha256':sha(ROOT/'PROTOCOL.md'),'protocol_matches_frozen':sha(ROOT/'PROTOCOL.md')==run.get('protocol_sha256'),'checkpoint_sha256':sha(ROOT/ck['path']) if ck.get('path') else None,'checkpoint_matches_manifest':sha(ROOT/ck['path'])==ck.get('sha256') if ck.get('path') else False,'root_manifest_matches_training_plan':sha(ROOT/'manifests/frozen_roots.json')==plan.get('root_manifest_sha256') if plan else False}
    delivery={'utc':utc(),'fixed_inputs':fixed_inputs,'stage_output_integrity':integrity,'stage_mismatches':[x for x in integrity if x['state']=='MISMATCH'],'counts_match_frozen_training':train.get('updates')==plan.get('C_target_updates') and train.get('completed_epochs')==plan.get('C_target_epochs'),'formal_test_not_run_because_dev_floor':floor and not testrows,'dev_policy_rollouts_within64':len(devrows)<=64,'expert_replays_within10':(sem.get('expert_n') or 0)<=10,'old_projects_modified_by_this_task':False,'git_operations_by_this_task':'none'}
    atomic_json(ROOT/'delivery_integrity.json',delivery)
    g=resource['gpu_allocation_upper_seconds_from_stage_intervals']/3600;ram=(resource['sampled_process_tree_RSS_peak_bytes'] or 0)/1024**3;vram=resource['torch_reserved_peak_bytes']/1024**3;disk=(resource['sampled_max_new_disk_bytes'] or 0)/1024**3;network=(resource['download_bytes_conservative'] or 0)/1024**3
    sens=test.get('dev_fixed_action_sensitivity',{}).get('persistent-10',{});height=dev.get('auxiliary',{}).get('object_height_mean_max_m',0);gripper=audit.get('fixed_metadata10',{}).get('gripper_sign_disagreement_fraction_mean',0)
    condition_lines='\n'.join('| '+c+' | '+x['state']+' | '+(str(x['successes']) if x['successes'] is not None else 'NA')+' / '+(str(x['n']) if x['n'] is not None else 'NA')+' |' for c,x in test.get('conditions',{}).items())
    report=f'''# KYC 相机条件策略复现最终报告

**任务已按冻结停止规则结束。完整度：{completeness}；证据状态：{evidence}。**

C完成官方训练数量，但准确外参dev为 **{dev.get('successes','NA')}/{dev.get('n','NA')}成功**，未达到4/32最低工程门槛。正式持续偏差 vs IID、0/5/10°任务曲线、真实相机移动分解全部 **NOT_RUN**。本轮没有可辨识的标定误差任务成功结论，不能称论文数值复现或科学阴性。

停止原因：{reason}。不是预算耗尽；不因还有GPU余额而继续调参、重训或追加条件。报告生成：{local(utc())}。

## 来源与执行范围

用户原始人类消息已从主聊天read_thread核验，包含实际实验及完成后回传授权，见[authorization.json](authorization.json)。发布时间2026-10-29 01:26:35 +08:00，派发设置gpt-6.1-sol / max。冻结协议SHA256 `{run.get('protocol_sha256')}`，未修改。

KYC固定commit [`e0647105a0f3946581d253c55dc9fd1218fa0974`](https://github.com/ripl/CamPoseOpensource/tree/e0647105a0f3946581d253c55dc9fd1218fa0974)，RoboSuite固定commit [`0df3a5f5782937fa2e8fa923910d616b73310b8d`](https://github.com/ripl/robosuite/tree/0df3a5f5782937fa2e8fa923910d616b73310b8d)。上游源码未编辑，直接导入官方ACT、Dataset、delta wrapper；新代码只负责监督、恢复和评估。

官方公开Drive单文件liftrand_eef_delta.hdf5：ID `1s2sGrLVbHIpTCDXld0NIu8bI5HoRYsqo`，46,832,160 bytes，SHA256 `fc89e2a46624b877cd35ae383df9ad09a84b7881c655bc114812164d6ff45377`。300原始demos中只用0–199训练、200–209验证，无数据扩展。另取官方ImageNet ResNet18权重，无KYC训练完成权重。资产及依赖见[asset_manifest.json](asset_manifest.json)、[requirements.freeze](requirements.freeze)。本地旧环境的runtime/依赖独立复制到新目录后补齐，原环境未改动，没有使用旧任务策略权重。

## 分阶段完整度

| 阶段 | 完整度 | 真实结果 |
|---|---|---|
| 动作/几何验收 | COMPLETE，有1项记录修复 | expert10/10成功，ray方向/矩/投影通过 |
| C冒烟 | COMPLETE | 2 epochs +30更新，共36更新，计入总量 |
| C训练 | COMPLETE | 20,001 epochs，60,003优化更新，seed0 |
| U训练 | NOT_RUN | 等量训练和评估不适合冻结预算；仅初始化接口阴性检查 |
| dev准确外参 | COMPLETE / IMPLEMENTATION-LIMITED | 0/32成功、0接近、0夹持；另1次clean重放不算独立root |
| dev固定观测动作诊断 | COMPLETE | 32 roots；5/10°及zero/shuffle，不增加闭环噪声rollout |
| 50 test roots ×7设置 | NOT_RUN | dev地板规则触发，未生成test物理场景或执行test策略 |
| 配对成功差及区间 | NOT_RUN | success/n/difference/CI均null，不填0 |

### 训练与恢复证据

保持官方Lift配置：original=0、200 demos、n=3/m=1、单side camera、256×256、crop、late_imagenet、batch70（每epoch70/70/60）、chunk30及其余默认ACT超参。没有缩图、缩网络、减少示范或新方法训练。配置见[manifests/C_config.json](manifests/C_config.json)。每epoch遍历200-demo Dataset，20,001 epochs对应60,003更新。

完整batch冒烟稳态均值{smoke.get('steady_full_batch_seconds_mean',0):.4f}s，计划于{local(plan.get('frozen_utc'))}、任何test之前一次冻结为C-only。C记录训练时间{train.get('train_elapsed_seconds',0)/3600:.3f}h，最终checkpoint于{local(ck.get('utc'))}保存。最后训练loss {loss.get('last_train_loss')}，末1000更新平均L1 {loss.get('last1000_mean_train_l1')}，最后验证loss {loss.get('last_validation',{}).get('loss')}。loss下降未建立任务学习证据。

最终checkpoint SHA256：`{ck.get('sha256')}`。包含model、optimizer、scheduler、Python/NumPy/CPU/CUDA RNG、sampler排列/游标/生成器。正式阶段真实恢复smoke的36更新检查点，并在对话中断期间独立完成60003更新。五小时检查重算最终hash、验证PID启动ticks及flock，没有重启训练。

### 语义验收与已知偏差

eef_delta经官方wrapper累加成世界坐标绝对目标；前10条固定demo全部成功，最大EEF轨迹偏差约43微米，首目标重建最大误差约2.4e-7。公开HDF5无逐demo XML，回放仅用官方生成器默认seed42+i，未搜索成功seed。HDF5 env_version为1.4.1，固定子模块声明1.5.1；无法证明精确采集模型一致。

cam2world为OpenGL坐标，RGB竖直翻转；ray通道为origin×unit direction后接unit direction，crop同步。保留官方raymap额外0.5像素偏置，解析投影按同接口验证。见[results/semantics/camera_raymap_checks.json](results/semantics/camera_raymap_checks.json)。

原轨迹末状态/compiled XML重载图像不一致，失败exit1和原件保留，原因没有证明。修复后对与配对评估相同的“源码模型XML+初始完整state”连续恢复，图像逐像素一致；dev root1000完整clean rollout额外重放一次，全部动作及成功状态完全一致。本验收不承诺任意中途状态恢复。详见[repairs.json](repairs.json)、[patches/README.md](patches/README.md)。

验证相机按协议改为训练pool，禁用训练内test rollout，使用最终固定checkpoint。自定义可恢复sampler的独立seed0 RNG流与官方DataLoader不完全相同。U接口阴性检查延到dev，未训练U。smoke的两份滚动状态文件被正式训练更新，旧hash不能重验；不可变吞吐结果、日志及最终阶段hash保留。评估入口在五小时续查时完成，训练结束至检查之间约12分钟空闲监督。这些偏差均不作为已排除的失败原因。

## dev观察与结论边界

准确外参0/32成功，均执行150步，无非有限动作；0次EEF到目标距离小于5cm，0次夹持。各root最大对象高度均值{height:.6f}m。root1000的目标平移增量总和约[-0.00091,-0.00114,-0.07668]m，x/y增量很小；这是目标增量之和，不是实测EEF位移。逐根结果见[results/dev_per_root.csv](results/dev_per_root.csv)，原始动作、高度、成功/夹持标签在results/traces/，未删除失败根。

固定观测下，10°metadata误差导致30×3平移动作差Frobenius范数均值约{1000*sens.get('translation_L2_over_chunk_mean',0):.3f}mm，旋转分量差范数约{sens.get('rotation_L2_over_chunk_mean',0):.6f}rad；夹持通道符号分歧比例均值{gripper:.3f}。这些是动作张量差，不能当作任务或EEF位姿误差。zero/shuffle也改变输出，故C并非数值上完全忽略raymap；在baseline地板下仍无法推断成功率影响。

RGB-only初始化架构对同RGB下扰动raymap的输出最大差为0，只是接口阴性检查，不是学会任务的U基线。原始chunk及有向平移/旋转差见[results/dev_fixed_observation.jsonl](results/dev_fixed_observation.jsonl)、[results/offline_action_audit.json](results/offline_action_audit.json)。

正式设置与dev的0/32分开：

| 正式设置 | 状态 | success / n |
|---|---|---|
{condition_lines}

主对比persistent10−iid10、5°诊断、移动stale−correct、discordance、bootstrap95%区间与0/5/10°成功曲线均NOT_RUN。冻结的50个test root与噪声轴仅是计划，不能算已执行样本。移动方案围绕名义workspace_center位移并重新朝向；原pose有target jitter，实际旋转角另存；边界符号按结果前几何反向。该协议解释已注明且本轮未执行，供研究者后续审查。

## 资源与交付

GPU按阶段起止并包含轮询尾部的保守分配约{g:.3f}h，上限8h；torch reserved峰值{vram:.3f}GiB；分钟采样进程树RSS峰值{ram:.3f}GiB。下载保守统计{network:.3f}GiB，新增磁盘采样峰值{disk:.3f}GiB。详见[resource_summary.json](resource_summary.json)和logs/resources.jsonl。RSS/设备显存/磁盘是分钟采样，不能声称没有采样间峰值；torch另记录allocator峰值。

模型/仿真在dev地板处停止，早于12:26:35计算截止；最终13:26:35上限未改变。没有新worktree，没有修改系统Python/CUDA/驱动/ROS/旧项目，没有Git index、commit/push操作。原始计数见[actual_counts.json](actual_counts.json)，阶段exit与hash见stages/，恢复和实际命令见[RECOVERY.md](RECOVERY.md)，交付一致性见[delivery_integrity.json](delivery_integrity.json)。环境、权重、数据、镜像、缓存、完整XML和日志留本地；原创小型成果由主研究者独立复核后公开同步。

**下一步应先取得可信的官方行为基线，再研究标定时间相关性。** 专家回放和接口检查降低了明显动作/通道接错的疑虑，但没有证明实现与论文等价。研究者可先审查数据/依赖/采集版本、训练过程及先验推理的数值一致性，或取得可信官方checkpoint；目前不能指定根因、提出新网络必要性、宣称鲁棒或科学无效。本轮停止，不追加实验。
'''
    (ROOT/'FINAL_REPORT.md').write_text(report)
    (ROOT/'STATUS.md').write_text(f'# 状态\n\nTERMINAL / {completeness} / {evidence}\n\nC完成20001 epochs /60003更新；dev准确外参0/32成功，触发冻结科学停止。正式误差/真实移动rollout、U训练和配对成功统计全部NOT_RUN。无剩余授权实验。\n\nGPU保守分配约{g:.3f}h，截止时间未改变。报告：[FINAL_REPORT.md](FINAL_REPORT.md)。只读恢复入口：[RECOVERY.md](RECOVERY.md)。\n\n一次完成回传的状态见completion.json；成功回执见notification_receipt.json。\n')
    previous=read_json(ROOT/'completion.json',{})
    completion={'utc':utc(),'terminal':True,'completeness':completeness,'evidence_status':evidence,'stop_reason':reason,'scientific_conclusion':'No identifiable calibration task-success result: baseline dev gate failed. Not a scientific null or paper numerical reproduction.','actual_counts':counts,'gpu_allocation_upper_hours':g,'report_path':str(ROOT/'FINAL_REPORT.md'),'report_sha256':sha(ROOT/'FINAL_REPORT.md'),'parent_thread_id':'01a18138-0f15-76b2-b5cf-20e1722782a9','notification_state':previous.get('notification_state','PENDING_CHAT_TOOL'),'stage_exit_codes':{k:v.get('exit_code') for k,v in stages.items()},'further_experiments_authorized':False}
    atomic_json(ROOT/'completion.json',completion)
    print(json.dumps({'terminal':True,'completeness':completeness,'evidence_status':evidence,'gpu_hours':g,'integrity_mismatches':len(delivery['stage_mismatches'])},ensure_ascii=False))
if __name__=='__main__':main()
