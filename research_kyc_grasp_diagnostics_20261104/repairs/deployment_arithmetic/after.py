"""One exact ACT/internal accounting and BF16 call path for all GPU phases."""
from .common import *
from .ledger import reserve
from .call_guard import CallGuard
from .loader import load_actual


def execute_denormalize(normalized,stats):
    """Exactly official eval float32 multiply/add; never float64-driven control."""
    import numpy as np
    value=np.asarray(normalized,dtype=np.float32)
    return value*np.asarray(stats['action_std'],dtype=np.float32)+np.asarray(stats['action_mean'],dtype=np.float32)


class ModelRuntime:
    def __init__(self,save_inputs=True):
        import torch
        import numpy as np
        self.torch=torch;self.np=np;self.save_inputs=save_inputs;self.captured=None;self.branch=None
        self.guard=CallGuard(reserve,lambda event,ticket:append(P/'model_events.jsonl',dict(utc=utc(),event=event,ticket=ticket)))
        modules,_=load_actual();ACTPolicy=modules['models.act'].ACTPolicy;DETRVAE=modules['models.detr_vae'].DETRVAE
        old_policy=ACTPolicy.__call__;old_internal=DETRVAE.forward
        runtime=self
        def policy_call(obj,data):
            runtime.guard.policy_enter(runtime.branch,data=data)
            require(not obj.training and not torch.is_grad_enabled(),'eval/no_grad required')
            result=old_policy(obj,data);runtime.guard.complete();return result
        def internal(obj,data):
            runtime.guard.internal_enter(data=data)
            labels=data.get('actions') is not None
            require(not obj.training and not torch.is_grad_enabled(),'internal train/grad mode')
            require(labels or data.get('is_pad') is None,'prior mask leakage')
            runtime.internal_hashes={k:hashlib.sha256(v.detach().cpu().numpy().tobytes()).hexdigest()
                for k,v in data.items() if torch.is_tensor(v)}
            runtime.internal_arrays={k:v.detach().cpu().numpy().copy() for k,v in data.items()
                if torch.is_tensor(v)} if runtime.save_inputs else {}
            a,pad,latent=old_internal(obj,data)
            def array(value):return value.detach().float().cpu().numpy().copy() if value is not None else np.empty((0,),np.float32)
            runtime.captured=dict(normalized_chunk=array(a)[0],padding_prediction=array(pad)[0],
                mu=array(latent[0]),logvar=array(latent[1]))
            return a,pad,latent
        ACTPolicy.__call__=policy_call;DETRVAE.forward=internal

    def call(self,policy,inputs,item,stats,folder):
        torch,np=self.torch,self.np
        self.branch=item['branch'];self.guard.expect(item);self.captured=None
        if item.get('seed') is not None:
            import random
            seed=item['seed'];random.seed(seed);np.random.seed(seed);torch.manual_seed(seed);torch.cuda.manual_seed_all(seed)
        hashes={k:hashlib.sha256(v.detach().cpu().numpy().tobytes()).hexdigest() for k,v in inputs.items()}
        with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16):
            output=policy({k:v.clone() for k,v in inputs.items()})
        torch.cuda.synchronize()
        require(self.captured is not None and self.captured['normalized_chunk'].shape==(30,7)
            and all(np.isfinite(v).all() for v in self.captured.values()),'malformed/nonfinite model output')
        require(torch.is_tensor(output) and tuple(output.shape)==(1,30,7),'prior policy returned wrong interface')
        returned=output[0].float().cpu().numpy().copy()
        require(np.array_equal(returned,self.captured['normalized_chunk']),'official policy return differs from captured internal action')
        raw=execute_denormalize(returned,stats)
        require(raw.dtype==np.float32 and np.isfinite(raw).all(),'execution actions must be finite official float32')
        folder.mkdir(exist_ok=True,parents=True);path=folder/(item['id']+'.npz');require(not path.exists(),'prediction overwrite/retry')
        save_npz(path,raw_chunk=raw,**self.captured,**{'internal_'+k:v for k,v in self.internal_arrays.items()})
        record=dict(utc=utc(),**item,policy_input_keys=sorted(inputs),input_hashes=hashes,
            internal_input_hashes=self.internal_hashes,output_npz=str(path.relative_to(P)),output_sha256=sha(path),
            precision='FP32 weights/inputs + CUDA BF16 autocast, TF32 off',
            raw_execution_dtype=str(raw.dtype),official_policy_return_bit_equal_internal=True,
            prior_latent='zero z' if item['branch']!='official_posterior' else None,
            loss={k:float(v) for k,v in output.items()} if isinstance(output,dict) else None)
        write(folder/(item['id']+'.json'),record)
        return self.captured['normalized_chunk'],raw,record
