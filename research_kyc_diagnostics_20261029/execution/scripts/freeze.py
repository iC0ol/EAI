"""Freeze provenance and the reviewed plan before numerical diagnostics."""
from diag_common import *
import subprocess
import shutil

def main():
    dispatch = check_gate()
    assert not (E / 'run_manifest.json').exists(), 'already frozen; never restart'
    for name in ['cache', 'tmp', 'logs', 'results', 'inputs', 'local_only', 'stages']:
        (E / name).mkdir(exist_ok=True)
    started = datetime.datetime.fromisoformat(dispatch['dispatched_local']).timestamp()
    budget = {'frozen_utc': utc(), 'fixed_forward_cap': 32, 'batch_size': 1,
              'rollout_cap': 16, 'steps_per_rollout': 150, 'queries_per_rollout': 5,
              'closed_query_cap': 80, 'total_policy_cap': 112, 'optimizer_update_cap': 0,
              'gpu_allocation_seconds_cap': 3600, 'gpu_process_hard_terminate_seconds': 3590,
              'cpu_threads': 3, 'workers': 0, 'rss_cap_bytes': 16 * 2**30,
              'vram_cap_bytes': 12 * 2**30, 'mem_available_floor_bytes': 5 * 2**30,
              'mem_low_grace_seconds': 60, 'disk_free_floor_bytes': 60 * 2**30,
              'new_disk_cap_bytes': 2 * 2**30, 'download_model_data_packages_bytes': 0,
              'dispatch_epoch': started, 'final_deadline_epoch': started + 8 * 3600,
              'stage0_active_work_seconds_cap': 5400,
              'gpu_definition': 'conservative entire supervised GPU child lifetime, including import/load/render/input/simulation/failures',
              'gpu_release_margin_seconds': 10, 'max_engineering_repairs': 2}
    write(E / 'budget.json', budget, exclusive=True)
    old_files = [p for p in R.rglob('*') if p.is_file() and
                 not any(z in p.relative_to(R).parts for z in ('env', 'cache', 'tmp', '.git', '__pycache__'))]
    baseline = {str(p.relative_to(R)): {'bytes': p.stat().st_size,
                'mtime_ns': p.stat().st_mtime_ns, 'sha256': sha(p)} for p in sorted(old_files)}
    write(E / 'local_only/old_file_baseline.json', baseline, exclusive=True)
    named = ['checkpoints/C_latest.pt', 'assets/liftrand_eef_delta.hdf5',
             'manifests/C_config.json', 'manifests/dataset_stats.json',
             'manifests/frozen_roots.json', 'cache/torch/hub/checkpoints/resnet18-f37072fd.pth']
    sources = {n: {'bytes': (R/n).stat().st_size, 'sha256': sha(R/n)} for n in named}
    assert sources[named[0]]['sha256'] == 'c904a97002571d96e3ee6b66057d09162cbdcb5e926cb6ea0b660ca1390bce13'
    assert sources[named[1]]['sha256'] == 'fc89e2a46624b877cd35ae383df9ad09a84b7881c655bc114812164d6ff45377'
    camera = read(K / 'camera_poses/train_cameras.json')['poses']
    rootplan = []
    old_roots = {v['root_id']: v for v in read(R/'manifests/frozen_roots.json')['roots'] if v['split'] == 'dev'}
    for root, index in zip(range(1000,1008), range(0,200,25)):
        order = ['train', 'dev'] if root % 2 == 0 else ['dev', 'train']
        for condition in order:
            rootplan.append({'root': root, 'condition': condition,
                             'train_camera_index': index, 'old_root': old_roots[root],
                             'T': camera[index] if condition == 'train' else old_roots[root]['T']})
    write(E / 'root_plan.json', {'independent_physical_roots': 8, 'ordered_rollouts': rootplan,
          'condition_order': 'even root train then dev; odd root dev then train',
          'interpretation': 'train-pool camera paired with old dev physical state; not full training conditions'}, exclusive=True)
    git = {label: subprocess.check_output(cmd, cwd=W, text=True) for label,cmd in {
        'head': ['git','rev-parse','HEAD'], 'branch': ['git','branch','--show-current'],
        'status': ['git','status','--porcelain'], 'unstaged_diff': ['git','diff','--binary'],
        'staged_diff': ['git','diff','--cached','--binary']}.items()}
    write(E / 'git_baseline.json', git, exclusive=True)
    assert not git['staged_diff'], 'shared index unexpectedly contains work'
    hardware = {}
    for label,cmd in {'gpu':['nvidia-smi','--query-gpu=index,name,uuid,memory.total,memory.used,utilization.gpu','--format=csv'],
                      'gpu_processes':['nvidia-smi','--query-compute-apps=pid,process_name,used_memory','--format=csv'],
                      'memory':['free','-b'], 'cpu':['lscpu'], 'processes':['ps','-eo','pid,lstart,args']}.items():
        z = subprocess.run(cmd, capture_output=True, text=True)
        hardware[label] = {'exit_code': z.returncode, 'stdout': z.stdout}
    hardware['disk'] = dict(zip(['total','used','free'],shutil.disk_usage(E)))
    write(E / 'local_only/machine_before.json', hardware, exclusive=True)
    manifest = {'created_utc':utc(), 'protocol_sha256': PROTOCOL_SHA, 'dispatch': dispatch,
                'runtime': str(R/'env/bin/python'), 'sources': sources,
                'old_file_baseline_sha256': sha(E/'local_only/old_file_baseline.json'),
                'sample_definition': {'demos':[0,50,100,150], 'time_order':['t=0 for four demos','floor((L-1)/2) for four demos'], 'camera_index':'demo_id+1', 'seed1':'20261029+j','seed2':'20262029+j for j<4'},
                'fixed_calls': {'official_prior':8,'custom_prior':8,'official_repeats_samples':[0,1],
                                'custom_repeats_samples':[2,3],'posterior_first_seed':8,'posterior_second_seed':4},
                'crop_check': {'top':11,'left':17,'size':224,'output':256,'interpolation':'nearest; joint 9 channels; tensor-only'},
                'budget_sha256':sha(E/'budget.json'),'root_plan_sha256':sha(E/'root_plan.json'),
                'no_training':True,'source_baseline_file_count':len(baseline)}
    write(E / 'run_manifest.json', manifest, exclusive=True)
    write(E/'counts.json', {'utc':utc(), 'fixed_forward_attempts':0,'closed_query_attempts':0,
          'total_policy_attempts':0,'optimizer_updates':0,'rollout_attempts':0,
          'closed_steps_reserved':0,'rollouts':{}})
    write(E/'status.json', {'state':'STAGE0','utc':utc(),'gpu_allocation_seconds':0})
    print(json.dumps({'frozen':True,'old_files':len(baseline),'manifest_sha256':sha(E/'run_manifest.json')}))

if __name__ == '__main__':
    main()
