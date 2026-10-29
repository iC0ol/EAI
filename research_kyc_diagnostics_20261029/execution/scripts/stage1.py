"""Joint-approved fixed-sample inference and gated paired camera rollouts.

No optimizer updates. Third-party modules are imported read-only. All writes stay here.
"""
from diag_common import *
import contextlib
import gc
import pickle
import random
import signal
import sys
from types import SimpleNamespace
import numpy as np
import torch
import h5py
from PIL import Image

sys.path.insert(0,str(R/'scripts'))
import experiment_lib as lib
from utils import EpisodicDataset, RandomCrop
from eval import Evaluator
from models.act import ACTPolicy
from cam_embedding import PluckerEmbedder
from analyze_fixed import analyze

STOP=False
def stopped(sig,frame):
    global STOP
    STOP=True
    raise InterruptedError(f'budget/termination signal {sig}')

def forbidden(*args,**kwargs):
    raise RuntimeError('Training/backward/download forbidden in diagnostic execution')

def array(x):
    return x.detach().float().cpu().numpy() if torch.is_tensor(x) and x.dtype!=torch.bool else (x.detach().cpu().numpy() if torch.is_tensor(x) else np.asarray(x))

def digest(x):
    a=array(x)
    return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()

def metadata(x):
    a=array(x)
    return {'shape':list(a.shape),'dtype':str(x.dtype if torch.is_tensor(x) else a.dtype),
            'min':float(a.min()),'max':float(a.max()),'finite':bool(np.isfinite(a).all()),'sha256':digest(a)}

def compare(a,b,exact=False):
    a=array(a);b=array(b)
    if a.shape!=b.shape:return {'shape_equal':False,'a_shape':list(a.shape),'b_shape':list(b.shape),'pass':False}
    equal=np.array_equal(a,b)
    diff=np.abs(a.astype(np.float64)-b.astype(np.float64))
    return {'shape_equal':True,'bit_equal':bool(equal),'max_abs':float(diff.max()),
            'allclose_atol_1e_7_rtol_1e_6':bool(np.allclose(a,b,atol=1e-7,rtol=1e-6)),
            'pass':bool(equal if exact else np.allclose(a,b,atol=1e-7,rtol=1e-6))}

def rng_hash(s):
    h=hashlib.sha256(pickle.dumps((s['python'],s['numpy']),protocol=4))
    for t in [s['torch']]+s['cuda']:h.update(t.cpu().numpy().tobytes())
    return h.hexdigest()

@contextlib.contextmanager
def frozen_dataset_choices(sample):
    """Only replace the two upstream draws; restore functions and all RNG states."""
    state=lib.rng_state();before=rng_hash(state)
    torch.save(state,E/f'local_only/sample_{sample["sample"]:02d}_rng_before.pt')
    randint=np.random.randint;choice=np.random.choice
    uses={'time':0,'camera':0}
    def fixed_time(low,high=None,size=None,dtype=int):
        if high is None and low==sample['demo_length'] and size is None and uses['time']==0:
            uses['time']+=1;return sample['t']
        return randint(low,high=high,size=size,dtype=dtype)
    def fixed_camera(a,size=None,replace=True,p=None):
        expected=np.arange(sample['demo_id'],sample['demo_id']+3,dtype=np.int64)
        if np.array_equal(a,expected) and size==1 and replace is False and uses['camera']==0:
            uses['camera']+=1;return np.array([sample['camera_index']],dtype=np.int64)
        return choice(a,size=size,replace=replace,p=p)
    np.random.randint=fixed_time;np.random.choice=fixed_camera
    info={'before_rng_sha256':before}
    try:yield info
    finally:
        np.random.randint=randint;np.random.choice=choice
        lib.restore_rng(state)
        after=rng_hash(lib.rng_state())
        info.update(after_rng_sha256=after,rng_restored=before==after,intercepted_draws=uses,
                    original_numpy_functions_restored=np.random.randint is randint and np.random.choice is choice)
        assert before==after and uses=={'time':1,'camera':1}

def prepare_state(env,state):
    env.sim.set_state_from_flattened(state)
    env.sim.forward()

