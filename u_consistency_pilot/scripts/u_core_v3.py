"""Frozen model, read-only HDF5, prospective root generator and physical metrics."""
import atexit,hashlib, importlib, json, os, sys, time, types
from pathlib import Path
import numpy as np
import torch
from download_v3 import BASE, atomic, sha, utc

SWM=BASE/'external/stable-worldmodel-21446f1ede6d5284e981bd7b47f432b994e6d812/stable_worldmodel'
RUN_ID=os.environ.get('U_RUN_ID','20261027T115450Z')
RUN=BASE/'outputs'/('v3_'+RUN_ID)
GPU_LOG_RUN=RUN
GPU_REGISTERED=False
WORK=BASE/'.work'/RUN_ID
WORK.mkdir(parents=True,exist_ok=True)
torch.set_num_threads(4)
torch.set_num_interop_threads(1)
COUNTS={}
STOP_REQUESTED=False
def count(name,n=1):COUNTS[name]=COUNTS.get(name,0)+n
def flush_counts(stage):
    path=RUN/'step_counts.json';old=json.loads(path.read_text()) if path.exists() else {'by_stage':{},'total':{}}
    old['by_stage'][stage+':pid_'+str(os.getpid())]=COUNTS.copy()
    old['total']={k:sum(s.get(k,0) for s in old['by_stage'].values()) for k in {k for s in old['by_stage'].values() for k in s}}
    atomic(path,old)

