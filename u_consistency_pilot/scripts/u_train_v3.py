"""Small flow/MLP inverse probes; no candidate-action input at inference."""
import copy, json, math, os, random, signal, time
from pathlib import Path
import numpy as np
import torch
from torch import nn
from u_core_v3 import BASE,RUN,WORK,atomic,append,progress,stable_hash,jsonable,utc,gpu_context

STOP=False
def request_stop(*_):
    global STOP;STOP=True
    import u_core_v3 as core
    core.STOP_REQUESTED=True
signal.signal(signal.SIGTERM,request_stop)
signal.signal(signal.SIGINT,request_stop)

class FlowG(nn.Module):
    def __init__(self):
        super().__init__();d=192
        self.latent=nn.Linear(192,d);self.action=nn.Linear(10,d)
        self.time=nn.Sequential(nn.Linear(32,d),nn.SiLU(),nn.Linear(d,d))
        self.position=nn.Parameter(torch.zeros(1,3,d))
        layer=nn.TransformerEncoderLayer(d,3,768,dropout=0.,activation='gelu',batch_first=True,norm_first=True)
        self.blocks=nn.TransformerEncoder(layer,4,enable_nested_tensor=False)
        self.out=nn.Sequential(nn.LayerNorm(d),nn.Linear(d,10))
        mask=torch.zeros(3,3,dtype=torch.bool);mask[:2,2]=True
        self.register_buffer('mask',mask)
    def forward(self,condition,noisy_action,t):
        scale=torch.exp(torch.arange(16,device=t.device)*(-math.log(10000)/15))
        time_embed=t[:,None]*scale[None]*1000
        time_embed=torch.cat([time_embed.sin(),time_embed.cos()],-1)
        prefix=self.latent(condition)
        suffix=self.action(noisy_action)+self.time(time_embed)
        tokens=torch.cat([prefix,suffix[:,None]],dim=1)+self.position
        return self.out(self.blocks(tokens,mask=self.mask)[:,-1])
    @torch.inference_mode()
    def sample(self,condition,epsilon):
        # One Euler step from t=1 to 0. No known candidate A argument.
        return epsilon-self(condition,epsilon,torch.ones(len(epsilon),device=epsilon.device))

class MLP(nn.Module):
    def __init__(self,dim):
        super().__init__();self.net=nn.Sequential(nn.Linear(dim,256),nn.LayerNorm(256),nn.GELU(),nn.Linear(256,256),nn.LayerNorm(256),nn.GELU(),nn.Linear(256,10))
    def forward(self,x):return self.net(x)

def seed_all(seed):
    random.seed(seed);np.random.seed(seed);torch.manual_seed(seed);torch.cuda.manual_seed_all(seed)
def condition_numpy(Z,past,kind,scaler):
    z=(np.asarray(Z)-scaler['mean'])/scaler['std']
    if kind=='flow':return z[:,[2,3]]
    if kind=='mlp':return np.concatenate([z[:,2],z[:,3],z[:,3]-z[:,2]],axis=1)
    history=np.concatenate([z[:,:3].reshape(len(z),-1),np.asarray(past).reshape(len(z),20)],axis=1)
    if kind=='history':return history
    if kind=='strong':return np.concatenate([history,z[:,3],z[:,3]-z[:,2]],axis=1)
    raise ValueError(kind)
def model_for(kind,shape):return FlowG() if kind=='flow' else MLP(int(np.prod(shape)))
def save_checkpoint(path,model,opt,step,best,best_loss,wait,generator,metadata):
    payload={'model':model.state_dict(),'optimizer':opt.state_dict(),'step':step,'best_model':best,'best_loss':best_loss,'wait':wait,
             'python_rng':random.getstate(),'numpy_rng':np.random.get_state(),'torch_rng':torch.get_rng_state(),'cuda_rng':torch.cuda.get_rng_state_all(),'batch_rng':generator.bit_generator.state,
             'code_hash':os.environ.get('U_CODE_HASH'),'config_hash':os.environ.get('U_CONFIG_HASH'),**metadata}
    tmp=path.with_suffix('.tmp');torch.save(payload,tmp);os.replace(tmp,path)
