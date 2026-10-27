#!/usr/bin/env python3
"""Detached stage supervisor, checkpoint admission, deadlines and failure finalizer."""
import argparse, fcntl, hashlib, json, os, signal, subprocess, sys, time
from pathlib import Path
from datetime import datetime, timezone
from download_v3 import BASE, atomic, sha, utc

STAGES=['assets','decompress','semantics','prepare','train','cal_collect','cal_fit',
        'score_dev','execute_dev','analyze_dev','seal_test','score_test','execute_test','analyze_test']
EXIT=False
def stop(*_):
    global EXIT;EXIT=True
def records(path):
    if not path.exists():return []
    result=[]
    for line in path.read_text().splitlines():
        try:result.append(json.loads(line))
        except ValueError:pass
    return result
def append(path,value):
    with path.open('a') as f:f.write(json.dumps(value,allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())
def validate_marker(marker,base,code_hash,config_hash):
    m=json.loads(Path(marker).read_text())
    if m.get('code_hash')!=code_hash or m.get('config_hash')!=config_hash:raise RuntimeError('RESUME_HASH_MISMATCH')
    if m.get('complete') is not True:raise RuntimeError('RESUME_INCOMPLETE_MARKER')
    if not all((base/path).exists() and sha(base/path)==digest for path,digest in m['outputs'].items()):raise RuntimeError('RESUME_OUTPUT_INVALID')
    return m
def self_test(run_id):
    # Actual detached worker death + checkpoint resume, isolated from scientific stages.
    folder=BASE/'.work'/run_id/'supervisor_TEST_ONLY';folder.mkdir(parents=True,exist_ok=True)
    checkpoint=folder/'checkpoint.json'
    if checkpoint.exists():checkpoint.unlink()
    worker=folder/'worker.py'
    worker.write_text("import json,time,sys\nfrom pathlib import Path\np=Path(sys.argv[1])\nn=json.loads(p.read_text())['n'] if p.exists() else 0\nfor i in range(n+1,7):\n q=p.with_suffix('.tmp');q.write_text(json.dumps({'n':i}));q.replace(p);time.sleep(.1)\n")
    child=subprocess.Popen([sys.executable,str(worker),str(checkpoint)],start_new_session=True)
    while not checkpoint.exists() or json.loads(checkpoint.read_text())['n']<2:time.sleep(.02)
    os.killpg(child.pid,signal.SIGKILL);first=child.wait();saved=json.loads(checkpoint.read_text())['n']
    second=subprocess.run([sys.executable,str(worker),str(checkpoint)],check=True).returncode
    if first!=-signal.SIGKILL or saved>=6 or json.loads(checkpoint.read_text())['n']!=6:raise RuntimeError('SUPERVISOR_RESUME_TEST_FAILED')
    marker=folder/'complete.json';atomic(marker,{'complete':True,'code_hash':'TEST_ONLY','config_hash':'TEST_ONLY','outputs':{str(checkpoint.relative_to(BASE)):sha(checkpoint)}})
    validate_marker(marker,BASE,'TEST_ONLY','TEST_ONLY')
    checkpoint.write_text('{"n":7}')
    try:validate_marker(marker,BASE,'TEST_ONLY','TEST_ONLY')
    except RuntimeError:rejected=True
    else:raise RuntimeError('RESUME_CORRUPTION_NOT_REJECTED')
    atomic(BASE/'outputs'/('v3_'+run_id)/'engineering_only_supervisor_resume.json',{'scope':'TEST_ONLY','status':'PASS','first_worker_exit':first,'saved_progress_before_kill':saved,'resume_exit':second,'reached_final_checkpoint':6,'tampered_output_rejected':rejected,'worker_output_separate_from_science':True})
    print('TEST_ONLY supervisor checkpoint/resume/hash validation PASS')
def admit(run_id):
    run=BASE/'outputs'/('v3_'+run_id)
    for name in ['engineering_only_integrity.json','engineering_only_training_resume.json','engineering_only_supervisor_resume.json','engineering_only_statistics_guard.json']:
        if json.loads((run/name).read_text()).get('status')!='PASS':raise RuntimeError('ENGINEERING_CHECK_NOT_PASSED_'+name)
    smoke=json.loads((run/'engineering_only_smoke.json').read_text())
    if smoke['strict_missing_keys'] or smoke['strict_unexpected_keys'] or len(smoke['actual'])!=8:raise RuntimeError('SMOKE_NOT_VALID')
    code=['scripts/'+x for x in ['download_v3.py','u_core_v3.py','u_train_v3.py','u_stage_v3.py']]
    code+=['scripts/with_env_v3.sh']
    code+=[str(x.relative_to(BASE)) for x in sorted((BASE/'external/stable-worldmodel-21446f1ede6d5284e981bd7b47f432b994e6d812').rglob('*.py'))]
    inputs={'models/v3/weights.pt':'48938400ae3464c9680731287f583a9cb516f55a8ec64ea13a91be47fb15b607','models/v3/config.json':sha(BASE/'models/v3/config.json'),'configs/requirements_v3_min.txt':sha(BASE/'configs/requirements_v3_min.txt')}
    if not all(sha(BASE/k)==v for k,v in inputs.items()):raise RuntimeError('STATIC_INPUT_ADMISSION_FAILED')
    digest=hashlib.sha256(''.join(x+':'+sha(BASE/x)+'\n' for x in code).encode()).hexdigest()
    ready={'at':utc(),'scope':'code/environment readiness only; scientific 0A still must execute','code_files':code,'code_hash':digest,'config_hash':sha(BASE/'configs/protocol_v3.json'),'static_inputs':inputs}
    atomic(run/'.control/implementation_ready.json',ready);atomic(run/'implementation_admission.json',ready)
    atomic(run/'protocol_snapshot.json',json.loads((BASE/'configs/protocol_v3.json').read_text()))
    print(json.dumps({'admission':'CODE_ENV_READY','code_hash':digest,'run_id':run_id}))
def main():
    p=argparse.ArgumentParser();p.add_argument('--run-id',required=True);p.add_argument('--self-test',action='store_true');p.add_argument('--admit',action='store_true');a=p.parse_args()
    if a.self_test:return self_test(a.run_id)
    if a.admit:return admit(a.run_id)
    run=BASE/'outputs'/('v3_'+a.run_id);ctl=run/'.control';ctl.mkdir(parents=True,exist_ok=True)
    lock=(run/'.lock').open('a')
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:raise SystemExit('RUN_ALREADY_LOCKED')
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    cfg=json.loads((BASE/'configs/protocol_v3.json').read_text())
    cutoff=datetime.fromisoformat(cfg['report_cutoff_utc']).timestamp()
    deadline=datetime.fromisoformat(cfg['hard_deadline_utc']).timestamp()
    commands=run/'commands.jsonl';state={'run_id':a.run_id,'supervisor_pid':os.getpid(),'started_at_utc':cfg['task_started_at_utc'],'hard_deadline_utc':cfg['hard_deadline_utc'],'report_cutoff_utc':cfg['report_cutoff_utc'],'status':'PREPARATION','stage':None,'completed_stages':[],'heartbeat_at_utc':utc()}
    child=None;failure=None
    def heartbeat():
        state['heartbeat_at_utc']=utc();state['remaining_to_report_cutoff_seconds']=max(0,cutoff-time.time())
        if (run/'progress.json').exists():
            try:state['recent_progress']=json.loads((run/'progress.json').read_text())
            except ValueError:pass
        if (run/'progress_dataset.json').exists():
            try:state['download_progress']=json.loads((run/'progress_dataset.json').read_text())
            except ValueError:pass
        if (run/'resource_watch.json').exists():
            try:
                r=json.loads((run/'resource_watch.json').read_text());state['resources']={k:r.get(k) for k in ['task_rss_sum_bytes','task_vram_bytes','foreign_vram_bytes','disk_free_bytes','gpu_process_card_seconds_upper_bound']}
            except ValueError:pass
        atomic(run/'status.json',state)
    try:
        heartbeat()
        # The supervisor is live while code/environment work proceeds. No invented stage completion.
        while not (ctl/'implementation_ready.json').exists():
            if EXIT or time.time()>=cutoff:raise RuntimeError('PARTIAL-DEADLINE_IMPLEMENTATION_NOT_READY')
            if (ctl/'resource_stop.json').exists():raise RuntimeError('RESOURCE-BLOCK')
            heartbeat();time.sleep(10)
        ready=json.loads((ctl/'implementation_ready.json').read_text())
        script=BASE/'scripts/u_stage_v3.py'
        science_files=[BASE/x for x in ready['code_files']]
        code_hash=hashlib.sha256(''.join(str(x.relative_to(BASE))+':'+sha(x)+'\n' for x in science_files).encode()).hexdigest()
        if code_hash!=ready['code_hash']:raise RuntimeError('CODE_HASH_MISMATCH_AT_ADMISSION')
        config_hash=sha(BASE/'configs/protocol_v3.json')
        if config_hash!=ready['config_hash']:raise RuntimeError('CONFIG_HASH_MISMATCH_AT_ADMISSION')
        if not all(sha(BASE/k)==v for k,v in ready['static_inputs'].items()):raise RuntimeError('STATIC_INPUT_HASH_MISMATCH')
        state['code_hash']=code_hash;state['config_hash']=config_hash
        env=os.environ.copy();env.update({'OMP_NUM_THREADS':'4','MKL_NUM_THREADS':'4','OPENBLAS_NUM_THREADS':'4','NUMEXPR_NUM_THREADS':'4','PYTHONDONTWRITEBYTECODE':'1','SDL_VIDEODRIVER':'dummy','SDL_AUDIODRIVER':'dummy','PYGAME_HIDE_SUPPORT_PROMPT':'1','HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','HF_HOME':str(BASE/'.cache/v3/hf'),'TORCH_HOME':str(BASE/'.cache/v3/torch'),'XDG_CACHE_HOME':str(BASE/'.cache/v3'),'TMPDIR':str(BASE/'.cache/v3/tmp'),'PIP_CACHE_DIR':str(BASE/'.cache/v3/pip'),'TOKENIZERS_PARALLELISM':'false','U_RUN_ID':a.run_id,'U_CODE_HASH':code_hash,'U_CONFIG_HASH':config_hash,'U_CUTOFF_EPOCH':str(cutoff)})
        env.pop('PYTHONPATH',None);env['PYTHONNOUSERSITE']='1'
        for stage in STAGES:
            if hashlib.sha256(''.join(str(x.relative_to(BASE))+':'+sha(x)+'\n' for x in science_files).encode()).hexdigest()!=code_hash:raise RuntimeError('SCIENTIFIC_CODE_CHANGED_AFTER_ADMISSION')
            state.update({'stage':stage,'status':'RUNNING'});heartbeat()
            marker=run/f'stage_{stage}.json'
            if marker.exists():
                m=validate_marker(marker,BASE,code_hash,config_hash)
                state['completed_stages'].append(stage);continue
            # Conservative measured ETA from stage progress / completed steps, never effect-based stopping.
            eta_path=run/'eta.json';eta=json.loads(eta_path.read_text()) if eta_path.exists() else {}
            estimate=eta.get(stage,60)
            if time.time()+estimate>cutoff:raise RuntimeError('PARTIAL-DEADLINE_NEXT_STAGE_'+stage)
            if EXIT:raise RuntimeError('INTERRUPTED')
            if (ctl/'resource_stop.json').exists():raise RuntimeError('RESOURCE-BLOCK')
            for attempt in range(2):
                env['U_STAGE']=stage
                argv=[str(BASE/'.venv-v3/bin/python'),'-u','-B',str(script),'--run-id',a.run_id,'--stage',stage]
                logdir=run/'logs';logdir.mkdir(exist_ok=True);log=logdir/f'{stage}_{attempt}.log'
                with log.open('ab') as handle:
                    child=subprocess.Popen(argv,cwd=BASE.parent,env=env,stdout=handle,stderr=subprocess.STDOUT,start_new_session=True)
                    command={'stage':stage,'attempt':attempt,'argv':[x.replace(str(BASE.parent),'$EAI') for x in argv],'cwd_alias':'EAI','pid':child.pid,'pgid':os.getpgid(child.pid),'started_at_utc':utc(),'code_hash':code_hash,'config_hash':config_hash}
                    append(commands,{**command,'event':'START'});state['child_pid']=child.pid;heartbeat()
                    last=0
                    progress_stamp=(run/'progress.json').stat().st_mtime if (run/'progress.json').exists() else 0;last_progress=time.time()
                    while child.poll() is None:
                        if time.time()-last>=60:heartbeat();last=time.time()
                        stamp=(run/'progress.json').stat().st_mtime if (run/'progress.json').exists() else 0
                        if stamp!=progress_stamp:progress_stamp=stamp;last_progress=time.time()
                        hung=stage!='assets' and time.time()-last_progress>900
                        if EXIT or time.time()>=cutoff or (ctl/'resource_stop.json').exists() or hung:
                            os.killpg(child.pid,signal.SIGTERM)
                            try:child.wait(timeout=45)
                            except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
                            failure='STAGE_PROGRESS_TIMEOUT' if hung else 'RESOURCE-BLOCK' if (ctl/'resource_stop.json').exists() else 'PARTIAL-DEADLINE'
                            break
                        time.sleep(2)
                    code=child.wait();append(commands,{**command,'event':'END','ended_at_utc':utc(),'exit_code':code})
                child=None;state.pop('child_pid',None)
                if failure:
                    if failure=='STAGE_PROGRESS_TIMEOUT' and attempt==0 and time.time()+estimate<cutoff:
                        append(run/'repairs.jsonl',{'at':utc(),'stage':stage,'repair':'One bounded fresh-process retry after900s without progress; resume only validated checkpoint/root outputs','attempt':attempt});failure=None;continue
                    raise RuntimeError(failure)
                if code==0 and marker.exists():break
                text=log.read_text(errors='replace')[-12000:]
                if 'out of memory' in text.lower() and attempt==0:
                    env['U_MICROBATCH']='32';append(run/'repairs.jsonl',{'at':utc(),'stage':stage,'repair':'reduce microbatch to 32; maintain effective batch with accumulation','attempt':attempt});continue
                # Agent can repair only before scientific admission, or start a separate semantic run.
                raise RuntimeError('STAGE_FAILED_'+stage+'_EXIT_'+str(code)+' '+text[-1800:])
            if not marker.exists():raise RuntimeError('MISSING_VALIDATED_COMPLETION_'+stage)
            m=json.loads(marker.read_text())
            if not m.get('complete') or not all((BASE/k).exists() and sha(BASE/k)==v for k,v in m['outputs'].items()):raise RuntimeError('INVALID_STAGE_OUTPUT_'+stage)
            state['completed_stages'].append(stage);heartbeat()
        state['status']='SCIENTIFIC_STAGES_COMPLETE'
    except BaseException as e:
        failure=type(e).__name__+': '+str(e)
        state.update({'status':'STOPPED','failure':failure})
    finally:
        if child and child.poll() is None:
            try:os.killpg(child.pid,signal.SIGTERM);child.wait(timeout=30)
            except Exception:pass
        heartbeat()
        finalizer=BASE/'scripts/finalize_v3.py'
        if finalizer.exists():
            cmd=[sys.executable,'-u','-B',str(finalizer),'--run-id',a.run_id,'--reason',failure or 'COMPLETE','--publish']
            with (run/'log_finalize.txt').open('ab') as f:
                try:result=subprocess.run(cmd,cwd=BASE.parent,stdout=f,stderr=subprocess.STDOUT,timeout=max(30,min(2400,deadline-time.time())))
                except Exception as e:state['finalizer_error']=str(e)
                else:state['finalizer_exit_code']=result.returncode
        if state.get('finalizer_exit_code')==0:
            atomic(ctl/'supervisor_ended.json',{'at':utc(),'finalizer_exit_code':0})
        else:
            state['status']='FINALIZATION_FAILED';state['ended_at_utc']=utc();heartbeat()
if __name__=='__main__':main()
