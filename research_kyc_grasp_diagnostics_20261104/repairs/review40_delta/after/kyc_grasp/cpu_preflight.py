"""Same runtime/cwd/CLI and real loader; CPU guard installed before dependencies."""
from .common import *
import sys,importlib

def main():
    auth=read(P/'CPU_PREPARATION_AUTHORIZATION.json')
    require(auth and auth['state']=='CPU_PREPARATION_ONLY' and auth['scope_id']==SCOPE_ID and auth['executor']==EXECUTOR and not auth['GPU_authorized'],'CPU authorization missing')
    require(auth['user_task_sha256']==sha(P/'00_本轮用户任务书_原文.md') and auth['parent_prompt_sha256']==sha(P/'orchestration/preparation_dispatch_prompt.md'),'CPU scope authority changed')
    from .runtime_safety import isolation
    isolation()
    from .cpu_guard import CPUAudit
    audit=CPUAudit();audit.install_before_torch();result=dict(utc=utc(),status='RUNNING',scope_id=SCOPE_ID,interpreter=sys.executable,cwd=os.getcwd(),CUDA_VISIBLE_DEVICES=os.environ.get('CUDA_VISIBLE_DEVICES'),dont_write_bytecode=sys.dont_write_bytecode)
    try:
        import torch
        audit.install_torch(torch)
        from .loader import load_actual,origins
        modules,provenance=load_actual()
        import numpy as np,h5py
        # Actual local safe entry modules are imported, not AST/mocked.
        local=[]
        for name in ['run_experiment','evaluate','validate_semantics']:
            module=importlib.import_module(name);require(Path(module.__file__).resolve()==R/('scripts/'+name+'.py'),'local entry origin mismatch');local.append(origins(module))
        helper=P/'tmp/official_atomic_probe.json';modules['common'].atomic_json(helper,{'scope':SCOPE_ID,'CPU_ONLY':True});require(read(helper)=={'scope':SCOPE_ID,'CPU_ONLY':True},'actual atomic helper semantic failure')
        stamp=modules['common'].utc();require(datetime.datetime.fromisoformat(stamp).tzinfo is not None,'upstream UTC is naive')
        ck=torch.load(R/'checkpoints/C_latest.pt',map_location='cpu',weights_only=False);state=ck['model_state_dict'];config=read(R/'manifests/C_config.json');stats=read(R/'manifests/dataset_stats.json')
        require(len(state)==375 and ck['args']==config and all(v.device.type=='cpu' and torch.isfinite(v).all().item() for v in state.values()),'CPU checkpoint metadata/finite mismatch')
        require(all(np.array_equal(np.asarray(ck['stats'][k],np.float32),np.asarray(v,np.float32)) for k,v in stats.items()),'stats mismatch')
        require(sha(R/'checkpoints/C_latest.pt')=='c904a97002571d96e3ee6b66057d09162cbdcb5e926cb6ea0b660ca1390bce13','checkpoint changed')
        require(sha(R/'assets/liftrand_eef_delta.hdf5')=='fc89e2a46624b877cd35ae383df9ad09a84b7881c655bc114812164d6ff45377','dataset changed')
        rootplan=read(P/'root_plan.json');sampleplan=read(P/'sample_plan.json');data_rows=[]
        with h5py.File(R/'assets/liftrand_eef_delta.hdf5','r') as data:
            spec=json.loads(data['data'].attrs['env_args']);require(data['data'].attrs['action_space']=='eef_delta','action space')
            ctrl=spec['env_kwargs']['controller_configs']['body_parts']['right'];require(ctrl['input_type']=='absolute' and ctrl['input_ref_frame']=='world' and not spec['env_kwargs']['reward_shaping'] and spec['env_kwargs']['ignore_done'],'control/reward/horizon semantics differ')
            XML_entries=[]
            for key in data['data']:
                group=data['data'][key]
                for n in list(group)+list(group.attrs):
                    if 'xml' in n.lower() or 'model' in n.lower():XML_entries.append(key+'/'+n)
            require(not XML_entries,'per-demo XML evidence changed; substitute-root protocol needs review')
            for root in rootplan['roots']:
                d=data['data/demo_'+str(root['demo_id'])]
                with np.load(P/root['expert_file'],allow_pickle=False) as z:
                    require('reference_next_eef' in z.files,'expert reference_next_eef missing')
                    reference=z['reference_next_eef'];source_reference=d['next_obs/robot0_eef_pos'][()]
                    require(reference.shape==(root['expert_steps'],3) and np.isfinite(reference).all() and np.array_equal(reference,source_reference),'expert reference_next_eef shape/finite/HDF5 source mismatch')
                    require(np.array_equal(z['source_initial_state'],d['states'][0]) and np.array_equal(z['actions'],d['actions'][()]) and np.array_equal(z['starting_abs_action'],d['starting_abs_action'][()]),'expert/initial state source changed')
                    require(hashlib.sha256(z['actions'].tobytes()).hexdigest()==root['HDF5_actions_sha256'] and sha(P/root['expert_file'])==root['expert_file_sha256'],'plan expert SHA mismatch')
                    require(z['actions'].shape==(root['expert_steps'],7) and root['expert_steps']<=150 and all(np.isfinite(z[k]).all() for k in z.files),'expert arrays invalid')
                require(root['env_seed']==42+root['demo_id'] and root['demo_id']<=root['train_camera_index']<root['demo_id']+3,'root/camera index changed')
                data_rows.append(dict(demo=root['demo_id'],steps=root['expert_steps'],state_shape=list(d['states'].shape),actions_dtype=str(d['actions'].dtype),attrs=list(d.attrs),reference_next_eef_present=True,reference_next_eef_shape=list(reference.shape),reference_next_eef_finite=True,reference_next_eef_HDF5_exact=True))
            require(len(rootplan['roots'])==4 and sum(x['steps'] for x in data_rows)==430,'expert plan')
            for item in sampleplan['samples']:require(0<=item['t']<len(data['data/demo_'+str(item['demo_id'])+'/actions']),'C time index out of range')
        require(len(read(P/'rollout_plan.json')['rollouts'])==12 and len(read(P/'call_plan.json')['calls'])==40 and len(sampleplan['samples'])==22 and sampleplan['total_getitems']==44,'planned caps differ')
        by_id={x['id']:x for x in sampleplan['samples']};repeats=[x for x in sampleplan['samples'] if 'repeat_of' in x]
        require(len(by_id)==22 and sum(x['split']=='validation' for x in by_id.values())==10 and sum(x['split']=='train' for x in by_id.values())==12,'C split/unique sample contract changed')
        require([(x['id'],x['repeat_of']) for x in repeats]==[('train_d0_t0_repeat','train_d0_t0'),('train_d1_t0_repeat','train_d1_t0')],'C bounded repeat plan differs')
        for repeat in repeats:
            original=by_id[repeat['repeat_of']]
            require(all(repeat[k]==original[k] for k in ['split','dataset_index','demo_id','t','camera_index','seed']),'C repeat state/camera/RNG start differs')
        from .reader_worker import within_arm_repeats
        not_run=within_arm_repeats(sampleplan['samples'],[])
        require(len(not_run)==2 and all(x['state']=='NOT_RUN' and len(x['missing_sample_ids'])==2 for x in not_run),'C unexecuted repeats must remain NOT_RUN')
        from .cli import ROUTES,resolve
        entries=[]
        for mode in ROUTES:
            module=resolve(mode);require(callable(module.main),'CLI entry missing');entries.append(dict(mode=mode,**origins(module)))
        for name in ['builders','render_audit','roots','control','model_runtime','reader_worker','ledger','gates','cpu_budget_checks']:
            module=importlib.import_module('kyc_grasp.'+name);entries.append(origins(module))
        from .cpu_budget_checks import run_checks
        checks=run_checks();device=audit.finish(torch);require(not device['blocked'] and not device['CUDA_initialized_after'] and not device['GL_modules_imported'],'CPU attempted a device path')
        code={str(f.relative_to(P)):sha(f) for f in [P/'run.py']+sorted((P/'kyc_grasp').glob('*.py'))};snapshot=P/'cpu_preflight/code_snapshot';snapshot.mkdir(exist_ok=False)
        import shutil
        for n in code:
            target=snapshot/n;target.parent.mkdir(exist_ok=True,parents=True);shutil.copyfile(P/n,target)
        result.update(status='CPU_IMPORT_READY',actual_imports=True,provenance=provenance,actual_local_entry_imports=local,final_entry_modules_verified=entries,code_hashes=code,device_audit=device,budget_and_wrapper_CPU_checks=checks,checkpoint_tensors=375,checkpoint_all_CPU_finite=True,args_and_stats_match=True,checkpoint_updates=ck['updates'],checkpoint_epochs=ck['completed_epochs'],expert_sources=data_rows,C_repeat_plan=dict(repeats=repeats,same_state_camera_seed_asserted=True,unexecuted_comparison_contract=not_run,per_arm_getitems=22,total_getitems=44),per_demo_XML_available=False,env_spec=spec,actual_GPU_workers=0,actual_GPU_seconds=0,actual_env_render_ACT_step=0,ENGINEERING_READY=False,GPU_DEFERRED=['four substitute root generation and exact physical/controller restore','actual input/GL construction/cleanup','two healthy readbacks','ACT construct/strict load','all A/B trajectories','actual Dataset crop+collate arms'],torch_version=torch.__version__,numeric_threads=torch.get_num_threads(),interop_threads=torch.get_num_interop_threads())
        del ck,state
    except BaseException as exc:
        import traceback
        (P/'logs/cpu_preflight_traceback.log').write_text(traceback.format_exc());result.update(status='CPU_PREFLIGHT_FAILED',error=type(exc).__name__+': '+str(exc),device_attempts=audit.blocked);write(P/'cpu_preflight/result.json',result);raise
    write(P/'cpu_preflight/result.json',result)
