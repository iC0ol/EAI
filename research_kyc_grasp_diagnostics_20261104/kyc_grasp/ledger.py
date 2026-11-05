"""Same pure charge logic used by CPU refusal tests and actual workers."""
from .common import *
def fresh():return dict(scope_id=SCOPE_ID,counts={k:0 for k in CAPS},phase_counts={},stages={},GPU_seconds=0.,active_lease=None,active_rollout=None)
def charge(state,kind,stage,label,limits=None):
    limits=limits or read(P/'phase_plan.json')['phase_caps']
    require(stage in limits and kind in CAPS,'unknown operation/phase')
    maximum=limits[stage].get(kind,0);phase=state['phase_counts'].setdefault(stage,{})
    require(phase.get(kind,0)<maximum,'phase operation forbidden/capped: '+kind)
    require(state['counts'][kind]<CAPS[kind],'scope operation capped: '+kind)
    if kind in ['ACT','env_steps'] or (kind in ['renders','readPixels'] and stage in ['expert-a','policy-b']):
        row=state.get('active_rollout');require(row,'operation outside rollout')
        cap={'ACT':5,'env_steps':150,'renders':6 if stage=='policy-b' else 2,'readPixels':12 if stage=='policy-b' else 4}[kind]
        require(row.get(kind,0)<cap,'per-rollout cap: '+kind);row[kind]=row.get(kind,0)+1
    phase[kind]=phase.get(kind,0)+1;state['counts'][kind]+=1
    return state['counts'][kind]
def current_stage():return ((read(P/'scope_state.json',{}) or {}).get('active_lease') or {}).get('stage')
def reserve(kind,worker,label):
    with (P/'counter.lock').open('a+') as f:
        fcntl.flock(f,fcntl.LOCK_EX);s=read(P/'scope_state.json');lease=(s or {}).get('active_lease') or {}
        require(lease and not (P/'terminal_stop.json').exists(),'no active scope lease')
        require(time.time()<lease['wall_deadline_epoch'],'scope wall deadline')
        append(P/'call_ledger.jsonl',dict(utc=utc(),event='ATTEMPT_BEFORE_OPERATION',phase=lease['stage'],kind=kind,label=label))
        n=charge(s,kind,lease['stage'],label);write(P/'scope_state.json',s);return n
def begin_rollout(label):
    reserve('rollouts','worker',label)
    with (P/'counter.lock').open('a+') as f:
        fcntl.flock(f,fcntl.LOCK_EX);s=read(P/'scope_state.json');require(label not in s.get('rollout_labels',[]),'rollout retry')
        s.setdefault('rollout_labels',[]).append(label);s['active_rollout']={'label':label};write(P/'scope_state.json',s)
def finish_rollout():
    with (P/'counter.lock').open('a+') as f:
        fcntl.flock(f,fcntl.LOCK_EX);s=read(P/'scope_state.json');s['active_rollout']=None;write(P/'scope_state.json',s)
