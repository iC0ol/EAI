import sys,json,csv,hashlib,math,resource
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path('u_consistency_pilot/scripts').resolve()))
from download_v3 import BASE,sha,atomic,utc
from run_overnight_v3 import validate_marker,STAGES
rid='20261027T172105Z_sourcefix';run=BASE/'outputs'/('v3_'+rid);work=BASE/'.work'/rid
read=lambda p:json.loads(p.read_text())
lines=lambda p:[json.loads(x) for x in p.read_text().splitlines() if x.strip()]
H=lambda x:hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
admission=read(run/'implementation_admission.json');summary=read(run/'summary.json');delta=read(run/'semantics.json')['delta_J'];roots={r['root']:r for r in read(run/'roots_frozen.json')}
for stage in STAGES:validate_marker(run/f'stage_{stage}.json',BASE,admission['code_hash'],admission['config_hash'])
seal=read(run/'test_seal.json')
assert all(sha(BASE/k)==v for k,v in seal['inputs'].items())
checks={};all_frozen_times=[];all_real_times=[]
for split,n in [('dev',16),('test',64)]:
    fr=lines(run/f'frozen_predictions_{split}.jsonl');real=lines(run/f'real_transitions_{split}.jsonl');diag=lines(run/f'per_candidate_diagnostics_{split}.jsonl');metrics=list(csv.DictReader((run/f'per_root_metrics_{split}.csv').open()))
    assert len(fr)==len(real)==len(diag)==8*n;assert len(metrics)==9*n
    fm={(r['root'],r['candidate']):r for r in fr};rm={(r['root'],r['candidate']):r for r in real};dm={(r['root'],r['candidate']):r for r in diag};mm={(r['root'],r['method']):r for r in metrics};flips=0;same=0;gains=[]
    assert len(fm)==len(rm)==len(dm)==8*n
    assert max(r['frozen_at'] for r in fr)<min(r['executed_at'] for r in real)
    if split=='test':assert seal['at']<min(r['frozen_at'] for r in fr)
    for root in sorted({r['root'] for r in fr}):
        rows=[fm[(root,j)] for j in range(8)];f=rows[0];selection=f['selected_index'];methods=list(f['total_costs']);goal=np.array([r['goal_cost'] for r in rows]);J=np.array([rm[(root,j)]['J'] for j in range(8)])
        payload={'root':root,'seed':f['seed'],'at':f['frozen_at'],'A':[r['action_normalized'] for r in rows],'raw_A':[r['action_block'] for r in rows],'goal':goal.tolist(),'inverse':{m:[r['inverse_costs'][m] for r in rows] for m in f['inverse_costs']},'total':{m:[r['total_costs'][m] for r in rows] for m in methods},'selected':selection,'code_hash':f['code_hash'],'config_hash':f['config_hash']}
        assert H(payload)==f['frozen_hash']
        for j,row in enumerate(rows):
            rr=rm[(root,j)];d=dm[(root,j)];assert rr['frozen_hash']==row['frozen_hash']
            assert sha(work/f'real_{split}/{root}_{j}.npy')==rr['real_image_sha256']
            assert (row['candidate_source']=='official_CEM_initial')==(j<4)
            assert np.allclose(np.array(d['e_pred']),np.array(d['e_real'])-np.array(d['d_G']),rtol=1e-6,atol=1e-6)
            assert np.allclose(row['e_pred'],d['e_pred'],rtol=0,atol=1e-12)
            state=np.array(rr['state']);g=np.array(roots[root]['goal_state']);pos=np.linalg.norm(g[:4]-state[:4]);angle=abs(g[4]-state[4])%(2*np.pi);angle=min(angle,2*np.pi-angle);expected=max(pos/20,angle/(np.pi/9))
            assert abs(expected-rr['J'])<1e-12;assert rr['success']==bool(expected<1)
        for method in methods:
            k=int(np.argmin([r['total_costs'][method] for r in rows]));assert k==selection[method]
            m=mm[(root,method)];R=(J[k]-J.min())/max(float(J.max()-J.min()),.05)
            assert int(m['selected_index'])==k and abs(float(m['R'])-R)<1e-12 and 0<=R<=1
            assert abs(float(m['J'])-J[k])<1e-12
        k=selection['B1'];flips+=any(J[k]-J[j]>=delta and goal[j]<=goal[k] and rows[j]['total_costs']['B1']>rows[k]['total_costs']['B1'] for j in range(8))
        same+=selection['B2']==selection['B1'];gains.append(float(mm[(root,'B0')]['R'])-float(mm[(root,'B2')]['R']))
    checks[split]={'roots':n,'candidate_records':len(fr),'frozen_before_all_execution':True,'root_score_hashes_verified':n,'metric_and_selection_rows_verified':8*n,'images_verified':8*n,'harmful_B1_flip_roots':flips,'B2_same_index_as_B1_roots':same,'nonzero_B2_vs_B0_regret_roots':sum(x!=0 for x in gains)}
    if split=='test':
        for m,v in summary['methods'].items():
            for field,source in [('R','R'),('J','J'),('block_only','block_only'),('success','success')]:
                values=[(row[source]=='True') if field=='success' else float(row[source]) for row in metrics if row['method']==m]
                assert abs(float(np.mean(values))-v[field])<1e-12
        source_diffs={mm[(root,'B2')]['source']:float(mm[(root,'B0')]['R'])-float(mm[(root,'B2')]['R']) for root in sorted({r['root'] for r in fr})}; ordered=np.array([source_diffs[k] for k in sorted(source_diffs)]);rng=np.random.default_rng(270901);samples=ordered[rng.choice(n,size=(5000,n),replace=True)].mean(1);ci=np.quantile(samples,[.025,.975]);reported=summary['primary_comparison']['R_improvement'];assert abs(np.mean(gains)-reported['point_baseline_minus_U'])<1e-12 and np.allclose(ci,reported['CI95'],rtol=0,atol=1e-12)
