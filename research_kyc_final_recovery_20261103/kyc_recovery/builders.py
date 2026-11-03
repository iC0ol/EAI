"""The exact constructors used by GPU preflight and science workers."""
from .common import *
from .loader import load_actual
from types import SimpleNamespace


def configuration():
    modules, provenance=load_actual()
    import numpy as np
    args=SimpleNamespace(**read(R/'manifests/C_config.json'))
    stats={k:np.asarray(v,np.float32) for k,v in read(R/'manifests/dataset_stats.json').items()}
    require(args.chunk_size==30 and args.prob_drop_proprio==1 and not args.use_cam_pose
            and args.use_fp16 and args.use_plucker and args.num_side_cam==1,'configuration differs')
    return modules,provenance,args,stats


def physics_setup(lib,runtime,seed):
    from .gates import reserve
    reserve('make_env','input','shared_physics_builder.make_env')
    env=lib.make_env(seed)
    runtime.expected_context=runtime.api.owner(env.sim._render_context_offscreen.gl_ctx)
    runtime.expected_ids=runtime.api.ids(env.sim._render_context_offscreen.con)
    runtime.api.check()
    return env


def input_setup():
    from .gates import reserve, current_stage
    from .input_runtime import InputRuntime
    from .runtime_safety import torch_guards
    modules,provenance,args,stats=configuration()
    import torch
    import numpy as np
    torch_guards(torch)
    import robosuite.utils.binding_utils as bu
    from robosuite.renderers.context import egl_context as ec
    from robosuite.environments.base import MujocoEnv
    runtime=InputRuntime(ec,bu,np);runtime.install()
    lib=modules['experiment_lib']
    if current_stage()!='s2-closed':
        MujocoEnv.step=lambda *a,**kw:reserve('env_steps','input','forbidden_step')
    env=ds=evaluator=embedder=None
    try:
        runtime.label('INIT_make_env');env=physics_setup(lib,runtime,0);runtime.api.check()
        if current_stage()!='s2-closed':
            env.step=lambda *a,**kw:reserve('env_steps','input','forbidden_outer_step')
        runtime.expected_context=runtime.api.owner(env.sim._render_context_offscreen.gl_ctx)
        runtime.expected_ids=runtime.api.ids(env.sim._render_context_offscreen.con)
        require(runtime.expected_context and runtime.api.live(runtime.expected_context),'unknown active owner')
        runtime.label('INIT_Dataset')
        ds=modules['utils'].EpisodicDataset(list(range(200)),stats,args,
            camera_poses_file='train_cameras.json',transform='id',env=env,max_seq_length=130)
        runtime.api.check();runtime.label('INIT_Evaluator')
        evaluator=modules['eval'].Evaluator(env,stats,str(lib.DATA),args)
        runtime.api.check();runtime.label('INIT_embedder')
        embedder=modules['cam_embedding'].PluckerEmbedder(img_size=256,device='cuda')
        runtime.api.check()
        return dict(env=env,ds=ds,evaluator=evaluator,embedder=embedder,runtime=runtime,
                    lib=lib,args=args,stats=stats,modules=modules,provenance=provenance)
    except BaseException:
        if ds is not None:ds.env=None
        if env is not None:env.close()
        raise


def close_input(bundle):
    runtime=bundle['runtime'];runtime.label('CLEANUP')
    bundle['ds'].env=None;bundle['env'].close()
    bundle.update(ds=None,env=None,evaluator=None,embedder=None)
    runtime.api.check()
    require(not any(x['alive'] for x in runtime.api.contexts.values()),'live GL context after shared cleanup')


def model_setup():
    modules,provenance,args,stats=configuration()
    import torch
    import numpy as np
    import random
    from .runtime_safety import torch_guards,cached_backbone_only,forbidden
    torch_guards(torch)
    cached_loader=cached_backbone_only(torch)
    import torchvision.models._api
    torchvision.models._api.load_state_dict_from_url=cached_loader
    class NoOptimizer:
        def __init__(self,*a,**kw):pass
        step=zero_grad=state_dict=load_state_dict=forbidden
    class Proxy:
        def __getattr__(self,name):
            return SimpleNamespace(AdamW=NoOptimizer) if name=='optim' else getattr(torch,name)
    modules['models.detr_vae'].torch=Proxy()
    torch.optim.AdamW.step=forbidden
    torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True
    random.seed(0);np.random.seed(0);torch.manual_seed(0);torch.cuda.manual_seed_all(0)
    policy=modules['models.act'].ACTPolicy(args)
    ck=torch.load(R/'checkpoints/C_latest.pt',map_location='cpu',weights_only=False)
    require(ck['args']==vars(args),'checkpoint args differ')
    require(all(np.array_equal(np.asarray(ck['stats'][k],np.float32),v) for k,v in stats.items()),'stats differ')
    state=ck['model_state_dict']
    require(len(state)==375 and all(torch.isfinite(v).all().item() for v in state.values()),'checkpoint tensors invalid')
    loaded=policy.load_state_dict(state,strict=True)
    require(not loaded.missing_keys and not loaded.unexpected_keys,'strict-load mismatch')
    policy.eval();policy.configure_optimizers=forbidden
    for parameter in policy.parameters():parameter.requires_grad_(False)
    require(all(torch.isfinite(v).all().item() for v in policy.state_dict().values()),'loaded state nonfinite')
    record=dict(utc=utc(),strict=True,missing_keys=list(loaded.missing_keys),unexpected_keys=list(loaded.unexpected_keys),
        checkpoint_sha256=sha(R/'checkpoints/C_latest.pt'),optimizer_created=False,
        optimizer_state_loaded=False,cached_pretrained_sha256=sha(R/'cache/torch/hub/checkpoints/resnet18-f37072fd.pth'))
    del ck,state
    return dict(policy=policy,args=args,stats=stats,modules=modules,provenance=provenance,strict_load=record)


def close_model(bundle):
    import torch
    bundle['policy']=None
    torch.cuda.synchronize();torch.cuda.empty_cache()
