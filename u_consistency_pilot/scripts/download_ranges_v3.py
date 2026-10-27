#!/usr/bin/env python3
"""Official HF byte-range download, disjoint resumable chunks, shared byte budget."""
import concurrent.futures, json, os, time, urllib.request
from pathlib import Path
from download_v3 import BASE, account, atomic, sha, utc

URL='https://huggingface.co/datasets/quentinll/lewm-pusht/resolve/655cd446b9929369d7d406001da85c15d1457850/pusht_expert_train.h5.zst'
SIZE=13136247974
DIGEST='7cfbd6d90fa2f27876379a5ff169715a36ed82edbda64f9e5b5bfa34d212f318'

def main():
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--run-id',required=True);p.add_argument('--workers',type=int,default=6);a=p.parse_args()
    run=BASE/'outputs'/('v3_'+a.run_id);data=BASE/'data/v3';final=data/'pusht_expert_train.h5.zst'
    if final.exists():
        if final.stat().st_size!=SIZE or sha(final)!=DIGEST: raise RuntimeError('FINAL_HASH_INVALID')
        return
    parts=data/'download_parts';parts.mkdir(exist_ok=True)
    old=data/'pusht_expert_train.h5.zst.partial'
    prefix=parts/'prefix'
    if old.exists() and not prefix.exists(): os.replace(old,prefix)
    n=prefix.stat().st_size if prefix.exists() else 0
    chunk=128*1024*1024
    ranges=[(s,min(s+chunk,SIZE)-1) for s in range(n,SIZE,chunk)]
    def get(pair):
        start,end=pair;f=parts/f'{start:012d}_{end:012d}.part'
        while True:
            done=f.stat().st_size if f.exists() else 0
            if done==end-start+1:return
            if done>end-start+1:raise RuntimeError('BAD_RANGE_PART_SIZE')
            # Small subrequests finish before observed long-connection truncation.
            # Storage chunks remain128MiB so all existing partial bytes are reusable.
            request_end=min(start+done+8*1024*1024-1,end);err=None
            for attempt in range(4):
                offset=f.stat().st_size if f.exists() else 0
                if start+offset>request_end:break
                if attempt:time.sleep([30,120,300][attempt-1])
                try:
                    request=urllib.request.Request(URL,headers={'Range':f'bytes={start+offset}-{request_end}','User-Agent':'EAI-U-v3-public-research/1.0'})
                    with urllib.request.urlopen(request,timeout=90) as response:
                        expected=f'bytes {start+offset}-{request_end}/{SIZE}'
                        if response.status!=206 or response.headers.get('Content-Range')!=expected:raise RuntimeError('RANGE_NOT_HONORED')
                        with f.open('ab') as out:
                            while True:
                                b=response.read(1024*1024)
                                if not b:break
                                account(run,len(b),'dataset');out.write(b)
                                if os.statvfs(BASE).f_bavail*os.statvfs(BASE).f_frsize<40000000000:raise RuntimeError('DISK_FREE_FLOOR')
                    if start+f.stat().st_size!=request_end+1:raise RuntimeError('RANGE_SIZE_INCOMPLETE')
                    break
                except Exception as e:
                    err=str(e)
                    with (run/'download_events.jsonl').open('a') as log:log.write(json.dumps({'at':utc(),'asset':'dataset_range','range':[start+offset,request_end],'storage_chunk':[start,end],'attempt':attempt,'error':type(e).__name__+': '+err})+'\n')
                    if any(x in err for x in ['BUDGET','DISK_FREE','HTTP Error 401','HTTP Error 403','RANGE_NOT_HONORED']):raise
            else:raise RuntimeError('NETWORK_BLOCK_RANGE '+str(pair)+' '+str(err))
    began=time.monotonic();initial_bytes=sum(f.stat().st_size for f in parts.glob('*') if f.is_file())
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as pool:
        futures=[pool.submit(get,r) for r in ranges]
        while not all(f.done() for f in futures):
            for f in futures:
                if f.done() and f.exception():
                    atomic(run/'download_failure.json',{'at':utc(),'error':str(f.exception()),'partial_chunks_retained':True})
                    # Do not let ThreadPoolExecutor wait for queued requests after
                    # a fatal range failure. All writes are resumable own partials.
                    os._exit(2)
            received=sum(f.stat().st_size for f in parts.glob('*') if f.is_file())
            atomic(run/'progress_dataset.json',{'at':utc(),'bytes':received,'expected_bytes':SIZE,'workers':a.workers,'resumed_bytes':initial_bytes,'elapsed_seconds':time.monotonic()-began,'payload_bytes_per_second':max(received-initial_bytes,0)/max(time.monotonic()-began,1),'complete':False})
            time.sleep(10)
        for f in futures:f.result()
    assembled=data/'pusht_expert_train.h5.zst.assembling'
    with assembled.open('wb') as out:
        for f in ([prefix] if prefix.exists() else [])+[parts/f'{s:012d}_{e:012d}.part' for s,e in ranges]:
            with f.open('rb') as inp:
                for b in iter(lambda:inp.read(8*1024*1024),b''):out.write(b)
    if assembled.stat().st_size!=SIZE or sha(assembled)!=DIGEST:raise RuntimeError('DATASET_SHA256_MISMATCH')
    os.replace(assembled,final)
    atomic(run/'progress_dataset.json',{'at':utc(),'bytes':SIZE,'expected_bytes':SIZE,'sha256':DIGEST,'complete':True,'elapsed_seconds':time.monotonic()-began})
    for f in parts.iterdir():f.unlink()
    parts.rmdir()
if __name__=='__main__':main()
