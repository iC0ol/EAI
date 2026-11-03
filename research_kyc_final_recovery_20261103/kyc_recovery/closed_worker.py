"""Conditional accurate-camera paired Lift evaluation, no perturbations."""
from .common import *
from .gates import worker_gate,reserve,begin_rollout


def main():
    worker_gate('s2-closed')
    from .runtime_safety import isolation,torch_guards
    isolation()
    from .loader import load_actual
    modules,provenance=load_actual();lib=modules['experiment_lib']
    import numpy as np
    import torch
    torch_guards(torch)
    import robosuite.utils.binding_utils as bu
    from robosuite.renderers.context import egl_context as ec
    from .input_runtime import InputRuntime
    from .model_runtime import ModelRuntime
    from .builders import model_setup,physics_setup,close_model
    runtime=InputRuntime(ec,bu,np);runtime.install()
    model_runtime=ModelRuntime(save_inputs=False);bundle=None;env=None;previous=None;rows=[]
    root_plan=read(P/'root_plan.json')['ordered_rollouts']
    require(len(root_plan)==16 and {x['root'] for x in root_plan}==set(range(1000,1008)),'root plan mismatch')
    oldrows={x['root_id']:x for x in [json.loads(line) for line in (R/'results/dev_rollouts.jsonl').read_text().splitlines()] if x['tag'] is None}
    try:
        bundle=model_setup();policy=bundle['policy'];stats=bundle['stats']
        embedder=modules['cam_embedding'].PluckerEmbedder(img_size=256,device='cuda')
        write(P/'results/closed_strict_load.json',bundle['strict_load'])
        for item in root_plan:
            root=item['root'];condition=item['condition'];key=str(root)+'_'+condition;T=np.asarray(item['T'])
            if previous!=root:
                if env is not None:runtime.label('CLEANUP_PREVIOUS_ROOT');env.close()
                runtime.label('INIT_ROOT_'+str(root));env=physics_setup(lib,runtime,item['old_root']['env_seed']);previous=root
                actual_step=env.step
                def step(action):
                    reserve('env_steps','closed','actual_outer_env.step')
                    return actual_step(action)
                env.step=step
            begin_rollout(key)
            folder=R/('root_states/dev/'+str(root));manifest=read(folder/'manifest.json')
            for filename,field in [('model.xml','xml_sha256'),('state.npy','state_sha256'),('rng.pt','rng_sha256')]:
                require(sha(folder/filename)==manifest[field],'root physical/RNG source changed')
            runtime.label('RESTORE_'+key)
            env.reset_from_xml_string((folder/'model.xml').read_text())
            initial=np.load(folder/'state.npy',allow_pickle=False)
            env.sim.set_state_from_flattened(initial);env.sim.forward();env.set_init_action()
            lib.restore_rng(torch.load(folder/'rng.pt',map_location='cpu',weights_only=False))
            lib.camera_pose(env,T)
            require(np.array_equal(env.sim.get_state().flatten(),initial),'physical state not restored exactly')
            runtime.expected_context=runtime.api.owner(env.sim._render_context_offscreen.gl_ctx)
            runtime.expected_ids=runtime.api.ids(env.sim._render_context_offscreen.con);runtime.api.check()
            actions=[];eef=[];objects=[];success=[];grasp=[];reach=[];queries=[];done=False
            for q in range(5):
                runtime.label('r%d_%s_q%d'%(root,condition,q))
                rgb=lib.render(env,T)  # exactly one policy observation; no screenshots/video
                rgb_sha=hashlib.sha256(np.ascontiguousarray(rgb).tobytes()).hexdigest()
                inputs=lib.policy_input(rgb,T,lib.intrinsics(env),stats,embedder,True)
                call=dict(id=key+'_q'+str(q),sample=root,branch='custom_prior',repeat=False,seed=None)
                norm,chunk,record=model_runtime.call(policy,inputs,call,stats,P/'results/closed_predictions')
                oldcmp=None
                if condition=='dev':
                    with np.load(R/oldrows[root]['trace_path'],allow_pickle=False) as z:
                        old_chunk=z['actions'][q*30:q*30+len(chunk)].copy()
                    oldcmp=dict(shape_equal=old_chunk.shape==chunk.shape,
                        maxabs_by_dim=np.max(abs(old_chunk-chunk),axis=0).tolist() if old_chunk.shape==chunk.shape else None,
                        interpretation='descriptive only; never an equality gate')
                queries.append(dict(q=q,prediction=record,RGB_sha256=rgb_sha,
                    old_initial_RGB_equal=rgb_sha==manifest['clean_RGB'] if condition=='dev' and q==0 else None,
                    old_action_comparison=oldcmp))
                for action in chunk:
                    if done or len(actions)>=150:break
                    obs,reward,done,info=env.step(action)
                    site=env.sim.model.camera_name2id('agentview')  # camera identity recorded, never fed labels
                    eef_site=env.sim.model.site_name2id('gripper0_right_grip_site')
                    e=np.asarray(env.sim.data.site_xpos[eef_site]).copy()
                    o=np.asarray(env.sim.data.body_xpos[env.cube_body_id]).copy()
                    actions.append(action.copy());eef.append(e);objects.append(o)
                    success.append(bool(env._check_success()))
                    grasp.append(bool(env._check_grasp(gripper=env.robots[0].gripper,object_geoms=env.cube)))
                    reach.append(bool(np.linalg.norm(e-o)<.05))
                if done or len(actions)>=150:break
            path=P/('results/closed_'+key+'.npz')
            np.savez_compressed(path,actions=np.asarray(actions),eef_xyz=np.asarray(eef),object_xyz=np.asarray(objects),
                success=np.asarray(success),grasp=np.asarray(grasp),reach=np.asarray(reach),initial_state=initial,T=T)
            row=dict(root=root,condition=condition,success=any(success),reach=any(reach),grasp=any(grasp),
                steps=len(actions),queries=len(queries),query_records=queries,initial_state_sha256=hashlib.sha256(initial.tobytes()).hexdigest(),
                source_xml_sha256=manifest['xml_sha256'],source_state_sha256=manifest['state_sha256'],source_rng_sha256=manifest['rng_sha256'],
                trace=str(path.relative_to(P)),trace_sha256=sha(path))
            rows.append(row);append(P/'results/closed_rollouts.jsonl',row)
        require(model_runtime.guard.policy_entries==model_runtime.guard.internal_entries<=80,'closed model counter mismatch')
        summary={c:dict(success=sum(x['success'] for x in rows if x['condition']==c),
                reach=sum(x['reach'] for x in rows if x['condition']==c),grasp=sum(x['grasp'] for x in rows if x['condition']==c),n=8)
                for c in ['train','dev']}
        write(P/'closed_result.json',dict(utc=utc(),state='COMPLETE',rows=rows,conditions=summary,
            physical_roots=8,paired=[dict(root=r,**{c:next(x for x in rows if x['root']==r and x['condition']==c) for c in ['train','dev']}) for r in range(1000,1008)],
            interpretation='BASELINE_LIMITED' if summary['train']['success']==0 else 'TASK_POSITIVITY_OBSERVED_DUAL_REVIEW_REQUIRED',
            no_automatic_F_claim=True,Stage3='PLAN_ONLY_NOT_EXECUTED'))
    except BaseException as exc:
        write(P/'closed_result.json',dict(utc=utc(),state='STOPPED',rows=rows,error=type(exc).__name__+': '+str(exc)));raise
    finally:
        if env is not None:runtime.label('CLEANUP');env.close();env=None
        runtime.api.check();require(not any(x['alive'] for x in runtime.api.contexts.values()),'closed GL context leak')
        if bundle is not None:policy=None;close_model(bundle)
