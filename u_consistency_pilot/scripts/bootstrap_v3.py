#!/usr/bin/env python3
"""Workstation bootstrap/reproduction helper. Existing environments are read-only.

--install prepares this workstation's isolated Python/torch stack and public
sources/model. --verify-existing only audits imports/files, never re-downloads
the 13GB dataset. Dataset transfer is started separately with download_ranges_v3.
"""
import argparse,json,os,shutil,subprocess,sys,tarfile
from pathlib import Path
from download_v3 import BASE,atomic,sha,utc,account

def main():
    p=argparse.ArgumentParser();p.add_argument('--run-id',required=True);g=p.add_mutually_exclusive_group(required=True);g.add_argument('--install',action='store_true');g.add_argument('--verify-existing',action='store_true');a=p.parse_args()
    run=BASE/'outputs'/('v3_'+a.run_id);run.mkdir(parents=True,exist_ok=True)
    old=BASE.parent/'spatial_intervention_pilot';runtime=BASE/'.runtime/python311';venv=BASE/'.venv-v3'
    env=os.environ.copy();env.pop('PYTHONPATH',None);env.update({'PYTHONNOUSERSITE':'1','PYTHONDONTWRITEBYTECODE':'1','TMPDIR':str(BASE/'.cache/v3/tmp'),'PIP_CACHE_DIR':str(BASE/'.cache/v3/pip'),'XDG_CACHE_HOME':str(BASE/'.cache/v3'),'PIP_DISABLE_PIP_VERSION_CHECK':'1'})
    for path in [BASE/'.cache/v3/tmp',BASE/'.cache/v3/pip',BASE/'.cache/v3/wheels',BASE/'.runtime',BASE/'external']:path.mkdir(parents=True,exist_ok=True)
    def execute(argv):
        proc=subprocess.Popen(argv,env=env,cwd=BASE.parent)
        with (run/'commands.jsonl').open('a') as f:f.write(json.dumps({'at':utc(),'stage':'bootstrap','argv':[str(x).replace(str(BASE.parent),'$EAI') for x in argv],'cwd_alias':'EAI','pid':proc.pid,'event':'START'})+'\n')
        code=proc.wait()
        with (run/'commands.jsonl').open('a') as f:f.write(json.dumps({'at':utc(),'stage':'bootstrap','pid':proc.pid,'event':'END','exit_code':code})+'\n')
        if code:raise RuntimeError('BOOTSTRAP_COMMAND_FAILED_'+str(code))
    if a.install:
        if (run/'.control/implementation_ready.json').exists():raise RuntimeError('ENVIRONMENT_FROZEN_FOR_SCIENTIFIC_RUN')
        if not runtime.exists():
            source=old/'.runtime/python/cpython-3.11.17-linux-x86_64-gnu'
            if not source.exists():raise RuntimeError('WORKSTATION_REFERENCE_RUNTIME_UNAVAILABLE_NEEDS_NEW_BOOTSTRAP_ADAPTATION')
            shutil.copytree(source,runtime,symlinks=True)
        if not venv.exists():execute([str(runtime/'bin/python3'),'-m','venv',str(venv)])
        target=venv/'lib/python3.11/site-packages';source=old/'.venv-vlm/lib/python3.11/site-packages'
        # Copy, never link package data back into the old writable environment.
        for item in source.iterdir():
            if not (item.name.startswith(('torch','nvidia','triton')) or item.name=='cusparselt'):continue
            if (target/item.name).exists():continue
            if item.is_dir():shutil.copytree(item,target/item.name,symlinks=True)
            else:shutil.copy2(item,target/item.name)
        req=BASE/'configs/requirements_v3_min.txt';wheels=BASE/'.cache/v3/wheels'
        # Conservative reservation covers payload and HTTP metadata for this bounded
        # small-stack download. Large torch binaries are reused locally above.
        account(run,600000000,'bootstrap_dependency_download_upper_allowance')
        execute([str(venv/'bin/python'),'-m','pip','download','--retries','0','--dest',str(wheels),'-r',str(req)])
        execute([str(venv/'bin/python'),'-m','pip','install','--no-index','--find-links',str(wheels),'-r',str(req)])
        for kind in ['sources','model']:
            execute([sys.executable,'-B',str(BASE/'scripts/download_v3.py'),'--run-id',a.run_id,'--kind',kind])
        archive=BASE/'.cache/v3/lewm_8edfeb336732b5f3ce7b8b210d0ba370a09e2cac.tar.gz'
        with tarfile.open(archive,'r:gz') as tar:
            target=(BASE/'external').resolve()
            if any(m.issym() or m.islnk() or target not in (target/m.name).resolve().parents for m in tar.getmembers()):raise RuntimeError('UNSAFE_SOURCE_ARCHIVE')
            tar.extractall(target)
    execute(['bash',str(BASE/'scripts/with_env_v3.sh'),'-m','pip','check'])
    if sha(BASE/'models/v3/weights.pt')!='48938400ae3464c9680731287f583a9cb516f55a8ec64ea13a91be47fb15b607':raise RuntimeError('MODEL_HASH_INVALID')
    atomic(run/'bootstrap_verification.json',{'at':utc(),'mode':'install+verify' if a.install else 'verify-existing','model_sha256':sha(BASE/'models/v3/weights.pt'),'python_interpreter_alias':'EAI/U/.venv-v3/bin/python','minimal_requirements_sha256':sha(BASE/'configs/requirements_v3_min.txt'),'old_environments_modified':False,'dataset_transfer_separate':True})
if __name__=='__main__':main()
