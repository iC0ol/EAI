"""Independent, CPU-only pre-output reference scores for the four fixed states."""
import datetime
import hashlib
import json
from pathlib import Path
import h5py
import numpy as np

P = Path(__file__).resolve().parents[1]
W = P.parent
OLD = W / 'research_kyc_diagnostics_20261029/execution'
R = W / 'research_expansion_20261029/reproduction'
def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(8 << 20), b''): h.update(b)
    return h.hexdigest()
def digest(a): return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()

const = json.loads((OLD/'constants.json').read_text())
stats = json.loads((R/'manifests/dataset_stats.json').read_text())
mean, std = (np.asarray(stats[k], dtype=np.float64) for k in ('action_mean', 'action_std'))
plan = [x for x in json.loads((OLD/'sample_plan.json').read_text())['ordered_samples'] if x['sample'] in (0,1,4,5)]
data = R/'assets/liftrand_eef_delta.hdf5'
assert sha(data) == const['source_data_sha256']
baselines = {name: np.asarray(const[f'per_position_{name}_raw'], dtype=np.float64) for name in ('mean','median')}
rows = []
with h5py.File(data, 'r') as f:
    for s in plan:
        group = f['data'][f'demo_{s["demo_id"]}']
        target = np.asarray(group['actions'][s['t']:s['t']+30], dtype=np.float32)
        assert digest(target) == s['raw_expert_chunk']['sha256']
        assert len(target) == s['valid_chunk_steps'] == 30
        with np.load(OLD/f'inputs/sample_{s["sample"]:02d}.npz', allow_pickle=False) as z:
            assert np.array_equal(target, z['expert_raw_chunk'])
            assert not z['mask_chunk'].any()
        scores = {}
        for name,b in baselines.items():
            err = b - target.astype(np.float64)
            e = err / std
            scores[name] = {'xyz_normalized_MAE': float(abs(e[:,:3]).mean()),
                'all7_normalized_MAE': float(abs(e).mean()),
                'all7_normalized_RMSE': float(np.sqrt((e*e).mean())),
                'raw_MAE_by_dim': abs(err).mean(0).tolist(),
                'raw_RMSE_by_dim': np.sqrt((err*err).mean(0)).tolist()}
        rows.append({'sample':s['sample'],'demo':s['demo_id'],'t':s['t'],
            'target_sha256':digest(target),'valid_steps':len(target),'scores':scores,
            'expert_xyz_direction_valid_count':int((np.linalg.norm(target[:,:3],axis=1)>1e-6).sum()),
            'expert_gripper_values':np.unique(target[:,6]).tolist()})
metrics = ['xyz_normalized_MAE','all7_normalized_MAE','all7_normalized_RMSE']
aggregate = {name:{m:float(np.mean([r['scores'][name][m] for r in rows])) for m in metrics} for name in baselines}
out = {'checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'new_GL_model_observations':0,'independent_demos':2,'states':4,
    'constant_sha256':sha(OLD/'constants.json'),'stats_sha256':sha(R/'manifests/dataset_stats.json'),
    'data_sha256':const['source_data_sha256'],'samples':rows,'equal_state_aggregate':aggregate,
    'aggregate_winner_by_metric':{m:min(baselines,key=lambda name:aggregate[name][m]) for m in metrics},
    'evaluation_arithmetic':'float64 physical targets converted from fixed float32, then divided by frozen std; RMSE aggregation stated as mean of per-state RMSE',
    'no_new_constant_fit':True,'baseline_selection':'one complete mean or median across all four states per metric; no per-sample/coordinate oracle'}
(P/'artifacts/parent_reference_baselines.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'reference_targets_verified':True,'aggregate':aggregate,'winners':out['aggregate_winner_by_metric']}))
