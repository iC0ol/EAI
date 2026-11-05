"""One actual CPU preflight in the final same interpreter/cwd/CLI."""
from .common import *
import subprocess
from .supervisor import terminate

def main():
    auth=read(P/'CPU_PREPARATION_AUTHORIZATION.json');require(auth and auth['state']=='CPU_PREPARATION_ONLY' and not auth['GPU_authorized'],'CPU dispatch missing')
    require(not (P/'cpu_preflight/started.json').exists(),'CPU probe already attempted; inspect original evidence')
    os.sched_setaffinity(0,set(sorted(os.sched_getaffinity(0))[:3]));cmd=[str(R/'env/bin/python'),'-B',str(P/'run.py'),'cpu-preflight'];env=envvars();env['CUDA_VISIBLE_DEVICES']=''
    started=time.monotonic();reason=None;samples=[]
    with (P/'logs/cpu_preflight.log').open('x') as f:child=subprocess.Popen(cmd,cwd=P,env=env,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
    identity=proc(child.pid);write(P/'cpu_preflight/started.json',dict(utc=utc(),command=cmd,cwd=str(P),identity=identity,supervisor=proc(os.getpid()),CUDA_VISIBLE_DEVICES='',affinity=sorted(os.sched_getaffinity(0))),exclusive=True)
    try:
        while child.poll() is None:
            q=subprocess.run(['nvidia-smi','--query-compute-apps=pid,used_memory','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=2);require(q.returncode==0,'CPU GPU-process monitor unavailable')
            gpu=any(v.split(',')[0].strip()==str(child.pid) for v in q.stdout.splitlines());info=proc(child.pid);elapsed=time.monotonic()-started
            samples.append(dict(elapsed=elapsed,own_GPU_process_seen=gpu,rss=info['rss'] if info else 0))
            if gpu:reason='CPU_PROCESS_ON_GPU'
            if elapsed>=165:reason='CPU_DEADLINE'
            if info and info['rss']>16*2**30:reason='CPU_RSS_CAP'
            if sum(f.stat().st_size for f in P.rglob('*') if f.is_file())>150*2**20:reason='OUTPUT_CAP'
            if reason:terminate(child,identity);break
            try:child.wait(timeout=1)
            except subprocess.TimeoutExpired:pass
    finally:
        if child.poll() is None:terminate(child,identity)
        result=read(P/'cpu_preflight/result.json',{});record=dict(utc=utc(),command=cmd,identity=identity,supervisor=proc(os.getpid()),exit_code=child.returncode,elapsed_seconds=time.monotonic()-started,reason=reason or 'PROCESS_EXITED',actual_status=result.get('status'),samples=samples,experimental_GPU_worker=False,allocated_GPU_seconds_if_observed=time.monotonic()-started if any(x['own_GPU_process_seen'] for x in samples) else 0,original_process_inactive=not active(identity))
        write(P/'cpu_preflight/process.json',record);print(json.dumps({k:record[k] for k in ['exit_code','elapsed_seconds','actual_status','reason','allocated_GPU_seconds_if_observed']}))
        require(child.returncode==0 and result.get('status')=='CPU_IMPORT_READY' and not reason,'actual CPU preflight failed; do not execute GPU')
