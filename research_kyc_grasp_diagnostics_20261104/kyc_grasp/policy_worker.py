"""Eight fixed accurate-camera rollouts; no old MAE gate and no outcome selection."""
from .common import *
from .gates import worker_gate
from .ledger import begin_rollout,finish_rollout

def main(stage='policy-b'):
    worker_gate(stage)
    from .runtime_safety import isolation,torch_guards
    isolation()
    from .builders import configuration,audit_runtime,make_physics,close_physics,model_setup,close_model
    from .model_runtime import ModelRuntime
    from .roots import restore
    from .control import StepRecorder
    import numpy as np,torch
    modules,provenance,args,stats=configuration();torch_guards(torch);lib=modules['experiment_lib'];runtime=ModelRuntime(save_inputs=False)
    audit=audit_runtime(strict=True,owner_release=True);env=None;model=None;rows=[];error=None;state='PARTIAL'
    try:
        model=model_setup();write(P/'policy_strict_load.json',model['strict_load']);policy=model['policy'];env=make_physics(lib,audit,42)
        embedder=modules['cam_embedding'].PluckerEmbedder(img_size=256,device='cuda')
        roots=read(P/'root_plan.json')['roots'];calls=read(P/'call_plan.json')['calls']
        for rollout in [x for x in read(P/'rollout_plan.json')['rollouts'] if x['phase']=='policy-b']:
            root=next(x for x in roots if x['root_id']==rollout['root']);T=np.asarray(root['T_'+rollout['condition']]);restored=restore(env,lib,audit,root,T);label=rollout['id'];begin_rollout(label);rec=StepRecorder(env,audit.out,label);query_rows=[]
            for item in [x for x in calls if x['rollout_id']==label]:
                rgb,frame=audit.frame(lib,T,item['id'],save_png=item['query'] in [0,4]);data=lib.policy_input(rgb,T,lib.intrinsics(env),model['stats'],embedder,True)
                require(set(data)=={'image','qpos','cam_extrinsics'},'truth/action label leaked to prior')
                norm,raw,record=runtime.call(policy,data,item,model['stats'],P/'results/policy_predictions');query_rows.append(dict(model=record,frame=frame,T=T.tolist()))
                for action in raw:rec.step(action)
            require(len(rec.rows)==150 and len(query_rows)==5,'fixed150step/5query trajectory incomplete')
            audit.frame(lib,T,label+'_final',save_png=True);summary=rec.summary();summary.update(id=label,root=root['root_id'],condition=rollout['condition'],restore=restored,queries=query_rows);rows.append(summary)
            write(P/'policy_progress.json',dict(state='PARTIAL',rollouts=rows));finish_rollout()
        require(runtime.guard.policy_entries==runtime.guard.internal_entries==40 and len(rows)==8,'policy logical/internal/rollout count mismatch')
        state='COMPLETE_EIGHT_PAIRED_ROLLOUTS_PENDING_DUAL_REVIEW'
    except BaseException as exc:error=type(exc).__name__+': '+str(exc);raise
    finally:
        cleanup=None
        try:
            if env is not None:close_physics(env,audit)
            if model is not None:policy=None;embedder=None;close_model(model)
        except BaseException as exc:cleanup=type(exc).__name__+': '+str(exc);state='PARTIAL'
        write(P/'policy_result.json',dict(utc=utc(),state=state,error=error,cleanup_error=cleanup,rollouts=rows,policy_entries=runtime.guard.policy_entries,internal_entries=runtime.guard.internal_entries,roots_manifest_sha256=sha(P/'roots/manifest.json'),independent_physical_roots=4,original_dev_physics=False,no_paper_reproduction_claim=True,provenance=provenance))
        if cleanup and error is None:raise RuntimeError(cleanup)
