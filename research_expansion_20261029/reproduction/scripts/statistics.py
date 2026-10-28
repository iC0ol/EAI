import json,csv
from common import ROOT,read_json,atomic_json,utc,sha
import numpy as np
CONDITIONS=['C-clean','C-persistent-5','C-iid-5','C-persistent-10','C-iid-10','C-moved-correct','C-moved-stale']
def rows(p):return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []
def main():
    dev=read_json(ROOT/'results/dev_summary.json',{});test=rows(ROOT/'results/test_rollouts.jsonl');by={(r['root_id'],r['condition']):r for r in test};roots=list(range(5000,5050))
    with (ROOT/'results/per_root_success.csv').open('w') as f:
        w=csv.writer(f);w.writerow(['root_id']+CONDITIONS)
        for i in roots:w.writerow([i]+[int(by[(i,c)]['success']) if (i,c) in by else 'NOT_RUN' for c in CONDITIONS])
    conditions={}
    for c in CONDITIONS:
        a=[r for r in test if r['condition']==c];conditions[c]={'state':'COMPLETE' if len(a)==50 else ('PARTIAL' if a else 'NOT_RUN'),'successes':sum(r['success'] for r in a) if a else None,'n':len(a) if a else None,'success_rate':sum(r['success'] for r in a)/len(a) if a else None}
    comparisons={};rng=np.random.default_rng(20261029)
    pairs=[('primary_persistent10_minus_iid10','C-persistent-10','C-iid-10'),('persistent5_minus_iid5','C-persistent-5','C-iid-5'),('persistent10_minus_clean','C-persistent-10','C-clean'),('iid10_minus_clean','C-iid-10','C-clean'),('moved_stale_minus_moved_correct','C-moved-stale','C-moved-correct'),('moved_correct_minus_clean','C-moved-correct','C-clean')]
    for name,a,b in pairs:
        ids=[i for i in roots if (i,a) in by and (i,b) in by]
        if not ids:comparisons[name]={'state':'NOT_RUN','n':None,'difference':None,'bootstrap_95':None,'discordance':None};continue
        A=np.array([by[(i,a)]['success'] for i in ids],dtype=float);B=np.array([by[(i,b)]['success'] for i in ids],dtype=float);d=A-B;indices=rng.integers(0,len(ids),size=(50000,len(ids)));boot=d[indices].mean(1);ci=np.quantile(boot,[.025,.975]).tolist()
        comparisons[name]={'state':'COMPLETE' if len(ids)==50 else 'PARTIAL','n':len(ids),'difference':float(d.mean()),'bootstrap_95':ci,'bootstrap_replicates':50000,'bootstrap_seed':20261029,'discordance':{'A_only_success':int(np.sum((A==1)&(B==0))),'B_only_success':int(np.sum((A==0)&(B==1))),'both_success':int(np.sum((A==1)&(B==1))),'both_failure':int(np.sum((A==0)&(B==0)))},'degenerate_bootstrap':bool(np.all(d==d[0]))}
    fixed=rows(ROOT/'results/dev_fixed_observation.jsonl');sensitivity={}
    for k in ['persistent-5','persistent-10','zero','shuffle']:
        if not fixed:continue
        sensitivity[k]={'n':len(fixed),'max_abs_chunk_delta_median':float(np.median([x['metrics'][k]['raw_chunk_max_abs_delta'] for x in fixed])),'max_abs_chunk_delta_max':float(np.max([x['metrics'][k]['raw_chunk_max_abs_delta'] for x in fixed])),'first_translation_signed_mean_xyz_m':np.mean([x['metrics'][k]['first_translation_delta_xyz_m'] for x in fixed],axis=0).tolist(),'first_rotation_signed_mean_components_rad':np.mean([x['metrics'][k]['first_rotation_delta_axisangle_components_rad'] for x in fixed],axis=0).tolist(),'chunk_translation_signed_mean_xyz_m':np.mean([x['metrics'][k]['chunk_accumulated_translation_delta_xyz_m'] for x in fixed],axis=0).tolist(),'translation_L2_over_chunk_mean':float(np.mean([x['metrics'][k]['translation_delta_l2_over_chunk'] for x in fixed])),'rotation_L2_over_chunk_mean':float(np.mean([x['metrics'][k]['rotation_delta_l2_over_chunk'] for x in fixed]))}
    primary=comparisons['primary_persistent10_minus_iid10'];interpretation='NOT_IDENTIFIABLE_BASELINE_FLOOR' if not dev.get('test_allowed') else 'INCONCLUSIVE'
    if dev.get('test_allowed') and primary.get('bootstrap_95') and primary['n']==50:
        if primary['bootstrap_95'][1]<0:interpretation='PERSISTENT_PENALTY_OBSERVED_SINGLE_TRAINING_SEED'
        elif primary['bootstrap_95'][0]>0:interpretation='PERSISTENT_NOT_WORSE_IN_THIS_CONTROLLED_RUN'
    summary={'utc':utc(),'state':'COMPLETE' if len(test)==350 else ('PARTIAL' if test else 'NOT_RUN'),'complete':len(test)==350,'rollouts':len(test) if test else None,'independent_roots':len({r['root_id'] for r in test}) if test else None,'conditions':conditions,'comparisons':comparisons,'interpretation':interpretation,'U_state':'NOT_RUN','U_comparisons':{'C_clean_minus_U_clean':None,'C_persistent10_minus_U_clean':None},'limitations':['single training seed; checkpoint is not an independent replicate','50 independent roots per executed setting, not350 independent samples','no deployment frequency estimate for calibration error','no pose-jitter or new-method comparison','bootstrap uncertainty does not establish equivalence; degenerate samples need special caution'],'dev_fixed_action_sensitivity':sensitivity}
    atomic_json(ROOT/'results/test_summary.json',summary)
    with (ROOT/'results/paired_statistics.csv').open('w') as f:
        w=csv.writer(f);w.writerow(['contrast','state','paired_n','difference','ci_low','ci_high','A_only_success','B_only_success'])
        for k,x in comparisons.items():
            ci=x['bootstrap_95'] or ['NOT_RUN','NOT_RUN'];d=x['discordance'] or {'A_only_success':'NOT_RUN','B_only_success':'NOT_RUN'};w.writerow([k,x['state'],x['n'] if x['n'] is not None else 'NOT_RUN',x['difference'] if x['difference'] is not None else 'NOT_RUN',*ci,d['A_only_success'],d['B_only_success']])
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
