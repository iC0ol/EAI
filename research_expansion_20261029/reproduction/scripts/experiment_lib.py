import os,sys,json,random,copy,pathlib,time
from common import ROOT,atomic_json,utc
sys.path.insert(0,str(ROOT/'vendor/kyc/policy_robosuite'))
import numpy as np
import torch,h5py
from scipy.spatial.transform import Rotation
torch.set_num_threads(3)
torch.set_num_interop_threads(1)
DATA=ROOT/'assets/liftrand_eef_delta.hdf5'
def seed_all(seed):
    random.seed(seed);np.random.seed(seed);torch.manual_seed(seed);torch.cuda.manual_seed_all(seed)
def rng_state():return {'python':random.getstate(),'numpy':np.random.get_state(),'torch':torch.get_rng_state(),'cuda':torch.cuda.get_rng_state_all()}
def restore_rng(s):
    random.setstate(s['python']);np.random.set_state(s['numpy']);torch.set_rng_state(s['torch']);torch.cuda.set_rng_state_all(s['cuda'])
def env_spec():
    with h5py.File(DATA) as f:return json.loads(f['data'].attrs['env_args']),str(f['data'].attrs['action_space'])
def make_env(seed=0):
    import robosuite as suite
    from robosuite.wrappers.action_wrapper import wrap_env_action_space
    seed_all(seed);spec,space=env_spec();kw=copy.deepcopy(spec['env_kwargs'])
    kw.update(has_renderer=False,has_offscreen_renderer=True,use_camera_obs=False,camera_heights=256,camera_widths=256,camera_names=['agentview'],original=False)
    env=suite.make(env_name=spec['env_name'],**kw);env=wrap_env_action_space(env,space);env.reset();env.sim.forward();env.set_init_action();return env
def camera_pose(env,T):
    i=env.sim.model.camera_name2id('agentview');env.sim.model.cam_pos[i]=T[:3,3];q=Rotation.from_matrix(T[:3,:3]).as_quat();env.sim.model.cam_quat[i]=q[[3,0,1,2]];env.sim.forward()
def render(env,T):
    camera_pose(env,T);return np.flipud(env.sim.render(camera_name='agentview',height=256,width=256,depth=False)).copy()
def intrinsics(env):
    i=env.sim.model.camera_name2id('agentview');f=128/np.tan(np.deg2rad(env.sim.model.cam_fovy[i])/2)
    return np.array([[f,0,128],[0,f,128],[0,0,1]],dtype=np.float32)
def default_args(conditioning=True):
    # Defaults copied from the frozen official train.py; exact paper Lift overrides.
    from types import SimpleNamespace
    return SimpleNamespace(name='F_C_seed0' if conditioning else 'F_U_seed0',dataset_path=str(DATA),dataset_suffix='liftrand_eef_delta',camera_poses_dir=str(ROOT/'vendor/kyc/policy_robosuite/camera_poses'),policy_class='act',num_episodes=200,use_plucker=conditioning,train_poses_file='train_cameras.json',test_poses_file='train_cameras.json',pose_files=['train_cameras.json'],n=3,m=1,num_side_cam=1,default_cam=False,batch_size=70,seed=0,num_epochs=20001,lr=2e-5,use_fp16=True,transform='crop',prob_drop_proprio=1.,use_cam_pose=False,original=False,dropout=0.1,latent_drop_prob=0.,kl_weight=1.,chunk_size=30,hidden_dim=512,weight_decay=1e-4,obs_dim=7,action_dim=7,nheads=8,ffn_dim=2048,enc_layers=4,dec_layers=7,pre_norm=True,activation='relu',backbone='late_imagenet',patch_size=8,eval_max_steps=150,eval_save_n_video=0)
def policy_input(rgb,T,K,stats,embedder,conditioning=True):
    image=torch.from_numpy(rgb).permute(2,0,1).float().cuda()/255
    if conditioning:
        p=embedder(torch.tensor(K,device='cuda')[None],torch.tensor(T,dtype=torch.float32,device='cuda')[None])['plucker'][0].permute(2,0,1)
    else:p=torch.zeros(6,256,256,device='cuda')
    q=(-np.asarray(stats['state_mean'])/np.asarray(stats['state_std'])).astype(np.float32)
    return {'image':torch.cat([image,p])[None,None],'qpos':torch.tensor(q,device='cuda')[None],'cam_extrinsics':torch.zeros(1,2,4,4,device='cuda')}
def clone_input(d):return {k:v.clone() if torch.is_tensor(v) else v for k,v in d.items()}