def official_eval_data(evaluator,rgb,T):
    # Exact blocks from Evaluator.evaluate (without its reset/rollout/side effects).
    image=torch.stack([evaluator._image_to_tensor(rgb,T)],dim=0).unsqueeze(0).cuda()
    if evaluator.args.use_cam_pose and not evaluator.args.default_cam:
        raise AssertionError('frozen configuration requires zero direct camera tokens')
    extrinsics=torch.zeros(1,2,4,4,device='cuda')
    state_vector=evaluator.env.sim.data.qpos[:7]
    if np.random.rand()<evaluator.args.prob_drop_proprio:state_vector=np.zeros_like(state_vector)
    normalized=(state_vector-evaluator.norm_stats['state_mean'].cpu().numpy())/evaluator.norm_stats['state_std'].cpu().numpy()
    qpos=torch.tensor(normalized,device='cuda').float()[None]
    return {'image':image,'qpos':qpos,'cam_extrinsics':extrinsics}

def camera_record(env,T):
    i=env.sim.model.camera_name2id('agentview')
    pos=np.asarray(env.sim.data.cam_xpos[i]).copy()
    mat=np.asarray(env.sim.data.cam_xmat[i]).reshape(3,3).copy()
    actual=np.eye(4);actual[:3,:3]=mat;actual[:3,3]=pos
    return {'actual_cam2world':actual.tolist(),'cam_fovy_degrees':float(env.sim.model.cam_fovy[i]),
            'actual_vs_given_maxabs':float(abs(actual-np.asarray(T)).max()),
            'independent_visible_point_projection':'NOT_COMPLETED: no reliable labeled visible surface/pixel correspondence established in this batch',
            'half_pixel_convention':'upstream ray builder has two +0.5 offsets; preserved; actual camera equality is not full ray-to-RGB proof'}

