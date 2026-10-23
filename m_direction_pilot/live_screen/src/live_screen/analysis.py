"""Frozen descriptive signed-outcome rules. No averaging of opposite directions."""
import numpy as np
from .io import OUT,read_json,config


def results():return [read_json(p) for p in sorted((OUT/'branches').glob('*.json'))]


def signed_summary(records):
    b=[r for r in records if r['stage']!='A' and r['status']=='completed']
    nominal={r['state_id']:r for r in b if r['direction']=='nominal'}
    states=[];raw=[];asym=[];improvements=[]
    for sid,n in sorted(nominal.items()):
        perturb=[r for r in b if r['state_id']==sid and r['direction']!='nominal']
        ys=[]
        for r in perturb:
            loss=int(n['ever_success'])-int(r['ever_success']);ys.append(bool(r['ever_success']))
            row={'state_id':sid,'source_episode':n['source_episode'],'direction':r['direction'],'sign':r['sign'],
                 'Y_nominal':int(n['ever_success']),'Y_perturbed':int(r['ever_success']),'delta_Y':loss,'branch_id':r['branch_id']}
            raw.append(row)
            if loss==-1:improvements.append(row)
        for d in config()['directions']:
            pair=[r for r in perturb if r['direction']==d]
            if len(pair)==2 and pair[0]['ever_success']!=pair[1]['ever_success']:
                asym.append({'state_id':sid,'source_episode':n['source_episode'],'direction':d,
                             'minus_Y':int(next(r['ever_success'] for r in pair if r['sign']==-1)),
                             'plus_Y':int(next(r['ever_success'] for r in pair if r['sign']==1))})
        states.append({'state_id':sid,'source_episode':n['source_episode'],'split':n['split'],'nominal_Y':int(n['ever_success']),
                       'perturbations':len(perturb),'directionally_informative':len(set(ys))>1,
                       'all_perturbations_equal_nominal':all(y==n['ever_success'] for y in ys),
                       'perturbed_successes':sum(ys),'damage':sum(r['delta_Y']==1 for r in raw if r['state_id']==sid),
                       'improvement':sum(r['delta_Y']==-1 for r in raw if r['state_id']==sid)})
    def strong(rows):
        return len({r['source_episode'] for r in rows})>=2 and len({r['direction'] for r in rows})>=2
    return {'states':states,'signed_rows':raw,'asymmetries':asym,'improvements':improvements,
            'strong_asymmetry_warning':strong(asym),'strong_improvement_warning':strong(improvements),
            'strong_symmetric_PSD_warning':strong(asym) or strong(improvements),
            'directional_source_episodes':sorted({s['source_episode'] for s in states if s['directionally_informative']})}


def gate(stage,records):
    summary=signed_summary(records)
    if any(r['status']!='completed' for r in records):return {'decision':'Technical Invalid','continue':False,'summary':summary}
    if summary['strong_symmetric_PSD_warning']:
        return {'decision':'Model No-Go: symmetric, penalty-only PSD on proxy states','continue':False,'summary':summary}
    if stage=='B1' and summary['signed_rows'] and all(r['delta_Y']==0 for r in summary['signed_rows']):
        return {'decision':'Stop: insufficient terminal-label information','continue':False,'summary':summary}
    if stage=='B2' and len(summary['directional_source_episodes'])<2:
        return {'decision':'Stop: directional information from fewer than two dev sources','continue':False,'summary':summary}
    return {'decision':f'Eligible for {"B2" if stage=="B1" else "baseline audit then B3"}', 'continue':True,'summary':summary}
