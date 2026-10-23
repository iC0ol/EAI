"""No environment creation, inference or simulation. Freeze assets and the160-row plan."""
import sys
import h5py
import numpy as np
import torch
import mujoco
import robomimic
import robosuite
import scipy

from live_screen.io import ROOT,M_ROOT,D_ROOT,OUT,REPORT,BASE,config,sha256,array_hash,read_json,read_csv,write_json,write_csv,git,now
from m_direction.assets import data_path,checkpoint_path
from m_direction.perturb import intervention

def main():
    c=config()
    historical={}
    for p in git("ls-tree","-r","--name-only",BASE,"m_direction_pilot").splitlines():
        q=M_ROOT.parent/p;historical[p]=sha256(q)
    for manifest in [M_ROOT/"outputs/gate0/sha256_manifest.json",M_ROOT/"outputs/replay_recovery/sha256_manifest.json"]:
        for p,h in read_json(manifest)["sha256"].items():assert sha256(M_ROOT/p)==h,p
    states=read_csv(M_ROOT/"outputs/gate0/frozen_state_manifest.csv")
    assert len(states)==12
    write_csv(OUT/"frozen_state_manifest.csv",states)
    rows=[];technical=[]
    with h5py.File(data_path(),"r") as f:
        for s in states:
            ep=f[f"data/{s['source_episode']}"];a=ep['actions'][int(s['t'])]
            np.testing.assert_array_equal(a,json_action:=__import__('json').loads(s['expert_action']))
            for d in c['directions']:
                for sign in [-1,1]:
                    try:
                        action,delta=intervention(a,d,sign,c['radius']);status='eligible';reason=''
                    except ValueError as exc:action=None;delta=None;status='technical_rejection';reason=str(exc)
                    technical.append({'state_id':s['state_id'],'source_episode':s['source_episode'],'direction':d,'sign':sign,
                        'status':status,'reason':reason,'logged_action7':a.tolist(),'requested_action7':action.tolist() if action is not None else None})
    def add(stage,sid,d,sign,r,repeat=''):
        rows.append({'branch_id':f"L{stage}_{sid}_{d}_{sign:+d}{repeat}",'stage':stage,'state_id':sid,
                     'direction':d,'sign':sign,'radius':r,'checkpoint_seed':42,'stream':0})
    for sid in c['A_states']:
        for i in range(2):add('A',sid,'nominal',0,0.,f'_repeat{i}')
    for sid in c['development_states']:
        add('B1',sid,'nominal',0,0.)
        for d in ['x','y','z']:
            for sign in [-1,1]:add('B1',sid,d,sign,.2)
    for sid in c['development_states']:
        for d in ['xy','xz','yz']:
            for sign in [-1,1]:add('B2',sid,d,sign,.2)
    for sid in c['heldout_states']:
        add('B3',sid,'nominal',0,0.)
        for d in c['directions']:
            for sign in [-1,1]:add('B3',sid,d,sign,.2)
    assert len(rows)==160
    write_csv(OUT/'branch_plan.csv',rows);write_csv(OUT/'action_eligibility.csv',technical)
    legacy=read_json(M_ROOT/'configs/gate0.json')
    assets=[data_path(),checkpoint_path(42),D_ROOT/'configs/gate1.json',D_ROOT/'data/manifests/normalization.json',D_ROOT/'requirements.lock']
    assert sha256(data_path())==legacy['data_sha256']
    assert sha256(checkpoint_path(42))==legacy['checkpoint_sha256']['42']
    dependencies=read_json(M_ROOT/'outputs/replay_recovery/R0_audit.json')['source_files']
    for p,h in dependencies.items():assert sha256(M_ROOT.parent/p)==h,p
    write_json(OUT/'resource_audit.json',{'utc':now(),'base':BASE,'historical_files':historical,
        'old_branch_heads':{b:git('rev-parse',b) for b in ['main','research/d-gate1','research/d-gate1-q2','research/m-gate0','research/m-gate0-replay-recovery']},
        'assets':{str(p.relative_to(M_ROOT.parent)):sha256(p) for p in assets},'upstream_files':dependencies,
        'versions':{'python':sys.version,'torch':torch.__version__,'mujoco':mujoco.__version__,'robomimic':robomimic.__version__,'robosuite':robosuite.__version__,'scipy':scipy.__version__},
        'python_prefix':sys.prefix,'cuda_available':torch.cuda.is_available(),'GPU':torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        'new_steps':0,'inference_calls':0,'action_rejections':sum(t['status']!='eligible' for t in technical),
        'model_unchanged':'16D native inputs, horizon16, obs2, action8, DDIM16, OA[1:9], fixed Clean42',
        'old_P0_P1_P2_evidence':'online replay physically repeatable but source state not recovered; R-Fail accepted'})
    print(f"Audited {len(historical)} old files; frozen12 states/160 branches;144 action checks; zero new steps/inference")

if __name__=='__main__':main()
