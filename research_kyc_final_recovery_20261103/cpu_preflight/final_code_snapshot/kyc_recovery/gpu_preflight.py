"""Candidate: sequential input init/cleanup then model strict-load in ONE worker."""
from .common import *
from .gates import worker_gate


def main():
    worker_gate('gpu-preflight')
    from .runtime_safety import isolation
    isolation()
    from .loader import load_actual
    modules,provenance=load_actual()
    from .builders import input_setup,close_input,model_setup,close_model
    from .model_runtime import ModelRuntime
    bundle=None;model=None;status='ENGINEERING_BLOCKED';error=None
    try:
        bundle=input_setup()
        write(P/'results/preflight_input_provenance.json',bundle['provenance'])
        close_input(bundle);bundle=None
        import torch
        torch.cuda.empty_cache()
        runtime=ModelRuntime(save_inputs=False)
        model=model_setup();write(P/'results/preflight_strict_load.json',model['strict_load'])
        require(runtime.guard.policy_entries==runtime.guard.internal_entries==0,'preflight attempted ACT')
        close_model(model);model=None
        status='ENGINEERING_READY_INPUT_AND_STRICT_LOAD'
    except BaseException as exc:
        error=type(exc).__name__+': '+str(exc);raise
    finally:
        if bundle is not None:close_input(bundle)
        if model is not None:close_model(model)
        write(P/'gpu_preflight_result.json',dict(utc=utc(),status=status,error=error,shared_loader='kyc_recovery.loader.load_actual',
            shared_builders=['input_setup','model_setup'],input_initializer='Dataset/Evaluator/embedder built, no __getitem__',
            render='NOT_RUN',readPixels='NOT_RUN',ACT='NOT_RUN',step='NOT_RUN',strict_load=status!='ENGINEERING_BLOCKED',
            actual_GPU_path=False if status=='ENGINEERING_BLOCKED' else True,
            scientific_observations=0,provenance=provenance))