def prepare_inputs(args,stats):
    plan=read(E/'sample_plan.json');samples=plan['ordered_samples']
    env=lib.make_env(0)
    source_xml=env.model.get_xml()
    (E/'local_only/fixed_source_model.xml').write_text(source_xml)
    ds=EpisodicDataset(list(range(200)),stats,args,camera_poses_file='train_cameras.json',transform='id',env=env,
                       max_seq_length=plan['training_dataset_max_seq_length'])
    evaluator=Evaluator(env,stats,str(lib.DATA),args)
    embedder=PluckerEmbedder(img_size=256,device='cuda')
    data=[];comparisons=[]
    try:
        with h5py.File(lib.DATA,'r') as f:
            for sample in samples:
                j=sample['sample'];T=np.asarray(sample['T'])
                rawstate=f[f'data/demo_{sample["demo_id"]}/states'][sample['t']].astype(np.float32)
                lib.seed_all(sample['seed1']);rng0=lib.rng_state()
                prepare_state(env,rawstate);state_before=env.sim.get_state().flatten().copy()
                xml_before=hashlib.sha256(env.model.get_xml().encode()).hexdigest()
                with frozen_dataset_choices(sample) as control:
                    ds_item=ds[sample['demo_id']]
                state_ds=env.sim.get_state().flatten().copy()
                # Recover uint8 from exact Dataset float32 /255 RGB; retain float image separately.
                rgb_ds=np.rint(array(ds_item['image'][0,:3]).transpose(1,2,0)*255).astype(np.uint8)
                lib.restore_rng(rng0);prepare_state(env,rawstate)
                rgb_eval=evaluator._render_cam_image(T)
                ev=official_eval_data(evaluator,rgb_eval,T)
                state_ev=env.sim.get_state().flatten().copy()
                lib.restore_rng(rng0);prepare_state(env,rawstate)
                rgb_custom=lib.render(env,T)
                custom=lib.policy_input(rgb_custom,T,lib.intrinsics(env),stats,embedder,True)
                state_custom=env.sim.get_state().flatten().copy()
                official={k:ds_item[k][None] for k in ['image','qpos','cam_extrinsics']}
                posterior={k:v[None] for k,v in ds_item.items()}
                raw_actions=ds.demo_actions[sample['demo_id']][sample['t']:sample['t']+30]
                expert=np.zeros((30,7),np.float32);expert[:len(raw_actions)]=raw_actions
                mask=array(ds_item['is_pad'][:30]);normalized=(expert-np.asarray(stats['action_mean']))/np.asarray(stats['action_std'])
                tests={'rgb_dataset_vs_evaluator':compare(rgb_ds,rgb_eval,True),
                       'rgb_dataset_vs_custom':compare(rgb_ds,rgb_custom,True),
                       'state_source_vs_dataset':compare(state_before,state_ds,True),
                       'state_dataset_vs_evaluator':compare(state_ds,state_ev,True),
                       'state_dataset_vs_custom':compare(state_ds,state_custom,True),
                       'normalized_actions':compare(ds_item['actions'][:30],normalized),
                       'mask':compare(mask,np.arange(30)>=len(raw_actions),True)}
                for name,x in [('official_eval',ev),('custom',custom)]:
                    for key in ['image','qpos','cam_extrinsics']:tests[f'dataset_vs_{name}_{key}']=compare(official[key],x[key])
                    tests[f'dataset_vs_{name}_plucker6']=compare(official['image'][:,:,3:],x['image'][:,:,3:])
                # Check official joint crop against an independently sliced tensor; no policy call.
                from torchvision.transforms import functional as TF, InterpolationMode
                source=ds_item['image'][0].clone()
                saved_random=random.getstate();saved_randint=random.randint;sequence=iter([224,11,17])
                try:
                    random.randint=lambda low,high: next(sequence)
                    cropped=RandomCrop(min_side=int(256*0.8),max_side=256,output_size=256)(source.clone())
                finally:
                    random.randint=saved_randint;random.setstate(saved_random)
                expected=TF.resize(source[:,11:235,17:241],[256,256],interpolation=InterpolationMode.NEAREST)
                tests['joint_rgb_ray_frozen_crop']=compare(cropped,expected,True)
                tests['source_xml_unchanged']={'pass':xml_before==hashlib.sha256(env.model.get_xml().encode()).hexdigest()}
                arrays={'dataset_image':array(official['image']),'dataset_qpos':array(official['qpos']),
                        'dataset_cam_extrinsics':array(official['cam_extrinsics']),
                        'eval_image':array(ev['image']),'eval_qpos':array(ev['qpos']),
                        'eval_cam_extrinsics':array(ev['cam_extrinsics']),
                        'custom_image':array(custom['image']),'custom_qpos':array(custom['qpos']),
                        'custom_cam_extrinsics':array(custom['cam_extrinsics']),
                        'normalized_actions_full':array(ds_item['actions']),'mask_full':array(ds_item['is_pad']),
                        'expert_raw_chunk':expert,'mask_chunk':mask,'rgb_uint8':rgb_ds,
                        'T_given':T,'intrinsics':evaluator.intrinsics,'source_state_f32':rawstate,
                        'state_before':state_before,'state_dataset':state_ds,'state_evaluator':state_ev,'state_custom':state_custom,
                        'joint_crop_9ch':array(cropped)}
                path=E/f'inputs/sample_{j:02d}.npz';np.savez_compressed(path,**arrays)
                Image.fromarray(rgb_ds).save(E/f'inputs/sample_{j:02d}.png')
                row={'sample':sample,'all_inputs_pass':all(t['pass'] for t in tests.values()),
                     'comparisons':tests,'tensor_metadata':{k:metadata(v) for k,v in arrays.items()},
                     'dataset_rng_control':control,'source_xml_sha256':xml_before,'geometry':camera_record(env,T),
                     'rng_end_restored':rng_hash(rng0),'npz_sha256':sha(path)}
                comparisons.append(row);write(E/'results/input_comparisons.json',{'state':'PARTIAL','samples':comparisons})
                data.append({'sample':sample,'official':ev,'custom':custom,'posterior':posterior})
                lib.restore_rng(rng0)
                print('INPUT',j,row['all_inputs_pass'],flush=True)
    finally:
        ds.env=None
        env.close()
    result={'state':'COMPLETE','all_inputs_pass':all(v['all_inputs_pass'] for v in comparisons),'samples':comparisons,
            'independent_geometry_correspondence':'NOT_COMPLETED','geometry_boundary':'same-state camera matrices compared; no claim of independent visible-pixel ray validation'}
    write(E/'results/input_comparisons.json',result)
    return data,result

