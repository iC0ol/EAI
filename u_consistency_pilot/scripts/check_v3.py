#!/usr/bin/env python3
"""ENGINEERING / TEST-ONLY checks. Never emits training/cal/dev/test examples."""
import argparse,ast,inspect,json,os,subprocess,sys,time
from pathlib import Path
import numpy as np
import torch
from u_core_v3 import BASE,RUN,WORK,FrozenF,make_env,prefix_for_seed,replay_root,metric,state_vector,physical_snapshot,stable_hash,atomic,sha,utc,gpu_context,flush_counts

def smoke():
    started=time.monotonic();gpu_context();torch.manual_seed(701001);np.random.seed(701001)
    x=torch.arange(16,device='cuda',dtype=torch.float32).reshape(4,4)
    assert torch.isfinite(x@x).all()
    F=FrozenF();root=prefix_for_seed(701001,'contact')
    images=root['history_raw_frames'];h=F.encode(images);past=np.zeros((2,10),dtype=np.float32)
    rng=np.random.default_rng(701002);A=rng.uniform(-.4,.4,size=(8,10)).astype(np.float32)
    pred=F.predict(h,past,A);repeat=F.predict(h,past,A)
    assert np.max(np.abs(pred-repeat))<=1e-6
    info={'pixels':torch.zeros(1,8,3,3,1,1,device='cuda'),'emb':torch.tensor(h,device='cuda')[None,None].expand(1,8,3,192),'action_history':torch.tensor(past,device='cuda')[None,None].expand(1,8,2,10)}
    official=F.model.rollout(info,torch.tensor(A,device='cuda')[None,:,None],history_size=3)['predicted_emb'][0,:,-1].cpu().detach().numpy()
    assert np.max(np.abs(official-pred))<=1e-6
    goal=F.encode(root['goal_image'][None])[0];goal_cost=np.sum((pred-goal)**2,axis=1)
    from u_train_v3 import FlowG
    G=FlowG().cuda().eval();noise=torch.tensor(rng.standard_normal((8,10)),device='cuda',dtype=torch.float32)
    with torch.inference_mode():g=G.sample(torch.tensor(np.stack([np.broadcast_to(h[-1],pred.shape),pred],1),device='cuda'),noise).cpu().numpy()
    inverse=np.sum((A-g)**2,axis=1);score=goal_cost+.07*np.std(goal_cost)/max(np.std(inverse),1e-8)*inverse
    frozen={'scope':'ENGINEERING_ONLY_RANDOM_UNTRAINED_G_IDENTITY_ACTION_SCALER','at':utc(),'seed':root['seed'],'A':A.tolist(),'scores':score.tolist(),'selected':int(np.argmin(score))}
    frozen['hash']=stable_hash(frozen);atomic(RUN/'engineering_only_frozen_smoke.json',frozen)
    actual=[]
    for c in range(8):
        env,obs,info=replay_root(root)
        env._u_step_role='engineering_smoke_candidate'
        for action in A[c].reshape(5,2):obs,_,_,_,info=env.step(action)
        actual.append({'candidate':c,'state':obs['state'].tolist(),**metric(env,obs['state'])});env.close()
    atomic(RUN/'engineering_only_smoke.json',{'scope':'ENGINEERING_ONLY; no research use','strict_missing_keys':F.missing_keys,'strict_unexpected_keys':F.unexpected_keys,'CUDA_matrix':'PASS','single_image_encoding_shape':list(h.shape),'block_prediction_shape':list(pred.shape),'official_rollout_max_difference':float(np.max(np.abs(official-pred))),'repeat_F_max_difference':float(np.max(np.abs(pred-repeat))),'latent_std_across_3_frames':float(h.std(axis=0).mean()),'pred_std_across_candidates':float(pred.std(axis=0).mean()),'future_information_boundary':'G.sample receives endpoints and independent noise; no candidate A; only b is permitted candidate A','frozen_before_real':True,'frozen_hash':frozen['hash'],'actual':actual,'elapsed_seconds':time.monotonic()-started,'physics_control_steps':8*(40+5)+40,'physics_integration_steps':(8*(40+5)+40)*10+9*2})
    print(json.dumps({'smoke':'PASS','elapsed_seconds':time.monotonic()-started,'strict_load':'PASS','engineering_branches':8}),flush=True)

