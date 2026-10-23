"""Read-only post-experiment audit/export. Never calls env.step or policy inference."""
import csv
import gzip
import io
import json
import time
from pathlib import Path

import numpy as np

from live_screen.io import ROOT,M_ROOT,OUT,REPORT,BASE,read_json,read_csv,write_json,write_csv,sha256,array_hash,git,now,config
from live_screen.audit import verify,Ledger
from live_screen.analysis import results,signed_summary
from live_screen.baselines import MODELS,evaluate


def save_report(name,body):
    p=REPORT/name
    with p.open('x') as f:f.write(body)


def public_trace(r):
    """Lossless numeric CSV: raw trace arrays stay local; public rows retain all values."""
    path=OUT/'raw_trajectories'/f"{r['branch_id']}.csv.gz";path.parent.mkdir(exist_ok=True)
    with np.load(ROOT/r['trace_path']) as x,path.open('xb') as raw:
        arrays={k:{'shape':list(x[k].shape),'dtype':str(x[k].dtype)} for k in x.files}
        with gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0) as gz,io.TextIOWrapper(gz,newline='') as stream:
            w=csv.writer(stream,lineterminator='\n');w.writerow(['phase','control_step','array','values_json'])
            for key in x.files:
                array=x[key]
                for i,row in enumerate(array):
                    # Prefix and suffix state arrays contain their initial sample;
                    # action/flag arrays describe the transition to the next sample.
                    phase='prefix' if key.startswith('prefix_') else ('inference' if key in ['initial_noise','replan_histories'] else 'suffix')
                    index=i if phase=='prefix' else (int(r['t'])+i if phase=='suffix' else i)
                    w.writerow([phase,index,key,json.dumps(row.tolist(),separators=(',',':'),allow_nan=False)])
    return {'branch_id':r['branch_id'],'public_path':str(path.relative_to(ROOT)),'public_sha256':sha256(path),
            'local_npz':r['trace_path'],'local_npz_sha256':r['trace_sha256'],'public_bytes':path.stat().st_size,'arrays':arrays}


