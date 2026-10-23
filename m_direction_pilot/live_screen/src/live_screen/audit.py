import fcntl
import json
import os
import time

from .io import ROOT,M_ROOT,OUT,BASE,config,read_json,read_csv,write_json,sha256,git,now,encode


def verify():
    r=read_json(OUT/'registration.json')
    for p,h in r['frozen_files'].items():assert sha256(ROOT/p)==h,p
    for p,h in r['historical_files'].items():assert sha256(M_ROOT.parent/p)==h,p
    for p,h in r['assets'].items():assert sha256(M_ROOT.parent/p)==h,p
    for p,h in r['upstream_files'].items():assert sha256(M_ROOT.parent/p)==h,p
    assert not git('diff','--name-only','HEAD','--','m_direction_pilot/live_screen/src','m_direction_pilot/live_screen/scripts','m_direction_pilot/live_screen/run.sh')
    assert read_json(OUT/'resource_audit.json')['action_rejections']==0
    return r


def deadline():
    epoch=read_json(OUT/'execution_clock.json')
    if time.time()>=epoch['deadline_unix']:raise TimeoutError('Frozen12-hour/absolute deadline reached')


class Ledger:
    def __init__(self,out=OUT):self.out=out;self.path=out/'attempt_ledger.jsonl';out.mkdir(parents=True,exist_ok=True)
    def events(self):return [json.loads(s) for s in self.path.read_text().splitlines()] if self.path.exists() else []
    def append(self,event):
        with self.path.open('a') as f:
            f.write(json.dumps({'utc':now(),**event},default=encode,allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())
    def reserve(self,b,check_deadline=True):
        if check_deadline:deadline()
        with (self.out/'.ledger.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            events=self.events();starts=[x for x in events if x['event']=='started']
            if any(x['branch_id']==b['branch_id'] for x in starts):raise RuntimeError('Refuse overwrite/retry of started suffix')
            ended={x['branch_id'] for x in events if x['event']=='finished'}
            if any(x['branch_id'] not in ended for x in starts):raise RuntimeError('Unfinished attempt; no automatic restart')
            if len(starts)>=160 or sum(x['stage']==b['stage'] for x in starts)>=config()['stage_limits'][b['stage']]:raise RuntimeError('Budget exhausted')
            self.append({'event':'started',**b})


def canonical_branch(b):
    return {**b,'sign':int(b['sign']),'radius':float(b['radius']),'checkpoint_seed':int(b['checkpoint_seed']),'stream':int(b['stream'])}