def jsonable(value):
    if isinstance(value,np.ndarray):return value.tolist()
    if isinstance(value,np.generic):return value.item()
    if isinstance(value,torch.Tensor):return value.detach().cpu().numpy().tolist()
    if isinstance(value,dict):return {str(k):jsonable(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [jsonable(v) for v in value]
    return value
def stable_hash(value):return hashlib.sha256(json.dumps(jsonable(value),sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def append(path,obj):
    with Path(path).open('a') as f:f.write(json.dumps(jsonable(obj),allow_nan=False,separators=(',',':'))+'\n');f.flush();os.fsync(f.fileno())
def progress(stage,**kwargs):atomic(RUN/'progress.json',{'at':utc(),'stage':stage,**jsonable(kwargs)})
def gpu_context():
    global GPU_REGISTERED
    if GPU_REGISTERED:return
    GPU_REGISTERED=True;path=GPU_LOG_RUN/'.control'/f'gpu_context_{os.getpid()}.json'
    record={'pid':os.getpid(),'start_epoch':time.time(),'started_at_utc':utc(),'stage':os.environ.get('U_STAGE','engineering'),'scope':'TEST_ONLY' if os.environ.get('U_CODE_HASH')=='TEST_ONLY' else 'task','card':0}
    atomic(path,record)
    def finish():
        import resource
        end={**record,'end_epoch':time.time(),'ended_at_utc':utc(),'peak_process_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
        if torch.cuda.is_initialized():end.update({'peak_torch_allocated_bytes':torch.cuda.max_memory_allocated(),'peak_torch_reserved_bytes':torch.cuda.max_memory_reserved()})
        atomic(path,end)
    atexit.register(finish)
def ensure_namespaces():
    # Bypass only package __init__ optional imports; execute pinned modules unchanged.
    for name,path in [('stable_worldmodel',SWM),('stable_worldmodel.envs',SWM/'envs'),('stable_worldmodel.envs.pusht',SWM/'envs/pusht'),('stable_worldmodel.wm',SWM/'wm'),('stable_worldmodel.wm.lewm',SWM/'wm/lewm')]:
        if name not in sys.modules:
            module=types.ModuleType(name);module.__path__=[str(path)];sys.modules[name]=module
    root=sys.modules['stable_worldmodel']
    root.utils=importlib.import_module('stable_worldmodel.utils')
    root.spaces=importlib.import_module('stable_worldmodel.spaces')

class FrozenF:
    def __init__(self,device='cuda'):
        ensure_namespaces()
        from transformers import ViTConfig,ViTModel
        from stable_worldmodel.wm.lewm.lewm import LeWM
        from stable_worldmodel.wm.lewm.module import Predictor,Embedder,MLP
        c=json.loads((BASE/'models/v3/config.json').read_text())
        if c['encoder']['pretrained'] is not False:raise RuntimeError('PRETRAINED_BACKBONE_DOWNLOAD_FORBIDDEN')
        self.config=c;self.device=torch.device(device)
        encoder=ViTModel(ViTConfig(hidden_size=192,num_hidden_layers=12,num_attention_heads=3,intermediate_size=768,image_size=224,patch_size=14),add_pooling_layer=False,use_mask_token=False)
        def kwargs(key):return {k:v for k,v in c[key].items() if not k.startswith('_') and k!='norm_fn'}
        self.model=LeWM(encoder,Predictor(**kwargs('predictor')),Embedder(**kwargs('action_encoder')),MLP(**kwargs('projector'),norm_fn=torch.nn.BatchNorm1d),MLP(**kwargs('pred_proj'),norm_fn=torch.nn.BatchNorm1d))
        state=torch.load(BASE/'models/v3/weights.pt',map_location='cpu',weights_only=True)
        loaded=self.model.load_state_dict(state,strict=True)
        if loaded.missing_keys or loaded.unexpected_keys:raise RuntimeError('STRICT_LOAD_FAILED')
        if self.device.type=='cuda':gpu_context()
        self.model.eval().requires_grad_(False).to(self.device)
        self.missing_keys=loaded.missing_keys;self.unexpected_keys=loaded.unexpected_keys
        self.mean=torch.tensor([.485,.456,.406],device=self.device)[None,:,None,None]
        self.std=torch.tensor([.229,.224,.225],device=self.device)[None,:,None,None]
        from torchvision.transforms.v2 import Resize
        self.resize=Resize((224,224),antialias=True)
    @torch.inference_mode()
    def encode(self,images,batch=64):
        result=[]
        for start in range(0,len(images),batch):
            arr=np.asarray(images[start:start+batch])
            if arr.ndim!=4 or arr.shape[-1]!=3 or arr.dtype!=np.uint8:raise RuntimeError('RGB_UINT8_NHWC_REQUIRED')
            x=torch.from_numpy(arr.copy()).to(self.device).permute(0,3,1,2).float()/255
            x=self.resize((x-self.mean)/self.std)
            z=self.model.projector(self.model.encoder(x,interpolate_pos_encoding=True).last_hidden_state[:,0])
            if not torch.isfinite(z).all():raise RuntimeError('NONFINITE_LATENT')
            result.append(z.cpu().numpy())
        return np.concatenate(result)
    @torch.inference_mode()
    def predict(self,history,past,candidates):
        # Each action is the block LEAVING its paired history frame.
        h=torch.as_tensor(history,dtype=torch.float32,device=self.device)
        if h.ndim==2:h=h[None].expand(len(candidates),-1,-1)
        p=np.asarray(past)
        if p.ndim==2:p=np.broadcast_to(p,(len(candidates),2,10))
        blocks=torch.as_tensor(np.concatenate([p,np.asarray(candidates)[:,None]],axis=1),dtype=torch.float32,device=self.device)
        if h.shape[1:]!=(3,192) or blocks.shape[1:]!=(3,10):raise RuntimeError('F_HISTORY_ALIGNMENT_SHAPE')
        pred=self.model.predict(h,self.model.action_encoder(blocks))[:,-1]
        if not torch.isfinite(pred).all():raise RuntimeError('NONFINITE_F_PREDICTION')
        return pred.cpu().numpy()

class H5Data:
    def __init__(self,path=None):
        import h5py
        try:import hdf5plugin
        except ImportError:pass
        self.file=h5py.File(path or BASE/'data/v3/pusht_expert_train.h5','r',rdcc_nbytes=32*1024*1024)
        self.f=self.file
        if not all(k in self.f for k in ['action','pixels','ep_len','ep_offset']):raise RuntimeError('HDF5_SCHEMA_NOT_SUPPORTED_'+str(list(self.f)))
        self.lengths=self.f['ep_len'][:].astype(np.int64).reshape(-1)
        self.offsets=self.f['ep_offset'][:].astype(np.int64).reshape(-1)
        if len(self.lengths)!=len(self.offsets):raise RuntimeError('EPISODE_METADATA_MISMATCH')
        if self.f['action'].shape[1:]!=(2,):raise RuntimeError('RAW_ACTION_NOT_2D')
        self.schema={k:{'shape':list(v.shape),'dtype':str(v.dtype),'compression':v.compression} for k,v in self.f.items() if hasattr(v,'shape')}
    def actions(self,ep,t):
        if ep<0 or ep>=len(self.lengths) or t<0 or t+5>self.lengths[ep]:raise ValueError('ACTION_BLOCK_CROSSES_SOURCE_EPISODE')
        return np.asarray(self.f['action'][self.offsets[ep]+t:self.offsets[ep]+t+5],dtype=np.float64)
    def window_indices(self,ep,start):
        if ep<0 or ep>=len(self.lengths) or start<0 or start+20>self.lengths[ep]:raise ValueError('HISTORY_WINDOW_CROSSES_SOURCE_EPISODE')
        return self.offsets[ep]+start+np.arange(4)*5
    def images(self,rows):
        x=np.asarray(self.f['pixels'][rows])
        if x.ndim==4 and x.shape[1]==3 and x.shape[-1]!=3:x=x.transpose(0,2,3,1)
        if x.ndim!=4 or x.shape[-1]!=3 or x.dtype!=np.uint8:raise RuntimeError('HDF5_PIXEL_SCHEMA_UNEXPECTED')
        return x
    def close(self):self.f.close()

def load_scaler():return json.loads((RUN/'action_scaler.json').read_text())
def norm_actions(a,s):return ((np.asarray(a,dtype=np.float64)-np.asarray(s['mean']))/np.asarray(s['std_ddof0'])).reshape(*np.asarray(a).shape[:-2],10)
def denorm_actions(a,s):return np.asarray(a).reshape(-1,5,2)*np.asarray(s['std_ddof0'])+np.asarray(s['mean'])
def action_residual_scale(s):return np.tile(np.asarray(s['std_ddof0'],dtype=np.float64),5)
def denorm_g(g,s):return np.asarray(g)*action_residual_scale(s)+np.tile(np.asarray(s['mean'],dtype=np.float64),5)
def make_env(seed,relative=True):
    ensure_namespaces()
    from stable_worldmodel.envs.pusht.env import PushT
    env=PushT(render_mode='rgb_array',resolution=224,relative=relative)
    env._u_step_role='reset'
    env._u_contacts=[]
    env._u_integration_index=0
    collision=env._handle_collision
    def counted_collision(arbiter,space,data):
        result=collision(arbiter,space,data)
        points=arbiter.contact_point_set
        roles=['agent' if shape.body is env.agent else 'block' if shape.body is env.block else 'wall' for shape in arbiter.shapes]
        normal=list(points.normal);impulse=list(arbiter.total_impulse);coords=[[*p.point_a,*p.point_b,p.distance] for p in points.points]
        if roles[0]>roles[1]:
            roles=roles[::-1];normal=[-x for x in normal];impulse=[-x for x in impulse];coords=[p[2:4]+p[:2]+p[4:] for p in coords]
        env._u_contacts.append({'integration_index':env._u_integration_index,'roles':roles,'normal':normal,'impulse':impulse,'points':coords})
        return result
    env._handle_collision=counted_collision
    setup=env._setup
    def counted_setup():
        setup();original=env.space.step
        def counted_physics(dt):
            count('physics_integration_steps');count(env._u_step_role+'_integration_steps')
            env._u_integration_index+=1
            return original(dt)
        env.space.step=counted_physics
    env._setup=counted_setup
    original_step=env.step
    def counted_step(action):
        if STOP_REQUESTED:raise RuntimeError('TERM_REQUESTED_BETWEEN_CONTROL_STEPS')
        count('control_steps');count(env._u_step_role+'_control_steps')
        env._u_contacts=[]
        return original_step(action)
    env.step=counted_step
    obs,info=env.reset(seed=int(seed))
    count('environment_resets');env._u_step_role='prefix'
    return env,obs,info
def physical_snapshot(env):
    return {'agent':[*env.agent.position,*env.agent.velocity,env.agent.angle,env.agent.angular_velocity,*env.agent.force,env.agent.torque],
            'block':[*env.block.position,*env.block.velocity,env.block.angle,env.block.angular_velocity,*env.block.force,env.block.torque],
            'controller':[env.k_p,env.k_v,env.dt,env.control_hz,env.action_scale],
            'latest_action':None if env.latest_action is None else np.asarray(env.latest_action).tolist(),
            'n_contacts':int(env.n_contact_points),'contacts':sorted(env._u_contacts,key=lambda x:json.dumps(x,sort_keys=True)),
            'physics_timestamp':float(env.space.current_time_step)}
def state_vector(env):
    s=physical_snapshot(env);return np.asarray(s['agent']+s['block']+s['controller']+[s['n_contacts']],dtype=np.float64)
def contacts_close(a,b,atol=1e-6):
    if isinstance(a,(float,int)) and isinstance(b,(float,int)):return abs(a-b)<=atol
    if type(a) is not type(b):return False
    if isinstance(a,dict):return a.keys()==b.keys() and all(contacts_close(a[k],b[k],atol) for k in a)
    if isinstance(a,list):return len(a)==len(b) and all(contacts_close(x,y,atol) for x,y in zip(a,b))
    return a==b
def contact_geometry(env):
    point=env.agent.position
    distance=min(shape.point_query(point).distance for shape in env.block.shapes)
    radius=max(getattr(shape,'radius',0) for shape in env.agent.shapes)
    return float(distance-radius)
def metric(env,state):
    goal=np.asarray(env.goal_state);state=np.asarray(state);pos=float(np.linalg.norm(goal[:4]-state[:4]));block=float(np.linalg.norm(goal[2:4]-state[2:4]))
    shape=env.shapes[int(env.variation_space['block']['shape'].value)];period=env.shape_symmetry_angles.get(shape,2*np.pi)
    angle=float(abs(goal[4]-state[4])%period);angle=min(angle,period-angle)
    J=max(pos/20,angle/(np.pi/9));block_J=max(block/20,angle/(np.pi/9))
    success=bool(env.eval_state(goal,state)[0])
    if bool(J<1)!=success:raise RuntimeError('J_SUCCESS_EQUIVALENCE_FAILED')
    return {'J':J,'block_only':block_J,'success':success,'joint_position_error':pos,'block_position_error':block,'periodic_angle_error':angle}

def prefix_for_seed(seed,stratum,relative=True):
    """Prescoring geometry only. No J, goal cost, F or G is consulted."""
    env,obs,info=make_env(seed,relative);actions=[];images=[env.render()]
    # Fixed 40-step controller; final 10 microsteps provide legal 3-frame history.
    for t in range(40):
        if stratum=='contact':target=np.asarray(env.block.position,dtype=np.float64)
        else:target=np.array([60.,450.])
        delta=(target-np.asarray(env.agent.position))/100
        # Stop approaching at geometric contact; do not push for 40 steps into a wall.
        if stratum=='contact' and contact_geometry(env)<=1:
            delta=np.zeros(2);target=np.asarray(env.agent.position)
        action=np.clip(delta,-.35,.35) if relative else np.clip(target,0,512)
        obs,_,_,_,info=env.step(action.astype(np.float64));actions.append(action.copy());images.append(env.render())
    gap=contact_geometry(env);accepted=gap<=2 if stratum=='contact' else gap>=35
    root={'seed':int(seed),'prefix_actions':np.asarray(actions).tolist(),'stratum':stratum,'geometry_gap':gap,'prefix_control_steps':40,'history_frame_offsets':[30,35,40],
          'history_raw_frames':np.asarray([images[30],images[35],images[40]]),'past_raw_blocks':np.asarray(actions[30:40]).reshape(2,5,2),'goal_image':np.asarray(info['goal']),'goal_state':np.asarray(env.goal_state).tolist(),'prefix_state':physical_snapshot(env),'accepted':bool(accepted)}
    env.close();return root
def replay_root(root,relative=True,with_history=False):
    env,obs,info=make_env(root['seed'],relative)
    pictures=[]
    for i,action in enumerate(root['prefix_actions']):
        obs,_,_,_,info=env.step(np.asarray(action,dtype=np.float64))
        if with_history and i+1 in root['history_frame_offsets']:pictures.append(env.render())
    if with_history:return env,obs,info,np.asarray(pictures)
    return env,obs,info
def candidates(root,train_actions,scaler):
    seed=int(root['candidate_seed']);gen=torch.Generator(device='cpu').manual_seed(seed)
    initial=torch.randn(4,10,generator=gen,dtype=torch.float32).numpy()
    rng=np.random.default_rng(seed+1);ids=rng.choice(len(train_actions),size=4,replace=False)
    proposed=np.concatenate([denorm_actions(initial,scaler),np.asarray(train_actions)[ids]],axis=0)
    low,high=scaler['raw_action_clip'];clipped=np.clip(proposed,low,high)
    normalized=norm_actions(clipped,scaler)
    return clipped,normalized,{'sources':['official_CEM_initial']*4+['training_real_block']*4,'training_indices':[None]*4+ids.tolist(),'coordinate_clip_fraction':np.mean(proposed!=clipped,axis=(1,2)).tolist(),'proposed_raw_blocks':proposed.tolist()}
def b_features(history,past,A,pca):
    # Exactly 78 inputs; function has no endpoint/J/model-error parameter.
    h=(np.asarray(history)-pca['mean'])@pca['components'].T
    prefix=np.concatenate([h.reshape(48),np.asarray(past).reshape(20)])
    features=np.concatenate([np.broadcast_to(prefix,(len(A),68)),np.asarray(A)],axis=1)
    if features.shape!=(len(A),78):raise RuntimeError('CALIBRATION_FEATURE_DIMENSION')
    return features