def fit(kind,X,y,V,vy,name,max_steps=20000,initial=None,phase='idm',lr=1e-4,seed=270727,remaining_models=1):
    """Effective batch=256. Resume model+optimizer+all RNG; <=500 steps between saves."""
    gpu_context();seed_all(seed);generator=np.random.default_rng(seed)
    device='cuda';model=model_for(kind,X.shape[1:]).to(device)
    if initial is not None:model.load_state_dict(initial,strict=True)
    opt=torch.optim.AdamW(model.parameters(),lr=lr,weight_decay=1e-4)
    path=WORK/f'{name}_last.pt';best_path=WORK/f'{name}_best.pt'
    best=None;best_loss=float('inf');wait=0;start_step=0
    if path.exists():
        ck=torch.load(path,map_location=device,weights_only=False)
        if ck['code_hash']!=os.environ.get('U_CODE_HASH') or ck['config_hash']!=os.environ.get('U_CONFIG_HASH'):raise RuntimeError('TRAINING_RESUME_HASH_MISMATCH')
        model.load_state_dict(ck['model'],strict=True);opt.load_state_dict(ck['optimizer']);start_step=ck['step'];best=ck['best_model'];best_loss=ck['best_loss'];wait=ck['wait']
        max_steps=min(max_steps,ck.get('scheduled_max_steps',max_steps))
        random.setstate(ck['python_rng']);np.random.set_state(ck['numpy_rng']);torch.set_rng_state(ck['torch_rng'].cpu());torch.cuda.set_rng_state_all([s.cpu() for s in ck['cuda_rng']]);generator.bit_generator.state=ck['batch_rng']
    X=torch.as_tensor(X,dtype=torch.float32,device=device);y=torch.as_tensor(y,dtype=torch.float32,device=device)
    V=torch.as_tensor(V,dtype=torch.float32,device=device);vy=torch.as_tensor(vy,dtype=torch.float32,device=device)
    valgen=torch.Generator(device=device).manual_seed(270728);val_eps=torch.randn((len(vy),4,10),device=device,generator=valgen)
    micro=int(os.environ.get('U_MICROBATCH','64'));effective=256;micro=min(micro,effective);accum=math.ceil(effective/micro)
    began=time.monotonic();last_save=began;last_train=float('nan');loss_records=[]
    if start_step>=max_steps and best is not None:
        model.load_state_dict(best,strict=True);model.eval()
        return model,{'name':name,'kind':kind,'phase':phase,'actual_updates':start_step,'best_val_mse':best_loss,'elapsed_seconds':0.,'seed':seed,'checkpoint':str(best_path.relative_to(BASE)),'resumed_already_complete':True}
    for step in range(start_step+1,max_steps+1):
        if STOP or time.time()>float(os.environ.get('U_CUTOFF_EPOCH','inf'))-60:
            save_checkpoint(path,model,opt,step-1,best,best_loss,wait,generator,{'kind':kind,'phase':phase,'scheduled_max_steps':max_steps});raise RuntimeError('PARTIAL-DEADLINE_OR_TERM_CHECKPOINT_SAVED')
        model.train();opt.zero_grad(set_to_none=True);train_loss=0.
        learning=lr*min(step/500,1)*(.1+.9*(1+math.cos(math.pi*step/max_steps))/2)
        for group in opt.param_groups:group['lr']=learning
        for j in range(accum):
            n=min(micro,effective-j*micro);ids=torch.as_tensor(generator.integers(0,len(y),size=n),device=device);xx=X[ids];yy=y[ids]
            if kind=='flow':
                t=torch.rand(n,device=device).pow(1/1.5);noise=torch.randn_like(yy);noisy=t[:,None]*noise+(1-t[:,None])*yy
                loss=(model(xx,noisy,t)-(noise-yy)).square().mean()
            else:loss=(model(xx)-yy).square().mean()
            if not torch.isfinite(loss):raise RuntimeError('NONFINITE_BASELINE_OPTIMIZATION')
            (loss*n/effective).backward();train_loss+=loss.item()*n/effective
        torch.nn.utils.clip_grad_norm_(model.parameters(),1.);opt.step();last_train=train_loss
        if time.monotonic()-last_save>=300:
            save_checkpoint(path,model,opt,step,best,best_loss,wait,generator,{'kind':kind,'phase':phase,'scheduled_max_steps':max_steps});last_save=time.monotonic()
            progress('training_checkpoint',model=name,step=step,elapsed_seconds=time.monotonic()-began)
        if step%250==0 or step==max_steps:
            model.eval()
            with torch.inference_mode():
                total=0.;single=0.
                for lo in range(0,len(vy),128):
                    xx=V[lo:lo+128];yy=vy[lo:lo+128]
                    if kind=='flow':
                        samples=torch.stack([model.sample(xx,val_eps[lo:lo+128,k]) for k in range(4)],dim=1)
                        pred=samples.mean(1);single+=(samples[:,0]-yy).square().sum().item()
                    else:pred=model(xx)
                    total+=(pred-yy).square().sum().item()
                val=total/(len(vy)*10);single=single/(len(vy)*10) if kind=='flow' else val
            if val<best_loss-1e-6:
                best_loss=val;best=copy.deepcopy({k:v.detach().cpu() for k,v in model.state_dict().items()});wait=0
                tmp=best_path.with_suffix('.tmp');torch.save({'model':best,'kind':kind,'input_shape':list(X.shape[1:]),'step':step,'val_mse':val,'code_hash':os.environ.get('U_CODE_HASH'),'config_hash':os.environ.get('U_CONFIG_HASH')},tmp);os.replace(tmp,best_path)
            else:wait+=1
            row={'at':utc(),'model':name,'phase':phase,'step':step,'train_loss':train_loss,'val_mse_K4mean':val,'val_mse_K1':single,'learning_rate':learning,'elapsed_seconds':time.monotonic()-began,'updates_per_second':(step-start_step)/max(time.monotonic()-began,1e-9),'effective_batch':effective,'microbatch':micro}
            append(RUN/'training_progress.jsonl',row);loss_records.append(row);progress('training',**row)
            if step==1000:
                elapsed=time.monotonic()-began;rate=(step-start_step)/max(elapsed,1e-6)
                resource_file=RUN/'resource_watch.json';gpu_used=json.loads(resource_file.read_text()).get('gpu_process_card_seconds_upper_bound',0) if resource_file.exists() else 0
                wall_left=float(os.environ.get('U_CUTOFF_EPOCH','inf'))-time.time()-1800
                gpu_left=36000-gpu_used-900
                share=max(0,min(wall_left,gpu_left))/max(1,remaining_models+(phase=='idm'))
                original_cap=max_steps;max_steps=min(max_steps,max(1000,int(step+share*rate)))
                append(RUN/'training_budget_probes.jsonl',{'at':utc(),'model':name,'updates_measured':step,'updates_per_second':rate,'gpu_seconds_used_upper':gpu_used,'wall_seconds_left_after30min_eval_reserve':wall_left,'fair_time_share_seconds':share,'original_update_cap':original_cap,'scheduled_update_cap':max_steps,'budget_only_no_dev_test_information':True})
            if step%500==0 or time.monotonic()-last_save>=300:
                save_checkpoint(path,model,opt,step,best,best_loss,wait,generator,{'kind':kind,'phase':phase,'scheduled_max_steps':max_steps});last_save=time.monotonic()
            if step>=1000 and wait>=12:break
            if step>=max_steps:break
    save_checkpoint(path,model,opt,step,best,best_loss,wait,generator,{'kind':kind,'phase':phase,'scheduled_max_steps':max_steps})
    model.load_state_dict(best,strict=True);model.eval()
    return model,{'name':name,'kind':kind,'phase':phase,'actual_updates':step,'best_val_mse':best_loss,'elapsed_seconds':time.monotonic()-began,'seed':seed,'checkpoint':str(best_path.relative_to(BASE))}

