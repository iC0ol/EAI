"""Independent CPU-only real probe, no experimental GPU worker authorization."""
from .common import *
import subprocess
import signal
import sys


def main(round_number):
    label='final' if str(round_number)=='final' else 'R'+str(round_number)
    round_dir=P/('cpu_preflight/'+label); round_dir.mkdir(exist_ok=False)
    dispatch=read(P/'orchestration/preflight_dispatch.json')
    require(time.time()<dispatch['preparation_deadline_epoch'],'CPU deadline')
    command=[str(R/'env/bin/python'),'-B',str(P/'run.py'),'cpu-preflight']
    environment=envvars();environment.update(CUDA_VISIBLE_DEVICES='',KYC_CPU_REPAIR_ROUND=str(round_number))
    if label=='final':environment['KYC_FINAL_COVERAGE']='1'
    os.sched_setaffinity(0,set(sorted(os.sched_getaffinity(0))[:3]))
    started=time.monotonic();epoch=time.time();reason=None;rows=[]
    with (P/('logs/cpu_'+label+'.log')).open('x') as log:
        child=subprocess.Popen(command,cwd=P,env=environment,stdin=subprocess.DEVNULL,
            stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    identity=proc(child.pid)
    write(round_dir/'started.json',dict(utc=utc(),command=command,cwd=str(P),
        interpreter=str(R/'env/bin/python'),identity=identity,supervisor=proc(os.getpid()),
        epoch=epoch,CUDA_VISIBLE_DEVICES='',environment_difference_from_GPU='device visibility only; same loader/cwd/python/order'))
    try:
        while child.poll() is None:
            elapsed=time.monotonic()-started
            q=subprocess.run(['nvidia-smi','--query-compute-apps=pid,used_memory','--format=csv,noheader,nounits'],
                capture_output=True,text=True,timeout=2)
            own_gpu=any(line.split(',')[0].strip()==str(child.pid) for line in q.stdout.splitlines())
            info=proc(child.pid)
            row=dict(elapsed=elapsed,rss=info['rss'] if info else 0,own_GPU_process_seen=own_gpu)
            rows.append(row)
            if own_gpu:reason='CPU_PROCESS_APPEARED_ON_GPU'
            if elapsed>=165 or time.time()>=dispatch['preparation_deadline_epoch']-15:reason='CPU_DEADLINE'
            if info and info['rss']>16*2**30:reason='CPU_RSS_CAP'
            if sum(f.stat().st_size for f in P.rglob('*') if f.is_file())>150*2**20:reason='OUTPUT_CAP'
            if reason:
                os.killpg(child.pid,signal.SIGTERM)
                try:child.wait(3)
                except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait(2)
                break
            try:child.wait(timeout=1)
            except subprocess.TimeoutExpired:pass
    finally:
        if child.poll() is None:
            os.killpg(child.pid,signal.SIGKILL);child.wait(2)
        elapsed=time.monotonic()-started
        result=read(P/'cpu_preflight/result.json',{})
        record=dict(utc=utc(),round=round_number,command=command,identity=identity,
            exit_code=child.returncode,elapsed_seconds=elapsed,reason=reason or 'PROCESS_EXITED',
            actual_status=result.get('status'),samples=rows,
            GPU_allocated_seconds_if_side_effect=elapsed if any(x['own_GPU_process_seen'] for x in rows) else 0,
            CPU_controlled_process=True,experimental_GPU_worker=False)
        write(round_dir/'process.json',record)
        if (P/'cpu_preflight/result.json').exists():
            write(round_dir/'result.json',result)
        print(json.dumps({k:record[k] for k in ['round','exit_code','elapsed_seconds','actual_status','GPU_allocated_seconds_if_side_effect']}))
        require(record['exit_code']==0 and result.get('status')=='CPU_IMPORT_READY','real CPU preflight failed; inspect evidence before R2')


if __name__=='__main__':
    main(sys.argv[1])