def call(policy,inputs,label,sample,stats,category='fixed',rollout=None,seed=None):
    if STOP:raise InterruptedError('stop')
    posterior=label.startswith('posterior')
    if not posterior:assert set(inputs)=={'image','qpos','cam_extrinsics'}, 'prior must not contain labels'
    assert inputs['image'].shape[0]==1 and not policy.training
    if seed is not None:lib.seed_all(seed)
    before_rng=rng_hash(lib.rng_state())
    captured=[]
    def capture(module,arguments,output):
        a,pad,(mu,logvar)=output
        captured.append({'normalized_chunk':array(a[0]),'is_pad_hat':array(pad[0]),
                         'mu':array(mu[0]) if mu is not None else np.zeros((0,),np.float32),
                         'logvar':array(logvar[0]) if logvar is not None else np.zeros((0,),np.float32),
                         'output_dtype':str(a.dtype)})
    hook=policy.model.register_forward_hook(capture)
    before_call(category,f's{sample:02d}_{label}' if category=='fixed' else label,rollout)
    t=time.perf_counter()
    try:
        with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16):
            out=policy(lib.clone_input(inputs))
        torch.cuda.synchronize()
    finally:hook.remove()
    assert len(captured)==1, 'one internal forward only'
    values=captured[0]
    norm=values['normalized_chunk']
    assert norm.shape==(30,7) and np.isfinite(norm).all(), 'malformed/nonfinite chunk'
    assert all(np.isfinite(values[k]).all() for k in ['mu','logvar','is_pad_hat'])
    raw=norm*np.asarray(stats['action_std'])+np.asarray(stats['action_mean'])
    metrics={'utc':utc(),'label':label,'sample':sample,'category':category,'rollout':rollout,
             'seconds':time.perf_counter()-t,'seed':seed,'before_rng_sha256':before_rng,
             'input_hashes':{k:digest(v) for k,v in inputs.items()},'prior_contains_labels':False if not posterior else None,
             'output_dtype':values.pop('output_dtype'),'raw_chunk_metadata':metadata(raw),
             'normalized_chunk_metadata':metadata(norm),'internal_forward_count':len(captured)}
    if posterior:
        metrics['official_loss']={k:float(v) for k,v in out.items()}
        metrics['kl_recomputed_from_hook_float32']=float((-0.5*(1+values['logvar']-values['mu']**2-np.exp(values['logvar']))).sum())
    folder=E/'results/predictions' if category=='fixed' else E/'results/closed_predictions'
    folder.mkdir(exist_ok=True)
    name=f's{sample:02d}_{label}' if category=='fixed' else label
    path=folder/(name+'.npz')
    assert not path.exists()
    np.savez_compressed(path,raw_chunk=raw,**values)
    write(folder/(name+'.json'),dict(metrics,npz_sha256=sha(path)))
    append(E/'call_ledger.jsonl',{'utc':utc(),'event':'CALL_COMPLETED','category':category,'label':name,
                                'output_npz':str(path.relative_to(E)),'output_sha256':sha(path)})
    return norm,raw

