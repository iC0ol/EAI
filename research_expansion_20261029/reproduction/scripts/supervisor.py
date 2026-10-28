"""Detached, locked sequential stage runner. Never signal unrelated processes."""
import os,sys,time,json,subprocess,signal,fcntl,shutil,hashlib,datetime
from common import ROOT,utc,read_json,atomic_json,append_json,sha,own_env
def proc(pid):
    try:
        s=open(f'/proc/{pid}/stat').read(); vals=s[s.rfind(')')+2:].split()
        return {'pid':pid,'ppid':int(vals[1]),'start_ticks':int(vals[19]),'rss_bytes':int(vals[21])*os.sysconf('SC_PAGE_SIZE')}
    except (OSError,ValueError):return None
def tree(pid):
    allp={int(p):proc(int(p)) for p in os.listdir('/proc') if p.isdigit()}; found={pid}; more=True
    while more:
        more=False
        for p,x in allp.items():
            if x and x['ppid'] in found and p not in found:found.add(p);more=True
    return [allp[p] for p in found if allp.get(p)]
def resources(child,stage,gpu_s):
    ps=tree(os.getpid()); disk=shutil.disk_usage(ROOT)
    mem={k:int(v.split()[0])*1024 for k,v in (x.split(':',1) for x in open('/proc/meminfo'))}
    try:
        q=subprocess.check_output(['nvidia-smi','--query-gpu=memory.used,utilization.gpu','--format=csv,noheader,nounits'],text=True,timeout=8).strip().split(',')
        gpumem=int(q[0])*1024**2;gpuutil=int(q[1])
    except Exception:gpumem=gpuutil=None
    size=int(subprocess.check_output(['du','-sb',str(ROOT)],text=True).split()[0])
    downloads=0
    p=ROOT/'downloads.jsonl'
    if p.exists():
        for l in p.read_text().splitlines():
            try:downloads+=json.loads(l).get('bytes',0)
            except Exception:pass
    pipdir=ROOT/'cache/pip'
    if pipdir.exists(): downloads+=int(subprocess.check_output(['du','-sb',str(pipdir)],text=True).split()[0])
    return {'utc':utc(),'epoch':time.time(),'stage':stage,'child_pid':child.pid if child else None,'rss_bytes':sum(p['rss_bytes'] for p in ps),'mem_available_bytes':mem['MemAvailable'],'disk_free_bytes':disk.free,'new_disk_bytes':size,'download_bytes_conservative':downloads,'gpu_memory_total_used_bytes':gpumem,'gpu_utilization_percent':gpuutil,'gpu_allocation_seconds':gpu_s,'processes':ps}
def stop_child(p,reason):
    atomic_json(ROOT/'stop_request.json',{'utc':utc(),'reason':reason})
    try:os.killpg(p.pid,signal.SIGUSR1)
    except ProcessLookupError:return
    deadline=time.time()+45
    while p.poll() is None and time.time()<deadline:time.sleep(1)
    if p.poll() is None:
        os.killpg(p.pid,signal.SIGTERM)
        try:p.wait(10)
        except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
