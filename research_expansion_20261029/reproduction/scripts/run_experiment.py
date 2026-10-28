"""Official ACT and Dataset, fixed configuration, recoverable sampler/optimizer/RNG."""
import argparse,os,sys,time,json,signal,math,subprocess,hashlib,gc
from common import ROOT,utc,atomic_json,read_json,append_json,sha
from experiment_lib import *
from utils import EpisodicDataset,get_norm_stats,constant_schedule
from models.act import ACTPolicy
from torch.utils.data._utils.collate import default_collate
STOP=False
def stopping(signum,frame):
    global STOP
    STOP=True
class Loader:
    def __init__(self,dataset,batch=70):
        self.dataset=dataset;self.batch=batch;self.epoch=0;self.offset=0;self.order=None;self.gen=torch.Generator().manual_seed(0)
    def state_dict(self):return {'epoch':self.epoch,'offset':self.offset,'order':self.order,'generator_state':self.gen.get_state(),'batch':self.batch}
    def load_state_dict(self,s):
        self.epoch=s['epoch'];self.offset=s['offset'];self.order=s['order'];self.gen.set_state(s['generator_state']);assert self.batch==s['batch']
    def next(self):
        if self.order is None:self.order=torch.randperm(len(self.dataset),generator=self.gen).tolist()
        ids=self.order[self.offset:self.offset+self.batch]
        t=time.perf_counter();data=default_collate([self.dataset[i] for i in ids]);render_s=time.perf_counter()-t
        self.offset+=len(ids)
        if self.offset==len(self.dataset):self.epoch+=1;self.offset=0;self.order=None
        return data,render_s,ids
def save_checkpoint(policy,optimizer,scheduler,loader,updates,last_val,stats,args,train_time):
    path=ROOT/'checkpoints/C_latest.pt';temp=path.with_suffix('.tmp');prev=ROOT/'checkpoints/C_previous.pt'
    payload={'model_state_dict':policy.state_dict(),'optimizer_state_dict':optimizer.state_dict(),'scheduler_state_dict':scheduler.state_dict(),'loader_state':loader.state_dict(),'updates':updates,'completed_epochs':loader.epoch,'last_validated_epoch':last_val,'rng':rng_state(),'stats':stats,'args':vars(args),'train_elapsed_seconds':train_time,'utc':utc()}
    torch.save(payload,temp)
    if path.exists():path.replace(prev)
    temp.replace(path)
    atomic_json(ROOT/'checkpoint_manifest.json',{'path':str(path.relative_to(ROOT)),'bytes':path.stat().st_size,'sha256':sha(path),'utc':utc(),'updates':updates,'completed_epochs':loader.epoch,'includes':['model','optimizer','scheduler','python/numpy/CPU/CUDA RNG','sampler permutation/position/generator','stats','config']})
