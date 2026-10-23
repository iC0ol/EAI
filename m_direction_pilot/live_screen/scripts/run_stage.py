"""Run one frozen stage once, enforcing gate order and the shared12-hour clock."""
import argparse
import json
import time
import torch

from live_screen.io import ROOT,OUT,config,read_json,write_json,read_csv,sha256,git,now
from live_screen.audit import verify,deadline
from live_screen.runtime import execute
from live_screen.repeats import compare
from live_screen.analysis import results,gate
from live_screen.baselines import fit_all
from m_direction.policy import setup_torch,make_policy


def main(stage):
    verify();summary_path=OUT/f'stage_{stage}.json'
    assert not summary_path.exists(),'No stage rerun'
    if stage=='A':
        assert not (OUT/'attempt_ledger.jsonl').exists()
        clock_start=time.time();write_json(OUT/'execution_clock.json',{'utc_start':now(),'start_unix':clock_start,
          'deadline_unix':min(clock_start+43200,config()['absolute_outer_deadline_unix']),'definition':'entire new execution, including model loading/prefixes; stricter absolute12h ceiling'})
    else:
        preceding={'B1':'A','B2':'B1','B3':'B2'}[stage]
        assert read_json(OUT/f'stage_{preceding}.json')['continue'], 'Previous stage gate closed'
        if stage=='B3':
            frozen=read_json(OUT/'baselines_frozen.json')
            assert sha256(OUT/'fixed_baselines.json')==frozen['sha256']
            assert git('show','HEAD:m_direction_pilot/live_screen/outputs/fixed_baselines.json')==(OUT/'fixed_baselines.json').read_text().strip(),'Commit dev fits before held-out execution'
    deadline()
    plan=[b for b in read_csv(OUT/'branch_plan.csv') if b['stage']==stage]
    cards={s['state_id']:s for s in read_csv(OUT/'frozen_state_manifest.csv')}
    start,cpu=time.monotonic(),time.process_time();out={'stage':stage,'status':'running','continue':False,'completed':0,'attempted':0,'comparisons':[]}
    setup_torch();policy=make_policy(42);torch.cuda.reset_peak_memory_stats()
    previous=None
    try:
        for b in plan:
            r=execute(b,cards[b['state_id']],policy);out['attempted']+=1
            if r['status']!='completed':out.update({'status':'Technical Invalid','stop_branch':r['branch_id'],'error':r.get('error')});break
            out['completed']+=1
            if stage=='A':
                if previous is None:previous=r
                else:
                    cmp=compare(previous,r);out['comparisons'].append({'state_id':r['state_id'],**cmp});previous=None
                    print(json.dumps(out['comparisons'][-1]),flush=True)
                    if not cmp['passed']:out.update({'status':'Technical Invalid','error':'L-A online zero-repeat inconsistency'});break
        if out['status']=='running':
            if stage=='A':out.update({'status':'Technical qualification passed for proxy states only','continue':True})
            elif stage in ['B1','B2']:
                g=gate(stage,results());out.update({'status':g['decision'],'continue':g['continue'],'directional_summary':g['summary']})
                if stage=='B2' and out['continue']:
                    fits=fit_all(results());write_json(OUT/'fixed_baselines.json',fits)
                    write_json(OUT/'baselines_frozen.json',{'sha256':sha256(OUT/'fixed_baselines.json'),'utc':now(),'data_stages':['B1','B2'],'no_heldout_outcomes_seen':True})
                    needed=['world_full_PSD3x3','object_full_PSD3x3','task_full_PSD3x3']
                    if not all(fits[k]['available'] for k in needed):out.update({'status':'Stop: required fixed baseline fit unavailable','continue':False})
            else:
                g=gate('B3',results());out.update({'status':'Held-out screen completed' if g['continue'] else g['decision'],'continue':False,'directional_summary':g['summary']})
    except Exception as exc:
        import traceback
        out.update({'status':'Technical Invalid','error':str(exc),'traceback':traceback.format_exc(),'continue':False})
    finally:
        out['wall_seconds']=time.monotonic()-start;out['process_cpu_seconds']=time.process_time()-cpu;out['utc_finish']=now()
        write_json(summary_path,out);print(json.dumps({k:v for k,v in out.items() if k not in ['directional_summary','comparisons']}),flush=True)
    return 0 if stage=='A' and out['continue'] or out['completed']==len(plan) else 2

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['A','B1','B2','B3']);args=parser.parse_args();raise SystemExit(main(args.stage))
