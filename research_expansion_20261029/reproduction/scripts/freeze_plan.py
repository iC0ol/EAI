import json,time,math,hashlib
from common import ROOT,read_json,atomic_json,utc,sha
from experiment_lib import np,Rotation
def main():
    assert not (ROOT/'frozen_training_plan.json').exists(),'training plan already frozen'
    smoke=read_json(ROOT/'results/smoke_throughput.json');status=read_json(ROOT/'status.json');run=read_json(ROOT/'run.json')
    rows=[json.loads(x) for x in (ROOT/'logs/training_steps.jsonl').read_text().splitlines()]
    steady=sum(x['seconds'] for x in rows[6:])/10
    per_epoch=steady+0.05 # validation every 10 epochs + checkpoint/hash every100 amortization and startup reserve
    available_gpu=8*3600-status['gpu_allocation_seconds'];eval_reserve=3600;extra_reserve=600
    train_available=min(available_gpu-eval_reserve-extra_reserve,run['published_epoch']+10*3600-time.time())
    official=20001;safe_per_epoch=per_epoch*1.2
    K=min(official,int(train_available/safe_per_epoch)+smoke['epochs_completed'])
    assert K>=smoke['epochs_completed']
    estimateC=max(0,K-smoke['epochs_completed'])*per_epoch
    plan={'frozen_utc':utc(),'protocol_sha256':sha(ROOT/'PROTOCOL.md'),'before_formal_test':True,'C_target_epochs':K,'C_target_updates':3*K,'updates_per_epoch':3,'batch_schedule':[70,70,60],'effective_batch':70,'training_seed':0,'official_target_epochs':20001,'official_target_updates':60003,'C_evidence_target':'official training count, single seed' if K==official else 'budget-limited diagnostic','U_state':'NOT_RUN','U_reason':'Two full equal-budget ACT runs exceed measured safe 8GPUh budget. C-only prioritizes the same-model primary contrast. No short U is trained.','U_C_system_comparisons':'NOT_RUN','measured_steady_epoch_seconds':steady,'estimated_epoch_seconds_with_overheads':per_epoch,'throughput_margin_multiplier':1.2,'C_estimate_seconds':estimateC,'two_model_conservative_estimate_seconds':2*K*per_epoch,'remaining_gpu_seconds_at_freeze':available_gpu,'evaluation_gpu_reserve_seconds':eval_reserve,'engineering_gpu_reserve_seconds':extra_reserve,'training_stage_stop_epoch':time.time()+train_available,'train_selection':'fixed final update checkpoint; no test model selection; source in-training test rollouts disabled','validation':'independent demos200..209, train camera pool only','sampler':'independent torch.Generator(seed0), persisted permutations and cursor; differs in RNG stream from source DataLoader but same sampling design','smoke_included_in_C_updates':True,'configuration_sha256':sha(ROOT/'manifests/C_config.json'),'primary':'C-persistent-10 minus C-iid-10 paired success difference','significance':'paired root bootstrap 95%, seed20261029; 20pp is an investment threshold, not equivalence margin','official_paper_numerical_reproduction':False}
    posesdir=ROOT/'vendor/kyc/policy_robosuite/camera_poses';train=read_json(posesdir/'train_cameras.json');test=read_json(posesdir/'test_cameras.json');A=np.asarray(train['poses']);B=np.asarray(test['poses']);assert len(B)>=82 and A.shape[1:]==(4,4) and B.shape[1:]==(4,4)
    rng=np.random.default_rng(20261029);center=np.array(test['config']['workspace_center']);roots=[]
    for split,seeds,indices in [('test',range(5000,5050),range(50)),('dev',range(1000,1032),range(50,82))]:
        for seed,idx in zip(seeds,indices):
            T=B[idx];overlap=bool(np.any(np.max(np.abs(A-T),axis=(1,2))<1e-10));assert not overlap,'test/train camera overlap requires recorded pre-run replacement'
            axis=rng.normal(size=3);axis/=np.linalg.norm(axis);iid=rng.normal(size=(5,3));iid/=np.linalg.norm(iid,axis=1)[:,None];iid[0]=axis
            initial_sign=int(rng.choice([-1,1]));sign=initial_sign
            p=T[:3,3]-center;az=np.rad2deg(np.arctan2(p[1],p[0]));half=test['config']['azimuth_range']/2
            if not -half<=az+sign*10<=half:sign=-sign
            assert -half<=az+sign*10<=half
            Q=Rotation.from_rotvec([0,0,np.deg2rad(sign*10)]).as_matrix();newpos=center+Q@p;forward=center-newpos;forward/=np.linalg.norm(forward);right=np.cross(forward,[0,0,1.]);right/=np.linalg.norm(right);up=np.cross(right,forward)
            Tp=np.eye(4);Tp[:3,:3]=np.stack([right,up,-forward],axis=1);Tp[:3,3]=newpos
            nominal=(center-T[:3,3]);nominal/=np.linalg.norm(nominal)
            roots.append({'split':split,'root_id':seed,'env_seed':seed,'official_camera_index':idx,'T':T.tolist(),'T_moved':Tp.tolist(),'persistent_axis':axis.tolist(),'iid_axes':iid.tolist(),'first_query_axis_matched':True,'move_azimuth_degrees':sign*10,'initial_random_sign':initial_sign,'geometry_sign_reversed_at_domain_edge':sign!=initial_sign,'train_camera_overlap':overlap,'original_axis_vs_nominal_target_degrees':float(np.rad2deg(np.arccos(np.clip(np.dot(-T[:3,2],nominal),-1,1)))),'actual_moved_rotation_degrees':float(np.rad2deg(Rotation.from_matrix(Tp[:3,:3]@T[:3,:3].T).magnitude()))})
    manifest={'frozen_utc':utc(),'rng_seed':20261029,'train_pose_sha256':sha(posesdir/'train_cameras.json'),'test_pose_sha256':sha(posesdir/'test_cameras.json'),'root_unit':'independent state-camera initialization, paired across treatments','noise':'uniform spherical axis, fixed 5 or10deg world left rotation, position unchanged; IID resampled once per 30-action query','move_rule':'position orbit +/-10deg about official nominal workspace_center, same radius/elevation; new camera looks at that nominal center. Source poses have additional target jitter; actual orientation change separately recorded. Sign reversed only before outcomes if needed to remain in official azimuth domain.','roots':roots}
    atomic_json(ROOT/'manifests/frozen_roots.json',manifest);plan['root_manifest_sha256']=sha(ROOT/'manifests/frozen_roots.json');atomic_json(ROOT/'frozen_training_plan.json',plan)
    print(json.dumps(plan,ensure_ascii=False,indent=2),flush=True)
    repairs=read_json(ROOT/'repairs.json');repairs[0].update(state='ACCEPTED_FOR_INITIAL_ROOT_RESTORE',acceptance='results/semantics/initial_restore_check.json; exact zero pixel difference, 10/10 expert replays; poststate restore issue retained as a limitation');atomic_json(ROOT/'repairs.json',repairs)
if __name__=='__main__':main()