def main():
    lock=open(ROOT/'run.lock','a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    run=read_json(ROOT/'run.json');t0=run['published_epoch'];log=ROOT/'logs';log.mkdir(exist_ok=True)
    me=proc(os.getpid());me.update(utc=utc(),pgid=os.getpgrp(),sid=os.getsid(0),command=sys.argv)
    atomic_json(ROOT/'supervisor_identity.json',me)
    prior=read_json(ROOT/'status.json',{});gpu_s=prior.get('gpu_allocation_seconds',0);last=time.time();lastres=0;low_since=None;child=None;stage=None;reason=None
    while True:
        now=time.time();dt=now-last;last=now
        if child and child.poll() is None and stage.get('gpu'):gpu_s+=dt
        if now-lastres>=60:
            r=resources(child,stage['name'] if stage else 'PREPARING_QUEUE',gpu_s);append_json(log/'resources.jsonl',r);lastres=now
            if r['mem_available_bytes']<5*1024**3:low_since=low_since or now
            else:low_since=None
            if low_since and now-low_since>=60:reason='MemAvailable <5GiB for >=60s'
            if r['rss_bytes']>20*1024**3:reason='process-tree RSS >20GiB'
            if r['disk_free_bytes']<60*1024**3:reason='disk free <60GiB'
            if r['new_disk_bytes']>45*1024**3:reason='new disk >45GiB'
            if r['download_bytes_conservative']>12*1024**3:reason='download budget >12GiB'
            # This is conservative total device usage; unrelated display usage was measured at baseline.
            if child and stage.get('gpu') and r['gpu_memory_total_used_bytes'] and r['gpu_memory_total_used_bytes']>20*1024**3:reason='device memory >20GiB'
        if gpu_s>=8*3600:reason='8 GPU-hour allocation budget exhausted'
        if now>=t0+11*3600:reason='compute deadline T0+11h'
        queue=read_json(ROOT/'queue.json',{'stages':[],'closed':False})
        if not (ROOT/'frozen_training_plan.json').exists() and now>=t0+120*60:reason='preparation absolute limit 120min'
        if not (ROOT/'frozen_training_plan.json').exists() and now>=t0+90*60 and not read_json(ROOT/'preparation_extension.json',{}).get('authorized_progress'):reason='preparation limit 90min'
        if reason:
            if child and child.poll() is None:stop_child(child,reason)
            if stage:atomic_json(ROOT/'stages'/f"{stage['name']}.json",{'state':'BUDGET_STOP','utc':utc(),'exit_code':child.poll() if child else None,'reason':reason})
            break
        if child:
            code=child.poll()
            if code is not None:
                outputs={}
                for f in stage.get('outputs',[]):
                    p=ROOT/f
                    if p.is_file():outputs[f]={'sha256':sha(p),'bytes':p.stat().st_size}
                marker={'name':stage['name'],'state':'COMPLETE' if code==0 else 'FAILED','exit_code':code,'completed_utc':utc(),'command':stage['command'],'command_sha256':hashlib.sha256(json.dumps(stage['command']).encode()).hexdigest(),'outputs':outputs}
                atomic_json(ROOT/'stages'/f"{stage['name']}.json",marker)
                append_json(log/'events.jsonl',marker)
                child=None;stage=None
                # Failure requires an explicit recorded repair and new stage name; never silently rerun.
                if code!=0:atomic_json(ROOT/'attention.json',marker)
        if child is None and not (ROOT/'attention.json').exists():
            nextstage=next((s for s in queue['stages'] if not (ROOT/'stages'/f"{s['name']}.json").exists()),None)
            if nextstage:
                stage=nextstage;f=open(log/(stage['name']+'.log'),'a')
                child=subprocess.Popen(stage['command'],cwd=stage.get('cwd',str(ROOT)),env=own_env(),stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True);f.close()
                atomic_json(ROOT/'active_child.json',{'identity':proc(child.pid),'command':stage['command'],'stage':stage['name'],'utc':utc(),'sid':os.getsid(child.pid)})
                append_json(log/'events.jsonl',{'event':'START','stage':stage['name'],'pid':child.pid,'utc':utc()})
            elif queue.get('closed'):
                reason='all queued stages finished';break
        atomic_json(ROOT/'status.json',{'state':'RUNNING' if child else 'AWAITING_ENGINEERING','utc':utc(),'supervisor':me,'stage':stage['name'] if stage else None,'gpu_allocation_seconds':gpu_s,'elapsed_seconds':now-t0,'preparation_deadline_epoch':t0+90*60,'compute_deadline_epoch':t0+11*3600,'final_deadline_epoch':t0+12*3600,'attention':read_json(ROOT/'attention.json')})
        time.sleep(5)
    atomic_json(ROOT/'status.json',{'state':'FINISHED' if reason=='all queued stages finished' else 'STOPPED','utc':utc(),'reason':reason,'gpu_allocation_seconds':gpu_s,'elapsed_seconds':time.time()-t0,'exit_code':child.poll() if child else 0})
    subprocess.run([sys.executable,str(ROOT/'scripts/summarize.py')],cwd=ROOT,env=own_env(),stdout=open(log/'summarize.log','a'),stderr=subprocess.STDOUT)
if __name__=='__main__':main()
