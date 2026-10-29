"""Detached hard-stop monitor. Child failure is never silently retried."""
from diag_common import *
from finalize import finalize
import argparse
import shutil
import signal
import subprocess
import sys

def descendants(root):
    ps={int(p.name):proc(int(p.name)) for p in Path('/proc').iterdir() if p.name.isdigit()}
    found={root}
    for _ in range(20):
        new={pid for pid,v in ps.items() if v and v['ppid'] in found}
        if new<=found:break
        found|=new
    return [ps[p] for p in found if ps.get(p)]

def own_size():
    return sum(p.stat().st_size for p in E.rglob('*') if p.is_file())

def resources():
    ps=descendants(os.getpid())
    mem={k:int(v.split()[0])*1024 for k,v in (line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())}
    q=subprocess.run(['nvidia-smi','--query-compute-apps=pid,used_memory','--format=csv,noheader,nounits'],
                     capture_output=True,text=True,timeout=5)
    gpu=[]
    for line in q.stdout.splitlines():
        fields=line.split(',')
        if len(fields)==2 and fields[0].strip().isdigit() and fields[1].strip().isdigit():
            gpu.append({'pid':int(fields[0]),'bytes':int(fields[1])*2**20})
    ownpids={v['pid'] for v in ps}
    return {'utc':utc(),'processes':ps,'tree_rss_bytes':sum(v['rss_bytes'] for v in ps),
            'mem_available_bytes':mem['MemAvailable'],'disk_free_bytes':shutil.disk_usage(E).free,
            'new_disk_bytes':own_size(),'own_gpu_bytes':sum(v['bytes'] for v in gpu if v['pid'] in ownpids),
            'compute_gpu_processes':gpu,'nvidia_query_exit_code':q.returncode}

def terminate(child, identity, reason):
    write(E/'stop_request.json',{'utc':utc(),'reason':reason,'child_identity':identity})
    current=proc(child.pid)
    if child.poll() is None and current and current['start_ticks']==identity['start_ticks']:
        os.killpg(child.pid,signal.SIGTERM)
        try:child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            if proc(child.pid) and proc(child.pid)['start_ticks']==identity['start_ticks']:
                os.killpg(child.pid,signal.SIGKILL)
            child.wait(timeout=3)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--stage',choices=['stage0','stage1'],required=True)
    a=ap.parse_args();check_gate()
    lock=(E/'run.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    assert not (E/f'stages/{a.stage}.json').exists(), 'existing attempt; never repeat automatically'
    assert not (E/'completion.json').exists(), 'completed or failed; no automatic restart'
    if a.stage=='stage1':
        assert read(E/'stage0_gate.json')['decision']=='NEEDS_BOUNDED_STAGE1'
        assert (E/'stage0_report.md').exists()
    budget=read(E/'budget.json')
    current=read(E/'status.json',{})
    previous_gpu=current.get('gpu_allocation_seconds',0)
    me=proc(os.getpid());me.update(sid=os.getsid(0),pgid=os.getpgrp(),command=sys.argv,utc=utc())
    write(E/'supervisor_identity.json',me)
    command=[str(R/'env/bin/python'),'-B',str(E/f'scripts/{a.stage}.py')]
    started=time.time();monotonic=time.monotonic()
    with (E/f'logs/{a.stage}.log').open('x') as log:
        child=subprocess.Popen(command,cwd=E,env=own_env(cpu=a.stage=='stage0'),stdin=subprocess.DEVNULL,
                               stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    identity=proc(child.pid)
    write(E/'active_child.json',{'identity':identity,'command':command,'utc':utc(),'sid':os.getsid(child.pid),'stage':a.stage})
    append(E/'commands.jsonl',{'event':'START','utc':utc(),'command':command,'cwd':str(E),
                             'pid':child.pid,'start_ticks':identity['start_ticks'],'supervisor':me})
    low=None;last_resource=-99;reason=None;peak={};samples=0
    def stop(sig,frame):
        nonlocal reason
        reason=f'supervisor signal {sig}'
    for sig in [signal.SIGTERM,signal.SIGINT,signal.SIGUSR1]:signal.signal(sig,stop)
    try:
        while child.poll() is None:
            elapsed=time.monotonic()-monotonic
            gpu=previous_gpu+(elapsed if a.stage=='stage1' else 0)
            if elapsed-last_resource>=10:
                r=resources();samples+=1;append(E/'logs/resources.jsonl',dict(r,stage=a.stage,gpu_allocation_seconds=gpu))
                last_resource=elapsed
                for k in ['tree_rss_bytes','new_disk_bytes','own_gpu_bytes']:peak[k]=max(peak.get(k,0),r[k])
                if r['mem_available_bytes']<budget['mem_available_floor_bytes']:low=low or time.monotonic()
                else:low=None
                if low is not None and time.monotonic()-low>=60:reason='MemAvailable below 5GiB for 60 seconds'
                if r['tree_rss_bytes']>budget['rss_cap_bytes']:reason='tree RSS >16GiB'
                if r['own_gpu_bytes']>budget['vram_cap_bytes']:reason='own VRAM >12GiB'
                if r['disk_free_bytes']<budget['disk_free_floor_bytes']:reason='disk free <60GiB'
                if r['new_disk_bytes']>budget['new_disk_cap_bytes']:reason='new disk >2GiB'
            if a.stage=='stage0' and elapsed>=5400:reason='Stage0 CPU active process limit 90min'
            if a.stage=='stage1' and gpu>=budget['gpu_process_hard_terminate_seconds']:reason='GPU hard budget with release margin'
            if time.time()>=budget['final_deadline_epoch']-1800:reason='compute deadline leaves 30min finalization'
            write(E/'status.json',{'state':'RUNNING','utc':utc(),'stage':a.stage,'supervisor':me,
                  'child':identity,'gpu_allocation_seconds':gpu,'stage_wall_seconds':elapsed,'peak_samples':peak})
            if reason:
                terminate(child,identity,reason);break
            time.sleep(0.5)
    except BaseException as e:
        reason='SUPERVISOR_ERROR '+repr(e)
        terminate(child,identity,reason)
        raise
    finally:
        if child.poll() is None:terminate(child,identity,reason or 'unexpected supervisor exit')
        elapsed=time.monotonic()-monotonic
        gpu=previous_gpu+(elapsed if a.stage=='stage1' else 0)
        code=child.poll()
        outcome='BUDGET_STOP' if reason else ('COMPLETE' if code==0 else 'FAILED')
        marker={'stage':a.stage,'state':outcome,'command':command,'cwd':str(E),
                'started_epoch':started,'ended_epoch':time.time(),'utc':utc(),'exit_code':code,
                'reason':reason,'child_identity':identity,'supervisor':me,'wall_seconds':elapsed,
                'gpu_allocation_seconds':gpu,'resource_samples':samples,'peak_samples':peak}
        write(E/f'stages/{a.stage}.json',marker,exclusive=True);append(E/'commands.jsonl',dict(marker,event='EXIT'))
        write(E/'status.json',dict(marker,state='AWAITING_STAGE0_REVIEW' if a.stage=='stage0' and code==0 and not reason else outcome))
        if reason or code!=0:finalize(reason or f'{a.stage} exit {code}',outcome)
        elif a.stage=='stage1':finalize(read(E/'stage1_gate.json',{}).get('decision','STAGE1_FINISHED'),'EXECUTION_COMPLETE')
    return code or (1 if reason else 0)

if __name__=='__main__':
    os.sched_setaffinity(0,set(sorted(os.sched_getaffinity(0))[:3]))
    sys.exit(main())
