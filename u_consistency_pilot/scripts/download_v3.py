#!/usr/bin/env python3
"""Bounded public downloads, resumable partials and byte accounting (stdlib)."""
import argparse, fcntl, hashlib, json, os, time, urllib.request
from pathlib import Path
from datetime import datetime, timezone

BASE = Path(__file__).resolve().parents[1]

def utc(): return datetime.now(timezone.utc).isoformat()
def atomic(path, data):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(data, indent=2, allow_nan=False) + '\n'); os.replace(temp, path)
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024), b''): h.update(b)
    return h.hexdigest()
def account(run, count, asset):
    ledger=run/'download_bytes.json'; lock=run/'.download.lock'
    with lock.open('a') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        d=json.loads(ledger.read_text()) if ledger.exists() else {'payload_bytes_received':0,'limit_bytes':35000000000,'by_asset':{}}
        if d['payload_bytes_received']+count>d['limit_bytes']: raise RuntimeError('DOWNLOAD_BUDGET_EXCEEDED')
        d['payload_bytes_received']+=count; d['by_asset'][asset]=d['by_asset'].get(asset,0)+count
        atomic(ledger,d)
def fetch(url, path, run, asset, expected=None, digest=None, cap=None):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        if (expected is None or path.stat().st_size==expected) and (digest is None or sha(path)==digest): return
        raise RuntimeError('EXISTING_FINAL_ASSET_INVALID:'+asset)
    partial=path.with_name(path.name+'.partial'); error=None
    for attempt in range(4):
        if attempt: time.sleep([30,120,300][attempt-1])
        offset=partial.stat().st_size if partial.exists() else 0
        headers={'User-Agent':'EAI-U-v3-public-research/1.0'}
        if offset: headers['Range']=f'bytes={offset}-'
        with (run/'download_events.jsonl').open('a') as log:
            log.write(json.dumps({'at':utc(),'asset':asset,'attempt':attempt,'resume_offset':offset,'event':'REQUEST'})+'\n')
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=90) as response:
                if offset and response.status!=206:
                    # Server ignored Range: never silently append a full object.
                    offset=0; mode='wb'
                else: mode='ab' if offset else 'wb'
                length=response.headers.get('Content-Length')
                if cap and length and offset+int(length)>cap: raise RuntimeError('ASSET_SIZE_CAP')
                with partial.open(mode) as f:
                    last=time.monotonic()
                    while True:
                        b=response.read(4*1024*1024)
                        if not b: break
                        account(run,len(b),asset); f.write(b); offset+=len(b)
                        if cap and offset>cap: raise RuntimeError('ASSET_SIZE_CAP')
                        if time.monotonic()-last>=10:
                            atomic(run/f'progress_{asset}.json',{'at':utc(),'bytes':offset,'expected_bytes':expected,'attempt':attempt}); last=time.monotonic()
                        if os.statvfs(BASE).f_bavail*os.statvfs(BASE).f_frsize<40000000000: raise RuntimeError('DISK_FREE_FLOOR')
            if expected is not None and partial.stat().st_size!=expected: raise RuntimeError('SIZE_MISMATCH')
            actual=sha(partial)
            if digest and actual!=digest: raise RuntimeError('SHA256_MISMATCH')
            os.replace(partial,path)
            atomic(run/f'progress_{asset}.json',{'at':utc(),'bytes':path.stat().st_size,'sha256':actual,'complete':True,'attempt':attempt})
            return
        except Exception as e:
            error=type(e).__name__+': '+str(e)
            with (run/'download_events.jsonl').open('a') as log: log.write(json.dumps({'at':utc(),'asset':asset,'attempt':attempt,'event':'ERROR','error':error})+'\n')
            if any(x in error for x in ['BUDGET','SIZE_CAP','DISK_FREE','SHA256_MISMATCH','HTTP Error 401','HTTP Error 403','HTTP Error 404']): break
    raise RuntimeError('NETWORK_OR_ASSET_BLOCK '+asset+' '+str(error))

def main():
    p=argparse.ArgumentParser();p.add_argument('--run-id',required=True);p.add_argument('--kind',choices=['sources','model','data','papers'],required=True);a=p.parse_args()
    run=BASE/'outputs'/('v3_'+a.run_id);run.mkdir(exist_ok=True)
    if a.kind=='sources':
        rev='8edfeb336732b5f3ce7b8b210d0ba370a09e2cac'
        fetch(f'https://codeload.github.com/lucas-maes/le-wm/tar.gz/{rev}',BASE/'.cache/v3'/f'lewm_{rev}.tar.gz',run,'lewm',cap=50000000)
        rev='21446f1ede6d5284e981bd7b47f432b994e6d812'
        paths=['pyproject.toml','stable_worldmodel/utils.py','stable_worldmodel/spaces.py','stable_worldmodel/envs/utils.py','stable_worldmodel/envs/pusht/env.py','stable_worldmodel/envs/pusht/expert_policy.py','stable_worldmodel/wm/lewm/lewm.py','stable_worldmodel/wm/lewm/module.py','stable_worldmodel/planning/solver/cem.py','stable_worldmodel/data/dataset.py','stable_worldmodel/data/formats/hdf5.py','stable_worldmodel/data/formats/lance.py','docs/envs/pusht.md']
        for path in paths:
            fetch(f'https://raw.githubusercontent.com/galilai-group/stable-worldmodel/{rev}/{path}',BASE/f'external/stable-worldmodel-{rev}'/path,run,'swm_'+path.replace('/','_').replace('.','_'),cap=1000000)
    elif a.kind=='model':
        rev='22b330c28c27ead4bfd1888615af1340e3fe9052'
        for name,size,h in [('config.json',None,None),('weights.pt',72290721,'48938400ae3464c9680731287f583a9cb516f55a8ec64ea13a91be47fb15b607')]:
            fetch(f'https://huggingface.co/quentinll/lewm-pusht/resolve/{rev}/{name}',BASE/'models/v3'/name,run,'model_'+name.replace('.','_'),size,h,80000000)
    elif a.kind=='data':
        fetch('https://huggingface.co/datasets/quentinll/lewm-pusht/resolve/655cd446b9929369d7d406001da85c15d1457850/pusht_expert_train.h5.zst',BASE/'data/v3/pusht_expert_train.h5.zst',run,'dataset',13136247974,'7cfbd6d90fa2f27876379a5ff169715a36ed82edbda64f9e5b5bfa34d212f318',13136247974)
    else:
        for name,ref in [('ACID','2607.02403'),('ATM','2606.09028v2'),('WAV','2604.01985v2')]:
            fetch('https://arxiv.org/pdf/'+ref,BASE/'.cache/v3'/f'{name}.pdf',run,'paper_'+name,cap=40000000)
if __name__=='__main__': main()