# Audit existing calibrator predictions only. No fitting/retraining or test tuning.
cal=np.load(work/'cal_arrays.npz');pca=dict(np.load(work/'pca.npz'));coef=dict(np.load(work/'calibrators.npz'))
h=((cal['H']-pca['mean'])@pca['components'].T).reshape(32,48);prefix=np.concatenate([h,cal['past'].reshape(32,20)],axis=1);X=np.concatenate([np.broadcast_to(prefix[:,None],(32,8,68)),cal['A']],axis=2).reshape(256,78);xx=(X-coef['feature_mean'])/coef['feature_scale'];yv=cal['e_real'][24:].reshape(64,10);yp=xx[192:]@coef['ridge_coef'].T+coef['ridge_intercept'];mse=float(np.mean((yp-yv)**2));reported=read(run/'calibration_fit.json')['ridge_selection']['ridge']['cal_val_residual_MSE'];assert abs(mse-reported)<1e-9
cal_frozen=lines(run/'calibration_frozen_predictions.jsonl');assert len(cal_frozen)==32
for item in cal_frozen:assert H({k:v for k,v in item.items() if k!='hash'})==item['hash']
fitstd=coef['feature_scale'];standardized_val=np.max(np.abs(xx[192:]),axis=0);largest=np.argsort(standardized_val)[-8:][::-1]
result={'at':utc(),'status':'PASS','scope':'Post-run read-only validation; no new physical rollout, model update, selection or test re-use','completed_stage_markers_and_hashes':len(STAGES),'all_test_seal_inputs_verified':True,'checks':checks,'bootstrap5000_recomputed_from_raw_root_results':True,'test_effect_sign_or_size_used_to_change_any_setting':False,'ridge_stored_prediction_MSE_recomputed':mse,'ridge_feature_standardization_review':{'max_abs_cal_val_standardized_feature':float(np.max(standardized_val)),'largest_feature_columns':[{'index':int(i),'fit_scale':float(fitstd[i]),'max_abs_cal_val_standardized':float(standardized_val[i])} for i in largest],'note':'Historical latent PCA=columns0:48, past actions48:68, current candidate68:78. Analysis only; no feature scale floor or parameter modification after test.'},'source_isolation_validation_sha256':sha(run/'source_isolation_validation.json'),'postrun_process_peak_RSS_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'no_algorithm_mechanism_gain_attributed_to_B2':'B2 and B1 choose identical indices for all16dev and64test roots; B2-vs-B0 gain is shared with the uncalibrated inverse term.'}
atomic(run/'delivery_validation.json',result);print(json.dumps(result))
