"""One recovery, exact phase gates and cumulative accounting."""
from .common import *


def review(path,mh,ph):
    value=read(path);require(value and value.get('state')=='APPROVED','new double review missing')
    for name in ['codex','deepseek']:
        item=value.get(name,{})
        require(item.get('decision')=='APPROVE' and item.get('code_manifest_sha256')==mh
                and item.get('protocol_sha256')==ph,'review SHA mismatch')
        require(item.get('evidence_file') and sha(P/item['evidence_file'])==item['evidence_sha256'],'review evidence changed')
    return value


def gate(stage,full=False):
    require(stage in PHASES,'unknown phase')
    require(not (P/'terminal_stop.json').exists(),'recovery terminal; no retry/reset')
    manifest=read(P/'candidate_manifest.json');dispatch=read(P/('dispatch/'+stage+'.json'))
    require(manifest and dispatch,'no explicit GPU/science dispatch; CPU permission is insufficient')
    mh=sha(P/'candidate_manifest.json');ph=sha(P/'PROTOCOL.md')
    require(manifest['protocol_sha256']==ph,'protocol changed')
    for name,digest in manifest['files'].items():require(sha(P/name)==digest,'candidate changed: '+name)
    if full:
        for name,digest in manifest['sources'].items():require(sha(Path(name))==digest,'old source changed: '+name)
    require(dispatch.get('mode')=='RUN_PHASE' and dispatch.get('phase')==stage
            and dispatch.get('recovery_id')==RECOVERY_ID and dispatch.get('executor')==EXECUTOR,'wrong phase/executor')
    require(dispatch.get('code_manifest_sha256')==mh and dispatch.get('protocol_sha256')==ph
            and dispatch.get('total_GPU_seconds')==1800,'wrong SHA/budget')
    require(dispatch['dispatch_epoch']<=time.time()<dispatch['deadline_epoch'],'phase dispatch time')
    require(os.environ.get('CODEX_THREAD_ID') in [None,EXECUTOR['thread_id']],'wrong execution chat')
    review(P/('engineering_gate.json' if stage=='gpu-preflight' else 'science_gate.json'),mh,ph)
    cpu=read(P/'cpu_preflight/final/result.json')
    require(cpu and cpu['status']=='CPU_IMPORT_READY' and cpu.get('final_entry_modules_verified'),'final real CPU entry coverage missing')
    require(all(sha(P/name)==digest for name,digest in cpu['final_code_hashes'].items()),'code differs from final real CPU coverage')
    if stage!='gpu-preflight':
        eng=read(P/'gpu_preflight_result.json')
        require(eng and eng['status']=='ENGINEERING_READY_INPUT_AND_STRICT_LOAD','actual GPU engineering preflight not passed')
        clock=read(P/'science_clock.json')
        if clock:require(clock['deadline_epoch']==clock['started_epoch']+8*3600
                         and dispatch['deadline_epoch']==clock['deadline_epoch'],'science clock extension')
    if stage=='s1-model':input_gate(mh)
    if stage=='s2-closed':
        approved=review(P/'stage2_gate.json',mh,ph);analysis=read(P/'analysis.json')
        require(analysis and analysis['investment_screen']=='MINIMAL_CLOSED_LOOP_PLAN_SIGNAL_ONLY_NOT_EXECUTION_AUTHORIZATION','Stage1 did not pass')
        require(approved['analysis_sha256']==sha(P/'analysis.json') and approved['model_result_sha256']==sha(P/'model_result.json')
                and approved['root_plan_sha256']==sha(P/'root_plan.json'),'Stage2 originals changed')
    return dispatch


def current_stage():
    return ((read(P/'recovery_state.json',{}) or {}).get('active_lease') or {}).get('stage')


