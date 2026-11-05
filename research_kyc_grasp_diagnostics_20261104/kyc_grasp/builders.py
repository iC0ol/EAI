"""Actual loaders, constructors and strict-load path, shared by candidate phases."""
from .common import *
from .loader import load_actual
from .ledger import reserve
from types import SimpleNamespace

def configuration():
    modules,provenance=load_actual()
    import numpy as np
    args=SimpleNamespace(**read(R/'manifests/C_config.json'));stats={k:np.asarray(v,np.float32) for k,v in read(R/'manifests/dataset_stats.json').items()}
    require(args.chunk_size==30 and args.prob_drop_proprio==1 and not args.use_cam_pose and args.use_fp16 and args.use_plucker and args.num_side_cam==1 and args.transform=='crop','checkpoint interface differs')
    return modules,provenance,args,stats

def audit_runtime(strict=True,owner_release=True):
    from .render_audit import RenderAudit
    return RenderAudit(strict=strict,owner_release=owner_release)

def make_physics(lib,audit,seed):
    reserve('make_env','builder','make_env_seed'+str(seed));env=lib.make_env(seed);audit.env=env;audit.api.check();return env

def training_setup(env):
    modules,provenance,args,stats=configuration()
    # Exact local training initialization: no Evaluator or optimizer in this path.
    ds=modules['utils'].EpisodicDataset(list(range(200)),stats,args,camera_poses_file='train_cameras.json',transform='crop',env=env)
    val=modules['utils'].EpisodicDataset(list(range(200,210)),stats,args,camera_poses_file='train_cameras.json',transform='id',env=env,max_seq_length=ds.max_seq_length)
    return dict(train=ds,validation=val,args=args,stats=stats,provenance=provenance)

def close_physics(env,audit,datasets=()):
    audit.label('CLEANUP')
    for ds in datasets:
        if ds is not None:ds.env=None
    if env is not None:env.close()
    audit.env=None;audit.api.check()
    require(not any(x['alive'] for x in audit.api.contexts.values()),'live GL context after cleanup')

def model_setup():
    modules,provenance,args,stats=configuration()
    import torch,numpy as np,random
    from .runtime_safety import torch_guards,cached_backbone_only,forbidden
    torch_guards(torch);cached_loader=cached_backbone_only(torch)
    import torchvision.models._api
    torchvision.models._api.load_state_dict_from_url=cached_loader
    class NoOptimizer:
        def __init__(self,*a,**kw):pass
        step=zero_grad=state_dict=load_state_dict=forbidden
    class Proxy:
        def __getattr__(self,name):return SimpleNamespace(AdamW=NoOptimizer) if name=='optim' else getattr(torch,name)
    modules['models.detr_vae'].torch=Proxy();torch.optim.AdamW.step=forbidden
    torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False;torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True
    random.seed(0);np.random.seed(0);torch.manual_seed(0);torch.cuda.manual_seed_all(0)
    policy=modules['models.act'].ACTPolicy(args);ck=torch.load(R/'checkpoints/C_latest.pt',map_location='cpu',weights_only=False)
    require(ck['args']==vars(args) and all(np.array_equal(np.asarray(ck['stats'][k],np.float32),v) for k,v in stats.items()),'args/stats differ')
    state=ck['model_state_dict'];require(len(state)==375 and all(torch.isfinite(v).all().item() for v in state.values()),'checkpoint tensor count/nonfinite')
    loaded=policy.load_state_dict(state,strict=True);require(not loaded.missing_keys and not loaded.unexpected_keys,'strict load mismatch')
    policy.eval();policy.configure_optimizers=forbidden
    for v in policy.parameters():v.requires_grad_(False)
    require(all(torch.isfinite(v).all().item() for v in policy.state_dict().values()),'loaded state nonfinite')
    record=dict(utc=utc(),strict=True,missing_keys=[],unexpected_keys=[],checkpoint_sha256=sha(R/'checkpoints/C_latest.pt'),tensors=375,optimizer_created=False,optimizer_state_loaded=False,cached_pretrained_sha256=sha(R/'cache/torch/hub/checkpoints/resnet18-f37072fd.pth'))
    del ck,state
    return dict(policy=policy,args=args,stats=stats,provenance=provenance,strict_load=record)

def close_model(bundle):
    import torch
    bundle['policy']=None;torch.cuda.synchronize();torch.cuda.empty_cache()
