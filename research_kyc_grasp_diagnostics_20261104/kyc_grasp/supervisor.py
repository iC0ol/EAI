"""One new persistent ledger. No old workers, balance, retries or auto progression."""
from .common import *
from .gates import gate
from .ledger import fresh,reserve
import subprocess,signal,secrets

def terminate(child,identity):
    if child.poll() is not None:return
    require(active(identity),'refuse unrelated PID signal');os.killpg(child.pid,signal.SIGTERM)
    try:child.wait(3)
    except subprocess.TimeoutExpired:
        require(active(identity),'PID changed');os.killpg(child.pid,signal.SIGKILL);child.wait(2)

def resources():
    rows={int(f.name):proc(int(f.name)) for f in Path('/proc').iterdir() if f.name.isdigit()};ids={os.getpid()}
    for _ in range(10):
        found={pid for pid,v in rows.items() if v and v['ppid'] in ids}
        if found<=ids:break
        ids|=found
    q=subprocess.run(['nvidia-smi','--query-gpu=memory.used','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=2)
    require(q.returncode==0 and q.stdout.strip(),'VRAM monitor unavailable')
    return dict(rss=sum(v['rss'] for pid,v in rows.items() if pid in ids and v),whole_device_vram=max(int(x.strip())*2**20 for x in q.stdout.splitlines()),disk_bytes=sum(f.stat().st_size for f in P.rglob('*') if f.is_file()))

def main(stage):
    d=gate(stage,full=True)
    with (P/'supervisor.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);os.sched_setaffinity(0,set(sorted(os.sched_getaffinity(0))[:3]))
        s=read(P/'scope_state.json')
        if s is None:s=fresh();write(P/'scope_state.json',s,exclusive=True)
        require(s['scope_id']==SCOPE_ID and s['active_lease'] is None and stage not in s['stages'],'prior lease/attempt; no retry')
        require(not any(active(v.get('identity')) for v in s['stages'].values()),'prior worker alive')
        row=resources();require(row['rss']<=16*2**30 and row['whole_device_vram']<=12*2**30 and row['disk_bytes']<=150*2**20,'resources already beyond cap')
        write(P/('stages/'+stage+'_started.json'),dict(utc=utc(),supervisor=proc(os.getpid()),prelaunch_resources=row),exclusive=True)
        quota=min(d['phase_GPU_seconds'],900-s['GPU_seconds']);require(quota>20,'insufficient scope allocation')
        if stage!='gpu-preflight' and not (P/'science_clock.json').exists():write(P/'science_clock.json',dict(started_epoch=d['dispatch_epoch'],deadline_epoch=d['deadline_epoch']),exclusive=True)
        start=time.monotonic();epoch=time.time();s['active_lease']=dict(stage=stage,token=secrets.token_hex(24),supervisor_pid=os.getpid(),quota=quota,started_monotonic=start,wall_deadline_epoch=d['deadline_epoch']);write(P/'scope_state.json',s);reserve('workers','supervisor',stage)
        cmd=[str(R/'env/bin/python'),'-B',str(P/'run.py'),stage];env=envvars();env.update(CUDA_VISIBLE_DEVICES='0',KYC_STAGE_TOKEN=s['active_lease']['token'])
        child=None;identity=None;reason=None
        def interrupted(sig,frame):
            nonlocal reason
            reason='SUPERVISOR_SIGNAL_'+str(sig)
        for sig in [signal.SIGINT,signal.SIGTERM,signal.SIGUSR1]:signal.signal(sig,interrupted)
        try:
            with (P/('logs/'+stage+'.log')).open('x') as f:child=subprocess.Popen(cmd,cwd=P,env=env,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
            identity=proc(child.pid);require(identity,'worker identity unavailable');append(P/'commands.jsonl',dict(utc=utc(),phase=stage,command=cmd,identity=identity,supervisor=proc(os.getpid())))
            last=-10
            while child.poll() is None:
                elapsed=time.monotonic()-start
                if elapsed>=quota-15:reason='GPU_ALLOCATION_TERMINATION_MARGIN'
                if time.time()>=d['deadline_epoch']-30:reason='SCIENCE_OR_DISPATCH_DEADLINE'
                if reason:terminate(child,identity);break
                if elapsed-last>=2:
                    row=resources();last=elapsed;append(P/'resources.jsonl',dict(utc=utc(),phase=stage,elapsed=elapsed,**row))
                    if row['rss']>16*2**30 or row['whole_device_vram']>12*2**30 or row['disk_bytes']>150*2**20:reason='RESOURCE_CAP'
                time.sleep(.1)
            reason=reason or ('EXITED' if child.returncode==0 else 'WORKER_FAILED')
        except BaseException as exc:reason=reason or type(exc).__name__;raise
        finally:
            if child is not None and child.poll() is None:terminate(child,identity)
            elapsed=time.monotonic()-start
            with (P/'counter.lock').open('a+') as f:
                fcntl.flock(f,fcntl.LOCK_EX);s=read(P/'scope_state.json');s['GPU_seconds']+=elapsed
                record=dict(utc=utc(),phase=stage,identity=identity,exit_code=child.returncode if child else None,reason=reason,GPU_seconds=elapsed,cumulative_GPU_seconds=s['GPU_seconds'],quota=quota,started_epoch=epoch,ended_epoch=time.time(),counts=s['counts'].copy(),phase_counts=s['phase_counts'].get(stage,{}).copy())
                s['stages'][stage]=record;s['active_lease']=None;s['active_rollout']=None;write(P/'scope_state.json',s);write(P/('stages/'+stage+'.json'),record,exclusive=True)
            okay=record['exit_code']==0 and reason=='EXITED' and elapsed<=quota and s['GPU_seconds']<=900 and not active(identity)
            if not okay:write(P/'terminal_stop.json',dict(utc=utc(),phase=stage,reason=reason,no_retry=True))
            write(P/'status.json',dict(utc=utc(),phase=stage,state='WAITING_PARENT_REVIEW' if okay else 'STOPPED',GPU_seconds=s['GPU_seconds'],counts=s['counts'],active_GPU_lease=None,no_automatic_next_phase=True))
