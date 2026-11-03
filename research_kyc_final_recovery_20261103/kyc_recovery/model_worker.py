"""Stage1 model: saved healthy inputs only; real shared model constructor."""
from .common import *
from .gates import worker_gate


def main():
    worker_gate('s1-model')
    from .runtime_safety import isolation
    isolation()
    from .loader import load_actual
    modules,provenance=load_actual()
    from .builders import model_setup,close_model
    from .model_runtime import ModelRuntime
    import numpy as np
    import torch
    runtime=ModelRuntime(save_inputs=True);bundle=None;completed=[]
    try:
        bundle=model_setup();policy=bundle['policy'];stats=bundle['stats']
        write(P/'strict_load.json',bundle['strict_load']);write(P/'results/model_module_provenance.json',provenance)
        first={};repeats={}
        for item in read(P/'call_plan.json')['calls']:
            j=item['sample'];branch=item['branch']
            prefix='custom' if branch=='custom_prior' else ('dataset' if branch=='official_posterior' else 'official')
            path=P/('inputs/sample_%02d.npz'%j)
            with np.load(path,allow_pickle=False) as z:
                inputs={k:torch.from_numpy(z[prefix+'_'+k].copy()).to('cuda') for k in ['image','qpos','cam_extrinsics']}
                if branch=='official_posterior':
                    inputs['actions']=torch.from_numpy(z['actions_full'].copy()).to('cuda')[None]
                    inputs['is_pad']=torch.from_numpy(z['is_pad_full'].copy()).to('cuda')[None]
            require(all(torch.isfinite(v).all().item() for v in inputs.values()),'nonfinite input')
            norm,raw,record=runtime.call(policy,inputs,item,stats,P/'results/predictions')
            record['input_file_sha256']=sha(path);completed.append(record)
            write(P/'model_progress.json',dict(state='RUNNING',calls=completed))
            (repeats if item['repeat'] else first)[(j,branch)]=norm.copy()
            if j in [4,5] and branch=='custom_prior':
                require(float(abs(norm-first[(j,'official_prior')]).max())<=1e-5,'NUMERICAL_OR_ENTRY_INCONCLUSIVE')
            if item['repeat']:
                require(float(abs(norm-first[(j,branch)]).max())<=1e-3,'NUMERIC_UNSTABLE')
                if branch=='custom_prior':
                    noise=max(float(abs(repeats[(j,b)]-first[(j,b)]).max()) for b in ['official_prior','custom_prior'])
                    require(float(abs(first[(j,'official_prior')]-first[(j,'custom_prior')]).max())<=max(1e-5,2*noise),'ENTRY_INCONCLUSIVE')
        require(runtime.guard.policy_entries==runtime.guard.internal_entries==16,'ACT logical/internal accounting')
        write(P/'model_result.json',dict(utc=utc(),state='COMPLETE',calls=completed,policy_entries=16,internal_entries=16,
              backward='NOT_RUN',optimizer='NOT_CREATED',rollout='NOT_RUN'))
    except BaseException as exc:
        write(P/'model_result.json',dict(utc=utc(),state='STOPPED',calls=completed,error=type(exc).__name__+': '+str(exc)));raise
    finally:
        if bundle is not None:
            policy=None;close_model(bundle)
