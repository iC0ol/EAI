from repair_common import *
import subprocess,shutil
def main():
    g=gate();assert not (P/'run_manifest.json').exists()
    for n in ['cache','tmp','local_only','logs','results']:(P/n).mkdir(exist_ok=True)
    t0=datetime.datetime.fromisoformat(g['approved_local']).timestamp()
    dispatch=read(P/'dispatch.json',{})
    if dispatch.get('dispatched_local'):t0=datetime.datetime.fromisoformat(dispatch['dispatched_local']).timestamp()
    write(P/'budget.json',{'frozen_utc':utc(),'workers':2,'make_env':2,'renders':12,'readPixels':24,
       'gpu_seconds':300,'terminate_at_gpu_seconds':295,'cpu_threads':3,'rss_bytes':16*2**30,'vram_bytes':12*2**30,
       'new_disk_bytes':200*2**20,'ACT':0,'env_steps':0,'rollouts':0,'optimizer_updates':0,
       'deadline_epoch':t0+8*3600,'t0_epoch':t0,'anchor':'dispatch if available; otherwise conservatively approval time'},True)
    sample=read(D/'execution/sample_plan.json')['ordered_samples'][0]
    write(P/'sample.json',sample,True)
    baseline={str(p.relative_to(D/'execution')):{'bytes':p.stat().st_size,'mtime_ns':p.stat().st_mtime_ns,'sha256':sha(p)}
       for p in (D/'execution').rglob('*') if p.is_file() and not any(v in p.relative_to(D/'execution').parts for v in ['cache','tmp','logs','local_only','__pycache__'])}
    write(P/'local_only/old_execution_baseline.json',baseline,True)
    sources=[R/'scripts/experiment_lib.py',K/'utils.py',K/'eval.py',R/'vendor/robosuite/robosuite/utils/binding_utils.py',R/'vendor/robosuite/robosuite/renderers/context/egl_context.py',R/'vendor/robosuite/robosuite/environments/base.py',D/'execution/inputs/sample_00.npz']
    write(P/'run_manifest.json',{'utc':utc(),'protocol_sha256':SHA,'gate_sha256':sha(P/'review_gate.json'),
       'sample_sha256':sha(P/'sample.json'),'budget_sha256':sha(P/'budget.json'),
       'sources':{str(p):sha(p) for p in sources},'scripts':{p.name:sha(p) for p in (P/'scripts').glob('*.py')},
       'commands':[[str(R/'env/bin/python'),'-B',str(P/'scripts/supervisor.py')]],
       'git_index_owner':'parent; executor no Git mutations','old_execution_baseline_sha256':sha(P/'local_only/old_execution_baseline.json')},True)
    write(P/'counts.json',{k:0 for k in ['workers','make_env','renders','readPixels','ACT','env_steps','rollouts','optimizer_updates']})
    z=subprocess.run(['nvidia-smi','--query-gpu=index,name,memory.total,memory.used','--format=csv'],capture_output=True,text=True)
    write(P/'machine_before.json',{'utc':utc(),'gpu':z.stdout,'exit_code':z.returncode,'meminfo':Path('/proc/meminfo').read_text(),'disk_free':shutil.disk_usage(P).free},True)
    print({'frozen':True,'protocol_sha256':SHA})
if __name__=='__main__':main()