def audit(records,stages):
    registration=verify();events=Ledger().events()
    starts=[e for e in events if e['event']=='started'];ends=[e for e in events if e['event']=='finished']
    assert len(starts)==len(ends)==len(records)<=160
    assert len({r['branch_id'] for r in records})==len(records)
    assert {e['branch_id'] for e in starts}=={r['branch_id'] for r in records}=={e['branch_id'] for e in ends}
    for r in records:
        assert sha256(ROOT/r['trace_path'])==r['trace_sha256']
        end=next(e for e in ends if e['branch_id']==r['branch_id'])
        assert sha256(OUT/'branches'/f"{r['branch_id']}.json")==end['result_sha256']
        for p,h in r['code_sha256'].items():assert sha256(ROOT/p)==h
        if r['status']!='completed':continue
        assert r['prefix_control_steps']==r['t'] and r['suffix_control_steps']==400-r['t']
        assert r['prefix_integration_steps']==25*r['t'] and r['suffix_integration_steps']==25*(400-r['t'])
        assert r['partial_integration_steps']==0
        with np.load(ROOT/r['trace_path']) as x:
            assert x['prefix_states'].shape[0]==r['t']+1 and x['suffix_sim_states'].shape[0]==401-r['t']
            assert x['suffix_received_actions'].shape==(400-r['t'],7)
            assert len(x['initial_noise'])==len(r['replans'])==r['inference_calls']
            for i,p in enumerate(r['replans']):
                assert array_hash(x['initial_noise'][i])==p['initial_noise_sha256']
                assert array_hash(x['replan_histories'][i])==p['history_sha256']
            assert bool(x['suffix_success'].any())==r['ever_success'] and bool(x['suffix_success'][-1])==r['final_success']
            assert np.isfinite(x['suffix_sim_states']).all() and np.isfinite(x['suffix_observations']).all()
        if r['stage']!='A' and r['direction']!='nominal':
            n=next(a for a in records if a['branch_id']==r['nominal_branch_id'])
            assert r['fork_snapshot']==n['fork_snapshot']
            assert r['geometry']==n['geometry']
            keys=['replan_index','seed','generator_before_sha256','initial_noise_sha256','generator_after_sha256','absolute_step_before']
            assert [{k:p[k] for k in keys} for p in r['replans']]==[{k:p[k] for k in keys} for p in n['replans']]
            np.testing.assert_allclose(r['actual_delta7'],r['delta7'],atol=1e-15,rtol=0)
            assert not r['intervention_receipt']['command_clipped']
    names=list(stages);order=['A','B1','B2','B3']
    assert names==order[:len(names)]
    for i,s in enumerate(names[:-1]):assert stages[s]['continue']
    assert not stages[names[-1]]['continue'],'Do not export while a permitted next stage remains'
    protected=[]
    for p,h in registration['historical_files'].items():
        assert sha256(M_ROOT.parent/p)==h;protected.append(p)
    refs=read_json(OUT/'resource_audit.json')['old_branch_heads']
    for ref,h in refs.items():assert git('rev-parse',ref)==h
    changed=git('diff','--name-only',BASE).splitlines()
    assert all(p.startswith('m_direction_pilot/live_screen/') for p in changed)
    clock=read_json(OUT/'execution_clock.json')
    finish=max(Path(OUT/f'stage_{s}.json').stat().st_mtime for s in stages)
    assert finish<=clock['deadline_unix']
    return {'utc':now(),'passed':True,'protected_historical_files':len(protected),'original_branch_refs_unchanged':refs,
            'attempts':len(starts),'completed':sum(r['status']=='completed' for r in records),'unused_allocations':160-len(starts),
            'prefix_control_steps':sum(r['prefix_control_steps'] for r in records),'suffix_control_steps':sum(r['suffix_control_steps'] for r in records),
            'prefix_integration_steps':sum(r['prefix_integration_steps'] for r in records),'suffix_integration_steps':sum(r['suffix_integration_steps'] for r in records),
            'partial_integration_steps':sum(r['partial_integration_steps'] for r in records),'inference_calls':sum(r['inference_calls'] for r in records),
            'sum_branch_wall_seconds':sum(r['wall_seconds'] for r in records),'sum_branch_process_cpu_seconds':sum(r['process_cpu_seconds'] for r in records),
            'sum_inference_wall_seconds':sum(r['inference_wall_seconds'] for r in records),
            'sum_inference_gpu_seconds':sum(r['inference_gpu_ms'] for r in records)/1000,
            'sum_simulation_wall_seconds':sum(r['sim_wall_seconds'] for r in records),
            'peak_cuda_allocated_bytes':max(r['peak_cuda_allocated_bytes'] for r in records),
            'peak_cuda_reserved_bytes':max(r['peak_cuda_reserved_bytes'] for r in records),
            'execution_elapsed_seconds':finish-clock['start_unix'],'execution_deadline_unix':clock['deadline_unix'],
            'forbidden_activity':{'training_steps':0,'seed43_suffixes':0,'Gate1_suffixes':0,'source_state_restore_variants':0,
                                  'extra_states':0,'extra_radii':0,'new_data_collection':0},
            'final_stage':names[-1],'decision':stages[names[-1]]['status']}