def input_gate(mh):
    a=read(P/'input_gate.json');r=read(P/'input_result.json');s=read(P/'recovery_state.json')
    require(a and r and s,'parent input review missing')
    require(a.get('mode')=='RUN_MODEL' and a.get('decision')=='APPROVE' and a.get('actual_images_viewed')
            and a.get('CPU_originals_checked'),'actual parent image/raw review absent')
    require(a.get('recovery_id')==RECOVERY_ID and a.get('code_manifest_sha256')==mh
            and a.get('input_result_sha256')==sha(P/'input_result.json'),'input gate SHA/recovery mismatch')
    require(a.get('evidence_file') and sha(P/a['evidence_file'])==a['evidence_sha256'],'review evidence changed')
    require(r['state']=='COMPLETE_HEALTHY_PENDING_PARENT' and r['all_health_pass'],'input health failed')
    require(not (P/'results/input/fatal.json').exists(),'late input destructor fatal')
    actual={str(f.relative_to(P)) for directory in [P/'inputs',P/'results/input'] for f in directory.rglob('*') if f.is_file()}
    require(actual==set(r['input_files']) and a['input_files']==r['input_files'],'input file set changed')
    for name,digest in r['input_files'].items():require(sha(P/name)==digest,'input changed')
    require(r['source_hashes']==a['source_hashes']==read(P/'candidate_manifest.json')['sources'],'source hash set changed')
    old=s['stages'].get('s1-input',{})
    require(old.get('exit_code')==0 and not active(old.get('identity')),'input still alive/failed')
    require(a['stage_record_sha256']==sha(P/'stages/s1-input.json'),'input budget/process record changed')


def project(kind,stage):
    if kind=='workers':return 'gpu_workers'
    if kind in ['make_env','backward','optimizer']:return kind
    if stage.startswith('s1-'):return {'ACT':'s1_ACT','renders':'s1_renders','readPixels':'s1_readPixels'}.get(kind)
    if stage=='s2-closed':return {'ACT':'s2_queries','renders':'s2_renders','readPixels':'s2_readPixels','env_steps':'s2_steps','rollouts':'s2_rollouts'}.get(kind)
    return None


def charge(state,kind,stage,label):
    key=project(kind,stage);require(key is not None,'operation forbidden in phase: '+kind)
    require(state['counts'][key]<CAPS[key],key+' cumulative cap')
    if kind=='make_env':
        limit={'gpu-preflight':1,'s1-input':1,'s1-model':0,'s2-closed':8}[stage]
        uses=state.setdefault('phase_make_env',{})
        require(uses.get(stage,0)<limit,'unexpected make_env in phase')
        uses[stage]=uses.get(stage,0)+1
    if stage=='s2-closed' and kind in ['ACT','renders','readPixels','env_steps']:
        row=state.get('active_rollout');require(row,'operation outside rollout')
        maximum={'ACT':5,'renders':5,'readPixels':10,'env_steps':150}[kind]
        require(row.get(kind,0)<maximum,'per-rollout cap '+kind);row[kind]=row.get(kind,0)+1
    state['counts'][key]+=1
    return state['counts'][key]


def reserve(kind,worker,label):
    with (P/'counter.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX);state=read(P/'recovery_state.json');lease=(state or {}).get('active_lease') or {}
        require(lease and not (P/'terminal_stop.json').exists(),'no supervised active lease')
        require(time.time()<lease['wall_deadline_epoch'],'wall deadline')
        append(P/'call_ledger.jsonl',dict(utc=utc(),event='ATTEMPT_BEFORE_OPERATION',phase=lease['stage'],kind=kind,label=label))
        ordinal=charge(state,kind,lease['stage'],label);write(P/'recovery_state.json',state);return ordinal


def begin_rollout(label):
    reserve('rollouts','closed',label)
    with (P/'counter.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX);state=read(P/'recovery_state.json')
        require(label not in state.get('rollout_labels',[]),'rollout retry')
        state.setdefault('rollout_labels',[]).append(label);state['active_rollout']={'label':label};write(P/'recovery_state.json',state)


def worker_gate(stage):
    stage={'input':'s1-input','model':'s1-model'}.get(stage,stage)
    dispatch=gate(stage);state=read(P/'recovery_state.json');lease=state['active_lease']
    require(lease and lease['stage']==stage and lease['token']==os.environ.get('KYC_STAGE_TOKEN')
            and lease['supervisor_pid']==os.getppid(),'not an authorized child')
    import ctypes,signal
    require(ctypes.CDLL(None).prctl(1,signal.SIGTERM,0,0,0)==0,'parent-death protection failed')
    require(os.getppid()==lease['supervisor_pid'],'supervisor exited')
    seconds=lease['quota']-(time.monotonic()-lease['started_monotonic'])-5;require(seconds>0,'lease expired')
    signal.signal(signal.SIGALRM,signal.SIG_DFL);signal.setitimer(signal.ITIMER_REAL,seconds)
    gate(stage,full=True);return dispatch