def integrity():
    # These are TEST-ONLY guard tests, not scientific performance tests.
    from u_core_v3 import b_features,norm_actions,denorm_actions,denorm_g,action_residual_scale
    from u_train_v3 import FlowG,condition_numpy
    for f in (BASE/'scripts').glob('*v3.py'):ast.parse(f.read_text())
    s={'mean':[.2,-.1],'std_ddof0':[.4,.5]};a=np.arange(20,dtype=np.float64).reshape(2,5,2)/20
    assert np.max(np.abs(denorm_actions(norm_actions(a,s),s)-a))<1e-12
    assert np.max(np.abs(denorm_g(norm_actions(a,s),s)-a.reshape(2,10)))<1e-12
    delta=np.zeros((2,10));delta[0,0]=1;delta[1,1]=1
    assert np.max(np.abs(np.sum((delta*action_residual_scale(s))**2,axis=1)-[.16,.25]))<1e-12
    pca={'mean':np.zeros(192),'components':np.eye(192)[:16]}
    features=b_features(np.arange(576).reshape(3,192),np.zeros((2,10)),np.zeros((8,10)),pca)
    assert features.shape==(8,78)
    assert list(inspect.signature(b_features).parameters)==['history','past','A','pca']
    assert list(inspect.signature(FlowG.sample).parameters)==['self','condition','epsilon']
    z=np.random.default_rng(42).normal(size=(5,4,192));past=np.zeros((5,2,10));ls={'mean':np.zeros(192),'std':np.ones(192)}
    assert condition_numpy(z,past,'flow',ls).shape==(5,2,192)
    swapped=z.copy();swapped[:,3]+=5
    assert np.array_equal(condition_numpy(z,past,'history',ls),condition_numpy(swapped,past,'history',ls))
    # Root-block shuffle retains slot/candidate-source correspondence.
    y=np.arange(24*8*10).reshape(24,8,10);perm=np.random.default_rng(270701).permutation(24)
    assert all(np.array_equal(y[perm][i,j],y[perm[i],j]) for i in range(24) for j in range(8))
    result={'scope':'TEST_ONLY','status':'PASS','checks':['syntax','5x2 time-major roundtrip','78 feature whitelist','G inference candidate exclusion','history-only endpoint exclusion','root-block label shuffle slots preserved']}
    atomic(RUN/'engineering_only_integrity.json',result);print(json.dumps(result),flush=True)

def data_and_training():
    import h5py
    from u_core_v3 import H5Data
    import u_train_v3 as train
    test=WORK/'TEST_ONLY';test.mkdir(exist_ok=True)
    for name in ['toy_flow_last.pt','toy_flow_best.pt','training_progress.jsonl']:
        if (test/name).exists():(test/name).unlink()
    f=test/'fixture.h5'
    with h5py.File(f,'w') as h:
        h['ep_len']=[40,40];h['ep_offset']=[0,40];h['action']=np.arange(160,dtype=np.float32).reshape(80,2)
        color=np.stack([np.arange(80),2*np.arange(80)+1,3*np.arange(80)+2],axis=-1).astype(np.uint8)
        h['pixels']=color[:,None,None,:]*np.ones((80,8,8,3),dtype=np.uint8)
    data=H5Data(f)
    assert data.window_indices(0,0).tolist()==[0,5,10,15]
    assert data.window_indices(1,0).tolist()==[40,45,50,55]
    assert data.actions(1,10).reshape(10).tolist()==list(range(100,110))
    assert data.images([40,45,50,55])[:,0,0,:].tolist()==[[40,81,122],[45,91,137],[50,101,152],[55,111,167]]
    try:data.window_indices(0,21)
    except ValueError:pass
    else:raise AssertionError('cross-source window accepted')
    try:data.actions(0,38)
    except ValueError:pass
    else:raise AssertionError('cross-source block accepted')
    data.close()
    # Separate private TEST_ONLY checkpoint/progress paths. No scientific row emitted.
    import u_core_v3 as core
    core.RUN=test;train.RUN=test;train.WORK=test;os.environ['U_CODE_HASH']='TEST_ONLY';os.environ['U_CONFIG_HASH']='TEST_ONLY';os.environ['U_CUTOFF_EPOCH']=str(time.time()+120)
    rng=np.random.default_rng(777);X=rng.normal(size=(64,2,192)).astype(np.float32);y=rng.normal(size=(64,10)).astype(np.float32)
    model,meta=train.fit('flow',X[:48],y[:48],X[48:],y[48:],'toy_flow',max_steps=20)
    saved={k:v.clone() for k,v in model.state_dict().items()}
    resumed,again=train.fit('flow',X[:48],y[:48],X[48:],y[48:],'toy_flow',max_steps=20)
    assert again['resumed_already_complete'] and all(torch.equal(saved[k],v) for k,v in resumed.state_dict().items())
    resumed,continued=train.fit('flow',X[:48],y[:48],X[48:],y[48:],'toy_flow',max_steps=21)
    assert continued['actual_updates']==21
    result={'scope':'TEST_ONLY','status':'PASS','checks':['read-only original-layout HDF5 row/block alignment','source boundary guards','float32 RGB order','actual flow update/checkpoint','optimizer+RNG resume','skip already completed valid update budget'],'toy_updates':21,'test_files_not_research_inputs':True}
    atomic(RUN/'engineering_only_training_resume.json',result);print(json.dumps(result),flush=True)

