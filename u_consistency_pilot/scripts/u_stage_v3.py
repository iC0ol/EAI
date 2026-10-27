#!/usr/bin/env python3
"""U v3 stages. Frozen prospective rules, isolated scoring/execution, no F training."""
import argparse,csv,hashlib,importlib.metadata,json,math,os,signal,subprocess,sys,time
from pathlib import Path
import numpy as np
import torch
from download_v3 import BASE,atomic,sha,utc,account
from u_core_v3 import (RUN,WORK,FrozenF,H5Data,COUNTS,flush_counts,jsonable,append,stable_hash,progress,
    make_env,prefix_for_seed,replay_root,physical_snapshot,state_vector,contact_geometry,metric,
    load_scaler,norm_actions,denorm_actions,candidates,b_features,contacts_close,gpu_context,action_residual_scale,denorm_g)

CFG=json.loads((BASE/'configs/protocol_v3.json').read_text())
REPORT=BASE/'reports'/('v3_'+CFG['run_id']);REPORT.mkdir(exist_ok=True)
STAGE=None
def handle_stop(*_):
    import u_core_v3 as core
    core.STOP_REQUESTED=True
signal.signal(signal.SIGTERM,handle_stop);signal.signal(signal.SIGINT,handle_stop)
def write(path,obj):atomic(path,jsonable(obj))
def csvwrite(path,rows,fields=None):
    fields=fields or list(rows[0])
    with Path(path).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader()
        for row in rows:w.writerow({k:json.dumps(jsonable(v),separators=(',',':'),allow_nan=False) if isinstance(v,(list,dict,np.ndarray)) else v for k,v in row.items()})
def readlines(path):
    if not Path(path).exists():return []
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
def done(*paths):
    flush_counts(STAGE)
    outputs={str(Path(x).relative_to(BASE)):sha(x) for x in paths}
    write(RUN/f'stage_{STAGE}.json',{'complete':True,'stage':STAGE,'at':utc(),'code_hash':os.environ['U_CODE_HASH'],'config_hash':os.environ['U_CONFIG_HASH'],'outputs':outputs})
def check_time():
    import u_core_v3 as core
    if core.STOP_REQUESTED:raise RuntimeError('TERM_REQUESTED_CHECKPOINT_BOUNDARY')
    if time.time()>=float(os.environ.get('U_CUTOFF_EPOCH','inf'))-60:raise RuntimeError('PARTIAL-DEADLINE')
    if (RUN/'.control/resource_stop.json').exists():raise RuntimeError('RESOURCE-BLOCK')

def assets():
    # Large transfer runs independently; this stage checks real progress, not cached absence.
    final=BASE/'data/v3/pusht_expert_train.h5.zst'
    began=time.monotonic();last_bytes=-1;last_change=time.monotonic()
    while not final.exists():
        check_time()
        if (RUN/'download_failure.json').exists():raise RuntimeError('NETWORK-BLOCK_'+(RUN/'download_failure.json').read_text())
        p=RUN/'progress_dataset.json';d=json.loads(p.read_text()) if p.exists() else {}
        n=d.get('bytes',0)
        if n!=last_bytes:last_change=time.monotonic();last_bytes=n
        if time.monotonic()-last_change>650:raise RuntimeError('NETWORK-BLOCK_NO_DATA_BYTES_650_SECONDS')
        rate=d.get('payload_bytes_per_second',0);eta=(13136247974-n)/rate if rate else None
        progress('assets',download_bytes=n,download_eta_seconds=eta,elapsed_seconds=time.monotonic()-began)
        time.sleep(10)
    if final.stat().st_size!=13136247974 or sha(final)!='7cfbd6d90fa2f27876379a5ff169715a36ed82edbda64f9e5b5bfa34d212f318':raise RuntimeError('DATASET_HASH_INVALID')
    model=BASE/'models/v3/weights.pt'
    if model.stat().st_size!=72290721 or sha(model)!='48938400ae3464c9680731287f583a9cb516f55a8ec64ea13a91be47fb15b607':raise RuntimeError('MODEL_HASH_INVALID')
    gpu_context()
    versions={'python':sys.version,'executable_alias':'EAI/u_consistency_pilot/.venv-v3/bin/python','torch':torch.__version__,'cuda_build':torch.version.cuda,'gpu':torch.cuda.get_device_name(0),
              'distributions':{x.metadata['Name']:x.version for x in importlib.metadata.distributions() if x.metadata.get('Name')},'source_files':{str(x.relative_to(BASE)):sha(x) for x in (BASE/'external').rglob('*.py')},'model_config_sha256':sha(BASE/'models/v3/config.json'),'model_sha256':sha(model),'compressed_data_sha256':sha(final),'code_hash':os.environ['U_CODE_HASH'],'config_hash':os.environ['U_CONFIG_HASH']}
    write(RUN/'versions.json',versions)
    (REPORT/'requirements_v3.lock').write_text(''.join(f'{k}=={v}\n' for k,v in sorted(versions['distributions'].items())))
    write(RUN/'resource_manifest.json',{'model':{'bytes':model.stat().st_size,'sha256':sha(model),'revision':'22b330c28c27ead4bfd1888615af1340e3fe9052','verified':True},'data':{'bytes':final.stat().st_size,'sha256':versions['compressed_data_sha256'],'revision':'655cd446b9929369d7d406001da85c15d1457850','verified':True},'sources':versions['source_files'],'namespace_adapter':'Only package __init__ optional imports are bypassed; pinned PushT, spaces, utils and LeWM modules executed unchanged','backbone_adapter':'Direct transformers ViTModel with exact tiny configuration of inspected vit_hf; pretrained=False; no extra visual weights','HDF5_adapter':'Read-only original per-column HDF5; no Lance conversion','existing_environments_modified':False})
    done(RUN/'versions.json',RUN/'resource_manifest.json')

def decompress():
    import zstandard as zstd
    source=BASE/'data/v3/pusht_expert_train.h5.zst';target=source.with_suffix('')
    receipt=RUN/'decompression.json'
    if target.exists() and receipt.exists():
        meta=json.loads(receipt.read_text())
        if target.stat().st_size==meta['hdf5_bytes'] and sha(target)==meta['hdf5_sha256']:done(receipt);return
        raise RuntimeError('EXISTING_DECOMPRESSION_INVALID')
    partial=target.with_name(target.name+'.partial')
    # A zstd stream is not a tar archive. Interrupted own partial is recreated;
    # compressed transfer partials remain resumable and untouched.
    with source.open('rb') as f:header=f.read(18)
    if header[:4]!=bytes.fromhex('28b52ffd'):raise RuntimeError('NOT_ZSTD_SINGLE_FILE')
    params=zstd.get_frame_parameters(header);known=zstd.frame_content_size(header)
    if known not in [zstd.CONTENTSIZE_UNKNOWN,zstd.CONTENTSIZE_ERROR] and known>140000000000:raise RuntimeError('RESOURCE-BLOCK_KNOWN_DECOMPRESSED_SIZE_OVER_STORAGE_ALLOCATION')
    started=time.monotonic();written=0
    # python-zstandard0.23 uses bytes here: honor the verified frame's actual
    # window (8MiB for this pinned asset), rather than a smaller guessed limit.
    with source.open('rb') as inp,partial.open('wb') as out,zstd.ZstdDecompressor(max_window_size=params.window_size).stream_reader(inp) as reader:
        while True:
            b=reader.read(16*1024*1024)
            if not b:break
            out.write(b);written+=len(b)
            if written%(256*1024*1024)==0:
                check_time();disk=os.statvfs(BASE)
                if disk.f_bavail*disk.f_frsize<41000000000 or written>140000000000:raise RuntimeError('RESOURCE-BLOCK_STREAMING_DECOMPRESSION_DISK_GUARD')
                progress('decompress',bytes_written=written,elapsed_seconds=time.monotonic()-started)
    with partial.open('rb') as f:
        if f.read(8)!=b'\x89HDF\r\n\x1a\n':raise RuntimeError('DECOMPRESSED_OUTPUT_NOT_HDF5')
    os.replace(partial,target)
    write(receipt,{'format':'single zstd frame -> HDF5, not tar','zstd_window_bytes':params.window_size,'frame_content_size':None if known in [zstd.CONTENTSIZE_UNKNOWN,zstd.CONTENTSIZE_ERROR] else known,'hdf5_bytes':target.stat().st_size,'hdf5_sha256':sha(target),'elapsed_seconds':time.monotonic()-started})
    done(receipt)

