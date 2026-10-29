"""CPU-only independent audit of saved sources, tensors and observations."""
from diag_common import *
import gc
import importlib.metadata
import subprocess
import sys
import numpy as np
import h5py
import torch

def array_meta(a):
    a = np.asarray(a)
    return {'shape':list(a.shape),'dtype':str(a.dtype),'min':float(a.min()),
            'max':float(a.max()),'sha256':hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()}

def weighted_median(values, weights):
    out = []
    for j in range(values.shape[1]):
        order = np.argsort(values[:,j], kind='stable')
        cw = np.cumsum(weights[order], dtype=np.float64)
        index = np.searchsorted(cw, weights.sum(dtype=np.float64) / 2, side='left')
        out.append(float(values[order[index],j]))
    return out

def main():
    check_gate()
    assert not torch.cuda.is_initialized()
    torch.set_num_threads(3)
    torch.set_num_interop_threads(1)
    started = time.time()
    ck = torch.load(R/'checkpoints/C_latest.pt', map_location='cpu', weights_only=False)
    assert not torch.cuda.is_initialized()
    state = ck['model_state_dict']
    tensor_rows = []
    for name,t in state.items():
        v = t.detach().cpu()
        tensor_rows.append({'key':name,'shape':list(v.shape),'dtype':str(v.dtype),'numel':v.numel(),
                            'finite':bool(torch.isfinite(v).all()),'min':float(v.min()),
                            'max':float(v.max()),'mean':float(v.double().mean())})
    write(E/'results/checkpoint_tensors.json', tensor_rows)
    stats = {k:np.asarray(v,dtype=np.float32) for k,v in ck['stats'].items()}
    arg_diff = {k:[v,read(R/'manifests/C_config.json').get(k)] for k,v in ck['args'].items()
                if v != read(R/'manifests/C_config.json').get(k)}
    opt = ck['optimizer_state_dict']
    optsteps = sorted({int(v['step']) for v in opt['state'].values() if 'step' in v})
    checkpoint = {'sha256':sha(R/'checkpoints/C_latest.pt'),'bytes':(R/'checkpoints/C_latest.pt').stat().st_size,
                  'top_level_keys':list(ck),'updates':ck['updates'],'completed_epochs':ck['completed_epochs'],
                  'last_validated_epoch':ck['last_validated_epoch'],'utc':ck['utc'],
                  'train_elapsed_seconds':ck['train_elapsed_seconds'],'args':ck['args'],'args_vs_json_differences':arg_diff,
                  'state_dict_entries':len(state),'tensor_numel_including_buffers':sum(v['numel'] for v in tensor_rows),
                  'nonfinite_keys':[v['key'] for v in tensor_rows if not v['finite']],
                  'optimizer_saved_steps':optsteps,'loader':{k:v for k,v in ck['loader_state'].items() if k!='generator_state'},
                  'scheduler':ck['scheduler_state_dict'],
                  'rng_keys':list(ck['rng']),'cpu_only':not torch.cuda.is_initialized()}
    write(E/'results/checkpoint_audit.json',checkpoint)
    states, actions, lengths = [], [], []
    with h5py.File(R/'assets/liftrand_eef_delta.hdf5','r') as f:
        attrs = {k:v.decode() if isinstance(v,bytes) else v for k,v in f['data'].attrs.items()}
        schema = {'data_attributes':attrs,'first_demo_keys':list(f['data/demo_0']),
                  'first_demo_attributes':dict(f['data/demo_0'].attrs),
                  'data_attribute_keys':list(f['data'].attrs),'demos_read':list(range(200))}
        for d in range(200):
            states.append(f[f'data/demo_{d}/states'][()].astype(np.float32)[:,:7])
            a=f[f'data/demo_{d}/actions'][()].astype(np.float32)
            actions.append(a);lengths.append(len(a))
    # Exact ACT branch of upstream get_norm_stats: float32 concat, population std, 1e-4 clip.
    s=np.concatenate(states);a=np.concatenate(actions)
    recomputed={'state_mean':s.mean(0),'state_std':np.clip(s.std(0),1e-4,np.inf),
                'action_mean':a.mean(0),'action_std':np.clip(a.std(0),1e-4,np.inf)}
    jsonstats=read(R/'manifests/dataset_stats.json')
    comparisons={}
    for k,v in recomputed.items():
        comparisons[k]={'recomputed':v.tolist(),'checkpoint':stats[k].tolist(),'json':jsonstats[k],
                        'checkpoint_bit_equal':bool(np.array_equal(v,stats[k])),
                        'json_bit_equal_f32':bool(np.array_equal(v,np.asarray(jsonstats[k],np.float32))),
                        'checkpoint_maxabs':float(abs(v-stats[k]).max()),
                        'json_maxabs':float(abs(v-np.asarray(jsonstats[k],np.float32)).max())}
    normalized=(a-stats['action_mean'])/stats['action_std']
    roundtrip=normalized*stats['action_std']+stats['action_mean']
    statresult={'official_function_source_sha256':sha(K/'utils.py'),'formula':'upstream ACT branch, float32, ddof=0, std clip >=1e-4',
                'per_dimension':comparisons,'raw_action_roundtrip_maxabs_by_dim':abs(roundtrip-a).max(0).tolist(),
                'drop1_qpos':(-stats['state_mean']/stats['state_std']).tolist(),
                'qpos_drop_semantics':'raw zero then normalize; cam_extrinsics token zeros',
                'l1_denominators':{'official':'sum(abs(error)*valid)/(30*7) per batch1 sample',
                                   'effective':'sum(abs(error)*valid)/(valid_steps*7)'},
                'action_frames':len(a),'state_frames':len(s)}
    write(E/'results/normalization_audit.json',statresult)
    # No observation-dependent fitting. Each legal future item gets weight 1/(200*L_demo).
    med, mean, weightmass, counts = [], [], [], []
    for k in range(30):
        vals=np.concatenate([v[k:] for v in actions if len(v)>k])
        weights=np.concatenate([np.full(len(v)-k,1/(200*len(v)),dtype=np.float64) for v in actions if len(v)>k])
        med.append(weighted_median(vals,weights));mean.append(np.average(vals.astype(np.float64),axis=0,weights=weights).tolist())
        weightmass.append(float(weights.sum()));counts.append(len(vals))
    constants={'source_data_sha256':sha(R/'assets/liftrand_eef_delta.hdf5'),'demos':list(range(200)),
               'weight':'each valid a[d,t+k] has 1/(200 L_d), t uniform in [0,L_d-1], t+k<L_d; no padding',
               'weighted_median_tie':'stable sort ascending; first cumulative weight >= half total position mass',
               'position_valid_weight_mass':weightmass,'position_valid_items':counts,
               'per_position_median_raw':med,'per_position_mean_raw':mean,
               'per_position_median_normalized':((np.asarray(med)-stats['action_mean'])/stats['action_std']).tolist(),
               'per_position_mean_normalized':((np.asarray(mean)-stats['action_mean'])/stats['action_std']).tolist(),
               'all_frame_mean_raw':a.mean(0).tolist(),'all_frame_median_raw':np.median(a,axis=0).tolist(),
               'all_frame_mean_rule':'unweighted all training frames; one vector repeated 30 positions',
               'all_frame_median_rule':'np.median, average middle two if even; weaker repeated-vector comparator',
               'physical_zero_raw':[0.]*7,'action_mean':stats['action_mean'].tolist(),'action_std':stats['action_std'].tolist()}
    write(E/'constants.json',constants,exclusive=True)
    samples=[]
    cameras=read(K/'camera_poses/train_cameras.json')['poses']
    with h5py.File(R/'assets/liftrand_eef_delta.hdf5','r') as f:
        for mode in ['zero','middle']:
            for d in [0,50,100,150]:
                L=lengths[d];t=0 if mode=='zero' else (L-1)//2;index=d+1
                assert L>t>=0 and d<=index<d+3 and index<len(cameras)
                rawstate=f[f'data/demo_{d}/states'][t].astype(np.float32)
                rawchunk=actions[d][t:t+30]
                samples.append({'sample':len(samples),'demo_id':d,'t':t,'demo_length':L,
                                'source_state_f32':array_meta(rawstate),'source_state_original_dtype':str(f[f'data/demo_{d}/states'].dtype),
                                'valid_chunk_steps':len(rawchunk),'camera_index':index,'T':cameras[index],
                                'raw_expert_chunk':array_meta(rawchunk),'seed1':20261029+len(samples),
                                'seed2':20262029+len(samples) if len(samples)<4 else None})
    write(E/'sample_plan.json',{'frozen_before_model':True,'ordered_samples':samples,'independent_demos':4,
                              'source_states':8,'training_dataset_max_seq_length':max(lengths)},exclusive=True)
    schema['training_lengths']=lengths
    schema['environment_version_metadata']=json.loads(attrs['env_args']).get('env_version')
    schema['stored_rgb_or_xml']='none in inspected demo/data attributes; states/actions only'
    write(E/'results/data_schema.json',schema)
    rows=[json.loads(line) for line in (R/'logs/training_steps.jsonl').read_text().splitlines()]
    updates=[v['update'] for v in rows]
    bad_epochs=[]
    for e in range(20001):
        group=rows[e*3:(e+1)*3]
        ids=sum([v['demo_order'] for v in group],[])
        if len(group)!=3 or sorted(ids)!=list(range(200)) or [v['batch_n'] for v in group]!=[70,70,60]:
            bad_epochs.append(e)
    events=[json.loads(v) for v in (R/'logs/training_events.jsonl').read_text().splitlines()]
    sampling={'rows':len(rows),'updates_continuous_1_to_60003':updates==list(range(1,60004)),
              'every_epoch_covers_200_demos_once':not bad_epochs,'bad_epochs':bad_epochs,
              'batch_sizes':sorted({v['batch_n'] for v in rows}),'events':events,
              'resume_boundary_rows':[v for v in rows if 34<=v['update']<=38],
              'final_row':rows[-1], 'old_rng_limitation':'per-update timestep/camera/crop and framebuffer status were not recorded; cannot reconstruct all historic input tensors from seed',
              'sampler_difference':'independent Torch generator seed0 vs official global-RNG DataLoader; no proof of causal failure'}
    write(E/'results/sampling_audit.json',sampling)
    trajectories=[];firsts=[];allraw=[]
    for row in [json.loads(v) for v in (R/'results/dev_rollouts.jsonl').read_text().splitlines()]:
        path=R/row['trace_path']
        with np.load(path) as z:
            raw=z['actions'];firsts.append(raw[0]);allraw.append(raw)
            trajectories.append({'root_id':row['root_id'],'tag':row.get('tag'),'success':row['success'],
                                 'any_reach':row['any_reach'],'any_grasp':row['any_grasp'],'steps':len(raw),
                                 'action_first_raw':raw[0].tolist(),'target_delta_sum_xyz_m':raw[:,:3].sum(0).tolist(),
                                 'action_raw_mean':raw.mean(0).tolist(),'action_raw_std':raw.std(0).tolist(),
                                 'finite':bool(np.isfinite(raw).all()),'trace_sha256':sha(path),
                                 'trace_arrays':list(z),'eef_actual_recorded':False})
    independent=[x for x in trajectories if x['tag'] is None]
    independentfirst=np.asarray([x['action_first_raw'] for x in independent])
    traceaudit={'independent_roots':len(independent),'repeat_rollouts':len(trajectories)-len(independent),
                'total_steps':sum(v['steps'] for v in trajectories),'rows':trajectories,
                'independent_first_xyz_std_ddof0_m':independentfirst[:,:3].std(0).tolist(),
                'all_including_repeat_action_mean':np.concatenate(allraw).mean(0).tolist(),
                'caution':'target deltas are commands, not measured EEF displacement; prior traces lack actual EEF XYZ',
                'expert_existing':{'success':read(R/'results/semantics.json')['expert_successes'],'n':10,
                                  'limits':'rules out a completely unusable wrapper on those replays, not historic RGB corruption, exact source XML equivalence, or policy competence'}}
    write(E/'results/old_trajectory_audit.json',traceaudit)
    packages={}
    for name in ['torch','torchvision','numpy','h5py','mujoco','robosuite','PyOpenGL','scipy']:
        try: packages[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:packages[name]='not_distribution_metadata'
    versions={'python':sys.version,'packages':packages,
              'kyc_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=R/'vendor/kyc',text=True).strip(),
              'robosuite_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=R/'vendor/robosuite',text=True).strip(),
              'cuda_initialized':torch.cuda.is_initialized()}
    write(E/'results/versions.json',versions)
    failure=[]
    if checkpoint['nonfinite_keys']:failure.append('nonfinite checkpoint')
    if checkpoint['updates']!=60003 or checkpoint['completed_epochs']!=20001:failure.append('checkpoint updates/epochs mismatch')
    if arg_diff:failure.append('checkpoint args mismatch')
    if not all(v['checkpoint_bit_equal'] and v['json_bit_equal_f32'] for v in comparisons.values()):failure.append('normalization differs')
    if not sampling['updates_continuous_1_to_60003'] or bad_epochs:failure.append('training log coverage mismatch')
    assert not torch.cuda.is_initialized()
    gate={'utc':utc(),'decision':'STOP_CONCRETE_ISSUE' if failure else 'NEEDS_BOUNDED_STAGE1',
          'concrete_issues':failure,'stage0_cuda_initialized':False,'new_model_calls':0,'new_env_instances':0,
          'unresolved':['H1 same-state Dataset/Evaluator/custom tensors and prior outputs lack numerical comparison',
                        'H2 seen-source prior/posterior/position-weighted constant comparison absent',
                        'H3 training-pool and original dev-camera paired behavior absent',
                        'H4 historic framebuffer integrity and exact collection XML remain unknowable from saved assets'],
          'why_readonly_insufficient':'saved checkpoint stats, sampler logs and dev traces do not contain fixed seen-source prior/posterior outputs or corresponding entry tensors',
          'joint_protocol_sha256':PROTOCOL_SHA,'conditional_stage1_preapproved':not failure,
          'cpu_audit_wall_seconds':time.time()-started}
    write(E/'stage0_gate.json',gate,exclusive=True)
    print(json.dumps(gate,ensure_ascii=False))

if __name__=='__main__':
    main()