def load_probe(name,device='cuda'):
    if str(device).startswith('cuda'):gpu_context()
    ck=torch.load(WORK/f'{name}_best.pt',map_location='cpu',weights_only=False)
    model=model_for(ck['kind'],ck['input_shape']);model.load_state_dict(ck['model'],strict=True)
    return model.to(device).eval()

@torch.inference_mode()
def inverse_samples(model,kind,Z,past,latent_scaler,noise=None):
    started=time.perf_counter()
    x=condition_numpy(Z,past,kind,latent_scaler);t=torch.as_tensor(x,dtype=torch.float32,device=next(model.parameters()).device)
    if kind=='flow':
        if noise is None:raise RuntimeError('FLOW_PAIRED_NOISE_MUST_BE_EXPLICIT')
        eps=torch.as_tensor(noise,dtype=torch.float32,device=t.device)
        outputs=[];latencies=[]
        for k in range(eps.shape[1]):
            torch.cuda.synchronize();begin=time.perf_counter();outputs.append(model.sample(t,eps[:,k]));torch.cuda.synchronize();latencies.append(time.perf_counter()-begin)
        result=torch.stack(outputs,dim=1).cpu().numpy()
        append(RUN/'inference_timing.jsonl',{'at':utc(),'stage':os.environ.get('U_STAGE','engineering'),'kind':kind,'batch':len(Z),'K':len(latencies),'K1_seconds':latencies[0],'extra_K4_seconds':sum(latencies[1:]),'per_sample_seconds':latencies,'end_to_end_seconds':time.perf_counter()-started,'timing':'CUDA synchronized component wall time; fixed inputs, no selection effect'})
        return result
    result=model(t).cpu().numpy()
    append(RUN/'inference_timing.jsonl',{'at':utc(),'stage':os.environ.get('U_STAGE','engineering'),'kind':kind,'batch':len(Z),'K':1,'end_to_end_seconds':time.perf_counter()-started})
    return result
