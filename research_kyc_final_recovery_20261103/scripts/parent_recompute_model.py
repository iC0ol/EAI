"""Independent float64 analysis from saved predictions; never imports worker metrics."""
from pathlib import Path
import collections, datetime, hashlib, json, os
os.sched_setaffinity(0,set(sorted(os.sched_getaffinity(0))[:3]))
import numpy as np

P=Path(__file__).resolve().parents[1];D=P.parent/'research_kyc_diagnostics_20261029'
R=P.parent/'research_expansion_20261029/reproduction'
read=lambda p:json.loads(Path(p).read_text())
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
state=read(P/'recovery_state.json');model=read(P/'model_result.json')
assert state['active_lease'] is None and state['stages']['s1-model']['exit_code']==0
assert model['state']=='COMPLETE' and state['counts']['s1_ACT']==16
plan=read(P/'call_plan.json')['calls'];samples=read(P/'sample_plan.json')['samples']
assert [x['id'] for x in model['calls']]==[x['id'] for x in plan]
manifest=read(P/'candidate_manifest.json');gate=read(P/'input_gate.json')
assert all(sha(P/f)==h for f,h in manifest['files'].items())
assert all(sha(Path(f))==h for f,h in manifest['sources'].items())
assert all(sha(P/f)==h for f,h in gate['input_files'].items())
stats=read(R/'manifests/dataset_stats.json');std=np.array(stats['action_std'],dtype=np.float64);mean=np.array(stats['action_mean'],dtype=np.float64)
const=read(D/'execution/constants.json');pred={};repeat={};records=[]
for expected,rec in zip(plan,model['calls']):
    assert all(rec[k]==v for k,v in expected.items())
    assert sha(P/rec['output_npz'])==rec['output_sha256']
    with np.load(P/rec['output_npz'],allow_pickle=False) as z:
        norm=z['normalized_chunk'].astype(np.float64);raw=z['raw_chunk'].astype(np.float64)
        assert norm.shape==raw.shape==(30,7) and np.isfinite(raw).all()
        assert np.array_equal(raw,norm*std+mean)
    prefix={'official_prior':'official','custom_prior':'custom','official_posterior':'dataset'}[rec['branch']]
    with np.load(P/f"inputs/sample_{rec['sample']:02d}.npz",allow_pickle=False) as z:
        inputs={k:z[prefix+'_'+k].copy() for k in ['image','qpos','cam_extrinsics']}
        if rec['branch']=='official_posterior':inputs.update(actions=z['actions_full'][None],is_pad=z['is_pad_full'][None])
        assert set(rec['policy_input_keys'])==set(inputs)
        for k,v in inputs.items():assert hashlib.sha256(v.tobytes()).hexdigest()==rec['input_hashes'][k]
    (repeat if rec['repeat'] else pred)[(rec['sample'],rec['branch'])]=norm
    records.append({'id':rec['id'],'raw_file_sha256':rec['output_sha256'],'original_input_hashes_match':True})
names=['official_prior','custom_prior','official_posterior','mean','median'];rows=[];scores={n:[] for n in names};dirs={n:[] for n in names}
for sample in samples:
    j=sample['sample']
    with np.load(P/f'inputs/sample_{j:02d}.npz',allow_pickle=False) as z:
        truth=z['expert_raw_chunk'].astype(np.float64);mask=z['valid_mask'].astype(bool)
    row={'sample':j,'demo':sample['demo_id'],'metrics':{}}
    for name in names:
        raw=(pred[j,name]*std+mean) if name not in ['mean','median'] else np.array(const['per_position_'+name+'_raw'],np.float64)
        err=(raw-truth)[mask];ne=err/std
        pn=np.linalg.norm(raw[:,:3],axis=1);tn=np.linalg.norm(truth[:,:3],axis=1);eligible=mask&(tn>1e-6);both=eligible&(pn>1e-6)
        cs=np.zeros(30);cs[both]=(raw[both,:3]*truth[both,:3]).sum(1)/(pn[both]*tn[both]);cs=np.clip(cs,-1,1)
        ps,ts=np.sign(raw[:,6]),np.sign(truth[:,6]);adj=mask[1:]&mask[:-1]
        m={'xyz_normalized_MAE':float(np.abs(ne[:,:3]).mean()),'all7_normalized_MAE':float(np.abs(ne).mean()),
           'all7_normalized_RMSE':float(np.sqrt(np.square(ne).mean())),
           'normalized_MAE_by_dim':np.abs(ne).mean(0).tolist(),'raw_MAE_by_dim':np.abs(err).mean(0).tolist(),
           'cosine_mean':float(cs[eligible].mean()) if eligible.any() else None,
           'gripper_sign_accuracy':float((ps[mask]==ts[mask]).mean()),
           'gripper_transition_hamming':float(((ps[1:]!=ps[:-1])!=(ts[1:]!=ts[:-1]))[adj].mean()) if adj.any() else None,
           'expert_transition_count':int((ts[1:]!=ts[:-1])[adj].sum()),'valid_steps':int(mask.sum())}
        row['metrics'][name]=m;scores[name].append(m)
    rows.append(row)
