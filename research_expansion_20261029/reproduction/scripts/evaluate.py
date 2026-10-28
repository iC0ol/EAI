"""Fixed C-only dev gate and paired test evaluator; labels never enter policy input."""
import argparse,signal,time,json,hashlib,gc,os
from common import ROOT,atomic_json,read_json,append_json,utc,sha
from experiment_lib import *
from models.act import ACTPolicy
from cam_embedding import PluckerEmbedder
from PIL import Image
STOP=False
CONDITIONS=['C-clean','C-persistent-5','C-iid-5','C-persistent-10','C-iid-10','C-moved-correct','C-moved-stale']
def stopping(sig,frame):
    global STOP
    STOP=True
def jsonlines(p):return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []
def digest_array(a):return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()
def snapshot(env,root):
    d=ROOT/'root_states'/root['split']/str(root['root_id']);d.mkdir(parents=True,exist_ok=True)
    if not (d/'manifest.json').exists():
        xml=env.model.get_xml();(d/'model.xml').write_text(xml);np.save(d/'state.npy',env.sim.get_state().flatten());torch.save(rng_state(),d/'rng.pt')
        g=env.sim.model.geom_name2id(env.cube.contact_geoms[0])
        atomic_json(d/'manifest.json',{'utc':utc(),'root_id':root['root_id'],'env_seed':root['env_seed'],'xml_sha256':sha(d/'model.xml'),'state_sha256':sha(d/'state.npy'),'rng_sha256':sha(d/'rng.pt'),'cube_geom_size':env.sim.model.geom_size[g].tolist(),'state_shape':list(np.load(d/'state.npy').shape)})
    m=read_json(d/'manifest.json');assert sha(d/'model.xml')==m['xml_sha256'] and sha(d/'state.npy')==m['state_sha256']
    return {'dir':d,'xml':(d/'model.xml').read_text(),'state':np.load(d/'state.npy'),'rng':torch.load(d/'rng.pt',weights_only=False,map_location='cpu'),'manifest':m}
def reset_root(env,snap,root,T):
    env.reset_from_xml_string(snap['xml']);env.sim.set_state_from_flattened(snap['state']);env.sim.forward();env.set_init_action();restore_rng(snap['rng']);camera_pose(env,T)
def metadata(root,condition,query):
    T=np.array(root['T']);Tp=np.array(root['T_moved'])
    if condition=='C-moved-correct':return Tp
    if condition=='C-moved-stale' or condition=='C-clean':return T
    kind,angle=condition.split('-')[1:];angle=int(angle);axis=np.array(root['persistent_axis'] if kind=='persistent' else root['iid_axes'][query]);T[:3,:3]=Rotation.from_rotvec(np.deg2rad(angle)*axis).as_matrix()@T[:3,:3];return T
def predict(policy,data,stats):
    with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16):out=policy(clone_input(data))[0].float().cpu().numpy()
    return out*np.asarray(stats['action_std'])+np.asarray(stats['action_mean'])