def fixed_calls(data,policy,stats):
    outputs={};repeat_off=[];repeat_custom=[]
    for item in data:
        s=item['sample'];j=s['sample'];seed=s['seed1']
        outputs[j]={}
        norm,raw=call(policy,item['official'],'official_prior',j,stats,seed=seed);outputs[j]['official']=norm
        norm,raw=call(policy,item['custom'],'custom_prior',j,stats,seed=seed);outputs[j]['custom']=norm
        if j in [0,1]:
            norm,raw=call(policy,item['official'],'official_repeat',j,stats,seed=seed)
            repeat_off.append(float(abs(norm-outputs[j]['official']).max()))
        elif j in [2,3]:
            norm,raw=call(policy,item['custom'],'custom_repeat',j,stats,seed=seed)
            repeat_custom.append(float(abs(norm-outputs[j]['custom']).max()))
        call(policy,item['posterior'],'posterior_seed1',j,stats,seed=seed)
        if j<4:call(policy,item['posterior'],'posterior_seed2',j,stats,seed=s['seed2'])
        print('FIXED_SAMPLE_COMPLETE',j,read(E/'counts.json')['fixed_forward_attempts'],flush=True)
    ro=max(repeat_off);rc=max(repeat_custom);rmax=max(ro,rc);tol=max(1e-5,2*rmax)
    std=np.asarray(stats['action_std'])
    rows=[]
    for j,x in outputs.items():
        diff=abs(x['official']-x['custom'])
        rows.append({'sample':j,'normalized_maxabs':float(diff.max()),'raw_maxabs_by_dim':(diff*std).max(0).tolist(),
                     'bit_equal':bool(np.array_equal(x['official'],x['custom'])),'within_empirical_tolerance':bool(diff.max()<=tol)})
    result={'state':'COMPLETE','rmax_official':ro,'rmax_custom':rc,'rmax':rmax,'tolerance':tol,
            'numerical_unstable':bool(rmax>1e-3),'all_within_tolerance':all(x['within_empirical_tolerance'] for x in rows),
            'samples':rows,'official_repeats':repeat_off,'custom_repeats':repeat_custom,
            'interpretation':'agreement within this observed empirical tolerance only; two repeat states per entry do not characterize all non-determinism'}
    write(E/'results/output_comparisons.json',result)
    return result

def restore_root(env,root,T):
    folder=R/f'root_states/dev/{root}'
    manifest=read(folder/'manifest.json')
    assert sha(folder/'model.xml')==manifest['xml_sha256']
    assert sha(folder/'state.npy')==manifest['state_sha256']
    assert sha(folder/'rng.pt')==manifest['rng_sha256']
    env.reset_from_xml_string((folder/'model.xml').read_text())
    state=np.load(folder/'state.npy')
    env.sim.set_state_from_flattened(state);env.sim.forward();env.set_init_action()
    lib.restore_rng(torch.load(folder/'rng.pt',map_location='cpu',weights_only=False))
    lib.camera_pose(env,T)
    actual=env.sim.get_state().flatten().copy()
    assert np.array_equal(actual,state), 'old root physical state not restored exactly'
    return manifest,actual

