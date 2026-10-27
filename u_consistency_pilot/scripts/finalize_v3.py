#!/usr/bin/env python3
"""CPU/stdlib finalizer, usable after worker crashes; explicit public-file allowlist."""
import argparse,csv,hashlib,json,os,re,signal,subprocess,time
from pathlib import Path
from datetime import datetime,timezone
from download_v3 import BASE,atomic,sha,utc

def main():
    p=argparse.ArgumentParser();p.add_argument('--run-id',required=True);p.add_argument('--reason',default='COMPLETE');p.add_argument('--publish',action='store_true');a=p.parse_args()
    run=BASE/'outputs'/('v3_'+a.run_id);report=BASE/'reports'/('v3_'+a.run_id);report.mkdir(exist_ok=True)
    cfg=json.loads((BASE/'configs/protocol_v3.json').read_text())
    def load(name,default):
        try:return json.loads((run/name).read_text())
        except (OSError,ValueError):return default
    def clean(s):
        s=str(s).replace(str(BASE.parent),'$EAI').replace(str(Path.home()),'$HOME')
        s=re.sub(r'(?:gh[pousr]_|github_pat_|hf_)[A-Za-z0-9_]{20,}','[REDACTED]',s)
        s=re.sub(r'https://[^\s]+[?][^\s]+','[URL_QUERY_REDACTED]',s)
        return s
    # Stop only this run's own independent download if still pending.
    for path in Path('/proc').iterdir():
        if not path.name.isdigit():continue
        try:
            cmd=(path/'cmdline').read_bytes()
            if b'download_ranges_v3.py' in cmd and a.run_id.encode() in cmd and b'python' in cmd.split(b'\0')[0]:os.kill(int(path.name),signal.SIGTERM)
        except OSError:pass
    (run/'.control/watch_stop').touch()
    for _ in range(10):
        if load('resource_watch.json',{}).get('ended_at_utc'):break
        time.sleep(1)
    resources=load('resource_watch.json',{});download=load('download_bytes.json',{})
    result=load('scientific_summary.json',{})
    status=load('status.json',{});reason=clean(a.reason)
    if result.get('final_status') and a.reason=='COMPLETE':disposition=result['final_status']
    elif 'RESOURCE' in reason:disposition='RESOURCE-BLOCK'
    elif 'DEADLINE' in reason or 'INTERRUPTED' in reason:disposition='PARTIAL-DEADLINE'
    elif any(x in reason for x in ['NETWORK','HTTPError','NETWORK_BLOCK']):disposition='NETWORK-BLOCK'
    elif 'BASELINE' in reason:disposition='BASELINE-UNSUPPORTED'
    elif 'INCONCLUSIVE' in reason:disposition='INCONCLUSIVE'
    else:disposition='TECHNICAL-BLOCK-AFTER-REPAIR'
    end=datetime.now(timezone.utc);start=datetime.fromisoformat(cfg['task_started_at_utc'])
    counts={};missing=[]
    try:prospective=json.loads((run/'roots_frozen.json').read_text())
    except (OSError,ValueError):prospective=[]
    for split in ['cal','dev','test']:
        filename={'cal':'calibration_pairs.jsonl','dev':'real_transitions_dev.jsonl','test':'real_transitions_test.jsonl'}[split]
        rows=[]
        if (run/filename).exists():
            for line in (run/filename).read_text().splitlines():
                try:rows.append(json.loads(line))
                except ValueError:pass
        valid=[r for r in rows if r.get('status')=='OK'];by={(r['root'],r['candidate']):r for r in valid}
        expected={'cal':32,'dev':16,'test':64}[split]
        complete_roots=[root for root in {r['root'] for r in valid} if all((root,j) in by for j in range(8))]
        counts[split]={'valid_candidate_records':len(by),'duplicate_valid_records':len(valid)-len(by),'independent_roots_with_any_valid_candidate':len({r['root'] for r in valid}),'independent_roots':len(complete_roots),'independent_sources':len({r['source'] for r in valid if r['root'] in complete_roots}),'target_roots':expected}
        frozen={(r['root'],r['candidate']):r for r in load_lines(run/f'frozen_predictions_{split}.jsonl')}
        known={r['root']:r for r in prospective if r['split']==split}
        for index in range(expected):
            root=f'{split}_{index:03d}'
            for candidate in range(8):
                if (root,candidate) in by:continue
                score=frozen.get((root,candidate),{});actions=score.get('action_block')
                missing.append({'split':split,'root':root,'source':known.get(root,{}).get('source'),'seed':known.get(root,{}).get('seed'),'candidate':candidate,'action_block':actions,'status':'NOT_RUN','reason':reason,'J':None})
    write_missing(run/'missing_candidates.csv',missing)
    test_complete=(counts['test']['independent_roots']==64 and counts['test']['valid_candidate_records']==512 and counts['test']['duplicate_valid_records']==0 and 'analyze_test' in status.get('completed_stages',[]) and result.get('test_n_roots')==64)
    summary={**result,'run_id':a.run_id,'final_status':disposition,'reason':reason,'completed_stages':status.get('completed_stages',[]),'counts':counts,'ended_at_utc':end.isoformat(),'test_complete':test_complete,'primary_comparison':result.get('primary_comparison'),'evaluation_status':'COMPLETE' if test_complete else 'NOT_RUN_OR_PARTIAL','scientific_claim_scope':'One frozen LeWM, one G training seed, short-horizon shared-pool choice only','next_action':'STOP_AND_AWAIT_RESEARCHER_REVIEW','unrun_metrics_policy':'null / NOT_RUN, never synthetic zeros'}
    atomic(run/'summary.json',summary)
    stepcounts=load('step_counts.json',{})
    budget={'run_id':a.run_id,'started_at_utc':cfg['task_started_at_utc'],'ended_at_utc':end.isoformat(),'timezone_for_user':'Asia/Shanghai','wall_seconds_through_finalization':(end-start).total_seconds(),'wall_limit_seconds':43200,'report_reserve_seconds':2700,'gpu_process_seconds_upper_bound':resources.get('gpu_process_card_seconds_upper_bound'),'gpu_limit_seconds':36000,'gpu_accounting':'2-second samples; counts entire lifetime of this task CUDA processes, including idle context time; interval edges conservatively padded by a sample','resource_watch':resources,'download_payload_bytes_counted':download.get('payload_bytes_received'),'download_limit_bytes':35000000000,'download_accounting_limitations':load('preparation_accounting.json',{}),'step_counts':stepcounts,'scientific_stage_missing_counts':'NOT_RUN if absent; actual executed counters remain explicit','limits':cfg['boundaries']}
    atomic(run/'budget.json',budget)
    comparisons=result.get('primary_comparison')
    if comparisons:
        d=comparisons['R_improvement'];j=comparisons['raw_J_improvement']
        outcome=f"U*={comparisons['U_star']}，对照={comparisons['comparator']}；mean R={comparisons['U_mean_R']:.9g} / {comparisons['baseline_mean_R']:.9g}；mean J={comparisons['U_mean_J']:.9g} / {comparisons['baseline_mean_J']:.9g}。R 改善（对照−U）={d['point_baseline_minus_U']:.9g}，95% CI={d['CI95']}；原 J 同方向差={j['point_baseline_minus_U']:.9g}。完整精度及逐 root 差在 summary.json / CSV。"
    else:outcome='NOT_RUN：'+reason
    baseline=load('baseline_validity.json',{})
    prep=load('data_preparation.json',{});counts_text='；'.join(f"{s}: {c['independent_roots']} roots/{c['independent_sources']} sources" for s,c in counts.items())
    retry_count=sum('ERROR' in line for line in (run/'download_events.jsonl').read_text().splitlines()) if (run/'download_events.jsonl').exists() else 0
    morning=f'''# U v3 夜间运行交付\n\n**{disposition}**。run_id `{a.run_id}`。\n\n1. 实际完成阶段：{', '.join(status.get('completed_stages',[])) or '准备/实现'}。{counts_text}。完整 test：{summary['test_complete']}；IDM 各 split 来源数：{prep.get('source_counts','NOT_RUN')}。\n2. {outcome}\n3. 候选误罚、强 G 和打乱标签证据：{clean(result.get('mechanism_interpretation','NOT_RUN；未完成有效比较，不能解释为算法负结果'))}。初始基线状态：{baseline.get('status','NOT_RUN')}。\n4. 墙钟 {budget['wall_seconds_through_finalization']/3600:.4f} h；GPU 进程占用上界 {str(budget['gpu_process_seconds_upper_bound'])} 秒；下载预算计数 {str(budget['download_payload_bytes_counted'])} B（包含早期 pip 不完整计量的保守预留）。实测 RSS 合计峰值 {resources.get('peak_task_process_rss_sum_bytes')} B，采样任务 VRAM 峰值 {resources.get('peak_task_vram_bytes')} B；磁盘分配峰值 {resources.get('peak_task_disk_allocated_bytes')} B；下载错误事件 {retry_count}。后台占用、Torch 内部显存 watermark、前缀/积分步和全部修复见 budget.json / repairs.jsonl。监护前 CPU 准备峰值未完整采样，不冒充全程精确峰值。\n5. 结论范围：单个冻结 LeWM、单一训练 seed、5 控制步共享候选选择。未做 U1、Cube、闭环、多任务或大模型训练；下一步仅为研究者复审当前证据。\n\n| split | 独立 roots | 独立 sources | 有效候选记录 | 目标 roots |\n|---|---:|---:|---:|---:|\n'''
    for split,c in counts.items():morning+=f"| {split} | {c['independent_roots']} | {c['independent_sources']} | {c['valid_candidate_records']} | {c['target_roots']} |\n"
    morning+='\n停止/完成原因：'+reason+'。缺失项不填 0；上表的 0 只表示实际不存在的已执行记录。研究数值见逐 root 表，候选评分与真实结果在不同文件。\n'
    (report/'morning_report.md').write_text(morning)
    (report/'gate_decision.md').write_text('# U v3 决定\n\n**'+disposition+'**\n\n'+reason+'\n\n完整结果见 morning_report.md 与 summary.json；不自动继续 U1。\n')
    for name in ['preflight.md','baseline_validity.md','limitations.md']:
        if not (report/name).exists():(report/name).write_text('# '+name[:-3]+'\n\nNOT_RUN / 阶段未完成：'+reason+'。没有据此作科学否定。\n')
    if not (run/'per_root_metrics.csv').exists():
        (run/'per_root_metrics.csv').write_text('split,root,source,method,selected_index,R,J,block_only,success,status,reason\n')
    atomic(run/'status.json',{**status,'status':'FINALIZED','final_status':disposition,'ended_at_utc':end.isoformat(),'failure':None if a.reason=='COMPLETE' else reason,'publication':'attempted by finalizer; see delivery receipt'})
    if a.publish:
        scripts=['bootstrap_v3.py','download_v3.py','download_ranges_v3.py','resource_watch_v3.py','run_overnight_v3.py','u_stage_v3.py','u_core_v3.py','u_train_v3.py','finalize_v3.py','check_v3.py']
        paths=[BASE/'.gitignore',BASE/'configs/protocol_v3.json',BASE/'configs/requirements_v3_min.txt',BASE/'scripts/with_env_v3.sh']+[BASE/'scripts'/x for x in scripts if (BASE/'scripts'/x).exists()]
        if (BASE/'README_v3.md').exists():paths.append(BASE/'README_v3.md')
        paths+=sorted(report.glob('*.md'))
        if (report/'requirements_v3.lock').exists():paths.append(report/'requirements_v3.lock')
        paths+=[x for x in run.iterdir() if x.is_file() and x.suffix in ['.json','.jsonl','.csv','.md','.txt'] and not x.name.startswith('log_')]
        files=[]
        for x in paths:
            if x.stat().st_size>10000000:raise RuntimeError('PUBLIC_ARTIFACT_TOO_LARGE_'+x.name)
            contents=x.read_text()
            if re.search(r'(?:gh[pousr]_|github_pat_|hf_)[A-Za-z0-9_]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----',contents):raise RuntimeError('SECRET_SCAN_REJECTED_'+x.name)
            files.append(str(x.relative_to(BASE.parent)))
        branch=subprocess.run(['git','branch','--show-current'],cwd=BASE.parent,capture_output=True,text=True,check=True).stdout.strip()
        if not branch.startswith('research/u-gate0-v3-overnight'):raise RuntimeError('PUBLICATION_BRANCH_CHANGED')
        subprocess.run(['git','add','--',*files],cwd=BASE.parent,check=True)
        subprocess.run(['git','diff','--cached','--check','--',*files],cwd=BASE.parent,check=True)
        dirty=subprocess.run(['git','diff','--cached','--name-only','--',*files],cwd=BASE.parent,capture_output=True,text=True,check=True).stdout.strip()
        if dirty:subprocess.run(['git','commit','--only','-m',f'U v3 {a.run_id}: {disposition}','--',*files],cwd=BASE.parent,check=True)
        commit=subprocess.run(['git','rev-parse','HEAD'],cwd=BASE.parent,capture_output=True,text=True,check=True).stdout.strip()
        p=subprocess.run(['git','push','-u','origin','HEAD:refs/heads/'+branch],cwd=BASE.parent,capture_output=True,text=True,timeout=180)
        receipt={'at':utc(),'branch':branch,'commit':commit,'push_exit_code':p.returncode,'output':clean(p.stdout+p.stderr),'force_used':False}
        atomic(run/'.control/delivery_receipt.json',receipt)
        if p.returncode:print(json.dumps(receipt),flush=True)
    print(json.dumps({'final_status':disposition,'run_id':a.run_id,'publish_requested':a.publish}),flush=True)
def load_lines(path):
    if not path.exists():return []
    rows=[]
    for line in path.read_text().splitlines():
        try:rows.append(json.loads(line))
        except ValueError:pass
    return rows

def write_missing(path,rows):
    with path.open('w',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=['split','root','source','seed','candidate','action_block','status','reason','J'],lineterminator='\n');writer.writeheader()
        for row in rows:writer.writerow({key:json.dumps(value,ensure_ascii=False) if value is None or isinstance(value,list) else value for key,value in row.items()})

if __name__=='__main__':main()
