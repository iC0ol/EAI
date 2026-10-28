"""Small stdlib-only checks of existing records and formulas; no model code imports."""
from pathlib import Path
import csv, datetime, hashlib, json, math, statistics
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT.parent/'u_consistency_pilot/outputs/v3_20261027T172105Z_sourcefix'
out = {'scope': 'existing JSON/CSV and hand-constructed arithmetic only; no inference, training, simulator, or new data',
       'checked_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'inputs': {}, 'u': {}}
def read_rows(path):
    out['inputs'][str(path.relative_to(ROOT.parent))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]
manifest = {r['root']: r for r in csv.DictReader((OLD/'root_manifest.csv').open())}
for split in ('dev', 'test'):
    groups, real = defaultdict(list), defaultdict(list)
    for row in read_rows(OLD/f'frozen_predictions_{split}.jsonl'):
        groups[row['root']].append(row)
    for row in read_rows(OLD/f'real_transitions_{split}.jsonl'):
        real[row['root']].append(row)
    detail=[]
    for root, rows in sorted(groups.items()):
        assert len(rows)==8 and len({x['candidate'] for x in rows})==8
        goal=sorted(x['goal_cost'] for x in rows)
        gap=goal[1]-goal[0]; bound=.07*math.sqrt(2*len(rows))*statistics.pstdev(goal)
        selected=rows[0]['selected_index']
        for x in rows: assert x['selected_index']==selected
        block=[x['block_only'] for x in real[root]]
        detail.append({'root':root,'stratum':manifest[root]['stratum'], 'goal_gap':gap,
                       'max_inverse_pair_effect':bound,'locked':gap>bound,
                       'B1_B2_same':selected['B1']==selected['B2'],
                       'block_only_range':max(block)-min(block)})
    out['u'][split]={'roots':len(detail),'locked_roots':sum(r['locked'] for r in detail),
       'contact_roots':sum(r['stratum']=='contact' for r in detail),
       'contact_locked':sum(r['stratum']=='contact' and r['locked'] for r in detail),
       'B1_B2_same':sum(r['B1_B2_same'] for r in detail),
       'noncontact_equal_block_cost':sum(r['stratum']=='noncontact' and abs(r['block_only_range'])<1e-12 for r in detail),
       'detail':detail}
s=json.loads((OLD/'summary.json').read_text())['cal_val_residual_diagnostic']
out['u']['B3_MSE_ratio_from_saved_summary']=s['ridge_selection']['ridge']['cal_val_residual_MSE']/s['uncalibrated_cal_val_residual_MSE']
out['normalization_bound']={'n':8,'lambda':.07,'coefficient':.07*math.sqrt(16),
    'tight_example':[-2,2,0,0,0,0,0,0], 'population_std':1.0,'range':4,
    'proof':'For centered x: |x_i-x_j| <= ||x||_2 ||e_i-e_j||_2 = sqrt(2n)*population_std. Multiply by lambda*sigma_goal/sigma_cost. If disabled the effect is zero. Strict gap greater than bound locks argmin; equal gap can tie.'}
out['median_geometry']={'candidates':[[1,0,0],[0,1,0],[0,0,1]],'coordinate_median':[0,0,0],
    'inside_coordinate_box':True,'outside_convex_hull':True,
    'reason':'All candidate convex combinations have coordinate sum one; median sum is zero.',
    'scope':'Mathematical counterexample only. Does not establish robot failure frequency or medoid benefit.'}
out['batch_max_illustration']={'assumed_independent_binary_phase_probability':.1,'batch_size':128,
    'probability_at_least_one_phase_positive':1-.9**128,
    'scope':'Hypothetical binary IID phases; GAP published network produces continuous correlated probabilities, so this is not a measurement of its gate.'}
out['precision_planning']={'formula':'Approximate paired binary difference SE=sqrt((q-delta^2)/n), q=P(discordant pair); ignores training uncertainty.',
    'examples_for_95pct_halfwidth_0_10_at_delta0':{str(q):math.ceil(1.96**2*q/.1**2) for q in (.1,.2,1)},
    'scope':'Planning illustration, not a frozen sample size or achieved confidence interval. Paired trajectories are one unit, not timesteps; multiple training seeds required for optimization variability.'}
(ROOT/'artifacts/readonly_arithmetic_audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:{p:v for p,v in val.items() if p!='detail'} if isinstance(val,dict) else val for k,val in out['u'].items()},ensure_ascii=False,indent=2))