def compute_action_scaler(data):
    from sklearn.preprocessing import StandardScaler
    column=data.f['action'];n=len(column);fit=StandardScaler();valid_count=0;bad=0
    arr=np.lib.format.open_memmap(WORK/'all_actions.npy',mode='w+',dtype=column.dtype,shape=column.shape)
    amin=np.full(2,np.inf);amax=np.full(2,-np.inf)
    for lo in range(0,n,100000):
        x=column[lo:lo+100000];arr[lo:lo+len(x)]=x;good=np.isfinite(x).all(axis=1);bad+=int((~good).sum());x=x[good]
        if len(x):fit.partial_fit(x);valid_count+=len(x);amin=np.minimum(amin,x.min(0));amax=np.maximum(amax,x.max(0))
    arr.flush()
    if valid_count<2 or (fit.scale_<=0).any():raise RuntimeError('INVALID_ORIGINAL_ACTION_STATISTICS')
    # Match the original raw units; never rescale input from a new small dataset.
    # Recorded actions can exceed the declared Box because the environment's
    # step method does not itself clip. Infer units from exact PD/state timing,
    # never from a guessed numerical range or a research candidate outcome.
    probes={str(mode):original_action_alignment(data,{'relative':mode},record_name='action_unit_probe_'+str(mode)+'.json',enforce=False) for mode in [True,False]}
    compatible=[mode for mode in [True,False] if probes[str(mode)]['expected_leaving_action_row_q95_max_coord_error_pixels']<=.001]
    if len(compatible)!=1:raise RuntimeError('ACTION_UNITS_UNRESOLVED_BY_ORIGINAL_PD_STATE_TIMING')
    relative=compatible[0]
    write(RUN/'action_unit_selection.json',{'relative':relative,'criterion':'Unique source PD/state model q95<=.001pixel; same preregistered temporal tolerance','probes':probes,'raw_extrema_are_not_action_space_bounds':True,'study_outcomes_used':False})
    std1=fit.scale_*np.sqrt(valid_count/(valid_count-1))
    helper=torch.from_numpy(np.asarray(arr));helper=helper[~torch.isnan(helper).any(dim=1)]
    helper_mean=helper.mean(0).numpy();helper_std=helper.std(0,correction=1).numpy()
    result={'provenance':'All finite action rows in pinned original pretrained PushT HDF5; streamed StandardScaler.partial_fit','source_revision':'655cd446b9929369d7d406001da85c15d1457850','source_compressed_sha256':'7cfbd6d90fa2f27876379a5ff169715a36ed82edbda64f9e5b5bfa34d212f318','source_total_rows':n,'finite_rows':valid_count,'nan_or_nonfinite_rows':bad,'mean':fit.mean_.tolist(),'std_ddof0':fit.scale_.tolist(),'variance_ddof0':fit.var_.tolist(),'std_ddof1_same_exact_population':std1.tolist(),'ddof1_minus_ddof0':(std1-fit.scale_).tolist(),'ddof1_relative_difference':(std1/fit.scale_-1).tolist(),'ddof_note':'Bessel formula fields isolate ddof difference; exact original-dtype torch helper statistics additionally saved, including numeric rounding','adopted_path':'Original eval.py StandardScaler ddof=0; train helper utils.py torch.std defaults correction=1','original_dtype':str(column.dtype),'raw_min':amin.tolist(),'raw_max':amax.tolist(),'relative':relative,'raw_action_clip':[-1.,1.] if relative else [0.,512.],'control_hz':10,'physics_dt':.01,'relative_target_scale_pixels':100,'flatten':'C-order time-major: [u_t.x,u_t.y,u_t+1.x,u_t+1.y,...,u_t+4.x,u_t+4.y]'}
    lower,upper=result['raw_action_clip'];raw=np.asarray(arr)
    result.update({'recorded_coordinate_fraction_outside_declared_candidate_clip':float(np.mean((raw<lower)|(raw>upper))),'recorded_action_row_fraction_outside_declared_candidate_clip':float(np.mean(np.any((raw<lower)|(raw>upper),axis=1))),'original_statistics_actions_clipped':False,'unit_identification':'Exact source10-microstep PD/state timing, not min/max range','train_helper_exact_mean':helper_mean.tolist(),'train_helper_exact_std_correction1':helper_std.tolist(),'train_helper_actual_minus_eval_scale':(helper_std-fit.scale_).tolist(),'train_helper_mean_minus_eval_mean':(helper_mean-fit.mean_).tolist(),'helper_measurement':'HDF5 read streamed into small action-only memmap; exact original-dtype torch.mean/std on its finite rows; no RGB materialization'})
    write(RUN/'action_scaler.json',result);return result

def roots_for_split(split,n,base,relative):
    chosen=[];rejected=[]
    for stratum,offset in [('contact',0),('noncontact',10000)]:
        accepted=[]
        for index in range(512):
            check_time();seed=base+offset+index;r=prefix_for_seed(seed,stratum,relative)
            if not r['accepted']:
                rejection={'split':split,'seed':seed,'stratum':stratum,'reason':'prescoring_geometry_mismatch','geometry_gap':r['geometry_gap'],'prefix_actions':r['prefix_actions']}
                rejected.append(rejection);append(RUN/'root_rejections.jsonl',rejection);flush_counts(STAGE);continue
            number=2*len(accepted)+(0 if stratum=='contact' else 1)
            r.update({'split':split,'root':f'{split}_{number:03d}','source':f'independent_seed_{seed}','candidate_seed':seed+500000,'history_hash':hashlib.sha256(r['history_raw_frames'].tobytes()).hexdigest(),'goal_hash':hashlib.sha256(r['goal_image'].tobytes()).hexdigest()})
            accepted.append(r)
            append(RUN/'prospective_root_progress.jsonl',{k:jsonable(v) for k,v in r.items() if k not in ['history_raw_frames','goal_image']});flush_counts(STAGE)
            if len(accepted)==n//2:break
        if len(accepted)!=n//2:raise RuntimeError('INCONCLUSIVE_INDEPENDENT_ROOT_SUPPLY_'+split)
        chosen+=accepted
    return sorted(chosen,key=lambda x:x['root']),rejected

def original_action_alignment(data,s,record_name='original_action_alignment.json',enforce=True):
    # Agent is kinematic. Its PD update can be checked independently of hidden
    # object/contact state, using exactly the fixed source's integration rule.
    if 'state' not in data.f or data.f['state'].shape[1] not in [5,7]:raise RuntimeError('STATE_COLUMNS_FOR_ACTION_ALIGNMENT_UNAVAILABLE')
    def coefficients(velocity,target):
        p=0.;v=velocity
        for _ in range(10):v+=(100*(target-p)-20*v)*.01;p+=v*.01
        return p,v
    alpha,gamma=coefficients(0.,1.);beta,eta=coefficients(1.,0.)
    errors=[];shift_errors=[];examples=[]
    for ep in range(min(len(data.lengths),100)):
        length=int(data.lengths[ep]);off=int(data.offsets[ep]);take=min(length-1,30)
        if take<2:continue
        states=np.asarray(data.f['state'][off:off+take+1],dtype=np.float64);actions=np.asarray(data.f['action'][off:off+take+1],dtype=np.float64)
        for t in range(1,take):
            if not np.isfinite(np.r_[states[t-1],states[t],states[t+1],actions[t-1],actions[t],actions[t+1]]).all():continue
            def predicted(action):
                pos=states[t,:2].copy();prevpos=states[t-1,:2]
                previous_target=prevpos+actions[t-1]*100 if s['relative'] else actions[t-1]
                previous_delta=previous_target-prevpos
                previous_velocity=(pos-prevpos-alpha*previous_delta)/beta
                vel=gamma*previous_delta+eta*previous_velocity
                target=pos+action*100 if s['relative'] else action.copy()
                for _ in range(10):vel+=(100*(target-pos)-20*vel)*.01;pos+=vel*.01
                return pos
            err=float(np.max(np.abs(predicted(actions[t])-states[t+1,:2])));shift=float(np.max(np.abs(predicted(actions[t+1])-states[t+1,:2])))
            errors.append(err);shift_errors.append(shift)
            if len(examples)<12:examples.append({'source_episode':ep,'local_t':t,'leaving_action_error_pixels':err,'next_row_action_error_pixels':shift,'raw_action':actions[t].tolist()})
        if len(errors)>=1000:break
    if len(errors)<20:raise RuntimeError('ACTION_ALIGNMENT_INSUFFICIENT_FINITE_ORIGINAL_SAMPLES')
    result={'scope':'original public data temporal/control audit; not research performance','sample_count':len(errors),'expected_leaving_action_row_q95_max_coord_error_pixels':float(np.quantile(errors,.95)),'expected_leaving_action_row_max_error_pixels':float(max(errors)),'next_row_action_q95_error_pixels':float(np.quantile(shift_errors,.95)),'acceptance_q95_pixels':.001,'examples':examples,'formula':'same 10 source PD micro-integrations; p += v*.01 after v += (100*(target-p)-20*v)*.01; kinematic agent; reconstruct initial velocity from previous position and previous known action, supports both original 5D and extended 7D public state','PD_coefficients':{'alpha':alpha,'beta':beta,'gamma':gamma,'eta':eta},'relative':s['relative']}
    write(RUN/record_name,result)
    if enforce and result['expected_leaving_action_row_q95_max_coord_error_pixels']>.001:raise RuntimeError('ACTION_TIME_OR_PHYSICS_SEMANTICS_MISMATCH_NEEDS_REPAIR')
    return result

