"""Single remaining worker slot after preserved pre-render engineering failure.
Does not restart the terminal initial supervisor or reset any cap/time/counter.
"""
from repair_common import *
from supervisor import resource,terminate
import subprocess,sys
def main():
    gate();lock=(P/'run.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    assert not (P/'recovery_supervisor_identity.json').exists(),'no repeat recovery'
    initial=read(P/'initial_attempt_completion.json');assert initial['reason']=='WORKER_FAILED'
    c=read(P/'counts.json');assert c['workers']==1 and c['renders']==c['readPixels']==0
    os.sched_setaffinity(0,set(sorted(os.sched_getaffinity(0))[:3]))
    write(P/'recovery_supervisor_identity.json',dict(proc(os.getpid()),utc=utc(),sid=os.getsid(0)),True)
    write(P/'engineering_recovery_code.json',{'utc':utc(),'scripts':{p.name:sha(p) for p in (P/'scripts').glob('*.py')}},True)
    b=read(P/'budget.json');gpu0=initial['gpu_allocation_seconds'];reserve('workers',2,'one_engineering_recovery_exec')
    command=[str(R/'env/bin/python'),'-B',str(P/'scripts/worker.py'),'--worker','2']
    started=time.time();mono=time.monotonic();reason=None;last=-9
    first=initial['worker_processes'][0];assert first['ended_epoch']<started
    with (P/'logs/worker_2.log').open('x') as f:
        child=subprocess.Popen(command,cwd=P,env=envvars(),stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
    identity=proc(child.pid)
    write(P/'active_child_recovery.json',{'identity':identity,'command':command,'created_epoch':started,'previous_worker_ended_epoch':first['ended_epoch']},True)
    append(P/'commands.jsonl',{'event':'ENGINEERING_RECOVERY_START','utc':utc(),'command':command,'identity':identity,'created_epoch':started,'previous_worker_ended_epoch':first['ended_epoch']})
    try:
        while child.poll() is None:
            elapsed=time.monotonic()-mono
            if elapsed-last>=2:
                r=resource(child.pid);append(P/'resources.jsonl',dict(r,worker=2,gpu_allocation_seconds=gpu0+elapsed));last=elapsed
                if r['rss']>b['rss_bytes'] or r['vram']>b['vram_bytes'] or r['disk_bytes']>b['new_disk_bytes']:reason='RESOURCE_CAP'
            if gpu0+elapsed>=295:reason='GPU_BUDGET'
            if time.time()>=b['deadline_epoch']-1800:reason='DEADLINE'
            write(P/'status.json',{'utc':utc(),'state':'ENGINEERING_RECOVERY_RUNNING','gpu_allocation_seconds':gpu0+elapsed,'counts':read(P/'counts.json')})
            if reason:terminate(child,reason);break
            time.sleep(.2)
    finally:
        if child.poll() is None:terminate(child,reason or 'SUPERVISOR_EXCEPTION')
        gpu=gpu0+time.monotonic()-mono
        record={'worker':2,'command':command,'child_identity':identity,'started_epoch':started,'ended_epoch':time.time(),'exit_code':child.poll(),'gpu_allocation_seconds_cumulative':gpu}
        write(P/'worker_2_process.json',record,True);append(P/'commands.jsonl',dict(record,event='EXIT'))
        result={'utc':utc(),'state':'TERMINAL_PARTIAL','reason':reason or ('ENGINEERING_RECOVERY_FINISHED' if child.poll()==0 else 'RECOVERY_WORKER_FAILED'),
          'counts':read(P/'counts.json'),'gpu_allocation_seconds':gpu,'worker_processes':initial['worker_processes']+[record],
          'first_terminal_preserved':'initial_attempt_completion.json','independent_valid_worker_repetition':'NOT_RUN; OS slots consumed by engineering failure',
          'historic_0_of_32_cause':'UNKNOWN','ACT':'NOT_RUN','env_steps':0,'rollouts':'NOT_RUN','optimizer_updates':0,'requires_parent_review':True}
        write(P/'completion.json',result);write(P/'status.json',result)
if __name__=='__main__':main()
