"""Candidate only: four frozen roots + two registered frames + strict load, no ACT."""
from .common import *
from .gates import worker_gate

def main(stage='gpu-preflight'):
    worker_gate(stage)
    from .runtime_safety import isolation,torch_guards
    isolation()
    from .builders import configuration,audit_runtime,make_physics,training_setup,close_physics,model_setup,close_model
    from .model_runtime import ModelRuntime
    from .roots import freeze_one
    import numpy as np,torch
    modules,provenance,args,stats=configuration();torch_guards(torch);runtime=ModelRuntime(save_inputs=False)
    audit=audit_runtime(strict=True,owner_release=True);lib=modules['experiment_lib'];roots=[];env=None;ds=None;model=None;error=None;state='STOPPED'
    try:
        for root in read(P/'root_plan.json')['roots']:
            audit.label('PREFLIGHT_ROOT_'+str(root['root_id']));env=make_physics(lib,audit,root['env_seed'])
            if root['root_id']==0:ds=training_setup(env)
            row=freeze_one(env,lib,audit,root);roots.append(row)
            if root['root_id']==0:
                for condition in ['train','dev']:audit.frame(lib,np.asarray(root['T_'+condition]),'preflight_'+condition,save_png=True)
            close_physics(env,audit,[] if ds is None else [ds['train'],ds['validation']]);env=None;ds=None
        allfiles={n:v for root in roots for n,v in root['files'].items()}
        write(P/'roots/manifest.json',dict(utc=utc(),scope_id=SCOPE_ID,root_plan_sha256=sha(P/'root_plan.json'),roots=roots,files=allfiles,original_demonstrator_XML_reconstruction=False),exclusive=True)
        model=model_setup();write(P/'preflight_strict_load.json',model['strict_load']);close_model(model);model=None
        require(runtime.guard.policy_entries==runtime.guard.internal_entries==0,'implicit ACT in preflight')
        state='ENGINEERING_READY_ROOTS_AND_READBACK_AND_STRICT_LOAD'
    except BaseException as exc:error=type(exc).__name__+': '+str(exc);raise
    finally:
        cleanup=None
        try:
            if env is not None:close_physics(env,audit,[] if ds is None else [ds['train'],ds['validation']])
            if model is not None:close_model(model)
        except BaseException as exc:cleanup=type(exc).__name__+': '+str(exc);state='STOPPED'
        write(P/'gpu_preflight_result.json',dict(utc=utc(),state=state,error=error,cleanup_error=cleanup,actual_root_count=len(roots),frames=list(audit.frames),ACT=0,steps=0,rollouts=0,roots_manifest_sha256=sha(P/'roots/manifest.json') if (P/'roots/manifest.json').exists() else None,provenance=provenance,all_contexts_destroyed=not any(x['alive'] for x in audit.api.contexts.values()),current_scope_only=True))
        if cleanup and error is None:raise RuntimeError(cleanup)
