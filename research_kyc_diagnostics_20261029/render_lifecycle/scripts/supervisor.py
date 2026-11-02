"""Independent single run; fresh exec baseline then conditionally fixed worker."""
from lc_common import *
import subprocess,signal,sys,shutil

def resources():
    ps={int(p.name):proc(int(p.name)) for p in Path('/proc').iterdir() if p.name.isdigit()};ids={os.getpid()}
    for _ in range(10):
        found={p for p,v in ps.items() if v and v['ppid'] in ids}
        if found<=ids:break
        ids|=found
    q=subprocess.run(['nvidia-smi','--query-compute-apps=pid,used_memory','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=3)
    vram=0
    for line in q.stdout.splitlines():
        v=line.split(',')
        if len(v)==2 and all(x.strip().isdigit() for x in v) and int(v[0]) in ids:vram+=int(v[1])*2**20
    return {'utc':utc(),'rss':sum(v['rss'] for p,v in ps.items() if v and p in ids),'vram':vram,
       'new_disk_bytes':sum(p.stat().st_size for p in P.rglob('*') if p.is_file()),'free_bytes':shutil.disk_usage(P).free}

def stop(child,reason):
    write(P/'stop_request.json',{'utc':utc(),'reason':reason})
    if child.poll() is None:
        os.killpg(child.pid,signal.SIGTERM)
        try:child.wait(3)
        except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait(1)

def baseline_gate():
    file=P/'results/worker_1_baseline/events.jsonl'
    events=[json.loads(v) for v in file.read_text().splitlines()];pairs=[]
    for i,b in enumerate(events):
        if b['event']!='baseline_before_con_free' or not b['owner_context'] or not b['current_context'] or b['owner_context']==b['current_context']:continue
        after=next(((j,a) for j,a in enumerate(events[i+1:],i+1) if a['event']=='baseline_after_con_free' and a['owner_context']==b['owner_context']),None)
        if after is None:continue
        j,a=after;changes=[]
        before_objects=b.get('active_objects') or {};after_objects=a.get('active_objects') or {}
        if b['current_context']==a['current_context'] and before_objects.get('owner_context')==after_objects.get('owner_context')==b['current_context']:
            for category,flag in [('framebuffers','is_framebuffer'),('renderbuffers','is_renderbuffer')]:
                for key,value in before_objects.get(category,{}).items():
                    new=after_objects.get(category,{}).get(key,{})
                    if value.get(flag) and new.get('id')==value['id'] and new.get(flag) is False:changes.append({'category':category,'name':key,'id':value['id']})
        pairs.append({'before_index':i,'after_index':j,'owner_context':b['owner_context'],'current_context':b['current_context'],
             'owner_before_measurement':b['owner_objects']['state'],'owner_after_measurement':a['owner_objects']['state'],
             'current_active_object_true_to_false':changes})
    result={'utc':utc(),'supported':bool(pairs),'evidence_pairs':pairs,'events_sha256':sha(file),
       'choice':'owner-context resource release plus restoration of live previous, installed before initialization',
       'scope':'one atomic lifecycle repair; no FBO rebuild, render-time rebinding, GC disable or extra worker',
       'object_identity_rule':'baseline old owner NOT_MEASURED_WRONG_CONTEXT; changes belong to actual current active renderer'}
    write(P/'repair_choice.json',result,True)
    return result['supported']

def main():
    gate();lock=(P/'run.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    assert not (P/'completion.json').exists() and not (P/'supervisor_identity.json').exists(),'terminal run cannot restart'
    assert read(P/'cpu_mock.json')['passed']
    os.sched_setaffinity(0,set(sorted(os.sched_getaffinity(0))[:3]))
    write(P/'supervisor_identity.json',dict(proc(os.getpid()),utc=utc(),sid=os.getsid(0),command=sys.argv),True)
    budget=read(P/'budget.json');gpu=0.;records=[];child=None;reason=None;mono=None
    def interrupted(sig,frame):
        nonlocal reason
        reason='SUPERVISOR_SIGNAL_'+str(sig)
    for sig in [signal.SIGTERM,signal.SIGINT,signal.SIGUSR1]:signal.signal(sig,interrupted)
    try:
        for wid,mode in [(1,'baseline'),(2,'fix')]:
            if wid==2:
                if not baseline_gate():reason='NO_SUPPORTED_LIFECYCLE_BASELINE';break
                assert records[-1]['exit_code']==0 and records[-1]['ended_epoch']<time.time()
            if gpu>=budget['terminate_at_gpu_seconds']:reason='NO_GPU_BUDGET';break
            reserve('workers',wid,mode)
            command=[str(R/'env/bin/python'),'-B',str(P/'scripts/worker.py'),'--worker',str(wid),'--mode',mode]
            started=time.time();mono=time.monotonic();last=-9
            with (P/f'logs/worker_{wid}_{mode}.log').open('x') as log:
                child=subprocess.Popen(command,cwd=P,env=envvars(),stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            identity=proc(child.pid)
            write(P/'active_child.json',{'identity':identity,'worker':wid,'mode':mode,'command':command,'created_epoch':started,
                  'prior_worker_ended_epoch':records[-1]['ended_epoch'] if records else None})
            append(P/'commands.jsonl',{'event':'START','utc':utc(),'worker':wid,'mode':mode,'command':command,'identity':identity,'created_epoch':started})
            while child.poll() is None:
                elapsed=time.monotonic()-mono
                if gpu+elapsed>=budget['terminate_at_gpu_seconds']:reason='GPU_HARD_STOP_WITH_RELEASE_MARGIN'
                if time.time()>=budget['deadline_epoch']-1800:reason='COMPUTE_DEADLINE'
                if elapsed-last>=2 and not reason:
                    res=resources();last=elapsed;append(P/'resources.jsonl',dict(res,worker=wid,gpu_allocation_seconds=gpu+time.monotonic()-mono))
                    if res['rss']>16*2**30 or res['vram']>12*2**30 or res['new_disk_bytes']>200*2**20:reason='RESOURCE_CAP'
                write(P/'status.json',{'state':'RUNNING','utc':utc(),'worker':wid,'mode':mode,'gpu_allocation_seconds':gpu+time.monotonic()-mono,'counts':read(P/'counts.json')})
                if reason:stop(child,reason);break
                time.sleep(.2)
            gpu+=time.monotonic()-mono
            record={'worker':wid,'mode':mode,'command':command,'identity':identity,'started_epoch':started,'ended_epoch':time.time(),
               'exit_code':child.poll(),'gpu_allocation_seconds_cumulative':gpu,'utc':utc()}
            records.append(record);write(P/f'worker_{wid}_process.json',record,True);append(P/'commands.jsonl',dict(record,event='EXIT'));child=None;mono=None
            if record['exit_code']!=0:reason='WORKER_FAILED';break
            result=read(P/f'results/worker_{wid}_{mode}/result.json')
            if result['state']!='COMPLETE':reason='PARTIAL_WORKER';break
        reason=reason or 'BOTH_CONDITIONS_FINISHED'
    except BaseException as e:
        reason='SUPERVISOR_ERROR_'+type(e).__name__
        raise
    finally:
        if child is not None and child.poll() is None:stop(child,reason or 'EXCEPTION')
        if mono is not None:gpu+=time.monotonic()-mono
        result={'utc':utc(),'state':'TERMINAL','reason':reason,'counts':read(P/'counts.json'),'gpu_allocation_seconds':gpu,'worker_processes':records,
           'old_0_of_32_cause':'UNKNOWN','model_inference':'NOT_RUN','rollout':'NOT_RUN','optimizer_updates':0,'parent_review_required':True,'git_index_owner':'main'}
        write(P/'completion.json',result);write(P/'status.json',result)
        if not (P/'FINAL_REPORT.md').exists():(P/'FINAL_REPORT.md').write_text('# 生命周期诊断自动收尾\n\n'+str(reason)+'。原件、计数与GPU占用见completion及results。旧0/32仍UNKNOWN。无需agent存活也已终止自身worker。等待独立验收。\n')
if __name__=='__main__':main()