def fixed_observation_diagnostic(policy,embedder,env,snap,root,stats,split='dev'):
    T=np.array(root['T']);reset_root(env,snap,root,T);rgb=render(env,T);K=intrinsics(env);base=policy_input(rgb,T,K,stats,embedder,True);clean=predict(policy,base,stats);chunks={'clean':clean};metrics={}
    for label in ['persistent-5','persistent-10','zero','shuffle']:
        if label in ['zero','shuffle']:
            data=clone_input(base)
            if label=='zero':data['image'][:,:,3:]=0
            else:
                gen=torch.Generator(device='cuda').manual_seed(20261029+root['root_id']);perm=torch.randperm(256*256,generator=gen,device='cuda');ray=data['image'][:,:,3:].reshape(1,1,6,-1);data['image'][:,:,3:]=ray[:,:,:,perm].reshape(1,1,6,256,256)
        else:data=policy_input(rgb,metadata(root,'C-'+label,0),K,stats,embedder,True)
        raw=predict(policy,data,stats);delta=raw-clean;chunks[label]=raw
        metrics[label]={'raw_chunk_max_abs_delta':float(np.max(np.abs(delta))),'first_translation_delta_xyz_m':delta[0,:3].tolist(),'first_rotation_delta_axisangle_components_rad':delta[0,3:6].tolist(),'first_gripper_delta':float(delta[0,6]),'chunk_accumulated_translation_delta_xyz_m':delta[:,:3].sum(0).tolist(),'chunk_accumulated_rotation_delta_axisangle_components_rad':delta[:,3:6].sum(0).tolist(),'translation_delta_l2_over_chunk':float(np.linalg.norm(delta[:,:3])),'rotation_delta_l2_over_chunk':float(np.linalg.norm(delta[:,3:6]))}
    path=ROOT/'results/dev_fixed_chunks'/f"{root['root_id']}.npz";path.parent.mkdir(exist_ok=True);np.savez_compressed(path,**chunks)
    row={'utc':utc(),'root_id':root['root_id'],'fixed_RGB_sha256':digest_array(rgb),'metrics':metrics,'raw_chunks_path':str(path.relative_to(ROOT)),'raw_chunks_sha256':sha(path),'interpretation':'same observation and fixed model/RNG; action differences are not task success differences'}
    append_json(ROOT/'results/dev_fixed_observation.jsonl',row)
    return rgb,K,base,clean
def interface_negative(U,embedder,rgb,K,root,stats):
    # In the RGB-only architecture the backbone slices image[:3]; direct extrinsic tokens are zero in both official configs.
    a=policy_input(rgb,np.array(root['T']),K,stats,embedder,True);b=policy_input(rgb,metadata(root,'C-persistent-10',0),K,stats,embedder,True)
    x=predict(U,a,stats);y=predict(U,b,stats);ok=bool(np.allclose(x,y,atol=1e-7,rtol=1e-7))
    r={'utc':utc(),'allclose':ok,'max_abs_raw_action_difference':float(np.max(np.abs(x-y))),'initialization':'seed0 official U architecture, no optimizer updates and no U rollouts','scope':'interface invariance only, not a learned U baseline','same_RGB':True,'metadata_perturbation':'same raymap interface; extrinsic tokens remain zero per use_cam_pose=False'}
    atomic_json(ROOT/'results/U_metadata_negative_control.json',r);assert ok,'RGB-only metadata interface failed'
