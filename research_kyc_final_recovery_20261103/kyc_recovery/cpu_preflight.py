"""Actual authorized CPU dependency/checkpoint preflight; no GL/ACT instance."""
from .common import *
import sys


def main():
    dispatch = read(P/'orchestration/preflight_dispatch.json')
    gate = read(P/'preflight_scope_gate.json')
    require(dispatch['mode'] == 'CPU_PRE_FLIGHT_AND_REPAIR_ONLY' and not dispatch['GPU_authorized_now'], 'CPU scope missing')
    require(sha(P/'preflight_scope_gate.json') == dispatch['scope_gate_sha256']
            and sha(P/'01_有限恢复边界与阶段门.md') == gate['protocol_sha256'], 'CPU authorization SHA changed')
    require(time.time() < dispatch['preparation_deadline_epoch'], 'CPU preparation deadline')
    from .runtime_safety import isolation
    isolation()
    from .cpu_guard import CPUAudit
    audit = CPUAudit(); audit.install_before_torch()
    result = dict(utc=utc(), status='RUNNING', interpreter=sys.executable, cwd=os.getcwd(),
                  flags=dict(dont_write_bytecode=sys.dont_write_bytecode),
                  CUDA_VISIBLE_DEVICES=os.environ.get('CUDA_VISIBLE_DEVICES'), actual_imports=False)
    try:
        import torch
        audit.install_torch(torch)
        from .loader import load_actual
        modules, provenance = load_actual()
        result.update(actual_imports=True, provenance=provenance)
        import numpy as np
        import h5py
        lib, official = modules['experiment_lib'], modules['common']
        # Exercise the real upstream helper in NEW scratch space only.
        helper_path=P/'tmp/official_atomic_probe.json'
        official.atomic_json(helper_path, {'probe':'CPU_ONLY', 'number':3})
        payload=helper_path.read_text(); value,end=json.JSONDecoder().raw_decode(payload)
        require(value == {'probe':'CPU_ONLY','number':3} and not helper_path.with_suffix('.json.tmp').exists(),
                'atomic helper failed its real write/replace contract')
        result['official_atomic_semantics']=dict(JSON_prefix_equal=True, suffix=payload[end:],
            full_json_document=payload[end:].strip() == '', upstream_source_unchanged=True,
            used_for_formal_harness_bookkeeping=False)
        stamp=official.utc(); datetime.datetime.fromisoformat(stamp)
        result['utc_semantics']=dict(value=stamp, ISO8601_timezone_present=datetime.datetime.fromisoformat(stamp).tzinfo is not None)
        checkpoint=R/'checkpoints/C_latest.pt'; expected=read(D/'execution/results/checkpoint_audit.json')
        require(sha(checkpoint) == expected['sha256'], 'checkpoint SHA differs')
        ck=torch.load(checkpoint,map_location='cpu',weights_only=False)
        state=ck['model_state_dict']; config=read(R/'manifests/C_config.json')
        require(len(state)==375 and ck['args']==config,'checkpoint count/args differ')
        require(all(v.device.type=='cpu' and torch.isfinite(v).all().item() for v in state.values()), 'checkpoint CPU/finite failure')
        stats={k:np.asarray(v,np.float32) for k,v in read(R/'manifests/dataset_stats.json').items()}
        require(all(np.array_equal(np.asarray(ck['stats'][k],np.float32),v) for k,v in stats.items()),'stats differ')
        constants=read(D/'execution/constants.json'); require(sha(lib.DATA)==constants['source_data_sha256'],'dataset SHA differs')
        samples=read(P/'sample_plan.json')['samples']; rows=[]
        with h5py.File(lib.DATA,'r') as data:
            for s in samples:
                states=data['data/demo_%d/states'%s['demo_id']][s['t']].astype(np.float32)
                actions=data['data/demo_%d/actions'%s['demo_id']][s['t']:s['t']+30].astype(np.float32)
                require(hashlib.sha256(states.tobytes()).hexdigest()==s['source_state_f32']['sha256'],'state SHA')
                require(hashlib.sha256(actions.tobytes()).hexdigest()==s['raw_expert_chunk']['sha256'],'expert SHA')
                rows.append(dict(sample=s['sample'],state_shape=list(states.shape),action_shape=list(actions.shape)))
        result['resources']=dict(checkpoint_sha256=sha(checkpoint),checkpoint_tensors=375,
            checkpoint_all_finite=True,checkpoint_CPU=True,args_equal=True,stats_equal=True,
            dataset_sha256=sha(lib.DATA),cached_resnet_sha256=sha(R/'cache/torch/hub/checkpoints/resnet18-f37072fd.pth'),
            weighted_constants_sha256=sha(D/'execution/constants.json'),samples=rows)
        if os.environ.get('KYC_FINAL_COVERAGE')=='1':
            from .cli import ROUTES,resolve
            entries=[]
            for mode in ROUTES:
                module=resolve(mode)
                require(callable(module.main),'CLI entry has no callable main: '+mode)
                entries.append(dict(mode=mode,name=module.__name__,file=module.__file__,
                    spec_origin=module.__spec__.origin,sys_modules_same_object=sys.modules[module.__name__] is module,
                    source_sha256=sha(Path(module.__file__)),native_entry_execution='DEFERRED' if mode!='cpu-preflight' else 'CPU_ONLY'))
            from . import builders,model_runtime
            entries += [dict(name=x.__name__,file=x.__file__,spec_origin=x.__spec__.origin,
                sys_modules_same_object=sys.modules[x.__name__] is x,source_sha256=sha(Path(x.__file__)),
                constructor_execution='DEFERRED') for x in [builders,model_runtime]]
            from .cpu_budget_checks import run_checks
            result['budget_supervision_actual_CPU_tests']=run_checks()
            result['final_entry_modules_verified']=entries
            result['final_code_hashes']={str(f.relative_to(P)):sha(f) for f in
                [P/'run.py']+sorted((P/'kyc_recovery').glob('*.py'))}
            snapshot=P/'cpu_preflight/final_code_snapshot';snapshot.mkdir(exist_ok=False)
            import shutil
            for name in result['final_code_hashes']:
                target=snapshot/name;target.parent.mkdir(exist_ok=True,parents=True);shutil.copyfile(P/name,target)
        result['device_audit']=audit.finish(torch)
        require(not result['device_audit']['blocked'] and not result['device_audit']['CUDA_initialized_after'], 'CPU side effect')
        result['status']='CPU_IMPORT_READY'
        result['GPU_pending']=['actual input construction/cleanup','ACT construction and strict load',
                                'healthy native readback','BF16 real forward','closed-loop execution']
        result['ENGINEERING_READY']=False
        del ck,state
    except BaseException as exc:
        import traceback
        (P/'logs/cpu_preflight_traceback.log').write_text(traceback.format_exc())
        result.update(status='CPU_PREFLIGHT_FAILED', error=type(exc).__name__+': '+str(exc),
                      traceback='logs/cpu_preflight_traceback.log',device_attempts=audit.blocked)
        write(P/'cpu_preflight/result.json',result)
        raise
    write(P/'cpu_preflight/result.json',result)
