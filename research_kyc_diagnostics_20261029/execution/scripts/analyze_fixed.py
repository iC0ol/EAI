"""Pre-registered fixed-sample metrics. CPU only; never calls the model."""
from diag_common import *
import numpy as np

def directions(pred, expert):
    pn=np.linalg.norm(pred[:,:3],axis=1);en=np.linalg.norm(expert[:,:3],axis=1)
    valid=en>1e-4
    cos=np.full(len(pred),np.nan)
    usable=valid & (pn>0)
    cos[usable]=np.sum(pred[usable,:3]*expert[usable,:3],axis=1)/(pn[usable]*en[usable])
    ps=pred[:,:3].sum(0);es=expert[:,:3].sum(0)
    chunkcos=float(ps@es/(np.linalg.norm(ps)*np.linalg.norm(es))) if np.linalg.norm(es)>1e-4 and np.linalg.norm(ps)>0 else None
    return {'per_step_expert_xyz_norm_m':en.tolist(),'per_step_pred_xyz_norm_m':pn.tolist(),
            'per_step_xyz_direction_cosine':[float(x) if np.isfinite(x) else None for x in cos],
            'direction_NA_rule':'expert xyz norm <=1e-4m or predicted norm=0',
            'chunk_sum_expert_xyz_m':es.tolist(),'chunk_sum_pred_xyz_m':ps.tolist(),
            'chunk_sum_direction_cosine':chunkcos,'first_xyz_direction_cosine':float(cos[0]) if np.isfinite(cos[0]) else None}

def errors(pred,expert,mask,std):
    valid=~mask;v=int(valid.sum());delta=abs(pred-expert);norm=delta/std
    out={'valid_steps':v,'l1_normalized_valid_all7':float(norm[valid].mean()),
         'l1_normalized_official_padding_denominator_all7':float((norm*valid[:,None]).mean()),
         'l1_normalized_valid_xyz':float(norm[valid,:3].mean()),
         'raw_mae_by_dim':delta[valid].mean(0).tolist(),
         'raw_xyz_mae_m':float(delta[valid,:3].mean()),'raw_axisangle_mae_rad':float(delta[valid,3:6].mean()),
         'raw_gripper_mae':float(delta[valid,6].mean()),
         'first_raw_abs_error_by_dim':delta[0].tolist(),'first_normalized_xyz_mae':float(norm[0,:3].mean()),
         'pred_raw_std_by_dim_ddof0':pred[valid].std(0).tolist(),
         'expert_raw_std_by_dim_ddof0':expert[valid].std(0).tolist()}
    out.update(directions(pred[valid],expert[valid]))
    return out

def analyze():
    samples=read(E/'sample_plan.json')['ordered_samples'];constants=read(E/'constants.json')
    std=np.asarray(constants['action_std'],dtype=np.float64)
    choices={'position_weighted_median':np.asarray(constants['per_position_median_raw']),
             'position_weighted_mean':np.asarray(constants['per_position_mean_raw']),
             'frame_median_repeated':np.tile(constants['all_frame_median_raw'],(30,1)),
             'frame_mean_repeated':np.tile(constants['all_frame_mean_raw'],(30,1)),
             'physical_zero':np.zeros((30,7))}
    rows=[];experts=[];priors=[];first_exp=[];first_prior=[];P=[];M=[];Q=[];weights=[]
    for sample in samples:
        j=sample['sample']
        inp=np.load(E/f'inputs/sample_{j:02d}.npz')
        expert=inp['expert_raw_chunk'].astype(np.float64);mask=inp['mask_chunk'].astype(bool)
        predictions={}
        for path in sorted((E/'results/predictions').glob(f's{j:02d}_*.npz')):
            with np.load(path) as z:predictions[path.stem.split('_',1)[1]]=z['raw_chunk'].astype(np.float64)
        if 'official_prior' not in predictions or not any(k.startswith('posterior') for k in predictions):
            write(E/'results/fixed_metrics.json',{'state':'PARTIAL','samples':rows,'reason':'missing fixed output; no full floor computed'})
            return {'complete':False,'floor':None,'reason':'PARTIAL'}
        metrics={label:errors(x,expert,mask,std) for label,x in dict(choices,**predictions).items()}
        v=int((~mask).sum());w=3*v
        p=metrics['official_prior']['l1_normalized_valid_xyz'];m=metrics['position_weighted_median']['l1_normalized_valid_xyz']
        q=float(np.mean([v['l1_normalized_valid_xyz'] for k,v in metrics.items() if k.startswith('posterior')]))
        P.append(p);M.append(m);Q.append(q);weights.append(w)
        valid=~mask;experts.append(expert[valid,:3]);priors.append(predictions['official_prior'][valid,:3])
        first_exp.append(expert[0,:3]);first_prior.append(predictions['official_prior'][0,:3])
        rows.append({'sample':j,'demo':sample['demo_id'],'t':sample['t'],'valid_steps':v,'W':w,
                     'P_xyz':p,'M_xyz':m,'Q_xyz_mean_seed_error':q,'metrics':metrics})
    Psum=float(np.average(P,weights=weights));Msum=float(np.average(M,weights=weights));Qsum=float(np.average(Q,weights=weights))
    se=np.concatenate(experts).std(0);sp=np.concatenate(priors).std(0)
    bad=int(sum(p>=m for p,m in zip(P,M)))
    concentration=(se>=1e-4)&(sp<=0.1*se)
    concentrated=int(concentration.sum())>=2
    posterior_gap=Psum>1e-8 and Qsum<=0.5*Psum
    near_zero=Psum<=1e-8 and Msum<=1e-8
    floor=Psum>=Msum and bad>=6 and (concentrated or posterior_gap) and not near_zero
    gate={'complete':True,'floor':bool(floor),'P_xyz_normalized':Psum,'M_xyz_normalized':Msum,
          'Q_xyz_normalized':Qsum,'P_i':P,'M_i':M,'Q_i':Q,'W_i':weights,'bad_count_P_ge_M':bad,
          'bad_required':6,'expert_std_xyz_raw_m':se.tolist(),'prior_std_xyz_raw_m':sp.tolist(),
          'prior_to_expert_std_ratio':(sp/se).tolist(),'concentrated_axes':concentration.tolist(),
          'concentrated':bool(concentrated),'posterior_gap':bool(posterior_gap),'near_zero_uninformative':bool(near_zero),
          'first_expert_std_xyz_raw_m':np.asarray(first_exp).std(0).tolist(),
          'first_prior_std_xyz_raw_m':np.asarray(first_prior).std(0).tolist(),
          'independent_demos':4,'source_states':8,
          'interpretation':'descriptive budget-stop rule only; no task success or general training inability conclusion'}
    write(E/'results/fixed_metrics.json',{'state':'COMPLETE','samples':rows,'floor_gate':gate})
    write(E/'results/open_loop_floor.json',gate)
    return gate

if __name__=='__main__':
    print(json.dumps(analyze(),ensure_ascii=False))