def closed_loop(policy,args,stats):
    plan=read(E/'root_plan.json')['ordered_rollouts'];rows=[];env=None;previous=None
    embedder=PluckerEmbedder(img_size=256,device='cuda')
    oldrows={r['root_id']:r for r in [json.loads(v) for v in (R/'results/dev_rollouts.jsonl').read_text().splitlines()] if r['tag'] is None}
    try:
        for item in plan:
            root=item['root'];condition=item['condition'];key=f'{root}_{condition}';T=np.asarray(item['T'])
            if root!=previous:
                if env is not None:env.close()
                env=lib.make_env(item['old_root']['env_seed']);previous=root
            closed_start(key)
            manifest,initial_state=restore_root(env,root,T)
            rgb=lib.render(env,T);rgbhash=digest(rgb)
            if condition=='dev':assert rgbhash==manifest['clean_RGB'], 'old dev initial RGB hash mismatch'
            Image.fromarray(rgb).save(E/f'inputs/closed_{key}_initial.png')
            Kmat=lib.intrinsics(env);allactions=[];eef=[];objects=[];success=[];grasps=[];reaches=[];queries=[];done=False
            for q in range(5):
                if q>0:rgb=lib.render(env,T)
                inputs=lib.policy_input(rgb,T,Kmat,stats,embedder,True)
                inp_path=E/f'inputs/closed_{key}_q{q}.npz'
                np.savez_compressed(inp_path,**{k:array(v) for k,v in inputs.items()})
                norm,chunk=call(policy,inputs,f'{key}_q{q}',root,stats,'closed',key)
                oldcmp=None
                if condition=='dev':
                    with np.load(R/oldrows[root]['trace_path']) as z:oldchunk=z['actions'][q*30:q*30+len(chunk)]
                    oldcmp=compare(chunk,oldchunk)
                    write(E/f'results/closed_predictions/{key}_q{q}_old_comparison.json',oldcmp)
                    assert np.allclose(chunk,oldchunk,atol=1e-7,rtol=1e-7), 'old dev actions differ; stop to review restoration/numerics'
                queries.append({'q':q,'input_npz_sha256':sha(inp_path),'input_hashes':{k:digest(v) for k,v in inputs.items()},'old_dev_comparison':oldcmp})
                for action in chunk:
                    if done or len(allactions)>=150:break
                    before_step(key)
                    obs,reward,done,info=env.step(action)
                    site=env.sim.model.site_name2id('gripper0_right_grip_site')
                    e=np.asarray(env.sim.data.site_xpos[site]).copy();o=np.asarray(env.sim.data.body_xpos[env.cube_body_id]).copy()
                    allactions.append(action);eef.append(e);objects.append(o)
                    success.append(bool(env._check_success()));grasps.append(bool(env._check_grasp(gripper=env.robots[0].gripper,object_geoms=env.cube)))
                    reaches.append(bool(np.linalg.norm(e-o)<0.05))
                if done or len(allactions)>=150:break
            path=E/f'results/closed_{key}.npz'
            np.savez_compressed(path,actions=np.asarray(allactions),eef_xyz=np.asarray(eef),object_xyz=np.asarray(objects),
                                success=np.asarray(success),grasp=np.asarray(grasps),reach=np.asarray(reaches),initial_state=initial_state)
            row={'root':root,'condition':condition,'success':any(success),'reach':any(reaches),'grasp':any(grasps),
                 'steps':len(allactions),'queries':len(queries),'query_records':queries,'initial_rgb_sha256':rgbhash,
                 'initial_state_sha256':digest(initial_state),'source_state_file_sha256':manifest['state_sha256'],
                 'source_xml_sha256':manifest['xml_sha256'],'source_rng_sha256':manifest['rng_sha256'],
                 'T':T.tolist(),'trace_sha256':sha(path),'trace':str(path.relative_to(E))}
            rows.append(row);append(E/'results/closed_rollouts.jsonl',row)
            print('CLOSED',key,row['success'],row['steps'],flush=True)
    finally:
        if env is not None:env.close()
    from scipy.stats import beta
    paired=[]
    for root in range(1000,1008):
        pair={x['condition']:x for x in rows if x['root']==root}
        paired.append({'root':root,**{c:{k:pair[c][k] for k in ['success','reach','grasp']} for c in ['train','dev']}})
    summaries={}
    for c in ['train','dev']:
        n=8;s=sum(x[c]['success'] for x in paired)
        summaries[c]={'successes':s,'n':n,'rate':s/n,'reach':sum(x[c]['reach'] for x in paired),'grasp':sum(x[c]['grasp'] for x in paired),
                      'clopper_pearson_95_descriptive':[0. if s==0 else float(beta.ppf(.025,s,n-s+1)),1. if s==n else float(beta.ppf(.975,s+1,n-s))],
                      'one_sided95_upper_if_zero':float(1-.05**(1/n)) if s==0 else None}
    diff=np.asarray([int(x['train']['success'])-int(x['dev']['success']) for x in paired])
    rng=np.random.default_rng(20261029);boot=diff[rng.integers(0,8,size=(10000,8))].mean(1)
    result={'state':'COMPLETE','rollouts':len(rows),'independent_physical_roots':8,'paired':paired,'conditions':summaries,
            'train_only_success':int((diff==1).sum()),'dev_only_success':int((diff==-1).sum()),
            'paired_difference_train_minus_dev':float(diff.mean()),'paired_bootstrap95_descriptive':np.quantile(boot,[.025,.975]).tolist(),
            'limits':'8 old dev physical roots, two views each; no training-seed variance or universal task ability conclusion; degenerate bootstrap at all equal outcomes is not proof of equivalence'}
    write(E/'results/closed_summary.json',result)
    return result