def semantics():
    data=H5Data();s=compute_action_scaler(data);F=FrozenF();relative=s['relative']
    alignment=original_action_alignment(data,s)
    # Prospective root generator is frozen before any research score/outcome.
    write(RUN/'root_generator.json',{'version':3,'contact_rule':'geometric gap <=2; approach until gap<=1 then hold','noncontact_rule':'approach fixed corner (60,450), accept gap>=35','prefix_steps':40,'prefix_cap':100,'prefix_component_clip':.35,'search_limit_per_stratum':512,'history_control_indices':[30,35,40],'goal':'unaltered official reset goal; not selected using any candidate outcome','seeds':{'engineering':701100,'cal':702000,'dev':703000,'test':704000},'noncontact_seed_offset':10000,'candidate_seed_offset':500000,'candidate_distribution':'Official CEM initial N(0,I), var_scale=1; 4 samples, plus 4 fixed train-block draws; clip in raw physical units','selection_uses_no_F_G_J_or_scores':True})
    eng,rejected=roots_for_split('engineering',6,701100,relative);checks=[];maximum=0.;engtime=time.monotonic()
    for r in eng:
        rng=np.random.default_rng(r['candidate_seed']);raw=np.clip(denorm_actions(rng.standard_normal((1,10)),s)[0],*s['raw_action_clip'])
        prior=None
        for repeat in range(2):
            env,obs,info,pictures=replay_root(r,relative,with_history=True);snapshots=[state_vector(env)];renders=[env.render()];contacts=[physical_snapshot(env)['contacts']];env._u_step_role='engineering_candidate'
            for a in raw:obs,_,_,_,info=env.step(a);snapshots.append(state_vector(env));renders.append(env.render());contacts.append(physical_snapshot(env)['contacts'])
            J=metric(env,obs['state'])['J'];end=physical_snapshot(env);env._u_step_role='engineering_next_probe'
            next_action=np.zeros(2) if relative else np.asarray(env.agent.position)
            for _ in range(5):env.step(next_action);snapshots.append(state_vector(env));renders.append(env.render());contacts.append(physical_snapshot(env)['contacts'])
            now=(np.asarray(snapshots),np.asarray(renders),pictures,J,contacts)
            diff=0. if prior is None else float(np.max(np.abs(now[0]-prior[0])))
            pixels=True if prior is None else bool(np.array_equal(now[1],prior[1]) and np.array_equal(pictures,prior[2]))
            jd=0. if prior is None else abs(J-prior[3]);maximum=max(maximum,jd)
            contact_equal=True if prior is None else contacts_close(contacts,prior[4],1e-6)
            checks.append({'root':r['root'],'source':r['source'],'seed':r['seed'],'branch':repeat,'repeat':repeat,'candidate_source':'engineering_seeded_CEM_initial','action_block':raw.tolist(),'max_state_difference':diff,'pixels_equal':pixels,'contacts_equal':contact_equal,'J':J,'J_repeat_difference':jd,'status':'OK','final_snapshot':end})
            if diff>1e-6 or not pixels or not contact_equal:raise RuntimeError('REPLAY_INCONSISTENT_BEFORE_RESEARCH')
            prior=now;env.close()
    csvwrite(RUN/'replay_check.csv',checks)
    # Real source index table; zero-based local microstep times and preserved block flatten.
    ep=int(np.flatnonzero(data.lengths>=20)[0]);off=int(data.offsets[ep]);index_table=[]
    for k in range(3):index_table.append({'observation_local_index':k*5,'observation_global_row':off+k*5,'paired_action_local_indices':list(range(k*5,k*5+5)),'paired_action_global_rows':list(range(off+k*5,off+k*5+5)),'endpoint_local_index':(k+1)*5})
    semantic={'status':'PASS','strict_missing_keys':F.missing_keys,'strict_unexpected_keys':F.unexpected_keys,'F_frozen':all(not p.requires_grad for p in F.model.parameters()),'history':3,'frame_skip':5,'input_dim':10,'block_shape':[5,2],'index_table_example_source_episode':ep,'index_table':index_table,'flatten_order':s['flatten'],'control':{'relative':relative,'action_clip':s['raw_action_clip'],'control_hz':10,'physics_hz':100,'block_endpoint_seconds':.5,'target_scale':100 if relative else None},'engineering_max_repeat_J_difference':maximum,'delta_J':max(.001,10*maximum),'state_atol':1e-6,'render_rule':'pixel exact','engineering_branch_count':12,'engineering_candidate_control_steps':60,'engineering_extra_next_probe_control_steps':60,'engineering_repeat_wall_seconds':time.monotonic()-engtime,'HDF5_schema':data.schema,'goal_success_position_threshold':20.,'goal_success_angle_threshold':float(np.pi/9),'J':'max(norm(goal[:4]-state[:4])/20,periodic_angle/(pi/9)); official eval_state equivalence asserted on each observation','block_only':'same max with block-only 2D position','latent_source':'official encoder CLS -> official projector, single 192-vector; no repeated spatial pooling','RGB_preprocess':'NHWC uint8 RGB -> float /255 -> ImageNet mean/std -> bilinear antialiased Resize224, original eval.py order','F_no_future_microsteps':True}
    env,_,_=make_env(799001,relative);boundary_cases=0
    for position in [0.,19.999999,20.,20.000001]:
        for angle in [0.,np.pi/9-1e-8,np.pi/9+1e-8,2*np.pi-1e-8]:
            state=np.asarray(env.goal_state).copy();state[0]+=position;state[4]+=angle;metric(env,state);boundary_cases+=1
    env.close();semantic['success_boundary_checks_TEST_ONLY']=boundary_cases;semantic['data_action_alignment']=alignment
    write(RUN/'semantics.json',semantic)
    # All prospective research roots, including test, are selected now using geometry only.
    allroots=[]
    for split,n,base in [('cal',32,702000),('dev',16,703000),('test',64,704000)]:
        roots,rejs=roots_for_split(split,n,base,relative);allroots+=roots;rejected+=rejs
    # Store images privately; public manifest retains full seed/actions/goal and hashes.
    np.savez(WORK/'root_images.npz',history=np.stack([r.pop('history_raw_frames') for r in allroots]),goal=np.stack([r.pop('goal_image') for r in allroots]))
    for r in allroots:r['past_raw_blocks']=np.asarray(r['past_raw_blocks']).tolist()
    write(RUN/'roots_frozen.json',allroots);csvwrite(RUN/'root_manifest.csv',allroots)
    write(RUN/'root_manifest_seal.json',{'at':utc(),'root_count':112,'roots_sha256':sha(RUN/'roots_frozen.json'),'images_sha256':sha(WORK/'root_images.npz'),'generator_sha256':sha(RUN/'root_generator.json'),'selection':'prescoring geometry only; no candidate outcomes or F/G scores','engineering_rejected_count':sum(x['split']=='engineering' for x in rejected)})
    (REPORT/'preflight.md').write_text('# U v3 0A\n\nPASS：真实 strict 加载、CUDA、编码、一步预测、headless PushT 与工程重复通过。\n\n动作/原始时间索引和 scaler 见 semantics.json / action_scaler.json；每个块是五个二维控制动作。J 在每个被评价状态均和固定源码官方 success 比较；没有把 MSE 用作任务指标。\n\n只绕过可选包的 __init__ 导入，未修改物理源码；HDF5 只读 adapter 保留原样本/时间语义，未转 Lance。框架原 4-observation clip 覆盖 20 microsteps；F 使用前三个 leaving blocks，最后未用 future block 不进入 G。\n\n所有实验环境在 EAI/U 内，外部既有环境只读取并复制必要 torch 二进制；未升级原环境、系统 Python、CUDA、驱动或 ROS。工程重复是本机有限检查，不是全域确定性证明。\n')
    data.close();done(RUN/'semantics.json',RUN/'action_scaler.json',RUN/'original_action_alignment.json',RUN/'replay_check.csv',RUN/'root_manifest.csv',RUN/'roots_frozen.json',RUN/'root_manifest_seal.json',WORK/'root_images.npz')

