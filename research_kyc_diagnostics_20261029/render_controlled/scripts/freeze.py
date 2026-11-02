from lc_common import *
import ast,difflib,subprocess,shutil
def main():
    dispatch=gate();assert read(P/'cpu_mock.json')['passed'] and not (P/'run_manifest.json').exists()
    for name in ['cache','tmp','local_only','logs','results']:(P/name).mkdir(exist_ok=True)
    write(P/'budget.json',{'utc':utc(),'workers':2,'make_env':2,'renders':4,'readPixels':8,'gpu_seconds':180,'terminate_at_gpu_seconds':170,
       'cpu_threads':3,'rss_bytes':16*2**30,'vram_bytes':12*2**30,'new_disk_bytes':150*2**20,'ACT':0,'env_steps':0,'rollouts':0,'optimizer_updates':0,
       'dispatch_epoch':datetime.datetime.fromisoformat(dispatch['dispatch_local']).timestamp(),
       'deadline_epoch':datetime.datetime.fromisoformat(dispatch['deadline_local']).timestamp(),'release_margin_seconds':10},True)
    old={}
    for folder in [D/'execution',D/'render_repair',D/'render_lifecycle']:
        for f in folder.rglob('*'):
            if f.is_file() and not any(x in f.relative_to(folder).parts for x in ['cache','tmp','local_only','logs','__pycache__']):
                old[str(f.relative_to(D))]={'bytes':f.stat().st_size,'mtime_ns':f.stat().st_mtime_ns,'sha256':sha(f)}
    write(P/'local_only/old_directory_baseline.json',old,True)
    for row in read(P/'copied_sources.json')['files']:
        source=Path(row['source']);destination=P/row['new'];assert sha(source)==row['source_sha256']
        patch=''.join(difflib.unified_diff(source.read_text().splitlines(True),destination.read_text().splitlines(True),fromfile=str(source),tofile=row['new']))
        (P/'patches'/(destination.name+'.diff')).write_text(patch)
    for f in (P/'scripts').glob('*.py'):ast.parse(f.read_text())
    ref=read(P/'reference_verification.json');assert sha(Path(ref['reference_path']))==ref['reference_file_sha256']
    sources=[R/'scripts/experiment_lib.py',R/'manifests/C_config.json',D/'execution/inputs/sample_00.npz',
       Path(ref['reference_path']),R/'vendor/robosuite/robosuite/utils/binding_utils.py',
       R/'vendor/robosuite/robosuite/renderers/context/egl_context.py',R/'vendor/robosuite/robosuite/environments/base.py']
    write(P/'run_manifest.json',{'utc':utc(),'protocol_sha256':SHA,'scripts':{f.name:sha(f) for f in (P/'scripts').glob('*.py')},
       'cpu_mock_sha256':sha(P/'cpu_mock.json'),'reference':ref,'sources':{str(f):sha(f) for f in sources},
       'sample':read(D/'execution/sample_plan.json')['ordered_samples'][0],
       'budget_sha256':sha(P/'budget.json'),'pre_run_sha256':sha(P/'PRE_RUN.md'),
       'fixture':'both modes strongly hold exactly retired A and active B, before reference then one explicit guarded A release under original lock, after frame',
       'counter_scope':'all native renders/readback including implicit and failed; sentinel separately counted',
       'commands':[[str(R/'env/bin/python'),'-B',str(P/'scripts/supervisor.py')]],'git_index_owner':'main throughout'},True)
    write(P/'counts.json',{key:0 for key in ['workers','make_env','renders','readPixels','ACT','env_steps','rollouts','optimizer_updates']})
    gpu=subprocess.run(['nvidia-smi','--query-gpu=index,name,memory.total,memory.used','--format=csv'],capture_output=True,text=True)
    apps=subprocess.run(['nvidia-smi','--query-compute-apps=pid,process_name,used_memory','--format=csv'],capture_output=True,text=True)
    write(P/'machine_before.json',{'utc':utc(),'gpu':gpu.stdout,'gpu_exit':gpu.returncode,'gpu_processes':apps.stdout,'disk_free':shutil.disk_usage(P).free,'meminfo':Path('/proc/meminfo').read_text()},True)
    print({'frozen':True,'cpu_mock_passed':True,'old_files':len(old),'protocol_sha256':SHA})
if __name__=='__main__':main()
