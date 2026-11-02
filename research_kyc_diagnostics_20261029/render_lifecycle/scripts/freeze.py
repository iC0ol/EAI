from lc_common import *
import subprocess,shutil,ast
def main():
    dispatch=gate();assert read(P/'cpu_mock.json')['passed'] and not (P/'run_manifest.json').exists()
    for name in ['cache','tmp','local_only','logs','results']:(P/name).mkdir(exist_ok=True)
    t0=datetime.datetime.fromisoformat(dispatch['dispatch_local']).timestamp()
    write(P/'budget.json',{'utc':utc(),'workers':2,'make_env':2,'renders':8,'readPixels':16,'gpu_seconds':300,'terminate_at_gpu_seconds':290,
        'cpu_threads':3,'rss_bytes':16*2**30,'vram_bytes':12*2**30,'new_disk_bytes':200*2**20,'ACT':0,'env_steps':0,'rollouts':0,'optimizer_updates':0,
        'dispatch_epoch':t0,'deadline_epoch':datetime.datetime.fromisoformat(dispatch['deadline_local']).timestamp(),'release_margin_seconds':10},True)
    old={}
    for folder in [D/'execution',D/'render_repair']:
        for file in folder.rglob('*'):
            if file.is_file() and not any(x in file.relative_to(folder).parts for x in ['cache','tmp','local_only','logs','__pycache__']):
                old[str(file.relative_to(D))]={'bytes':file.stat().st_size,'mtime_ns':file.stat().st_mtime_ns,'sha256':sha(file)}
    write(P/'local_only/old_directory_baseline.json',old,True)
    sourcefiles=[R/'scripts/experiment_lib.py',R/'manifests/dataset_stats.json',K/'utils.py',K/'eval.py',K/'cam_embedding.py',
       R/'vendor/robosuite/robosuite/utils/binding_utils.py',R/'vendor/robosuite/robosuite/renderers/context/egl_context.py',
       R/'vendor/robosuite/robosuite/environments/base.py',D/'execution/inputs/sample_00.npz']
    code={p.name:sha(p) for p in (P/'scripts').glob('*.py')}
    for p in (P/'scripts').glob('*.py'):ast.parse(p.read_text())
    sample=read(D/'execution/sample_plan.json')['ordered_samples'][0];write(P/'sample.json',sample,True)
    write(P/'run_manifest.json',{'utc':utc(),'protocol_sha256':SHA,'scripts':code,'cpu_mock_sha256':sha(P/'cpu_mock.json'),
       'sample_sha256':sha(P/'sample.json'),'budget_sha256':sha(P/'budget.json'),'sources':{str(f):sha(f) for f in sourcefiles},
       'old_directory_baseline_sha256':sha(P/'local_only/old_directory_baseline.json'),'worker_plan':[['1','baseline','early,dataset,evaluator,custom'],['2','fix','early,dataset,evaluator,custom']],
       'commands':[[str(R/'env/bin/python'),'-B',str(P/'scripts/supervisor.py')]],'git_index_owner':'main; executor read-only Git'},True)
    write(P/'counts.json',{key:0 for key in ['workers','make_env','renders','readPixels','ACT','env_steps','rollouts','optimizer_updates']})
    gpu=subprocess.run(['nvidia-smi','--query-gpu=index,name,memory.total,memory.used','--format=csv'],capture_output=True,text=True)
    apps=subprocess.run(['nvidia-smi','--query-compute-apps=pid,process_name,used_memory','--format=csv'],capture_output=True,text=True)
    write(P/'machine_before.json',{'utc':utc(),'gpu':gpu.stdout,'gpu_exit':gpu.returncode,'gpu_processes':apps.stdout,'disk_free_bytes':shutil.disk_usage(P).free,
       'meminfo':Path('/proc/meminfo').read_text()},True)
    print({'frozen':True,'cpu_mock_passed':True,'old_files':len(old),'protocol_sha256':SHA})
if __name__=='__main__':main()