def prepare():
    from sklearn.decomposition import PCA
    from sklearn.neighbors import NearestNeighbors
    data=H5Data();s=load_scaler();all_actions=np.load(WORK/'all_actions.npy',mmap_mode='r')
    # The original asset contains101 trajectories at each of185 exact initial
    # states. Conservatively keep each whole initial-state family in one split;
    # metadata episode IDs alone do not establish independent source ancestry.
    source_states=np.asarray(data.f['state'][:])
    initial_hashes=[hashlib.sha256(source_states[off].tobytes()).hexdigest() for off in data.offsets]
    unique_groups=sorted(set(initial_hashes));group_index={h:i for i,h in enumerate(unique_groups)}
    episode_groups=np.array([group_index[h] for h in initial_hashes],dtype=np.int64)
    rng=np.random.default_rng(270700);family_order=rng.permutation(len(unique_groups));cut1=int(.8*len(family_order));cut2=int(.9*len(family_order))
    families={'train':family_order[:cut1],'val':family_order[cut1:cut2],'audit':family_order[cut2:]}
    groups={split:np.flatnonzero(np.isin(episode_groups,ids)) for split,ids in families.items()};sizes={'train':10000,'val':2000,'audit':6000}
    if any(set(groups[a])&set(groups[b]) for a,b in [('train','val'),('train','audit'),('val','audit')]):raise RuntimeError('SOURCE_SPLIT_LEAK')
    source_rows=[{'source_group':group_index[h],'initial_state_sha256':h,'metadata_episodes':np.flatnonzero(episode_groups==group_index[h]).tolist(),'split':next(split for split,ids in families.items() if group_index[h] in ids)} for h in unique_groups]
    csvwrite(RUN/'source_group_manifest.csv',source_rows)
    records=[];images_indices=[];actions=[];past=[];invalid=0;duplicate_skips=0;seen_inverse_blocks=set()
    for split in ['train','val','audit']:
        counts=np.maximum(data.lengths[groups[split]]-19,0)
        candidates_total=int(counts.sum())
        if candidates_total<sizes[split]:raise RuntimeError('INCONCLUSIVE_INSUFFICIENT_UNIQUE_BLOCKS_'+split)
        eps=np.repeat(groups[split],counts)
        starts=np.concatenate([np.arange(c,dtype=np.int64) for c in counts if c])
        order=rng.permutation(len(starts));selected=0
        for index in order:
            ep=int(eps[index]);start=int(starts[index]);off=int(data.offsets[ep]);block=np.asarray(all_actions[off+start:off+start+15])
            if not np.isfinite(block).all():invalid+=1;continue
            t=start+10;rows=data.window_indices(ep,start).tolist()
            fingerprint=hashlib.sha256(source_states[off+t].tobytes()+source_states[off+t+5].tobytes()+np.asarray(block[10:15],dtype=all_actions.dtype).tobytes()).hexdigest()
            if fingerprint in seen_inverse_blocks:duplicate_skips+=1;continue
            seen_inverse_blocks.add(fingerprint)
            record={'split':split,'source_episode':ep,'source_group':int(episode_groups[ep]),'inverse_block_sha256':fingerprint,'window_start':start,'current_t':t,'history_local_indices':[start,start+5,start+10],'endpoint_local_index':start+15,'action_local_indices':list(range(t,t+5)),'frame_global_rows':rows,'action_block_id':f'episode_{ep}:t_{t}','status':'OK'}
            records.append(record);images_indices.append(rows);actions.append(block[10:15].copy());past.append(block[:10].reshape(2,5,2).copy());selected+=1
            if selected==sizes[split]:break
        if selected!=sizes[split]:raise RuntimeError('INSUFFICIENT_FINITE_BLOCKS_'+split)
    if len({r['action_block_id'] for r in records})!=18000:raise RuntimeError('DUPLICATE_BLOCK_ID')
    csvwrite(RUN/'split_manifest.csv',records)
    actual_sources={split:len({r['source_group'] for r in records if r['split']==split}) for split in groups}
    metadata_sources={split:len({r['source_episode'] for r in records if r['split']==split}) for split in groups}
    if len(seen_inverse_blocks)!=18000:raise RuntimeError('DUPLICATE_OR_MISSING_UNIQUE_INVERSE_TRANSITIONS')
    if any({r['source_group'] for r in records if r['split']==a}&{r['source_group'] for r in records if r['split']==b} for a,b in [('train','val'),('train','audit'),('val','audit')]):raise RuntimeError('SOURCE_FAMILY_SPLIT_LEAK')
    index_array=np.asarray(images_indices,dtype=np.int64);unique,inverse=np.unique(index_array,return_inverse=True);inverse=inverse.reshape(-1,4)
    F=FrozenF();latent_path=WORK/'unique_latents.npy';cursor_path=WORK/'latent_cursor.json';cursor=0
    admission=stable_hash({'rows':unique,'model_sha256':sha(BASE/'models/v3/weights.pt'),'code_hash':os.environ['U_CODE_HASH']})
    if cursor_path.exists():
        saved=json.loads(cursor_path.read_text())
        if saved['admission']!=admission:raise RuntimeError('LATENT_CACHE_RESUME_HASH_MISMATCH')
        cursor=saved['completed_frames'];latents=np.lib.format.open_memmap(latent_path,mode='r+')
    else:latents=np.lib.format.open_memmap(latent_path,mode='w+',dtype=np.float32,shape=(len(unique),192))
    began=time.monotonic()
    for lo in range(cursor,len(unique),64):
        check_time();idx=unique[lo:lo+64];images=data.images(idx)
        latents[lo:lo+len(idx)]=F.encode(images,batch=int(os.environ.get('U_MICROBATCH','64')))
        if (lo//64)%32==0 or lo+len(idx)==len(unique):
            latents.flush();write(cursor_path,{'admission':admission,'completed_frames':lo+len(idx),'total_frames':len(unique)})
            progress('prepare',encoded_frames=lo+len(idx),total_frames=len(unique),frames_per_second=(lo+len(idx)-cursor)/max(time.monotonic()-began,1e-6))
    Z=np.asarray(latents[inverse]);Araw=np.asarray(actions,dtype=np.float64);Praw=np.asarray(past,dtype=np.float64);A=norm_actions(Araw,s);P=norm_actions(Praw,s)
    if not np.isfinite(Z).all() or float(Z[:10000].std(axis=(0,1)).mean())<1e-5:raise RuntimeError('NONFINITE_OR_CONSTANT_TRAIN_LATENTS')
    np.savez(WORK/'dataset.npz',Z=Z,A=A,past=P,raw_actions=Araw,source=np.array([r['source_group'] for r in records]),metadata_episode=np.array([r['source_episode'] for r in records]),window_start=np.array([r['window_start'] for r in records]))
    training=Z[:10000,:3].reshape(-1,192)
    pca=PCA(n_components=16,svd_solver='full');pca.fit(training)
    np.savez(WORK/'pca.npz',mean=pca.mean_,components=pca.components_)
    ls={'mean':training.mean(axis=0),'std':np.maximum(training.std(axis=0,ddof=0),1e-6)}
    np.savez(WORK/'latent_scaler.npz',**ls)
    reference=NearestNeighbors(n_neighbors=1,n_jobs=4).fit(A[:10000]);dist=[]
    for lo in range(12000,18000,128):dist.extend(reference.kneighbors(A[lo:lo+128],return_distance=True)[0][:,0].tolist())
    write(RUN/'support_reference.json',{'definition':'Euclidean nearest training-action-block distance in original F standardized 10-action coordinates; proxy only','fit_split':'IDM-train 10000','reference_split':'offline audit 6000, never used for b training','outside_support_threshold':float(np.quantile(dist,.95)),'reference_q50':float(np.quantile(dist,.5)),'reference_q95':float(np.quantile(dist,.95)),'n_reference_blocks':6000})
    write(RUN/'data_preparation.json',{'status':'PASS','counts':sizes,'source_counts':actual_sources,'metadata_episode_counts':metadata_sources,'total_initial_state_families':len(unique_groups),'source_unit':'Conservative exact initial-state family, all101 trajectories together; underlying collection IDs beyond metadata are unavailable','split_seed':270700,'source_episode_disjoint':True,'source_family_disjoint':True,'all_derived_windows_follow_source':True,'exact_inverse_block_dedup':'SHA256(original current7Dstate +5-control-end7Dstate +raw5x2 action block), global across all three splits; conservative physical-transition identity, no study outcomes','duplicate_inverse_block_candidates_skipped':duplicate_skips,'nonfinite_window_candidates_skipped':invalid,'unique_frames_encoded':len(unique),'latent_cache_bytes':latent_path.stat().st_size,'PCA_fit':'IDM-train historical observations only','PCA_explained_variance_ratio':pca.explained_variance_ratio_.tolist(),'PCA_sha256':sha(WORK/'pca.npz'),'latent_scaler_sha256':sha(WORK/'latent_scaler.npz'),'dataset_tensor_sha256':sha(WORK/'dataset.npz'),'F_pretraining_disclosure':'F was pretrained on this public original distribution, including families held out from G. G train/val/audit remain family-disjoint; online roots use new independent seeds.','encode_elapsed_seconds':time.monotonic()-began})
    write(RUN/'eta.json',{'train':3600,'cal_collect':600,'cal_fit':1200,'score_dev':300,'execute_dev':300,'analyze_dev':300,'seal_test':30,'score_test':600,'execute_test':1200,'analyze_test':300})
    data.close();done(RUN/'source_group_manifest.csv',RUN/'split_manifest.csv',RUN/'data_preparation.json',RUN/'support_reference.json',WORK/'dataset.npz',WORK/'pca.npz',WORK/'latent_scaler.npz')

def training_curves():
    rows=readlines(RUN/'training_progress.jsonl')
    if rows:csvwrite(RUN/'training_curves.csv',rows)

def train():
    from u_train_v3 import condition_numpy,fit,inverse_samples
    data=np.load(WORK/'dataset.npz');Z=data['Z'];A=data['A'];past=data['past'];ls=dict(np.load(WORK/'latent_scaler.npz'))
    metadata=[];models={};eval_results={};constant=A[:10000].mean(axis=0)
    for model_index,(kind,maxsteps) in enumerate([('flow',20000),('mlp',20000),('history',12000),('strong',12000)]):
        name='strong_base' if kind=='strong' else kind
        features=condition_numpy(Z,past,kind,ls)
        model,meta=fit(kind,features[:10000],A[:10000],features[10000:12000],A[10000:12000],name,max_steps=maxsteps,remaining_models=4-model_index)
        metadata.append(meta);models[kind]=model
        eval_results[kind]={}
        for split,lo,hi in [('val',10000,12000),('audit',12000,18000)]:
            predictions=[];pred1=[];sampling_var=[]
            for j in range(lo,hi,128):
                k=min(j+128,hi);noise=np.random.default_rng(270800+j).standard_normal((k-j,4,10)).astype(np.float32)
                out=inverse_samples(model,kind,Z[j:k],past[j:k],ls,noise if kind=='flow' else None)
                if kind=='flow':predictions.append(out.mean(1));pred1.append(out[:,0]);sampling_var.append(out.var(axis=1,ddof=1).mean(axis=1))
                else:predictions.append(out)
            pred=np.concatenate(predictions);result={'mse':float(np.mean((pred-A[lo:hi])**2)),'constant_mse':float(np.mean((constant-A[lo:hi])**2)),'n_blocks':hi-lo}
            if kind=='flow':result.update({'mse_K1':float(np.mean((np.concatenate(pred1)-A[lo:hi])**2)),'mean_sampling_variance_per_coordinate':float(np.concatenate(sampling_var).mean()),'K4_mean_sampling_variance_estimate':float(np.concatenate(sampling_var).mean()/4)})
            eval_results[kind][split]=result
        del model;models.pop(kind,None);torch.cuda.empty_cache();training_curves()
    history_mse=eval_results['history']['val']['mse'];mlp_mse=eval_results['mlp']['val']['mse'];flow_mse=eval_results['flow']['val']['mse'];constant_mse=eval_results['mlp']['val']['constant_mse']
    # Gross fitting sanity only, not a near-unique inverse-MSE threshold.
    finite=all(np.isfinite(v['best_val_mse']) for v in metadata)
    grossly_bad=mlp_mse>1.5*constant_mse or flow_mse>2*max(constant_mse,1e-8)
    status='BASELINE-UNSUPPORTED' if not finite or grossly_bad else 'PASS'
    validity={'status':status,'check_scope':'finite optimization, held-out fitting relative to constant/history controls; thresholds catch grossly broken fitting, never require an almost unique inverse map','gross_failure_rule_frozen_before_training':'MLP val MSE >1.5*constant or flow K4-mean MSE >2*constant, or nonfinite; interpret flow stochastic K1 separately','models':metadata,'evaluations':eval_results,'successor_information_gain_matched_history':history_mse-eval_results['strong']['val']['mse'],'successor_information_gain_mlp_vs_history_unmatched_inputs':history_mse-mlp_mse,'successor_information_gain_flow_vs_history_unmatched_inputs':history_mse-flow_mse,'initial_G_frozen':True,'flow_reference':'4 TransformerEncoder layers, width192, 3 heads; two latent prefix tokens and one noisy-action suffix; prefix cannot attend suffix; beta(1.5,1), one Euler step','ACID_difference':'No official weights; trained <=20k versus paper 200k;10D five-control-step chunks; whole-source split; microbatch64 accumulated to256; single training seed; flow K4 mean added as diagnostic','checkpoints':{name:sha(WORK/f'{name}_best.pt') for name in ['flow','mlp','history','strong_base']},'constant_action':constant.tolist()}
    validity['MSE_units']='standardized training actions; inference G is de-normalized and residual scores use original environment control units'
    write(RUN/'baseline_validity.json',validity);training_curves()
    (REPORT/'baseline_validity.md').write_text('# 初始 G 基线有效性\n\n'+status+'。固定训练 seed 270727；flow/MLP 与历史匹配的加强 G 预训练均实际执行。\n\n```json\n'+json.dumps(jsonable(validity),ensure_ascii=False,indent=2)+'\n```\n\nMSE 是拟合/信息诊断，未要求端点到动作唯一；与 ACID 的结构/更新预算差异已披露。离线 6000 块只用于误差和动作支持，不用于 b 拟合。加强 G 在后续 cal-fit 标签阶段继续训练，总更新不超过 20000。\n')
    if status!='PASS':raise RuntimeError('BASELINE-UNSUPPORTED_AFTER_REGISTERED_FITTING_BUDGET')
    (RUN/'training_curves_initial.csv').write_bytes((RUN/'training_curves.csv').read_bytes())
    done(RUN/'baseline_validity.json',RUN/'training_curves_initial.csv',*[WORK/f'{x}_best.pt' for x in ['flow','mlp','history','strong_base']])

def root_set(split):
    allroots=json.loads((RUN/'roots_frozen.json').read_text());ids=[i for i,r in enumerate(allroots) if r['split']==split]
    with np.load(WORK/'root_images.npz') as z:
        histories=z['history'][ids];goals=z['goal'][ids]
    return [allroots[i] for i in ids],histories,goals

def noise_for(root):return np.random.default_rng(root['candidate_seed']+400000).standard_normal((8,4,10)).astype(np.float32)
def latent_pack(history,endpoint):return np.concatenate([np.broadcast_to(history,(len(endpoint),3,192)),np.asarray(endpoint)[:,None]],axis=1)
def support_flags(A):
    from sklearn.neighbors import NearestNeighbors
    data=np.load(WORK/'dataset.npz');trainA=data['A'][:10000]
    dist=NearestNeighbors(n_neighbors=1,n_jobs=4).fit(trainA).kneighbors(A,return_distance=True)[0][:,0]
    threshold=json.loads((RUN/'support_reference.json').read_text())['outside_support_threshold']
    return dist,dist>threshold
def live_branch(root,Araw,relative,split,candidate):
    env,obs,info=replay_root(root,relative);env._u_step_role='candidate_'+split
    before=physical_snapshot(env)
    for action in Araw:obs,_,_,_,info=env.step(np.asarray(action,dtype=np.float64))
    image=env.render();state=obs['state'].copy();result=metric(env,state);snapshot=physical_snapshot(env);env.close()
    return image,{'root':root['root'],'source':root['source'],'seed':root['seed'],'branch':candidate,'candidate':candidate,'split':split,'status':'OK','state':state.tolist(),'final_snapshot':snapshot,'prefix_snapshot':before,'action_block':np.asarray(Araw).tolist(),**result}

def cal_collect():
    from u_train_v3 import load_probe,inverse_samples
    roots,himgs,goals=root_set('cal');s=load_scaler();F=FrozenF();G=load_probe('flow');ls=dict(np.load(WORK/'latent_scaler.npz'));train_data=np.load(WORK/'dataset.npz');trainraw=train_data['raw_actions'][:10000]
    H=F.encode(himgs.reshape(-1,224,224,3)).reshape(32,3,192);goalz=F.encode(goals)
    allrows=readlines(RUN/'calibration_pairs.jsonl');completed={(r['root'],r['candidate']):r for r in allrows if r.get('status')=='OK'}
    arrays={k:[] for k in ['H','past','A','pred','real','e_real','e_pred','noise','raw_A']}
    scale=action_residual_scale(s)
    for i,root in enumerate(roots):
        check_time();raw,A,meta=candidates(root,trainraw,s);past=norm_actions(np.asarray(root['past_raw_blocks']),s);pred=F.predict(H[i],past,A);noise=noise_for(root)
        gp=inverse_samples(G,'flow',latent_pack(H[i],pred),np.broadcast_to(past,(8,2,10)),ls,noise);ep=(A-gp[:,0])*scale
        frozen={'at':utc(),'split':'cal','root':root['root'],'source':root['source'],'seed':root['seed'],'raw_A':raw,'normalized_A':A,'goal_cost':np.sum((pred-goalz[i])**2,axis=1),'e_pred':ep,'candidate_metadata':meta}
        frozen_hash=stable_hash(frozen);existing=WORK/f'cal_{root["root"]}_freeze.json'
        if not existing.exists():write(existing,{**jsonable(frozen),'hash':frozen_hash})
        else:frozen_hash=json.loads(existing.read_text())['hash']
        images=[];results=[]
        for j in range(8):
            imagepath=WORK/f'cal_{root["root"]}_{j}.npy'
            if (root['root'],j) in completed:
                prior=completed[(root['root'],j)]
                if not imagepath.exists() or sha(imagepath)!=prior['real_image_sha256']:raise RuntimeError('CAL_RESUME_REAL_IMAGE_INVALID')
                images.append(np.load(imagepath));results.append(prior);continue
            physical_path=WORK/f'cal_{root["root"]}_{j}_physical.json'
            if physical_path.exists() and imagepath.exists():
                prior=json.loads(physical_path.read_text())
                if prior['frozen_hash']!=frozen_hash or sha(imagepath)!=prior['real_image_sha256']:raise RuntimeError('CAL_PHYSICAL_RESUME_HASH_INVALID')
                images.append(np.load(imagepath));results.append(prior);continue
            image,result=live_branch(root,raw[j],s['relative'],'cal',j);np.save(imagepath,image);images.append(image)
            result.update({'candidate_source':meta['sources'][j],'frozen_hash':frozen_hash,'frozen_at':json.loads(existing.read_text())['at'],'executed_at':utc(),'real_image_sha256':sha(imagepath),'coordinate_clip_fraction':meta['coordinate_clip_fraction'][j]});results.append(result)
            # Persist every branch before computing labels; true J never used to fit b.
            write(WORK/f'cal_{root["root"]}_{j}_physical.json',result)
        real=F.encode(np.asarray(images));gr=inverse_samples(G,'flow',latent_pack(H[i],real),np.broadcast_to(past,(8,2,10)),ls,noise);er=(A-gr[:,0])*scale
        for j,result in enumerate(results):
            if (root['root'],j) not in completed:
                result.update({'action_normalized':A[j].tolist(),'e_real':er[j].tolist(),'e_pred':ep[j].tolist(),'G_real':denorm_g(gr[j,0],s).tolist(),'G_pred':denorm_g(gp[j,0],s).tolist(),'residual_units':'raw environment control units','d_F':float(np.linalg.norm(pred[j]-real[j]))})
                append(RUN/'calibration_pairs.jsonl',result);completed[(root['root'],j)]=result
        for k,v in [('H',H[i]),('past',past),('A',A),('pred',pred),('real',real),('e_real',er),('e_pred',ep),('noise',noise),('raw_A',raw)]:arrays[k].append(v)
        progress('cal_collect',completed_roots=i+1,target_roots=32);flush_counts(STAGE)
    np.savez(WORK/'cal_arrays.npz',**{k:np.stack(v) for k,v in arrays.items()})
    if len(completed)!=256:raise RuntimeError('CAL_BRANCH_COUNT_INCOMPLETE')
    done(RUN/'calibration_pairs.jsonl',WORK/'cal_arrays.npz')

def cal_fit():
    from sklearn.linear_model import Ridge
    from sklearn.preprocessing import StandardScaler
    from u_train_v3 import condition_numpy,fit
    cal=np.load(WORK/'cal_arrays.npz');pca=dict(np.load(WORK/'pca.npz'));ls=dict(np.load(WORK/'latent_scaler.npz'));data=np.load(WORK/'dataset.npz')
    X=np.stack([b_features(cal['H'][i],cal['past'][i],cal['A'][i],pca) for i in range(32)]);Y=cal['e_real']
    feature_scaler=StandardScaler().fit(X[:24].reshape(192,78));xf=feature_scaler.transform(X[:24].reshape(192,78));xv=feature_scaler.transform(X[24:].reshape(64,78))
    yf=Y[:24].reshape(192,10);yv=Y[24:].reshape(64,10);perm=np.random.default_rng(270701).permutation(24);shuffled=Y[:24][perm].reshape(192,10)
    saved={};selection={};grid=[.01,.1,1.,10.,100.]
    for name,labels in [('ridge',yf),('shuffle',shuffled)]:
        results=[];best=None;besterr=float('inf')
        for alpha in grid:
            model=Ridge(alpha=alpha,fit_intercept=True).fit(xf,labels);error=float(np.mean((model.predict(xv)-yv)**2));results.append({'alpha':alpha,'cal_val_residual_MSE':error})
            if error<besterr:besterr=error;best=model;selection[name]={'alpha':alpha,'cal_val_residual_MSE':error}
        saved[name+'_coef']=best.coef_;saved[name+'_intercept']=best.intercept_;selection[name]['grid']=results
    constant=yf.mean(0);saved.update({'constant':constant,'feature_mean':feature_scaler.mean_,'feature_scale':feature_scaler.scale_})
    np.savez(WORK/'calibrators.npz',**saved)
    write(RUN/'calibration_shuffle.json',{'seed':270701,'unit':'root block; preserve 8 candidate slots/source correspondence','fit_root_order':[f'cal_{i:03d}' for i in range(24)],'permutation':perm.tolist(),'target_root_receives_labels_from':{f'cal_{i:03d}':f'cal_{j:03d}' for i,j in enumerate(perm)},'cal_val_labels':'true unchanged'})
    write(RUN/'calibration_fit.json',{'B2_cal_val_residual_MSE':float(np.mean((constant-yv)**2)),'uncalibrated_cal_val_residual_MSE':float(np.mean(yv**2)),'ridge_selection':selection,'features':78,'PCA_sha256':sha(WORK/'pca.npz'),'feature_scaler_fit_rows':192,'fit_roots':24,'val_roots':8,'feature_source_whitelist':['3 historical official latents PCA16 each','2 previous executed normalized blocks10 each','current candidate10'],'no_actual_endpoint_F_error_J_O_inputs':True,'checkpoint_sha256':sha(WORK/'calibrators.npz')})
    # Strengthened inverse model: same H and previous actions as b, same 192 extra
    # cal-fit true labels. Cal-val only validates; candidate A is target, never input.
    Zcal=np.concatenate([np.broadcast_to(cal['H'][:,None],(32,8,3,192)),cal['real'][:,:,None]],axis=2).reshape(256,4,192)
    Pcal=np.broadcast_to(cal['past'][:,None],(32,8,2,10)).reshape(256,2,10)
    strong_features=condition_numpy(Zcal,Pcal,'strong',ls);Xtrain=condition_numpy(data['Z'][:10000],data['past'][:10000],'strong',ls)
    # Equal total weight for original train and the additional matched cal-fit set.
    copies=52;tx=np.concatenate([Xtrain,np.tile(strong_features[:192],(copies,1))]);ty=np.concatenate([data['A'][:10000],np.tile(cal['A'][:24].reshape(192,10),(copies,1))])
    initial=torch.load(WORK/'strong_base_best.pt',map_location='cpu',weights_only=False)['model']
    strong,meta=fit('strong',tx,ty,strong_features[192:],cal['A'][24:].reshape(64,10),'strong',max_steps=8000,initial=initial,phase='matched_cal_fit',lr=5e-5)
    del strong;torch.cuda.empty_cache();training_curves()
    extra_constant=cal['A'][:24].reshape(192,10).mean(0)
    extra_constant_mse=float(np.mean((cal['A'][24:].reshape(64,10)-extra_constant)**2))
    strong_status='PASS' if meta['best_val_mse']<=1.5*extra_constant_mse else 'BASELINE-UNSUPPORTED'
    write(RUN/'strengthened_G.json',{'status':strong_status,'model':meta,'pretrained_model':'strong_base_best.pt','original_unique_train_blocks':10000,'extra_unique_cal_fit_labels':192,'cal_val_labels_validation_only':64,'cal_fit_oversampling_copies':copies,'approximate_fit_sampling_weights':[.5,.5],'input':'same 3 historical latents and 2 previous action blocks as b; plus real/predicted successor latent, no candidate A','initial_pretrain_update_cap':12000,'additional_update_cap':8000,'combined_update_cap':20000,'checkpoint_sha256':sha(WORK/'strong_best.pt')})
    valid=json.loads((RUN/'strengthened_G.json').read_text());valid.update({'status':strong_status,'cal_val_constant_MSE':extra_constant_mse,'gross_fitting_guard':'best cal-val MSE <=1.5*same-label constant prediction MSE; does not require a unique inverse map'});write(RUN/'strengthened_G.json',valid)
    if strong_status!='PASS':raise RuntimeError('BASELINE-UNSUPPORTED_MATCHED_HISTORY_EXTRA_LABEL_G')
    done(RUN/'calibration_shuffle.json',RUN/'calibration_fit.json',RUN/'strengthened_G.json',RUN/'training_curves.csv',WORK/'calibrators.npz',WORK/'strong_best.pt')

def score(split):
    from u_train_v3 import load_probe,inverse_samples
    realpath=RUN/f'real_transitions_{split}.jsonl'
    if realpath.exists() and realpath.stat().st_size:raise RuntimeError('FUTURE_INFORMATION_EXISTS_BEFORE_SCORE_INVALIDATE_AND_STOP')
    if split=='test' and not (RUN/'test_seal.json').exists():raise RuntimeError('TEST_NOT_SEALED')
    roots,himgs,goals=root_set(split);n=len(roots);F=FrozenF();G=load_probe('flow');strong=load_probe('strong');s=load_scaler();ls=dict(np.load(WORK/'latent_scaler.npz'));pca=dict(np.load(WORK/'pca.npz'));cal=dict(np.load(WORK/'calibrators.npz'));trainraw=np.load(WORK/'dataset.npz')['raw_actions'][:10000]
    H=F.encode(himgs.reshape(-1,224,224,3)).reshape(n,3,192);goalz=F.encode(goals)
    target=RUN/f'frozen_predictions_{split}.jsonl';temp=target.with_name(target.name+'.partial');temp.write_text('')
    arrays={k:[] for k in ['H','past','A','raw_A','pred','G_pred','noise']}
    scale=action_residual_scale(s)
    for i,root in enumerate(roots):
        check_time();raw,A,meta=candidates(root,trainraw,s);past=norm_actions(np.asarray(root['past_raw_blocks']),s);pred=F.predict(H[i],past,A);noise=noise_for(root);Z=latent_pack(H[i],pred);P=np.broadcast_to(past,(8,2,10));gp=inverse_samples(G,'flow',Z,P,ls,noise);gs=inverse_samples(strong,'strong',Z,P,ls)
        features=b_features(H[i],past,A,pca);features=(features-cal['feature_mean'])/cal['feature_scale'];b3=features@cal['ridge_coef'].T+cal['ridge_intercept'];b6=features@cal['shuffle_coef'].T+cal['shuffle_intercept'];ep=(A-gp[:,0])*scale
        inverse={'B1':np.sum(ep**2,1),'B2':np.sum((ep-cal['constant'])**2,1),'B3':np.sum((ep-b3)**2,1),'B4':np.sum(((A-gs)*scale)**2,1),'B5a':np.sum(((A-gp.mean(1))*scale)**2,1),'B5b':np.min(np.sum(((A[:,None]-gp)*scale)**2,2),axis=1),'B6':np.sum((ep-b6)**2,1)}
        goal=np.sum((pred-goalz[i])**2,axis=1);total={'B0':goal};disabled={};weights={}
        for name,cost in inverse.items():
            disable=bool(np.std(goal,ddof=0)<=1e-8 or np.std(cost,ddof=0)<=1e-8);weight=0. if disable else .07*np.std(goal,ddof=0)/max(np.std(cost,ddof=0),1e-8)
            total[name]=goal+weight*cost;disabled[name]=disable;weights[name]=float(weight)
        if not all(np.isfinite(c).all() for c in total.values()):raise RuntimeError('NONFINITE_FROZEN_SCORE')
        selected={name:int(np.argmin(c)) for name,c in total.items()};dists,outside=support_flags(A);at=utc()
        seal={'root':root['root'],'seed':root['seed'],'at':at,'A':A,'raw_A':raw,'goal':goal,'inverse':inverse,'total':total,'selected':selected,'code_hash':os.environ['U_CODE_HASH'],'config_hash':os.environ['U_CONFIG_HASH']};frozen_hash=stable_hash(seal)
        for j in range(8):append(temp,{'split':split,'root':root['root'],'source':root['source'],'seed':root['seed'],'branch':j,'candidate':j,'candidate_source':meta['sources'][j],'training_block_index':meta['training_indices'][j],'action_block':raw[j],'action_normalized':A[j],'goal_cost':float(goal[j]),'inverse_costs':{k:float(v[j]) for k,v in inverse.items()},'total_costs':{k:float(v[j]) for k,v in total.items()},'e_pred':ep[j],'selected_index':selected,'low_variance_disabled':disabled,'adaptive_weights':weights,'coordinate_clip_fraction':meta['coordinate_clip_fraction'][j],'support_nearest_train_distance':float(dists[j]),'outside_reference_support':bool(outside[j]),'frozen_at':at,'frozen_hash':frozen_hash,'code_hash':os.environ['U_CODE_HASH'],'config_hash':os.environ['U_CONFIG_HASH'],'status':'FROZEN_BEFORE_REAL'})
        for k,v in [('H',H[i]),('past',past),('A',A),('raw_A',raw),('pred',pred),('G_pred',gp),('noise',noise)]:arrays[k].append(v)
        progress('score_'+split,completed_roots=i+1,target_roots=n)
    np.savez(WORK/f'predictions_{split}.npz',**{k:np.stack(v) for k,v in arrays.items()});os.replace(temp,target)
    write(RUN/f'score_seal_{split}.json',{'at':utc(),'split':split,'roots':n,'candidate_records':n*8,'frozen_predictions_sha256':sha(target),'private_prediction_cache_sha256':sha(WORK/f'predictions_{split}.npz'),'true_transition_file_existed':False,'allowed_inputs':['frozen F/G/b/scalers','legal H','past actions','candidate A','goal observation','fixed independent noise'],'future_label_file_reads':[],'all_methods_shared_pool':True})
    done(target,RUN/f'score_seal_{split}.json',WORK/f'predictions_{split}.npz')

def execute(split):
    # No F, G or calibrator is loaded here. Only physically execute frozen actions.
    roots,_,_=root_set(split);rootmap={r['root']:r for r in roots};s=load_scaler();frozen=RUN/f'frozen_predictions_{split}.jsonl';seal=json.loads((RUN/f'score_seal_{split}.json').read_text())
    if sha(frozen)!=seal['frozen_predictions_sha256']:raise RuntimeError('FROZEN_SCORE_FILE_CHANGED')
    records=readlines(frozen);target=RUN/f'real_transitions_{split}.jsonl';prior=readlines(target);complete={(r['root'],r['candidate']):r for r in prior if r.get('status')=='OK'}
    images=WORK/f'real_{split}';images.mkdir(exist_ok=True);began=time.monotonic()
    for item in records:
        check_time();key=(item['root'],item['candidate']);imagepath=images/f'{item["root"]}_{item["candidate"]}.npy'
        if key in complete:
            old=complete[key]
            if old['frozen_hash']!=item['frozen_hash'] or not imagepath.exists() or sha(imagepath)!=old['real_image_sha256']:raise RuntimeError('REAL_BRANCH_RESUME_HASH_INVALID')
            continue
        image,result=live_branch(rootmap[item['root']],item['action_block'],s['relative'],split,item['candidate'])
        tmp=imagepath.with_suffix('.tmp')
        with tmp.open('wb') as f:np.save(f,image)
        os.replace(tmp,imagepath)
        result.update({'candidate_source':item['candidate_source'],'selected_index':item['selected_index'],'frozen_at':item['frozen_at'],'frozen_hash':item['frozen_hash'],'executed_at':utc(),'real_image_sha256':sha(imagepath),'failure_reason':None})
        append(target,result);complete[key]=result
        if item['candidate']==7:
            progress('execute_'+split,completed_roots=len(complete)//8,completed_branches=len(complete),target_roots=len(roots),elapsed_seconds=time.monotonic()-began);flush_counts(STAGE)
    if len(complete)!=8*len(roots):raise RuntimeError('PARTIAL_REAL_TRANSITION_COUNT')
    write(RUN/f'execution_timing_{split}.json',{'at':utc(),'completed_roots':len(roots),'branches':len(complete),'elapsed_seconds_this_process':time.monotonic()-began,'branch_seconds_this_process':(time.monotonic()-began)/max(1,len(complete)-len(prior)),'preexisting_valid_branches':len(prior)})
    done(target,RUN/f'execution_timing_{split}.json')

def posthoc(split):
    from u_train_v3 import load_probe,inverse_samples
    roots,_,_=root_set(split);pred=np.load(WORK/f'predictions_{split}.npz');F=FrozenF();G=load_probe('flow');ls=dict(np.load(WORK/'latent_scaler.npz'))
    frozen=readlines(RUN/f'frozen_predictions_{split}.jsonl');real=readlines(RUN/f'real_transitions_{split}.jsonl');realmap={(r['root'],r['candidate']):r for r in real if r.get('status')=='OK'};frozenmap={(r['root'],r['candidate']):r for r in frozen}
    s=load_scaler();scale=action_residual_scale(s)
    diagnostics=[];metrics=[];strata_metrics=[];flips=[];sems=json.loads((RUN/'semantics.json').read_text());delta=sems['delta_J']
    for i,root in enumerate(roots):
        rows=[realmap[(root['root'],j)] for j in range(8)];fr=[frozenmap[(root['root'],j)] for j in range(8)]
        images=[]
        for j,row in enumerate(rows):
            imagepath=WORK/f'real_{split}/{root["root"]}_{j}.npy'
            if row['frozen_hash']!=fr[j]['frozen_hash'] or sha(imagepath)!=row['real_image_sha256']:raise RuntimeError('POSTHOC_JOIN_HASH_INVALID')
            images.append(np.load(imagepath))
        zreal=F.encode(np.asarray(images));H=pred['H'][i];P=pred['past'][i];A=pred['A'][i];noise=pred['noise'][i];gp=pred['G_pred'][i];gr=inverse_samples(G,'flow',latent_pack(H,zreal),np.broadcast_to(P,(8,2,10)),ls,noise)
        er=(A-gr[:,0])*scale;ep=(A-gp[:,0])*scale;dg=(gp[:,0]-gr[:,0])*scale
        if not np.allclose(ep,er-dg,atol=1e-6,rtol=1e-6):raise RuntimeError('RESIDUAL_IDENTITY_FAILED')
        dF=np.linalg.norm(pred['pred'][i]-zreal,axis=1);O=np.sum(dg**2,axis=1);J=np.array([r['J'] for r in rows]);rangeJ=float(J.max()-J.min());denom=max(rangeJ,.05);goal=np.array([r['goal_cost'] for r in fr]);B1=np.array([r['total_costs']['B1'] for r in fr]);selections=fr[0]['selected_index'].copy()
        weight=0. if min(np.std(goal),np.std(O))<=1e-8 else .07*np.std(goal)/np.std(O);selections['O']=int(np.argmin(goal+weight*O))
        for j,row in enumerate(rows):
            diagnostics.append({'split':split,'root':root['root'],'source':root['source'],'seed':root['seed'],'candidate':j,'candidate_source':fr[j]['candidate_source'],'action_block':row['action_block'],'frozen_hash':fr[j]['frozen_hash'],'J':row['J'],'block_only':row['block_only'],'success':row['success'],'e_real':er[j],'e_pred':ep[j],'squared_e_real':float(np.sum(er[j]**2)),'squared_e_pred':float(np.sum(ep[j]**2)),'d_F':float(dF[j]),'d_G':dg[j],'O':float(O[j]),'G_real':denorm_g(gr[j,0],s),'G_pred':denorm_g(gp[j,0],s),'residual_units':'raw environment control units','common_noise_paired':True,'status':'POSTHOC_ONLY'})
        k=selections['B1'];witnesses=[j for j in range(8) if J[k]-J[j]>=delta and goal[j]<=goal[k] and B1[j]>B1[k]]
        if witnesses:
            j=min(witnesses,key=lambda q:J[q]);flips.append({'split':split,'root':root['root'],'source':root['source'],'B1_selected_k':k,'witness_j':j,'J_k':float(J[k]),'J_j':float(J[j]),'delta_J':delta,'goal_k':float(goal[k]),'goal_j':float(goal[j]),'B1_total_k':float(B1[k]),'B1_total_j':float(B1[j]),'e_real_squared_k':float(np.sum(er[k]**2)),'e_real_squared_j':float(np.sum(er[j]**2)),'e_pred_squared_k':float(np.sum(ep[k]**2)),'e_pred_squared_j':float(np.sum(ep[j]**2)),'d_F_k':float(dF[k]),'d_F_j':float(dF[j]),'candidate_source_j':fr[j]['candidate_source'],'candidate_source_k':fr[k]['candidate_source'],'outside_support_j':fr[j]['outside_reference_support'],'outside_support_k':fr[k]['outside_reference_support']})
        for method,index in selections.items():
            row=rows[index];metrics.append({'split':split,'root':root['root'],'source':root['source'],'seed':root['seed'],'stratum':root['stratum'],'method':method,'lambda':0. if method=='B0' else .07,'selected_index':index,'selected_candidate_source':fr[index]['candidate_source'],'R':float((J[index]-J.min())/denom),'J':row['J'],'block_only':row['block_only'],'success':row['success'],'candidate_min_J':float(J.min()),'candidate_max_J':float(J.max()),'candidate_range':rangeJ,'uninformative':rangeJ<=.001,'harmful_B1_flip_root':bool(witnesses),'coordinate_clip_fraction':fr[index]['coordinate_clip_fraction'],'outside_reference_support':fr[index]['outside_reference_support'],'status':'OK'})
            if method!='O':
                for candidate_source in ['official_CEM_initial','training_real_block']:
                    slots=[q for q in range(8) if fr[q]['candidate_source']==candidate_source]
                    chosen=min(slots,key=lambda q:fr[q]['total_costs'][method]);localJ=J[slots]
                    strata_metrics.append({'split':split,'root':root['root'],'source':root['source'],'candidate_source_stratum':candidate_source,'method':method,'selected_index':chosen,'R':float((J[chosen]-localJ.min())/max(float(localJ.max()-localJ.min()),.05)),'J':float(J[chosen]),'block_only':rows[chosen]['block_only'],'success':rows[chosen]['success'],'candidate_range':float(localJ.max()-localJ.min()),'status':'DESCRIPTIVE_SOURCE_RESTRICTION_USING_ORIGINAL_FROZEN_8_POOL_SCORES'})
    path=RUN/f'per_candidate_diagnostics_{split}.jsonl';path.write_text('')
    for row in diagnostics:append(path,row)
    flip_path=RUN/f'harmful_flips_{split}.jsonl';flip_path.write_text('')
    for row in flips:append(flip_path,row)
    csvwrite(RUN/f'per_root_metrics_{split}.csv',metrics)
    csvwrite(RUN/f'per_root_metrics_by_candidate_source_{split}.csv',strata_metrics)
    source_summary={source:{method:{field:float(np.mean([r[field] for r in strata_metrics if r['candidate_source_stratum']==source and r['method']==method])) for field in ['R','J','block_only','success']} for method in ['B0','B1','B2','B3','B4','B5a','B5b','B6']} for source in ['official_CEM_initial','training_real_block']}
    write(RUN/f'source_stratified_{split}.json',{'scope':'descriptive only; full-pool primary roots/candidates remain unchanged; original8-pool normalization retained','methods':source_summary,'independent_roots_per_source_stratum':len(roots)})
    methods={}
    for name in ['B0','B1','B2','B3','B4','B5a','B5b','B6','O']:
        r=[x for x in metrics if x['method']==name];methods[name]={key:float(np.mean([x[key] for x in r])) for key in ['R','J','block_only','success']}
    write(RUN/f'descriptive_{split}.json',{'methods':methods,'independent_roots':len(roots),'independent_sources':len({r['source'] for r in roots}),'candidate_branches':8*len(roots),'informative_roots':sum(not r['uninformative'] for r in metrics if r['method']=='B0'),'harmful_flip_roots':len(flips),'low_variance_disable_counts':{m:sum(fr['low_variance_disabled'][m] for fr in frozen if fr['candidate']==0) for m in ['B1','B2','B3','B4','B5a','B5b','B6']},'candidate_strata':{src:{'n':sum(r['candidate_source']==src for r in frozen),'mean_coordinate_clip_fraction':float(np.mean([r['coordinate_clip_fraction'] for r in frozen if r['candidate_source']==src])),'outside_support_fraction':float(np.mean([r['outside_reference_support'] for r in frozen if r['candidate_source']==src]))} for src in ['official_CEM_initial','training_real_block']},'O_role':'posthoc description only; not strict upper bound or deployable comparator'})
    return metrics,flips,methods

def analyze_dev():
    metrics,flips,methods=posthoc('dev')
    U='B2' if abs(methods['B2']['R']-methods['B3']['R'])<=.01 else min(['B2','B3'],key=lambda x:methods[x]['R'])
    comparator=min(['B0','B1','B4','B5a','B5b'],key=lambda x:methods[x]['R'])
    roots={r['root'] for r in metrics};by={(r['root'],r['method']):r for r in metrics}
    diffs=np.array([by[(root,comparator)]['R']-by[(root,U)]['R'] for root in sorted(roots)])
    informative=sum(not by[(root,'B0')]['uninformative'] for root in roots)
    checkpoints={str(p.relative_to(BASE)):sha(p) for p in [WORK/'flow_best.pt',WORK/'strong_best.pt',WORK/'calibrators.npz',WORK/'pca.npz',WORK/'latent_scaler.npz',RUN/'action_scaler.json',RUN/'semantics.json',RUN/'roots_frozen.json']}
    selection={'at':utc(),'U_star':U,'noncalibrated_comparator':comparator,'rule':'B2 if absolute dev mean R difference B2/B3<=0.01 else lower; lowest dev mean R among B0/B1/B4/B5a/B5b, stable listed tie order','lambda':.07,'methods':methods,'checkpoints_scalers_root_hashes':checkpoints,'no_test_outcomes_read':True,'dev_mean_R_improvement':float(diffs.mean()),'dev_improved_roots':int((diffs>0).sum()),'informative_dev_roots':informative,'harmful_flip_roots':len(flips),'v2_reference_only':{'at_least_12_informative':informative>=12,'at_least_4_flips':len(flips)>=4,'improvement_at_least_.05':float(diffs.mean())>=.05,'at_least_4_improved':int((diffs>0).sum())>=4},'test_gate_requires_positive_dev':False}
    write(RUN/'selection_dev.json',selection)
    (RUN/'per_root_metrics.csv').write_bytes((RUN/'per_root_metrics_dev.csv').read_bytes())
    done(RUN/'selection_dev.json',RUN/'per_root_metrics_dev.csv',RUN/'per_candidate_diagnostics_dev.jsonl',RUN/'harmful_flips_dev.jsonl',RUN/'descriptive_dev.json',RUN/'per_root_metrics_by_candidate_source_dev.csv',RUN/'source_stratified_dev.json')

def seal_test():
    if (RUN/'real_transitions_test.jsonl').exists():raise RuntimeError('TEST_ALREADY_TOUCHED')
    selection=json.loads((RUN/'selection_dev.json').read_text());baseline=json.loads((RUN/'baseline_validity.json').read_text());strong=json.loads((RUN/'strengthened_G.json').read_text());semantic=json.loads((RUN/'semantics.json').read_text())
    if baseline['status']!='PASS' or strong['status']!='PASS' or semantic['status']!='PASS':raise RuntimeError('TECHNICAL_OR_BASELINE_TEST_GATE_FAILED')
    if not all(sha(BASE/k)==v for k,v in selection['checkpoints_scalers_root_hashes'].items()):raise RuntimeError('TEST_INPUT_FREEZE_HASH_MISMATCH')
    # Estimate from actual completed stage wall times, plus a fixed conservative buffer.
    commands=readlines(RUN/'commands.jsonl');durations={}
    for row in commands:
        if row.get('event')=='END' and row.get('exit_code')==0:
            from datetime import datetime
            durations[row['stage']]=(datetime.fromisoformat(row['ended_at_utc'])-datetime.fromisoformat(row['started_at_utc'])).total_seconds()
    measured=sum(durations.get(k,60) for k in ['score_dev','execute_dev','analyze_dev']);estimate=4*measured+180
    remaining=float(os.environ['U_CUTOFF_EPOCH'])-time.time()
    if estimate>remaining:raise RuntimeError('PARTIAL-DEADLINE_TEST_ETA_EXCEEDS_REMAINING')
    roots=json.loads((RUN/'roots_frozen.json').read_text());test=[r for r in roots if r['split']=='test']
    if len(test)!=64:raise RuntimeError('TEST_ROOT_MANIFEST_COUNT_INVALID')
    write(RUN/'test_seal.json',{'at':utc(),'U_star':selection['U_star'],'noncalibrated_comparator':selection['noncalibrated_comparator'],'lambda':.07,'epsilon':1e-8,'inputs':selection['checkpoints_scalers_root_hashes'],'config_hash':os.environ['U_CONFIG_HASH'],'code_hash':os.environ['U_CODE_HASH'],'test_root_order':[r['root'] for r in test],'test_source_order':[r['source'] for r in test],'n_roots':64,'measured_dev_stage_seconds':durations,'estimated_test_seconds':estimate,'remaining_before_report_cutoff_seconds':remaining,'positive_dev_effect_required':False,'test_outcomes_read_before_seal':False})
    eta=json.loads((RUN/'eta.json').read_text());eta.update({'score_test':4*durations.get('score_dev',60)+30,'execute_test':4*durations.get('execute_dev',60)+30,'analyze_test':4*durations.get('analyze_dev',60)+60});write(RUN/'eta.json',eta)
    done(RUN/'test_seal.json')

def bootstrap_difference(rows,U,comparator,field='R',seed=270901):
    roots=sorted({r['root'] for r in rows});by={(r['root'],r['method']):r for r in rows}
    # Online roots have independent environment seeds. Retain clustering if a source repeats.
    sources=sorted({by[(r,U)]['source'] for r in roots});groups={s:[r for r in roots if by[(r,U)]['source']==s] for s in sources}
    differences={r:by[(r,comparator)][field]-by[(r,U)][field] for r in roots};rng=np.random.default_rng(seed);samples=[]
    for _ in range(5000):
        selected=rng.choice(sources,size=len(sources),replace=True);values=[differences[r] for s in selected for r in groups[s]];samples.append(np.mean(values))
    values=np.array(list(differences.values()),dtype=np.float64);ci=np.quantile(samples,[.025,.975])
    return {'point_baseline_minus_U':float(values.mean()),'CI95':ci.tolist(),'bootstrap_replicates':5000,'bootstrap_unit':'source cluster' if len(sources)<len(roots) else 'independent root','n_roots':len(roots),'n_sources':len(sources),'improved_roots':int((values>0).sum()),'worsened_roots':int((values<0).sum()),'paired_differences':differences}

def analyze_test():
    metrics,flips,methods=posthoc('test');seal=json.loads((RUN/'test_seal.json').read_text());U=seal['U_star'];comparator=seal['noncalibrated_comparator'];primary=bootstrap_difference(metrics,U,comparator,'R');rawJ=bootstrap_difference(metrics,U,comparator,'J',270902);block=bootstrap_difference(metrics,U,comparator,'block_only',270903)
    shuffled=bootstrap_difference(metrics,U,'B6') if U=='B3' else None
    desc=json.loads((RUN/'descriptive_test.json').read_text());cal=json.loads((RUN/'calibration_fit.json').read_text())
    statistical=primary['point_baseline_minus_U']>=.05 and primary['CI95'][0]>0 and rawJ['point_baseline_minus_U']>0 and (U!='B3' or shuffled['CI95'][0]>0)
    # No effect-based early stopping. All 64 frozen roots are evaluated first.
    if desc['informative_roots']==0:disposition='INCONCLUSIVE-MEASUREMENT'
    elif statistical and len(flips)>0:disposition='GO-MECHANISM-REVIEW'
    elif primary['CI95'][1]<.05:disposition='NO-GO-CURRENT-SCOPE'
    else:disposition='INCONCLUSIVE'
    by={(r['root'],r['method']):r for r in metrics};roots=sorted({r['root'] for r in metrics});improved=[r for r in roots if by[(r,comparator)]['R']>by[(r,U)]['R']]
    selected_support={'improved_roots':len(improved),'U_supported_and_unclipped_improved_roots':sum(not by[(r,U)]['outside_reference_support'] and by[(r,U)]['coordinate_clip_fraction']==0 for r in improved),'both_selected_supported_unclipped_improved_roots':sum(all(not by[(r,m)]['outside_reference_support'] and by[(r,m)]['coordinate_clip_fraction']==0 for m in [U,comparator]) for r in improved)}
    if disposition=='GO-MECHANISM-REVIEW' and selected_support['both_selected_supported_unclipped_improved_roots']==0:
        disposition='INCONCLUSIVE'
    mechanism=f"{len(flips)} independent test roots have auditable harmful B1 flips. Paired intervention on frozen shared candidate pools is compared to dev-selected {comparator}, with history/extra-label matched B4 and B6 controls. Real-domain residuals, F error, and d_G are recorded per candidate; no causal/off-manifold decomposition is identified. Benefit supported/unclipped selection counts: {selected_support}. Block-only improvement point: {block['point_baseline_minus_U']}."
    summary={'final_status':disposition,'U_star':U,'dev_selected_comparator':comparator,'test_n_roots':64,'test_n_sources':len({r['source'] for r in metrics}),'methods':methods,'primary_comparison':{'U_star':U,'comparator':comparator,'U_mean_R':methods[U]['R'],'baseline_mean_R':methods[comparator]['R'],'U_mean_J':methods[U]['J'],'baseline_mean_J':methods[comparator]['J'],'R_improvement':primary,'raw_J_improvement':rawJ,'block_only_improvement':block},'ridge_vs_shuffle':shuffled,'statistical_primary_gate_pass':statistical,'mechanism_interpretation':mechanism,'harmful_flip_roots':len(flips),'informative_roots':desc['informative_roots'],'selected_support_diagnostic':selected_support,'cal_val_residual_diagnostic':cal,'scientific_claim':'Current predefined short-horizon shared-pool diagnostic only; no novelty, closed-loop, or cross-task claim','single_training_seed':270727,'lambda':.07,'test_effect_not_used_for_sampling_or_stopping':True,'O':'Posthoc only, not deployable or strict upper bound','limitations':['One initial flow training seed','Endpoint inverse mapping can be nonunique','PCA16 may discard conditional bias information','F pretrained on original public distribution','Nearest-action support is a proxy','Official reset goals may be difficult in five control steps; uninformative pools retained'],'no_additional_experiments_after_this':True}
    write(RUN/'scientific_summary.json',summary)
    dev=list(csv.DictReader((RUN/'per_root_metrics_dev.csv').open()));test=list(csv.DictReader((RUN/'per_root_metrics_test.csv').open()));csvwrite(RUN/'per_root_metrics.csv',dev+test,fields=list(dev[0]))
    (REPORT/'limitations.md').write_text('# 局限\n\n'+('\n'.join('- '+x for x in summary['limitations']))+'\n\n后验 d_F/d_G 和恒等式不构成因果分解。O 非部署评分或严格上界。没有 U1、Cube、额外容量 sweep 或测试后补采。完整精度逐 root / candidate 记录独立保存，未运行项用 null/NOT_RUN。\n')
    done(RUN/'scientific_summary.json',RUN/'per_root_metrics_test.csv',RUN/'per_root_metrics.csv',RUN/'per_candidate_diagnostics_test.jsonl',RUN/'harmful_flips_test.jsonl',RUN/'descriptive_test.json')

def main():
    global STAGE
    p=argparse.ArgumentParser();p.add_argument('--run-id',required=True);p.add_argument('--stage',required=True);a=p.parse_args();STAGE=a.stage
    if a.run_id!=CFG['run_id']:raise RuntimeError('RUN_ID_CONFIG_MISMATCH')
    mapping={'assets':assets,'decompress':decompress,'semantics':semantics,'prepare':prepare,'train':train,'cal_collect':cal_collect,'cal_fit':cal_fit,'score_dev':lambda:score('dev'),'execute_dev':lambda:execute('dev'),'analyze_dev':analyze_dev,'seal_test':seal_test,'score_test':lambda:score('test'),'execute_test':lambda:execute('test'),'analyze_test':analyze_test}
    start=time.monotonic()
    try:mapping[STAGE]()
    finally:
        flush_counts(STAGE);progress(STAGE,elapsed_seconds=time.monotonic()-start,process_exiting=True)
if __name__=='__main__':main()