def rollout(policy,embedder,env,snap,root,condition,stats,tag=None):
    if STOP:raise InterruptedError('budget/termination signal')
    Tactual=np.array(root['T_moved'] if 'moved' in condition else root['T']);reset_root(env,snap,root,Tactual);K=intrinsics(env)
    first=render(env,Tactual);hashrgb=digest_array(first);key='moved_RGB' if 'moved' in condition else 'clean_RGB';m=snap['manifest'];expected=m.get(key)
    if expected is not None:assert expected==hashrgb,'paired root initial RGB mismatch'
    else:m[key]=hashrgb;atomic_json(snap['dir']/'manifest.json',m)
    runlabel=tag or condition;prefix=f"{root['split']}_{root['root_id']}_{runlabel}";tracedir=ROOT/'results/traces';tracedir.mkdir(exist_ok=True)
    frames=ROOT/'results/frames';frames.mkdir(exist_ok=True)
    if root['root_id'] in [1000,5000,5001]:Image.fromarray(first).save(frames/(prefix+'_initial.png'))
    t=time.perf_counter();allactions=[];heights=[];successes=[];grasped=[];queryrecords=[];anyreach=False;done=False
    for query in range(5):
        rgb=first if query==0 else render(env,Tactual);That=metadata(root,condition,query);data=policy_input(rgb,That,K,stats,embedder,True);action=predict(policy,data,stats)
        if action.shape!=(30,7) or not np.isfinite(action).all():raise RuntimeError('nonfinite or malformed action chunk')
        queryrecords.append({'query':query,'Rhat':That[:3,:3].tolist(),'translation_metadata':That[:3,3].tolist(),'actual_T':Tactual.tolist(),'raw_action_l2':float(np.linalg.norm(action)),'first_action':action[0].tolist(),'chunk_translation_sum':action[:,:3].sum(0).tolist(),'chunk_rotation_sum':action[:,3:6].sum(0).tolist()})
        for a in action:
            if len(allactions)>=150 or done:break
            if STOP:raise InterruptedError('budget/termination signal')
            obs,reward,done,info=env.step(a)
            # These labels and simulator quantities are used only by this evaluator after the policy query.
            success=bool(env._check_success());height=float(env.sim.data.body_xpos[env.cube_body_id][2]);grasp=bool(env._check_grasp(gripper=env.robots[0].gripper,object_geoms=env.cube))
            site=env.sim.model.site_name2id('gripper0_right_grip_site');anyreach=anyreach or bool(np.linalg.norm(env.sim.data.site_xpos[site]-env.sim.data.body_xpos[env.cube_body_id])<0.05)
            allactions.append(a);heights.append(height);successes.append(success);grasped.append(grasp)
        if done or len(allactions)>=150:break
    path=tracedir/(prefix+'.npz');np.savez_compressed(path,actions=np.asarray(allactions,dtype=np.float32),object_heights=np.asarray(heights),success=np.asarray(successes),grasp=np.asarray(grasped),Rhat=np.asarray([q['Rhat'] for q in queryrecords]))
    if root['root_id'] in [1000,5000,5001]:Image.fromarray(render(env,Tactual)).save(frames/(prefix+'_final.png'))
    row={'utc':utc(),'split':root['split'],'root_id':root['root_id'],'condition':condition,'tag':tag,'success':any(successes),'steps':len(allactions),'query_count':len(queryrecords),'executed_chunks':len(queryrecords),'seconds':time.perf_counter()-t,'initial_RGB_sha256':hashrgb,'max_object_height_m':max(heights),'any_reach':anyreach,'any_grasp':any(grasped),'nonfinite_actions':False,'action_l2_mean':float(np.mean(np.linalg.norm(np.asarray(allactions),axis=1))),'query_records':queryrecords,'trace_path':str(path.relative_to(ROOT)),'trace_sha256':sha(path),'root_xml_sha256':snap['manifest']['xml_sha256'],'root_state_sha256':snap['manifest']['state_sha256']}
    append_json(ROOT/'results'/f"{root['split']}_rollouts.jsonl",row);print('ROLLOUT',root['root_id'],runlabel,row['success'],row['steps'],round(row['seconds'],3),flush=True)
    return row,np.asarray(allactions)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--split',choices=['dev','test'],required=True);args=ap.parse_args()
    for sig in [signal.SIGUSR1,signal.SIGTERM,signal.SIGINT]:signal.signal(sig,stopping)
    if args.split=='test' and not read_json(ROOT/'results/dev_summary.json',{}).get('test_allowed'):
        atomic_json(ROOT/'results/test_summary.json',{'utc':utc(),'state':'NOT_RUN','complete':False,'reason':'dev gate did not permit test','rollouts':None,'U':'NOT_RUN'});return
    plan=read_json(ROOT/'frozen_training_plan.json');assert sha(ROOT/'manifests/frozen_roots.json')==plan['root_manifest_sha256']
    ckm=read_json(ROOT/'checkpoint_manifest.json');assert sha(ROOT/ckm['path'])==ckm['sha256']
    seed_all(0);policy=ACTPolicy(default_args(True)).cuda();ck=torch.load(ROOT/ckm['path'],map_location='cpu',weights_only=False);policy.load_state_dict(ck['model_state_dict']);stats=ck['stats'];del ck;gc.collect();policy.eval();emb=PluckerEmbedder(img_size=256,device='cuda')
    if args.split=='dev':
        seed_all(0);U=ACTPolicy(default_args(False)).cuda().eval()
    roots=[x for x in read_json(ROOT/'manifests/frozen_roots.json')['roots'] if x['split']==args.split];completed=jsonlines(ROOT/'results'/f'{args.split}_rollouts.jsonl');donekeys={(x['root_id'],x['tag'] or x['condition']) for x in completed}
    fixed_done={x['root_id'] for x in jsonlines(ROOT/'results/dev_fixed_observation.jsonl')}
    for root in roots:
        env=make_env(root['env_seed']);snap=snapshot(env,root)
        if args.split=='dev' and root['root_id'] not in fixed_done:
            rgb,K,data,raw=fixed_observation_diagnostic(policy,emb,env,snap,root,stats)
            if root['root_id']==1000 and not (ROOT/'results/U_metadata_negative_control.json').exists():interface_negative(U,emb,rgb,K,root,stats)
        conditions=['C-clean'] if args.split=='dev' else CONDITIONS
        original=None
        for condition in conditions:
            if (root['root_id'],condition) in donekeys:continue
            atomic_json(ROOT/'evaluation_active_attempt.json',{'utc':utc(),'root_id':root['root_id'],'split':args.split,'condition':condition,'checkpoint_sha256':ckm['sha256']})
            row,actions=rollout(policy,emb,env,snap,root,condition,stats);completed.append(row);donekeys.add((root['root_id'],condition));original=actions
        if args.split=='dev' and root['root_id']==1000 and (1000,'C-clean-repeat') not in donekeys:
            if original is None:
                firstrow=next(x for x in completed if x['root_id']==1000 and x['tag'] is None);original=np.load(ROOT/firstrow['trace_path'])['actions']
            row,again=rollout(policy,emb,env,snap,root,'C-clean',stats,tag='C-clean-repeat');completed.append(row)
            check={'utc':utc(),'same_actions_allclose':bool(np.allclose(original,again,atol=1e-7,rtol=1e-7)),'max_action_abs_difference':float(np.max(np.abs(original-again))),'same_success':row['success']==next(x['success'] for x in completed if x['root_id']==1000 and x['tag'] is None),'note':'one additional dev rollout, not an independent root'};atomic_json(ROOT/'results/clean_rollout_reproducibility.json',check);assert check['same_actions_allclose'] and check['same_success'],'clean rollout not reproducible'
        env.close()
    if args.split=='dev':
        rows=[x for x in completed if x['tag'] is None];fixed=jsonlines(ROOT/'results/dev_fixed_observation.jsonl');n=len(rows);s=sum(x['success'] for x in rows)
        insensitive=all(x['metrics'][k]['raw_chunk_max_abs_delta']<=1e-6 for x in fixed for k in ['persistent-10','zero','shuffle']);floor=s<=3
        result={'utc':utc(),'state':'IMPLEMENTATION-LIMITED' if floor else ('MEASUREMENT-LIMITED' if insensitive else 'DEV_GATE_PASSED'),'n':n,'successes':s,'success_rate':s/n,'extra_reproducibility_rollouts':1,'total_policy_rollouts':len(completed),'test_allowed':n==32 and not floor and not insensitive,'metadata_insensitive':insensitive,'checkpoint_sha256':ckm['sha256'],'checkpoint_updates':ckm['updates'],'checkpoint_epochs':ckm['completed_epochs'],'threshold':'0-3 of32 -> stop; >=4 not a paper reproduction pass','auxiliary':{'any_reach':sum(x['any_reach'] for x in rows),'any_grasp':sum(x['any_grasp'] for x in rows),'object_height_mean_max_m':float(np.mean([x['max_object_height_m'] for x in rows]))},'fixed_observation_n':len(fixed),'U':'NOT_RUN; initialized interface check only'}
        atomic_json(ROOT/'results/dev_summary.json',result);print(result,flush=True)
    else:
        rows=[x for x in completed if x['tag'] is None];atomic_json(ROOT/'results/test_execution.json',{'utc':utc(),'complete':len(rows)==350,'rollouts':len(rows),'independent_roots':len({x['root_id'] for x in rows}),'checkpoint_sha256':ckm['sha256'],'checkpoint_updates':ckm['updates'],'conditions':CONDITIONS})
if __name__=='__main__':main()
