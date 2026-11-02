"""Detached sequential exec workers, 300-second aggregate hard stop, no GPU imports."""
from repair_common import *
import subprocess,signal,sys,shutil
def resource(pid):
    ps={int(p.name):proc(int(p.name)) for p in Path('/proc').iterdir() if p.name.isdigit()};ids={os.getpid()}
    for _ in range(10):
        more={p for p,v in ps.items() if v and v['ppid'] in ids}
        if more<=ids:break
        ids|=more
    rss=sum(v['rss'] for p,v in ps.items() if v and p in ids)
    q=subprocess.run(['nvidia-smi','--query-compute-apps=pid,used_memory','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=3)
    vram=0
    for line in q.stdout.splitlines():
        fields=line.split(',')
        if len(fields)==2 and fields[0].strip().isdigit() and fields[1].strip().isdigit() and int(fields[0]) in ids:vram+=int(fields[1])*2**20
    size=sum(p.stat().st_size for p in P.rglob('*') if p.is_file())
    return {'utc':utc(),'rss':rss,'vram':vram,'disk_bytes':size,'free_bytes':shutil.disk_usage(P).free}
def terminate(p,why):
    write(P/'stop_request.json',{'utc':utc(),'reason':why})
    if p.poll() is None:
        os.killpg(p.pid,signal.SIGTERM)
        try:p.wait(3)
        except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait(1)
def main():
    gate();lock=(P/'run.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    assert not (P/'completion.json').exists() and not (P/'supervisor_identity.json').exists(),'no terminal restart'
    os.sched_setaffinity(0,set(sorted(os.sched_getaffinity(0))[:3]))
    write(P/'supervisor_identity.json',dict(proc(os.getpid()),utc=utc(),sid=os.getsid(0),command=sys.argv),True)
    b=read(P/'budget.json');gpu=0.;reason=None;records=[];child=None
    try:
        for worker in [1,2]:
            if worker==2:
                first=read(P/'results/worker_1/result.json',{})
                if first.get('state')!='REPAIR_PROVISIONAL_PASS_AWAIT_VISUAL':reason='WORKER1_NO_CONFIRMED_REPAIR';break
                while not (P/'worker2_go.json').exists():
                    write(P/'status.json',{'utc':utc(),'state':'AWAITING_WORKER1_VISUAL_REVIEW','gpu_allocation_seconds':gpu,'counts':read(P/'counts.json')})
                    if time.time()>=b['deadline_epoch']-1800:reason='TOTAL_DEADLINE_REVIEW_WAIT';break
                    time.sleep(1)
                if reason:break
                assert read(P/'worker2_go.json')['approved']
                assert records[-1]['exit_code']==0 and records[-1]['ended_epoch']<time.time()
            if gpu>=b['terminate_at_gpu_seconds']:reason='NO_GPU_BUDGET';break
            reserve('workers',worker,'fresh_exec')
            command=[str(R/'env/bin/python'),'-B',str(P/'scripts/worker.py'),'--worker',str(worker)]
            started=time.time();mono=time.monotonic();last=-9
            if worker==2:assert records[0]['ended_epoch']<started
            with (P/f'logs/worker_{worker}.log').open('x') as f:
                child=subprocess.Popen(command,cwd=P,env=envvars(),stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
            identity=proc(child.pid)
            write(P/'active_child.json',{'identity':identity,'worker':worker,'command':command,'created_epoch':started,'sid':os.getsid(child.pid)})
            append(P/'commands.jsonl',{'event':'START','utc':utc(),'worker':worker,'command':command,'pid':child.pid,'start_ticks':identity['start_ticks'],'created_epoch':started,
                 'preceding_worker_ended_epoch':records[-1]['ended_epoch'] if records else None})
            while child.poll() is None:
                elapsed=time.monotonic()-mono
                if elapsed-last>=2:
                    r=resource(child.pid);append(P/'resources.jsonl',dict(r,worker=worker,gpu_allocation_seconds=gpu+elapsed));last=elapsed
                    if r['rss']>b['rss_bytes'] or r['vram']>b['vram_bytes'] or r['disk_bytes']>b['new_disk_bytes']:reason='RESOURCE_CAP'
                if gpu+elapsed>=b['terminate_at_gpu_seconds']:reason='GPU_HARD_STOP_WITH_RELEASE_MARGIN'
                if time.time()>=b['deadline_epoch']-1800:reason='TOTAL_COMPUTE_DEADLINE'
                write(P/'status.json',{'utc':utc(),'state':'RUNNING','worker':worker,'gpu_allocation_seconds':gpu+elapsed,'child':identity,'counts':read(P/'counts.json')})
                if reason:terminate(child,reason);break
                time.sleep(.2)
            gpu+=time.monotonic()-mono
            record={'worker':worker,'command':command,'child_identity':identity,'started_epoch':started,'ended_epoch':time.time(),'exit_code':child.poll(),'gpu_allocation_seconds_cumulative':gpu,'utc':utc()}
            records.append(record);write(P/f'worker_{worker}_process.json',record,True);append(P/'commands.jsonl',dict(record,event='EXIT'))
            child=None
            if record['exit_code']!=0:reason='WORKER_FAILED';break
        reason=reason or 'TWO_WORKERS_FINISHED'
    except BaseException as e:
        reason='SUPERVISOR_ERROR_'+type(e).__name__
        if child and child.poll() is None:terminate(child,reason);gpu+=time.monotonic()-mono
        raise
    finally:
        completion={'utc':utc(),'state':'TERMINAL','reason':reason,'counts':read(P/'counts.json'),'gpu_allocation_seconds':gpu,
           'worker_processes':records,'historic_0_of_32_cause':'UNKNOWN','ACT':'NOT_RUN','env_steps':0,'rollouts':'NOT_RUN','optimizer_updates':0,
           'requires_parent_codex_deepseek_review':True,'git_index_owner':'parent','report':'FINAL_REPORT.md (emergency stub if agent interrupted)'}
        write(P/'completion.json',completion);write(P/'status.json',completion)
        if not (P/'FINAL_REPORT.md').exists():(P/'FINAL_REPORT.md').write_text('# 渲染微诊断收尾\n\n监督器已收尾：'+str(reason)+'。逐次原件见results/，计数与GPU时间见completion.json。无需活跃agent也已停止自身worker。待独立审查。\n')
if __name__=='__main__':main()