def main():
    check_gate();assert read(E/'stage0_gate.json')['decision']=='NEEDS_BOUNDED_STAGE1'
    assert not (E/'results/input_comparisons.json').exists(), 'existing attempt; no implicit repeat'
    for s in [signal.SIGTERM,signal.SIGINT,signal.SIGUSR1]:signal.signal(s,stopped)
    torch.set_grad_enabled(False)
    torch.Tensor.backward=forbidden;torch.autograd.backward=forbidden;torch.optim.AdamW.step=forbidden
    torch.hub.download_url_to_file=forbidden
    args=SimpleNamespace(**read(R/'manifests/C_config.json'))
    assert args.chunk_size==30 and args.use_fp16 and args.prob_drop_proprio==1 and not args.use_cam_pose
    stats={k:np.asarray(v,dtype=np.float32) for k,v in read(R/'manifests/dataset_stats.json').items()}
    write(E/'gpu_activity_started.json',{'utc':utc(),'before_first_possible_cuda_or_renderer':True,
                                       'accounting':'supervisor already counts entire child lifetime'})
    data,input_result=prepare_inputs(args,stats)
    if not input_result['all_inputs_pass']:
        write(E/'stage1_gate.json',{'utc':utc(),'decision':'STOP_INPUT_DISCREPANCY','C':'NOT_RUN','classification_boundary':'D; numerical discrepancy is not proof of H1 causal explanation'})
        write(E/'results/closed_summary.json',{'state':'NOT_RUN','reason':'A input discrepancy','successes':None,'n':None})
        return
    lib.seed_all(0)
    policy=ACTPolicy(args).cuda()
    ck=torch.load(R/'checkpoints/C_latest.pt',map_location='cpu',weights_only=False)
    loaded=policy.load_state_dict(ck['model_state_dict'],strict=True)
    write(E/'results/strict_load.json',{'utc':utc(),'missing_keys':list(loaded.missing_keys),'unexpected_keys':list(loaded.unexpected_keys),
          'checkpoint_sha256':sha(R/'checkpoints/C_latest.pt'),'optimizer_state_loaded':False,
          'official_build_creates_optimizer':True,'optimizer_step_and_backward_guarded':True})
    del ck;gc.collect();policy.eval()
    for p in policy.parameters():p.requires_grad_(False)
    torch.cuda.reset_peak_memory_stats()
    outputs=fixed_calls(data,policy,stats)
    metrics=analyze()
    stop=outputs['numerical_unstable'] or not outputs['all_within_tolerance'] or metrics.get('floor',False)
    why='NUMERICAL_UNSTABLE' if outputs['numerical_unstable'] else ('OUTPUT_DISCREPANCY' if not outputs['all_within_tolerance'] else ('OPEN_LOOP_FLOOR' if metrics.get('floor') else 'A_B_GATE_PASSED'))
    write(E/'stage1_gate.json',{'utc':utc(),'decision':why,'C':'NOT_RUN' if stop else 'AUTHORIZED_BY_FROZEN_GATE',
          'classification_boundary':'D/IMPLEMENTATION-LIMITED if open-loop stop; no general task inability inferred',
          'posterior_selection_boundary':'posterior_gap only determines whether C starts; never changes root/camera/seed/checkpoint/design'})
    if stop:
        write(E/'results/closed_summary.json',{'state':'NOT_RUN','reason':why,'successes':None,'n':None,'rollouts':None,'queries':None})
    else:
        result=closed_loop(policy,args,stats)
        write(E/'stage1_gate.json',{'utc':utc(),'decision':'C_COMPLETE','C':'COMPLETE','closed_summary_sha256':sha(E/'results/closed_summary.json')})
    write(E/'results/torch_memory.json',{'allocated_peak_bytes':torch.cuda.max_memory_allocated(),'reserved_peak_bytes':torch.cuda.max_memory_reserved()})
    assert read(E/'counts.json')['optimizer_updates']==0

if __name__=='__main__':main()
