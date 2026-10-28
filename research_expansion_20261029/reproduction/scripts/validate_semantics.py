import sys,time,json,hashlib,copy
from common import ROOT,utc,atomic_json,append_json,sha
from experiment_lib import *
from cam_embedding import PluckerEmbedder
from PIL import Image
def main():
    out=ROOT/'results/semantics';out.mkdir(parents=True,exist_ok=True)
    spec,space=env_spec()
    with h5py.File(DATA) as f:
        meta={'utc':utc(),'dataset_sha256':sha(DATA),'env_args':spec,'action_space':space,'demo_count':len(f['data']),'total_frames':int(f['data'].attrs['total']),'demo_0_keys':list(f['data/demo_0']),'per_demo_XML_present':False,'train_demos':list(range(200)),'validation_demos':list(range(200,210)),'test_demos_used_for_training':False}
    atomic_json(ROOT/'manifests/data_split.json',meta)
    replay=[json.loads(x) for x in (out/'expert_replays.jsonl').read_text().splitlines()] if (out/'expert_replays.jsonl').exists() else []
    for i in range(10):
        if any(x['demo']==i for x in replay):continue
        # Official generator's documented default seed=42, then seed+demo id; no search for a winning seed.
        env=make_env(42+i)
        with h5py.File(DATA) as f:
            d=f[f'data/demo_{i}'];states=d['states'][()];actions=d['actions'][()];ref_eef=d['next_obs/robot0_eef_pos'][()];first=d['starting_abs_action'][()]
        env.sim.set_state_from_flattened(states[0]);env.sim.forward();env.set_init_action()
        init=env._asw_last_abs_pose.copy();first_reconstructed=init+actions[0,:6]
        errors=[];success=False;t=time.perf_counter();maxh=0
        for j,a in enumerate(actions):
            env.step(a);success=success or bool(env._check_success())
            site=env.sim.model.site_name2id('gripper0_right_grip_site');errors.append(float(np.linalg.norm(env.sim.data.site_xpos[site]-ref_eef[j])))
            maxh=max(maxh,float(env.sim.data.body_xpos[env.cube_body_id][2]))
        row={'demo':i,'success':success,'steps':len(actions),'seconds':time.perf_counter()-t,'first_absolute_command_max_error':float(np.max(np.abs(first_reconstructed-first[:6]))),'eef_position_error_mean_m':float(np.mean(errors)),'eef_position_error_max_m':float(np.max(errors)),'max_object_height_m':maxh,'source_default_seed':42+i,'geometry_limitation':'Public HDF5 lacks per-demo XML/cube dimensions. Official generator default seed used once, no seed search.'}
        replay.append(row);append_json(out/'expert_replays.jsonl',row);print(row,flush=True)
        if i==1:
            poses=json.loads((ROOT/'vendor/kyc/policy_robosuite/camera_poses/train_cameras.json').read_text())['poses'];T=np.array(poses[0]);K=intrinsics(env)
            rootxml=env.model.get_xml();(out/'canonical_initial_model.xml').write_text(rootxml)
            state=states[0].copy()
            env.reset_from_xml_string(rootxml);env.sim.set_state_from_flattened(state);env.sim.forward();rgb=render(env,T)
            Image.fromarray(rgb).save(out/'expert_demo1_initial.png')
            env.reset_from_xml_string(rootxml);env.sim.set_state_from_flattened(state);env.sim.forward();rgb2=render(env,T)
            repeat={'same_xml_state_render_identical':bool(np.array_equal(rgb,rgb2)),'image_max_abs_difference':int(np.max(np.abs(rgb.astype(int)-rgb2.astype(int)))),'xml_sha256':sha(out/'canonical_initial_model.xml'),'state_shape':state.shape,'scope':'canonical XML plus initial state restored twice, exactly as paired evaluation roots; not mid-rollout restore'}
            atomic_json(out/'initial_restore_check.json',repeat)
            assert repeat['same_xml_state_render_identical'],'XML+state restore must reproduce image'
            emb=PluckerEmbedder(img_size=256,device='cuda');rays=emb(torch.tensor(K,device='cuda')[None],torch.tensor(T,dtype=torch.float32,device='cuda')[None])
            P=rays['plucker'][0].cpu().numpy();D=P[:,:,3:];M=P[:,:,:3];O=T[:3,3]
            checks=[]
            for y,x in [(0,0),(127,127),(255,255),(100,200)]:
                d=np.array([(x+1-K[0,2])/K[0,0],-(y+1-K[1,2])/K[1,1],-1.]);world=T[:3,:3]@d;world/=np.linalg.norm(world);point=O+world;local=T[:3,:3].T@(point-O)
                projected=np.array([K[0,2]-K[0,0]*local[0]/local[2]-1,K[1,2]+K[1,1]*local[1]/local[2]-1])
                checks.append({'xy':[x,y],'ray_direction_error':float(np.max(np.abs(D[y,x]-world))),'projection_error_pixels':float(np.max(np.abs(projected-[x,y])))})
            geometry={'cam_transform':'camera-to-world; OpenGL +x right, +y up, forward -z; rendered RGB flipped vertically','ray_channel_order':'moment origin cross unit_direction, then unit_direction','source_pixel_offset':'source grid adds 0.5 twice; index+1.0; retained unchanged (0.5 pixel relative to usual center convention)','unit_norm_max_error':float(np.max(np.abs(np.linalg.norm(D,axis=-1)-1))),'moment_max_error':float(np.max(np.abs(M-np.cross(np.broadcast_to(O,D.shape),D)))),'orthogonality_max_error':float(np.max(np.abs((M*D).sum(-1)))),'checks':checks,'rotation_error':'world-frame left multiplication of R only; translation fixed','crop':'official RandomCrop crops/resizes stacked RGB+raymap together using the same crop indices','policy_truth_channels':'none; evaluator geometry used only for checks'}
            atomic_json(out/'camera_raymap_checks.json',geometry)
            assert max(x['ray_direction_error'] for x in checks)<1e-5
            assert geometry['moment_max_error']<1e-5
        env.close()
    passed=sum(x['success'] for x in replay)>=9 and max(x['first_absolute_command_max_error'] for x in replay)<1e-4 and max(x['eef_position_error_max_m'] for x in replay)<0.02
    result={'utc':utc(),'state':'PASS' if passed else 'FAIL','expert_successes':sum(x['success'] for x in replay),'expert_n':10,'replay_seconds_total':sum(x['seconds'] for x in replay),'semantic_gate':'success>=9/10, first target mismatch<1e-4, EEF trajectory max deviation<2cm','rows':replay,'limitations':['HDF5 env_version is 1.4.1; fixed official submodule declares 1.5.1.','No per-demo XML in public dataset; exact collection model cannot be proven. Evaluation roots will preserve their own full XML and state.']}
    atomic_json(ROOT/'results/semantics.json',result)
    if not passed:raise SystemExit(20)
if __name__=='__main__':main()
