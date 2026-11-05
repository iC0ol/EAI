"""CPU preparation never grants GPU authority. Every phase needs a new RUN."""
from .common import *
from .ledger import reserve,current_stage

def review(path,mh,ph):
    v=read(path);require(v and v.get('state')=='APPROVED' and v.get('scope_id')==SCOPE_ID,'new scope dual review missing')
    for role in ['codex','deepseek']:
        x=v.get(role,{})
        require(x.get('decision')=='APPROVE' and x.get('manifest_sha256')==mh and x.get('protocol_sha256')==ph,'review exact SHA mismatch')
        require(x.get('evidence_file') and sha(P/x['evidence_file'])==x['evidence_sha256'],'review evidence changed')
    return v

def roots_gate():
    m=read(P/'roots/manifest.json');require(m and len(m['roots'])==4 and m['root_plan_sha256']==sha(P/'root_plan.json'),'all roots must be frozen before behavior')
    for n,v in m['files'].items():require(sha(P/n)==v,'frozen root artifact changed: '+n)
    return m

def gate(stage,full=False):
    require(stage in PHASES and not (P/'terminal_stop.json').exists(),'unknown/terminal scope phase')
    m=read(P/'candidate_manifest.json');d=read(P/('dispatch/'+stage+'.json'))
    require(m and d,'GPU not dispatched; CPU permission insufficient')
    mh=sha(P/'candidate_manifest.json');ph=sha(P/'PROTOCOL_CANDIDATE.md')
    require(m['protocol_sha256']==ph,'protocol changed')
    for n,v in m['files'].items():require(sha(P/n)==v,'candidate changed: '+n)
    if full:
        for n,v in m['sources'].items():require(sha(Path(n))==v,'readonly source changed: '+n)
    require(d.get('mode')=='RUN_PHASE' and d.get('phase')==stage and d.get('scope_id')==SCOPE_ID and d.get('executor')==EXECUTOR,'wrong dispatch/executor/scope')
    require(d.get('manifest_sha256')==mh and d.get('protocol_sha256')==ph and d.get('total_GPU_seconds')==900,'dispatch SHA/budget')
    require(d['dispatch_epoch']<=time.time()<d['deadline_epoch'],'dispatch expired')
    require(os.environ.get('CODEX_THREAD_ID') in [None,EXECUTOR['thread_id']],'wrong chat')
    review(P/('engineering_gate.json' if stage=='gpu-preflight' else 'science_gate.json'),mh,ph)
    cpu=read(P/'cpu_preflight/result.json');require(cpu and cpu['status']=='CPU_IMPORT_READY' and cpu['final_entry_modules_verified'],'actual CPU preflight missing')
    for n,v in cpu['code_hashes'].items():require(sha(P/n)==v,'code differs from actual CPU probe: '+n)
    if stage=='gpu-preflight':require(d.get('phase_GPU_seconds')==90,'preflight cap must be90')
    else:
        pre=read(P/'gpu_preflight_result.json');require(pre and pre['state']=='ENGINEERING_READY_ROOTS_AND_READBACK_AND_STRICT_LOAD','actual preflight not passed')
        roots_gate();alloc=review(P/'allocation_gate.json',mh,ph)
        require(alloc['preflight_result_sha256']==sha(P/'gpu_preflight_result.json') and alloc['roots_manifest_sha256']==sha(P/'roots/manifest.json'),'post-preflight budget/root binding changed')
        require(alloc['preflight_used_GPU_seconds']+sum(alloc['allocations'].values())<=900,'allocation expansion')
        require(d['phase_GPU_seconds']==alloc['allocations'][stage] and d['phase_GPU_seconds']>20,'phase allocation not frozen')
        clock=read(P/'science_clock.json')
        if clock:require(d['deadline_epoch']==clock['deadline_epoch']==clock['started_epoch']+28800,'science clock extension')
        else:require(d['deadline_epoch']==d['dispatch_epoch']+28800,'first science clock must be8h')
        if stage=='policy-b':
            e=read(P/'expert_result.json');v=review(P/'expert_gate.json',mh,ph)
            require(e and e['state']=='ALL_FOUR_MATCHED_EXPERT_CONTROLS_PASS' and len(e['rollouts'])==4 and all(x['success'] and x['control_checks_pass'] for x in e['rollouts']),'expert controls failed/incomplete')
            require(v['expert_result_sha256']==sha(P/'expert_result.json') and v['roots_manifest_sha256']==sha(P/'roots/manifest.json'),'expert gate originals changed')
    return d

def worker_gate(stage):
    gate(stage);s=read(P/'scope_state.json');v=s['active_lease']
    require(v and v['stage']==stage and v['token']==os.environ.get('KYC_STAGE_TOKEN') and v['supervisor_pid']==os.getppid(),'not an authorized child')
    import ctypes,signal
    require(ctypes.CDLL(None).prctl(1,signal.SIGTERM,0,0,0)==0 and os.getppid()==v['supervisor_pid'],'parent-death guard')
    seconds=min(v['quota']-(time.monotonic()-v['started_monotonic'])-5,v['wall_deadline_epoch']-time.time()-10);require(seconds>0,'lease expired')
    signal.signal(signal.SIGALRM,signal.SIG_DFL);signal.setitimer(signal.ITIMER_REAL,seconds);gate(stage,full=True)