def main():
    records=results();stages={s:read_json(OUT/f'stage_{s}.json') for s in ['A','B1','B2','B3'] if (OUT/f'stage_{s}.json').exists()}
    check=audit(records,stages);write_json(OUT/'final_audit.json',check)
    summary=signed_summary(records);write_json(OUT/'signed_summary.json',summary)
    plan=read_csv(OUT/'branch_plan.csv');index={r['branch_id']:r for r in records}
    all_rows=[]
    for b in plan:
        r=index.get(b['branch_id']);all_rows.append({**b,'status':r['status'] if r else 'not_run_gate_closed',
            'Y':int(r['ever_success']) if r and r['status']=='completed' else '',
            'Y_final':int(r['final_success']) if r and r['status']=='completed' else '',
            'prefix_steps':r['prefix_control_steps'] if r else 0,'suffix_steps':r['suffix_control_steps'] if r else 0,
            'reason':r.get('error','') if r else check['decision']})
    write_csv(OUT/'all160_allocations_actual.csv',all_rows)
    if summary['signed_rows']:write_csv(OUT/'signed_outcomes.csv',summary['signed_rows'])
    if summary['asymmetries']:write_csv(OUT/'sign_asymmetries.csv',summary['asymmetries'])
    if summary['improvements']:write_csv(OUT/'improvements.csv',summary['improvements'])
    state_rows=[];source_rows=[]
    cards=read_csv(OUT/'frozen_state_manifest.csv')
    for s in cards:
        rr=[r for r in records if r['state_id']==s['state_id']];complete=[r for r in rr if r['status']=='completed']
        n=next((r for r in complete if r['stage']!='A' and r['direction']=='nominal'),complete[0] if complete else None)
        ss=next((x for x in summary['states'] if x['state_id']==s['state_id']),{})
        row={'state_id':s['state_id'],'source_episode':s['source_episode'],'t':int(s['t']),'split':s['split'],'source_phase':s['phase'],
             'attempts':len(rr),'completed':len(complete),'nominal_Y':ss.get('nominal_Y',''),'perturbations':ss.get('perturbations',0),
             'perturbed_successes':ss.get('perturbed_successes',''),'damage':ss.get('damage',''),'improvements':ss.get('improvement',''),
             'within_state_Y_heterogeneity':ss.get('directionally_informative',''),
             'contact_frame_available':n['geometry']['contact']['available'] if n and 'geometry' in n else '',
             'contact_reason':n['geometry']['contact']['reason'] if n and 'geometry' in n else 'not measured'}
        state_rows.append(row)
        if n and 'geometry' in n:
            source_rows.append({'state_id':s['state_id'],'source_episode':s['source_episode'],'t':int(s['t']),
                 **{'native_'+k:v for k,v in n['source_deviation_at_fork'].items()},
                 **{'physical_'+k:v for k,v in n['source_physical_deviation_at_fork'].items()},
                 'native_physical_nut_gap_m':float(np.linalg.norm(np.array(n['geometry']['native_obs16'][:3])-np.array(n['geometry']['proxy_physical_obs16'][:3]))),
                 'native_physical_eef_gap_m':float(np.linalg.norm(np.array(n['geometry']['native_obs16'][7:10])-np.array(n['geometry']['proxy_physical_obs16'][7:10])))})
    write_csv(OUT/'all12_states_actual.csv',state_rows)
    if source_rows:write_csv(OUT/'source_proxy_deviation.csv',source_rows)
    episodes=[]
    for ep in sorted({s['source_episode'] for s in cards}):
        ss=[s for s in state_rows if s['source_episode']==ep];rr=[r for r in records if r['source_episode']==ep]
        episodes.append({'source_episode':ep,'split':ss[0]['split'],'frozen_states':len(ss),'attempts':len(rr),
            'completed':sum(r['status']=='completed' for r in rr),'informative_states':sum(s['within_state_Y_heterogeneity'] is True for s in ss),
            'sign_asymmetries':sum(a['source_episode']==ep for a in summary['asymmetries']),
            'improvements':sum(a['source_episode']==ep for a in summary['improvements'])})
    write_csv(OUT/'episode_summary.csv',episodes)
    cost_keys=['branch_id','stage','state_id','source_episode','status','prefix_control_steps','suffix_control_steps','prefix_integration_steps','suffix_integration_steps',
               'wall_seconds','process_cpu_seconds','prefix_wall_seconds','prefix_cpu_seconds','sim_wall_seconds','sim_cpu_seconds','inference_calls',
               'inference_wall_seconds','inference_cpu_seconds','inference_gpu_ms','peak_cuda_allocated_bytes','peak_cuda_reserved_bytes']
    write_csv(OUT/'branch_costs.csv',[{k:r.get(k,'') for k in cost_keys} for r in records])
    trace_index=[public_trace(r) for r in records];write_csv(OUT/'trace_index.csv',trace_index)
    if (OUT/'fixed_baselines.json').exists():
        fits=read_json(OUT/'fixed_baselines.json')
        baseline={k:{'available':v['available'],'heldout':evaluate(k,v['matrix'],records,'held-out') if v['available'] and 'B3' in stages else None} for k,v in fits.items()}
    else:
        baseline={k:{'available':False,'reason':'not fitted: earlier preregistered stage gate closed; not counted as defeated'} for k in MODELS}
        baseline['scalar']={'available':True,'matrix':np.eye(3),'reason':'no parameters; all equal-norm scores tie',
                            'dev':evaluate('scalar',np.eye(3),records,'development'),'heldout':None}
    write_json(OUT/'baseline_evaluation.json',baseline)
    plot(cards,records,source_rows)
    reports(records,stages,summary,check,state_rows,source_rows,episodes,baseline)
    print(json.dumps(check,indent=2))


