"""Matched expert controls through exactly the same root/reset/wrapper as B."""
from .common import *
from .gates import worker_gate
from .ledger import begin_rollout,finish_rollout

def main(stage='expert-a'):
    worker_gate(stage)
    from .runtime_safety import isolation,torch_guards
    isolation()
    from .builders import configuration,audit_runtime,make_physics,close_physics
    from .model_runtime import ModelRuntime
    from .roots import restore
    from .control import StepRecorder
    import numpy as np,torch
    modules,provenance,args,stats=configuration();torch_guards(torch);runtime=ModelRuntime(save_inputs=False);lib=modules['experiment_lib']
    audit=audit_runtime(strict=True,owner_release=True);env=None;rows=[];error=None;state='PARTIAL'
    try:
        env=make_physics(lib,audit,42)
        for root in read(P/'root_plan.json')['roots']:
            label='A_root'+str(root['root_id']);T=np.asarray(root['T_train']);restored=restore(env,lib,audit,root,T);begin_rollout(label)
            audit.frame(lib,T,label+'_initial',save_png=True);rec=StepRecorder(env,audit.out,label)
            with np.load(P/root['expert_file'],allow_pickle=False) as z:actions=z['actions'].copy();ref=z['reference_next_eef'].copy()
            deviations=[]
            for j,action in enumerate(actions):
                row=rec.step(action);deviations.append(float(np.linalg.norm(np.asarray(row['eef_pos'])-ref[j])))
            audit.frame(lib,T,label+'_final',save_png=True);summary=rec.summary();summary.update(id=label,root=root['root_id'],restore=restored,expert_EEF_deviation_max_m=max(deviations),expert_EEF_deviation_mean_m=float(np.mean(deviations)),control_checks_pass=summary['success_interfaces_agree'] and max(deviations)<.02)
            rows.append(summary);write(P/'expert_progress.json',dict(state='PARTIAL',rollouts=rows));finish_rollout()
            require(summary['success'] and summary['control_checks_pass'],'MATCHED_EXPERT_CONTROL_FAILED_STOP_NO_POLICY_B')
        require(runtime.guard.policy_entries==runtime.guard.internal_entries==0,'ACT in expert control')
        state='ALL_FOUR_MATCHED_EXPERT_CONTROLS_PASS'
    except BaseException as exc:error=type(exc).__name__+': '+str(exc);raise
    finally:
        cleanup=None
        try:close_physics(env,audit)
        except BaseException as exc:cleanup=type(exc).__name__+': '+str(exc);state='PARTIAL'
        write(P/'expert_result.json',dict(utc=utc(),state=state,error=error,cleanup_error=cleanup,rollouts=rows,roots_manifest_sha256=sha(P/'roots/manifest.json'),ACT=0,provenance=provenance,not_original_demo_XML=True))
        if cleanup and error is None:raise RuntimeError(cleanup)
