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
    from .gates import gate
    refused('GPU_gate_without_RUN',lambda:gate('gpu-preflight'))
    return dict(state='PASS_CPU_INTERFACE_AND_REFUSALS_ONLY',logical_mock_ACT_tickets=40,matching_mock_internal_entries=40,actual_ACT=0,actual_env_steps=0,refusals=rows,real_sleep_process_identity=identity,real_sleep_process_exit_code=sleeper.returncode,real_sleep_process_inactive=True,actual_supervisor_terminate_exercised=True,wrapper_source_sha256=sha(source),actual_wrapper_function_executed_on_fake_CPU_base=True,wrapper_absolute_commands=[v.tolist() for v in env.commands],physics_and_control_success='DEFERRED')