def validation(policy,dataset):
    policy.eval();data=default_collate([dataset[i] for i in range(len(dataset))])
    with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16):d=policy(data)
    result={k:float(v) for k,v in d.items()};policy.train();return result
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--smoke',action='store_true');a=ap.parse_args()
    assert read_json(ROOT/'results/semantics.json',{}).get('state')=='PASS','semantics gate not passed'
    if not a.smoke:assert (ROOT/'frozen_training_plan.json').exists()
    for sig in [signal.SIGUSR1,signal.SIGTERM,signal.SIGINT]:signal.signal(sig,stopping)
    seed_all(0);args=default_args(True);atomic_json(ROOT/'manifests/C_config.json',vars(args))
    env=make_env(0);stats=get_norm_stats(str(DATA),200,policy_class='act');atomic_json(ROOT/'manifests/dataset_stats.json',{k:v.tolist() for k,v in stats.items()})
    ds=EpisodicDataset(list(range(200)),stats,args,camera_poses_file='train_cameras.json',transform='crop',env=env)
    val=EpisodicDataset(list(range(200,210)),stats,args,camera_poses_file='train_cameras.json',transform='id',env=env,max_seq_length=ds.max_seq_length)
    loader=Loader(ds,70);policy=ACTPolicy(args).cuda();optimizer=policy.configure_optimizers();scheduler=constant_schedule(optimizer);policy.train()
    updates=0;last_val=-1;accumulated=0
    ckpath=ROOT/'checkpoints/C_latest.pt'
    if ckpath.exists():
        ck=torch.load(ckpath,map_location='cpu',weights_only=False);policy.load_state_dict(ck['model_state_dict']);optimizer.load_state_dict(ck['optimizer_state_dict']);scheduler.load_state_dict(ck['scheduler_state_dict']);loader.load_state_dict(ck['loader_state']);updates=ck['updates'];last_val=ck['last_validated_epoch'];accumulated=ck['train_elapsed_seconds']
        # map_location also moves RNG ByteTensors; restore requires CPU tensors.
        state=ck['rng'];state['torch']=state['torch'].cpu();state['cuda']=[x.cpu() for x in state['cuda']];restore_rng(state)
        append_json(ROOT/'logs/training_events.jsonl',{'utc':utc(),'event':'RESUMED','updates':updates,'epoch':loader.epoch,'checkpoint_sha256':sha(ckpath)});del ck;gc.collect();torch.cuda.empty_cache()
    target=36 if a.smoke else int(read_json(ROOT/'frozen_training_plan.json')['C_target_updates'])
    start=time.perf_counter();timings=[];last_save=time.monotonic();initial_updates=updates;last_save_updates=updates
    torch.cuda.reset_peak_memory_stats()
    deadline=None if a.smoke else read_json(ROOT/'frozen_training_plan.json')['training_stage_stop_epoch']
    budget_truncated=False
    while updates<target and not STOP:
        if deadline and time.time()>=deadline and loader.offset==0:
            budget_truncated=True;break
        if loader.offset==0 and loader.epoch%10==0 and last_val!=loader.epoch:
            v=validation(policy,val);last_val=loader.epoch;append_json(ROOT/'logs/validation.jsonl',{'utc':utc(),'epoch':loader.epoch,'updates':updates,**v});print('VALIDATION',loader.epoch,v,flush=True)
        st=time.perf_counter();data,render_s,ids=loader.next();torch.cuda.synchronize();forwardstart=time.perf_counter()
        optimizer.zero_grad(set_to_none=True)
        with torch.autocast('cuda',dtype=torch.bfloat16):lossd=policy(data);loss=lossd['loss']
        if not torch.isfinite(loss):raise RuntimeError('nonfinite training loss')
        loss.backward();torch.nn.utils.clip_grad_norm_(policy.parameters(),1.0);optimizer.step();scheduler.step();torch.cuda.synchronize();updates+=1
        step_s=time.perf_counter()-st
        row={'utc':utc(),'update':updates,'completed_epochs':loader.epoch,'epoch_offset':loader.offset,'seconds':step_s,'data_render_seconds':render_s,'model_seconds':time.perf_counter()-forwardstart,'batch_n':len(ids),'demo_order':ids,'loss':float(loss.detach()),'l1':float(lossd['l1'].detach()),'kl':float(lossd['kl'].detach()),'vram_allocated_peak_bytes':torch.cuda.max_memory_allocated(),'vram_reserved_peak_bytes':torch.cuda.max_memory_reserved()}
        timings.append(row);append_json(ROOT/'logs/training_steps.jsonl',row)
        atomic_json(ROOT/'training_progress.json',{'utc':utc(),'state':'SMOKE' if a.smoke else 'TRAINING','updates':updates,'completed_epochs':loader.epoch,'epoch_offset':loader.offset,'target_updates':target,'last_loss':row['loss'],'train_elapsed_seconds':accumulated+time.perf_counter()-start,'vram_allocated_peak_bytes':torch.cuda.max_memory_allocated(),'vram_reserved_peak_bytes':torch.cuda.max_memory_reserved()})
        print('STEP',updates,'epoch',loader.epoch,'s',round(step_s,3),'loss',round(row['loss'],4),flush=True)
        del data,lossd,loss
        if time.monotonic()-last_save>=600 or (loader.offset==0 and loader.epoch%100==0):
            save_checkpoint(policy,optimizer,scheduler,loader,updates,last_val,stats,args,accumulated+time.perf_counter()-start);last_save=time.monotonic();last_save_updates=updates
    if updates!=last_save_updates or not ckpath.exists():save_checkpoint(policy,optimizer,scheduler,loader,updates,last_val,stats,args,accumulated+time.perf_counter()-start)
    progress=read_json(ROOT/'training_progress.json');progress.update(state='INTERRUPTED' if STOP else ('BUDGET_TRUNCATED' if budget_truncated else ('SMOKE_COMPLETE' if a.smoke else 'COMPLETE')),checkpoint=read_json(ROOT/'checkpoint_manifest.json'));atomic_json(ROOT/'training_progress.json',progress)
    if a.smoke:
        full=[x for x in timings if x['batch_n']==70];steady=full[2:] or full
        result={'utc':utc(),'updates':updates-initial_updates,'target':'2 epochs (6 updates) +30 optimization steps','epochs_completed':loader.epoch,'seconds_wall':time.perf_counter()-start,'steady_full_batch_seconds_mean':float(np.mean([x['seconds'] for x in steady])),'all_batch_seconds_mean':float(np.mean([x['seconds'] for x in timings])),'seconds_per_epoch_observed':(time.perf_counter()-start)/(loader.epoch or 1),'render_seconds_per_sample':sum(x['data_render_seconds'] for x in timings)/sum(x['batch_n'] for x in timings),'vram_allocated_peak_bytes':torch.cuda.max_memory_allocated(),'vram_reserved_peak_bytes':torch.cuda.max_memory_reserved(),'parameters':sum(p.numel() for p in policy.parameters()),'sampler':'reproducible independent torch.Generator(seed0) permutations, batch 70/70/60; source Dataset unchanged','checkpoint':read_json(ROOT/'checkpoint_manifest.json')}
        atomic_json(ROOT/'results/smoke_throughput.json',result);print(result,flush=True)
    env.close()
    if STOP:raise SystemExit(75)
if __name__=='__main__':main()