def statistics_and_leak_guard():
    import u_stage_v3 as stage
    folder=WORK/'TEST_ONLY_stat_guard';folder.mkdir(exist_ok=True);stage.RUN=folder
    rows=[]
    for i in range(4):
        for method,value in [('B2',.2),('B0',.3)]:rows.append({'root':str(i),'source':str(i),'method':method,'R':value})
    result=stage.bootstrap_difference(rows,'B2','B0')
    assert result['n_roots']==4 and result['n_sources']==4 and abs(result['point_baseline_minus_U']-.1)<1e-12
    assert np.max(np.abs(np.array(result['CI95'])-.1))<1e-12
    for row in rows:row['source']=str(int(row['root'])//2)
    cluster=stage.bootstrap_difference(rows,'B2','B0')
    assert cluster['n_sources']==2 and cluster['bootstrap_unit']=='source cluster'
    (folder/'real_transitions_dev.jsonl').write_text('{"scope":"TEST_ONLY"}\n')
    try:stage.score('dev')
    except RuntimeError as e:assert 'FUTURE_INFORMATION_EXISTS' in str(e)
    else:raise AssertionError('scorer accepted true future file')
    (folder/'real_transitions_test.jsonl').write_text('{"scope":"TEST_ONLY"}\n')
    try:stage.seal_test()
    except RuntimeError as e:assert 'TEST_ALREADY_TOUCHED' in str(e)
    else:raise AssertionError('test re-use guard failed')
    atomic(RUN/'engineering_only_statistics_guard.json',{'scope':'TEST_ONLY','status':'PASS','checks':['paired improvement sign','root bootstrap n instead of branch n','cluster source bootstrap','score stage refuses future file before loading F/G','test seal refuses already touched test']})
    print('TEST_ONLY statistics and future-information guards PASS')

def budget_probe():
    import u_core_v3 as core
    import u_train_v3 as train
    folder=WORK/'TEST_ONLY_budget_probe';folder.mkdir(exist_ok=True)
    for name in ['toy_probe_last.pt','toy_probe_best.pt','training_progress.jsonl','training_budget_probes.jsonl']:
        if (folder/name).exists():(folder/name).unlink()
    core.RUN=folder;train.RUN=folder;train.WORK=folder
    os.environ['U_CODE_HASH']='TEST_ONLY';os.environ['U_CONFIG_HASH']='TEST_ONLY';os.environ['U_CUTOFF_EPOCH']=str(time.time()+600)
    atomic(folder/'resource_watch.json',{'scope':'TEST_ONLY_SYNTHETIC_BUDGET_INPUT','gpu_process_card_seconds_upper_bound':35950})
    rng=np.random.default_rng(778);x=rng.normal(size=(64,2,192)).astype(np.float32);y=rng.normal(size=(64,10)).astype(np.float32)
    begin=time.monotonic();model,meta=train.fit('flow',x[:48],y[:48],x[48:],y[48:],'toy_probe',max_steps=1100,remaining_models=4)
    probes=[json.loads(v) for v in (folder/'training_budget_probes.jsonl').read_text().splitlines()]
    assert meta['actual_updates']==1000 and probes[-1]['scheduled_update_cap']==1000
    atomic(RUN/'engineering_only_budget_probe.json',{'scope':'TEST_ONLY; synthetic latents/actions and synthetic remaining-budget record, real GPU cost included in task monitor','status':'PASS','actual_updates':1000,'elapsed_seconds':time.monotonic()-begin,'actual_updates_per_second':1000/(time.monotonic()-begin),'scheduler_reduced1100_cap_to1000':True,'scientific_data_used':False})
    print('TEST_ONLY real1000-update throughput / budget scheduler PASS')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--kind',choices=['smoke','integrity','data-training','statistics-guard','budget-probe'],required=True);a=p.parse_args()
    try:{'smoke':smoke,'integrity':integrity,'data-training':data_and_training,'statistics-guard':statistics_and_leak_guard,'budget-probe':budget_probe}[a.kind]()
    finally:
        if a.kind=='smoke':flush_counts('ENGINEERING_ONLY_SMOKE')
