"""One sequential recovery ledger; no GPU worker stays alive during reviews."""
from .common import *
from .gates import gate,reserve
import subprocess,signal,secrets


def terminate(child,identity):
    if child.poll() is not None:return
    require(active(identity),'refuse unrelated PID signal');os.killpg(child.pid,signal.SIGTERM)
    try:child.wait(3)
    except subprocess.TimeoutExpired:
        require(active(identity),'child identity changed');os.killpg(child.pid,signal.SIGKILL);child.wait(2)


def resources():
    allp={int(p.name):proc(int(p.name)) for p in Path('/proc').iterdir() if p.name.isdigit()};ids={os.getpid()}
    for _ in range(10):
        found={pid for pid,row in allp.items() if row and row['ppid'] in ids}
        if found<=ids:break
        ids|=found
    q=subprocess.run(['nvidia-smi','--query-gpu=memory.used','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=1)
    require(q.returncode==0 and q.stdout.strip(),'VRAM monitor unavailable')
    return dict(rss=sum(row['rss'] for pid,row in allp.items() if row and pid in ids),
        whole_device_vram=max(int(x.strip())*2**20 for x in q.stdout.splitlines()),
        disk_bytes=sum(f.stat().st_size for f in P.rglob('*') if f.is_file()))


def allocation(state,stage):
    remaining=1800-state['GPU_seconds']
    if stage=='gpu-preflight':return min(180-state['engineering_GPU_seconds'],remaining)
    if stage=='s1-input':return min(210,600-state['stage1_GPU_seconds'],remaining)
    if stage=='s1-model':return min(600-state['stage1_GPU_seconds'],remaining)
    return remaining


def main(stage):
    dispatch=gate(stage,full=True)
    with (P/'supervisor.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);os.sched_setaffinity(0,set(sorted(os.sched_getaffinity(0))[:3]))
        state=read(P/'recovery_state.json')
        if state is None:
            state=dict(recovery_id=RECOVERY_ID,counts={k:0 for k in CAPS},GPU_seconds=0.,engineering_GPU_seconds=0.,stage1_GPU_seconds=0.,stages={},active_lease=None)
            write(P/'recovery_state.json',state,exclusive=True)
        require(state['recovery_id']==RECOVERY_ID and state['active_lease'] is None,'wrong recovery/outstanding lease')
        require(not any(active(v.get('identity')) for v in state['stages'].values()),'prior worker alive')
        require(stage not in state['stages'],'phase already attempted; R1/R2 exhausted, no retry')
        (P/'stages').mkdir(exist_ok=True);write(P/('stages/'+stage+'_started.json'),dict(utc=utc(),supervisor=proc(os.getpid())),exclusive=True)
        quota=allocation(state,stage);require(quota>20,'insufficient remaining allocation')
        if stage=='s1-model':require(quota>=390,'model reserve missing')
        if stage=='s1-input':
            require(dispatch['deadline_epoch']==dispatch['dispatch_epoch']+8*3600,'science clock must be 8h')
            write(P/'science_clock.json',dict(started_epoch=dispatch['dispatch_epoch'],deadline_epoch=dispatch['deadline_epoch']),exclusive=True)
        started=time.monotonic();epoch=time.time()
        state['active_lease']=dict(stage=stage,token=secrets.token_hex(24),supervisor_pid=os.getpid(),quota=quota,
            started_monotonic=started,wall_deadline_epoch=dispatch['deadline_epoch'])
        write(P/'recovery_state.json',state);reserve('workers','supervisor',stage)
        command=[str(R/'env/bin/python'),'-B',str(P/'run.py'),stage]
        environment=envvars();environment.update(CUDA_VISIBLE_DEVICES='0',KYC_STAGE_TOKEN=state['active_lease']['token'],
            __GL_SHADER_DISK_CACHE='0',__GL_SHADER_DISK_CACHE_PATH=str(P/'cache/nvidia'),CUDA_CACHE_PATH=str(P/'cache/nvidia'))
        child=None;identity=None;reason=None
        def interrupted(sig,frame):
            nonlocal reason
            reason='SUPERVISOR_SIGNAL_'+str(sig)
        for sig in [signal.SIGTERM,signal.SIGINT,signal.SIGUSR1]:signal.signal(sig,interrupted)
        try:
            with (P/('logs/'+stage+'.log')).open('x') as log:
                child=subprocess.Popen(command,cwd=P,env=environment,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            identity=proc(child.pid);require(identity,'child identity missing')
            append(P/'commands.jsonl',dict(utc=utc(),command=command,identity=identity,phase=stage))
            last=-10
            while child.poll() is None:
                elapsed=time.monotonic()-started
                if elapsed>=quota-15:reason='GPU_ALLOCATION_TERMINATION_MARGIN'
                if time.time()>=dispatch['deadline_epoch']-30:reason='WALL_DEADLINE'
                if reason:terminate(child,identity);break
                if elapsed-last>=2:
                    row=resources();last=elapsed;append(P/'resources.jsonl',dict(row,phase=stage,elapsed=elapsed,utc=utc()))
                    if row['rss']>16*2**30 or row['whole_device_vram']>12*2**30 or row['disk_bytes']>150*2**20:reason='RESOURCE_CAP'
                time.sleep(.1)
            reason=reason or ('EXITED' if child.returncode==0 else 'WORKER_FAILED')
        except BaseException as exc:
            reason=reason or type(exc).__name__;raise
        finally:
            if child is not None and child.poll() is None:terminate(child,identity)
            elapsed=time.monotonic()-started
            with (P/'counter.lock').open('a+') as counter:
                fcntl.flock(counter,fcntl.LOCK_EX);state=read(P/'recovery_state.json');state['GPU_seconds']+=elapsed
                if stage=='gpu-preflight':state['engineering_GPU_seconds']+=elapsed
                if stage.startswith('s1-'):state['stage1_GPU_seconds']+=elapsed
                record=dict(utc=utc(),stage=stage,identity=identity,exit_code=child.returncode if child else None,reason=reason,
                    GPU_seconds=elapsed,cumulative_GPU_seconds=state['GPU_seconds'],quota=quota,started_epoch=epoch,
                    ended_epoch=time.time(),counts_after_exit=state['counts'].copy())
                state['stages'][stage]=record;state['active_lease']=None;state['active_rollout']=None
                write(P/'recovery_state.json',state);write(P/('stages/'+stage+'.json'),record,exclusive=True)
            okay=record['exit_code']==0 and reason=='EXITED' and elapsed<=quota and state['GPU_seconds']<=1800 and not active(identity)
            if not okay:write(P/'terminal_stop.json',dict(utc=utc(),phase=stage,reason=reason,repair_rounds_remaining=0))
            write(P/'status.json',dict(utc=utc(),phase=stage,state='WAITING_PARENT_REVIEW' if okay else 'ENGINEERING_BLOCKED',counts=state['counts'],GPU_seconds=state['GPU_seconds'],active_GPU_lease=None,no_automatic_next_phase=True))