def plot(cards,records,source_rows):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap,BoundaryNorm
    labels=['nominal']+[d+sign for d in config()['directions'] for sign in ['−','+']]
    grid=np.full((12,13),-1.)
    for r in records:
        if r['stage']=='A' or r['status']!='completed':continue
        i=next(i for i,s in enumerate(cards) if s['state_id']==r['state_id'])
        j=0 if r['direction']=='nominal' else 1+2*config()['directions'].index(r['direction'])+int(r['sign']==1)
        grid[i,j]=int(r['ever_success'])
    fig,ax=plt.subplots(figsize=(12,6))
    ax.imshow(grid,cmap=ListedColormap(['#e3e5e8','#e69a8d','#7db9a4']),norm=BoundaryNorm([-1.5,-.5,.5,1.5],3),aspect='auto')
    ax.set_xticks(range(13),labels);ax.set_yticks(range(12),[f"{s['state_id']} {s['source_episode']} t={s['t']} ({s['split']})" for s in cards])
    for i in range(12):
        for j in range(13):ax.text(j,i,'—' if grid[i,j]<0 else str(int(grid[i,j])),ha='center',va='center',fontsize=9)
    ax.axhline(7.5,color='black',linewidth=1.3);ax.axvline(6.5,color='black',linewidth=1)
    ax.set_title('Online replay surrogate: signed suffix ever-success Y\nGrey = unmeasured; paired random stream; no expert-label claim')
    fig.tight_layout();fig.savefig(REPORT/'signed_outcomes.png',dpi=170);plt.close(fig)
    if source_rows:
        fig,ax=plt.subplots(figsize=(8,4.5));x=np.arange(len(source_rows))
        ax.bar(x-.18,[1000*r['physical_object_position_m'] for r in source_rows],.36,label='Nut: physical proxy vs logged source')
        ax.bar(x+.18,[1000*r['physical_eef_position_m'] for r in source_rows],.36,label='EEF: physical proxy vs logged source')
        ax.axhline(1,color='red',linestyle='--',label='Original 1 mm threshold (unchanged)')
        ax.set_xticks(x,[r['state_id'] for r in source_rows]);ax.set_ylabel('Fork position error (mm)');ax.set_title('Online reproducibility does not restore the source state')
        ax.legend(fontsize=8);fig.tight_layout();fig.savefig(REPORT/'source_proxy_deviation.png',dpi=170);plt.close(fig)


def reports(records,stages,summary,check,state_rows,source_rows,episodes,baseline):
    # Final narratives are written separately after inspecting all raw outputs.
    write_json(OUT/'report_facts.json',{'stages':stages,'summary':summary,'audit':check,'states':state_rows,
              'source_deviation':source_rows,'episodes':episodes,'baseline':baseline})


if __name__=='__main__':main()
