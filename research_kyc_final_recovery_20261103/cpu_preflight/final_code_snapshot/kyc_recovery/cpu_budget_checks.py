"""Actual CPU test ledger and OS termination; never records real ACT work."""
from .common import *
from .gates import charge
from .call_guard import CallGuard
import subprocess


def run_checks():
    state=dict(counts={k:0 for k in CAPS},active_rollout=None)
    ledger=[]
    def counted(kind,worker,label):
        n=charge(state,kind,'s1-model',label)
        ledger.append(dict(event='CPU_SIMULATED_LOGICAL_ATTEMPT',ordinal=n));return n
    guard=CallGuard(counted,lambda *a:None)
    for _ in range(16):
        guard.expect(dict(branch='official_prior'))
        guard.policy_enter('official_prior',['image','qpos','cam_extrinsics'],1)
        guard.internal_enter(False,1);guard.complete()
    require(state['counts']['s1_ACT']==guard.internal_entries==16,'matching internal/policy counted twice')
    denied=[]
    for label,kind,stage in [('ACT17','ACT','s1-model'),('preflight_render','renders','gpu-preflight'),
                             ('preflight_ACT','ACT','gpu-preflight'),('S1_step','env_steps','s1-input'),
                             ('optimizer','optimizer','s1-model')]:
        try:charge(state,kind,stage,'CPU_TEST')
        except RuntimeError:denied.append(label)
        else:raise RuntimeError('real CPU budget refusal failed: '+label)
    state['active_rollout']={'label':'CPU_TEST_ONLY'}
    for _ in range(150):charge(state,'env_steps','s2-closed','CPU_TEST')
    try:charge(state,'env_steps','s2-closed','CPU_TEST_STEP151')
    except RuntimeError:denied.append('rollout_step151')
    else:raise RuntimeError('per-rollout bound failed')
    from .supervisor import terminate
    command=[str(R/'env/bin/python'),'-B','-c','import time; time.sleep(60)']
    started=time.monotonic()
    with (P/'logs/cpu_termination_test.log').open('w') as log:
        child=subprocess.Popen(command,cwd=P,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    identity=proc(child.pid);require(identity,'CPU test process identity absent')
    time.sleep(.15);terminate(child,identity)
    require(child.returncode is not None and not active(identity),'real CPU supervised termination failed')
    result=dict(utc=utc(),state='CPU_BUDGET_AND_OS_TERMINATION_PASSED',
        separate_test_ledger=True,not_ACT_observations=True,logical_tickets=16,matching_internal_entries=16,
        denied_operations=denied,test_counts=state['counts'],CPU_process_command=command,CPU_process_identity=identity,
        terminated_exit_code=child.returncode,CPU_test_elapsed=time.monotonic()-started,
        actual_ACT_forwards=0,actual_env_steps=0,actual_GPU_seconds=0)
    write(P/'cpu_preflight/cpu_budget_checks.json',result)
    return result