def average(rows,key):
    values=[r[key] for r in rows if r[key] is not None]
    return float(np.mean(values)) if values else None
agg={name:{key:average(scores[name],key) for key in ['xyz_normalized_MAE','all7_normalized_MAE','all7_normalized_RMSE','cosine_mean','gripper_sign_accuracy','gripper_transition_hamming']} for name in names}
agree=[]
for j in [0,1,4,5]:
    difference=float(np.max(abs(pred[j,'official_prior']-pred[j,'custom_prior'])))
    noise=[float(np.max(abs(repeat[j,b]-pred[j,b]))) for b in ['official_prior','custom_prior']] if j in [0,1] else None
    tolerance=max(1e-5,2*max(noise)) if noise is not None else 1e-5
    agree.append(dict(sample=j,difference=difference,own_repeat_noise=noise,tolerance=tolerance,passed=difference<=tolerance and (noise is None or max(noise)<=1e-3)))
good=[r for r in rows if all(r['metrics']['official_prior']['xyz_normalized_MAE']<r['metrics'][b]['xyz_normalized_MAE'] for b in ['mean','median'])]
o,med=agg['official_prior'],agg['median']
checks={'all_entry_comparisons_pass':all(x['passed'] for x in agree),
 'xyz_20percent_better_than_both':all(o['xyz_normalized_MAE']<=.8*agg[b]['xyz_normalized_MAE'] for b in ['mean','median']),
 'all7_not_worse_than_both':all(o['all7_normalized_MAE']<=agg[b]['all7_normalized_MAE'] for b in ['mean','median']),
 'three_states_both_demos':len(good)>=3 and len({r['demo'] for r in good})==2,
 'direction_no_degradation':o['cosine_mean'] is not None and med['cosine_mean'] is not None and o['cosine_mean']>=med['cosine_mean']-1e-8,
 'gripper_sign_no_degradation':o['gripper_sign_accuracy']>=med['gripper_sign_accuracy']-1e-8,
 'gripper_transitions_no_degradation':o['gripper_transition_hamming'] is not None and med['gripper_transition_hamming'] is not None and o['gripper_transition_hamming']<=med['gripper_transition_hamming']+1e-8,
 'no_near_zero_floor':all(agg[b][k]>1e-8 for b in ['mean','median'] for k in ['xyz_normalized_MAE','all7_normalized_MAE'])}
events=[json.loads(x) for x in (P/'model_events.jsonl').read_text().splitlines()];counter=dict(collections.Counter(x['event'] for x in events))
assert counter.get('POLICY_ENTER')==counter.get('INTERNAL_FORWARD_ENTER')==counter.get('POLICY_COMPLETE')==16
out={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'author':'Codex parent independent computation; executor analysis.json not read',
 'model_result_sha256':sha(P/'model_result.json'),'sources_and_input_files_reverified':True,'records':records,'per_state':rows,
 'equal_state_aggregate':agg,'entry_agreement':agree,'investment_checks':checks,'numeric_screen_passed':all(checks.values()),
 'total_GPU_seconds':state['GPU_seconds'],'counts':state['counts'],'model_event_counts':counter,
 'independent_demos':2,'training_states':4,'inference_scope':'descriptive only; no task success/generalization/visual-causality claim'}
(P/'artifacts/parent_model_recomputation.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:out[k] for k in ['equal_state_aggregate','entry_agreement','investment_checks','numeric_screen_passed','counts','total_GPU_seconds']},ensure_ascii=False,indent=2))
