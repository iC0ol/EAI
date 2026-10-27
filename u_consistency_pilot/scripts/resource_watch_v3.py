#!/usr/bin/env python3
"""Independent resource guardian. Never terminates a foreign process."""
import argparse, json, os, signal, subprocess, time
from pathlib import Path
from download_v3 import BASE, atomic, utc

def owned_processes():
    result={}
    for p in Path('/proc').iterdir():
        if not p.name.isdigit(): continue
        try:
            argv=(p/'cmdline').read_bytes().split(b'\0')
            if not argv or b'python' not in argv[0]:continue
            if not any(b'u_consistency_pilot/' in x for x in argv):continue
            if any(b'resource_watch_v3.py' in x for x in argv):continue
            rss=next(int(x.split()[1])*1024 for x in (p/'status').read_text().splitlines() if x.startswith('VmRSS:'))
            result[int(p.name)]=rss
        except (OSError, StopIteration, ValueError):pass
    return result

def gpu_processes():
    p=subprocess.run(['nvidia-smi','--query-compute-apps=pid,used_memory','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=8)
    if p.returncode: return {},p.stderr.strip()
    result={}
    for line in p.stdout.splitlines():
        try:
            pid,mem=line.split(',');result[int(pid)]=int(mem)*1024*1024
        except ValueError:pass
    return result,None

def main():
    p=argparse.ArgumentParser();p.add_argument('--run-id',required=True);a=p.parse_args()
    run=BASE/'outputs'/('v3_'+a.run_id);control=run/'.control';control.mkdir(exist_ok=True)
    previous=time.monotonic();previous_gpu=False;last_save=0;last_du=0;new_disk=0
    saved=run/'resource_watch.json'
    state=json.loads(saved.read_text()) if saved.exists() else {'started_at_utc':utc(),'gpu_process_card_seconds_upper_bound':0,'peak_task_process_rss_sum_bytes':0,'peak_task_vram_bytes':0,'peak_foreign_vram_bytes':0,'minimum_host_mem_available_bytes':None,'peak_task_disk_allocated_bytes':0,'samples':0,'gpu_intervals':[]}
    if 'legacy_sampled_gpu_seconds' not in state:
        state['legacy_sampled_gpu_seconds']=state['gpu_process_card_seconds_upper_bound'];state['legacy_brief_context_uncertainty_budget_seconds']=30
    def explicit_budget():
        intervals=[];markers=[]
        for path in control.glob('gpu_context_*.json'):
            try:r=json.loads(path.read_text())
            except (OSError,ValueError):continue
            end=r.get('end_epoch')
            if end is None and not Path('/proc',str(r['pid'])).exists():
                end=time.time();r['end_epoch']=end;r['end_observed_after_worker_exit']=True;atomic(path,r)
            intervals.append((r['start_epoch'],end or time.time()));markers.append(r)
        total=0.;left=None;right=None
        for start,end in sorted(intervals):
            if left is None:left,right=start,end
            elif start<=right:right=max(right,end)
            else:total+=right-left;left,right=start,end
        if left is not None:total+=right-left
        return total,markers
    interval=None
    while not (control/'watch_stop').exists():
        now=time.monotonic();owned=owned_processes();gpus,error=gpu_processes();active={pid:mem for pid,mem in gpus.items() if pid in owned}
        measured,markers=explicit_budget()
        state['gpu_process_card_seconds_upper_bound']=state['legacy_sampled_gpu_seconds']+state['legacy_brief_context_uncertainty_budget_seconds']+measured
        state['gpu_lifetime_markers']=markers
        state['gpu_accounting_method']='Explicit process context-init-to-exit lifetime union on one card; early engineering sampled windows plus 30-second conservative uncertainty allowance'
        if active and interval is None:interval={'started_at_utc':utc(),'task_pids_first_seen':list(active)}
        if not active and interval is not None:
            interval['ended_at_utc']=utc();state['gpu_intervals'].append(interval);interval=None
        previous=now;previous_gpu=bool(active)
        mem={x.split(':')[0]:int(x.split()[1])*1024 for x in Path('/proc/meminfo').read_text().splitlines()}
        available=mem['MemAvailable'];rss=sum(owned.values());vram=sum(active.values());foreign=sum(v for k,v in gpus.items() if k not in owned)
        disk=os.statvfs(BASE);free=disk.f_bavail*disk.f_frsize
        if now-last_du>60:
            d=subprocess.run(['du','-s','-B1',str(BASE)],capture_output=True,text=True,timeout=20)
            if d.returncode==0:new_disk=int(d.stdout.split()[0])
            last_du=now
        state.update({'last_at_utc':utc(),'task_pids':list(owned),'task_rss_sum_bytes':rss,'task_vram_bytes':vram,'foreign_vram_bytes':foreign,'host_mem_available_bytes':available,'disk_free_bytes':free,'disk_allocated_bytes':new_disk,'gpu_query_error':error})
        for key,value in [('peak_task_process_rss_sum_bytes',rss),('peak_task_vram_bytes',vram),('peak_foreign_vram_bytes',foreign),('peak_task_disk_allocated_bytes',new_disk)]:state[key]=max(state[key],value)
        state['minimum_host_mem_available_bytes']=available if state['minimum_host_mem_available_bytes'] is None else min(state['minimum_host_mem_available_bytes'],available)
        state['samples']+=1
        reason=None
        if rss>=28000000000:reason='TASK_RSS_28GB'
        if available<4000000000:reason='HOST_AVAILABLE_BELOW_4GB'
        if vram>=22000000000:reason='TASK_VRAM_22GB'
        if free<40000000000:reason='DISK_FREE_BELOW_40GB'
        if new_disk>160000000000:reason='TASK_NEW_DISK_160GB'
        if state['gpu_process_card_seconds_upper_bound']>=36000:reason='GPU_PROCESS_10H'
        if reason:
            atomic(control/'resource_stop.json',{'at':utc(),'reason':reason,'owned_pids':list(owned)})
            # Registered task Python processes only; preserve supervisor/finalizer.
            for pid in owned:
                try:
                    cmd=Path(f'/proc/{pid}/cmdline').read_bytes()
                    if b'run_overnight_v3.py' not in cmd and b'finalize_v3.py' not in cmd:os.kill(pid,signal.SIGTERM)
                except OSError:pass
        if now-last_save>=10 or reason:
            atomic(saved,{**state,'open_gpu_interval':interval});last_save=now
        time.sleep(2)
    if interval:
        interval['ended_at_utc']=utc();state['gpu_intervals'].append(interval)
    state['ended_at_utc']=utc();atomic(saved,state)

if __name__=='__main__':main()
