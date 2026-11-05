"""CPU-only production-charge refusals, real OS termination, extracted wrapper contract."""
from .common import *
from .ledger import charge,fresh
from .call_guard import CallGuard

def run_checks():
    import subprocess,ast,copy
    import numpy as np
    from .supervisor import terminate
    rows=[]
    def refused(label,fun):
        try:fun()
        except RuntimeError as exc:rows.append(dict(check=label,refused=True,reason=str(exc)))
        else:raise RuntimeError('budget refusal absent: '+label)
    for kind in ['ACT','env_steps','rollouts','getitems']:
        s=fresh();refused('preflight_'+kind,lambda s=s,kind=kind:charge(s,kind,'gpu-preflight','synthetic_CPU_only'))
    s=fresh();s['active_rollout']={'label':'CPU_only_fixture'};refused('training_optimizer',lambda:charge(s,'optimizer','policy-b','CPU'))
    s=fresh();s['active_rollout']={'label':'CPU_only_fixture'};guard=CallGuard(lambda kind,*args:charge(s,kind,'policy-b','CPU_ticket'),lambda *a:None)
    for i in range(40):
        if i%5==0:s['active_rollout']={'label':'CPU_only_fixture'}
        item=dict(branch='official_prior',batch=1,id=str(i));guard.expect(item);guard.policy_enter('official_prior',keys={'image','qpos','cam_extrinsics'},batch=1);guard.internal_enter(has_labels=False,batch=1);guard.complete()
    require(s['counts']['ACT']==guard.policy_entries==guard.internal_entries==40,'matching internal call double counted')
    refused('ACT41',lambda:charge(s,'ACT','policy-b','CPU_41'))
    s=fresh();s['active_rollout']={'label':'CPU_only_fixture'}
    for _ in range(150):charge(s,'env_steps','policy-b','CPU_step')
    refused('per_rollout_step151',lambda:charge(s,'env_steps','policy-b','CPU_step151'))
    s=fresh();s['active_rollout']={'label':'CPU_only_fixture'}
    for _ in range(5):charge(s,'ACT','policy-b','CPU_query')
    refused('per_rollout_query6',lambda:charge(s,'ACT','policy-b','CPU_query6'))
    s=fresh()
    for stage in ['c-local','c-official']:
        for _ in range(22):charge(s,'getitems',stage,'CPU')
    refused('getitem45',lambda:charge(s,'getitems','c-official','CPU'))
    s=fresh()
    for stage,n in [('expert-a',4),('policy-b',8)]:
        for _ in range(n):charge(s,'rollouts',stage,'CPU')
    refused('rollout13',lambda:charge(s,'rollouts','policy-b','CPU'))
    sleeper=subprocess.Popen([str(R/'env/bin/python'),'-B','-c','import time;time.sleep(60)'],cwd=P,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
    identity=proc(sleeper.pid);terminate(sleeper,identity);require(sleeper.returncode==-15 and not active(identity),'real OS termination failed')
    # Execute the actual wrapper source on a CPU fake base. This is an interface
    # contract test, explicitly not MuJoCo execution or an expert positive control.
    source=R/'vendor/robosuite/robosuite/wrappers/action_wrapper.py';tree=ast.parse(source.read_text());node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='wrap_env_action_space');scope={'np':np};exec(compile(ast.Module(body=[copy.deepcopy(node)],type_ignores=[]),str(source),'exec'),scope)
    class FakeBase:
        def step(self,action):self.commands.append(np.asarray(action).copy());return 'CPU_ONLY'
    env=FakeBase();env.commands=[];env=scope['wrap_env_action_space'](env,'eef_delta');env._asw_last_abs_pose=np.arange(6,dtype=float)/10;initial=env._asw_last_abs_pose.copy()
    actions=[np.array([.01,.02,-.03,.001,-.002,.003,-1.]),np.array([-.01,.04,.02,.002,.001,-.001,1.])]
    for a in actions:env.step(a)
    expected=initial.copy()
    for a,absolute in zip(actions,env.commands):expected+=a[:6];require(np.array_equal(absolute,np.r_[expected,a[-1]]),'actual wrapper CPU contract failed')
    from .model_runtime import execute_denormalize
    import torch
    from types import SimpleNamespace
    mkdir_checks=[]
    for name,receiver in [('render_audit','self.out'),('roots','directory')]:
        mkdir_source=P/('kyc_grasp/'+name+'.py');tree=ast.parse(mkdir_source.read_text())
        calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='mkdir' and ast.unparse(n.func.value)==receiver]
        require(len(calls)==1,'production output mkdir call changed')
        target=P/('tmp/review40_mkdir_'+name+'/missing_parent/leaf');require(not target.parent.exists(),'mkdir contract requires an absent parent')
        namespace={'self':SimpleNamespace(out=target),'directory':target}
        statement=ast.fix_missing_locations(ast.Module(body=[ast.Expr(value=copy.deepcopy(calls[0]))],type_ignores=[]));code=compile(statement,str(mkdir_source),'exec')
        exec(code,namespace);require(target.is_dir(),'production mkdir did not create missing parents')
        marker=target/'existing_evidence.txt';marker.write_text('preserve existing evidence\n')
        try:exec(code,namespace)
        except FileExistsError:pass
        else:raise RuntimeError('production mkdir allowed an existing output directory')
        require(marker.read_text()=='preserve existing evidence\n','existing evidence changed')
        mkdir_checks.append(dict(source=str(mkdir_source.relative_to(P)),source_sha256=sha(mkdir_source),actual_production_mkdir_expression_executed=True,missing_parents_created=True,existing_directory_refused=True,existing_evidence_unchanged=True,device_constructor_executed=False))
    normalized=np.linspace(-1.1,1.3,210,dtype=np.float32).reshape(30,7)
    stats={k:np.asarray(v,np.float32) for k,v in read(R/'manifests/dataset_stats.json').items()}
    tree=ast.parse((K/'eval.py').read_text());candidates=[n for n in ast.walk(tree) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='action_chunk' for t in n.targets) and isinstance(n.value,ast.BinOp) and 'action_std' in ast.unparse(n.value)]
    require(len(candidates)==1,'official denormalization assignment changed')
    reference=eval(compile(ast.Expression(body=copy.deepcopy(candidates[0].value)),str(K/'eval.py'),'eval'),dict(action_chunk=torch.from_numpy(normalized[None]),self=SimpleNamespace(norm_stats={k:torch.from_numpy(v) for k,v in stats.items()})))
    execution=execute_denormalize(normalized,stats);require(execution.dtype==reference.dtype==np.float32 and np.array_equal(execution,reference),'execution arithmetic differs from actual official CPU expression')
    arithmetic=dict(official_source_sha256=sha(K/'eval.py'),actual_official_expression_executed_on_real_CPU_tensor=True,output_dtype=str(execution.dtype),bit_equal=True,actual_ACT_calls=0)
    from .gates import gate
    refused('GPU_gate_without_RUN',lambda:gate('gpu-preflight'))
    return dict(state='PASS_CPU_INTERFACE_AND_REFUSALS_ONLY',logical_mock_ACT_tickets=40,matching_mock_internal_entries=40,actual_ACT=0,actual_env_steps=0,refusals=rows,real_sleep_process_identity=identity,real_sleep_process_exit_code=sleeper.returncode,real_sleep_process_inactive=True,actual_supervisor_terminate_exercised=True,wrapper_source_sha256=sha(source),actual_wrapper_function_executed_on_fake_CPU_base=True,wrapper_absolute_commands=[v.tolist() for v in env.commands],production_mkdir_contracts=mkdir_checks,official_float32_execution_contract=arithmetic,physics_and_control_success='DEFERRED')
